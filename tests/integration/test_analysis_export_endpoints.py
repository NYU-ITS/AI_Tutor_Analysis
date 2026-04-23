"""Integration tests for the analysis PDF/ZIP export endpoints.

Covers:
  GET /analysis/export/{analysis_id}  — single student PDF
  GET /analysis/export-homework/      — ZIP of one PDF per student
"""

import io
import zipfile

import fitz  # PyMuPDF — for text extraction from generated PDFs
import pytest

from app.models import (
    StudentAnalysis,
    StudentTopicPerformance,
    TutorHomework,
)


pytestmark = pytest.mark.integration


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract visible text from PDF bytes. reportlab compresses content
    streams, so raw-byte substring search doesn't work."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def _seed_analysis(db_session, *, student_id, email, homework_id):
    sa = StudentAnalysis(
        student_id=student_id,
        student_email=email,
        homework_id=homework_id,
        total_question=2,
        total_attempted=2,
        total_solved=1,
        total_errors=1,
    )
    db_session.add(sa)
    db_session.flush()
    db_session.add_all([
        StudentTopicPerformance(
            student_analysis_id=sa.id,
            topic_name="Derivatives",
            status="mastered",
            question_tested=1,
            questions_solved=1,
            details="Q1: Solved",
            reason="ok",
        ),
        StudentTopicPerformance(
            student_analysis_id=sa.id,
            topic_name="Limits",
            status="needs_practice",
            question_tested=1,
            questions_solved=0,
            details="Q2: Attempted (Conceptual)",
            reason="1 attempted but not solved",
        ),
    ])
    db_session.commit()
    return sa


def test_export_analysis_pdf_returns_404_for_missing_analysis(client):
    resp = client.get("/analysis/export/does-not-exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_export_analysis_pdf_returns_pdf_stream_with_filename(client, db_session):
    hw = TutorHomework(group_id="g-pdf", model_id="m-pdf", question_data="q", topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.flush()
    sa = _seed_analysis(db_session, student_id="s1", email="alice@example.edu", homework_id=hw.id)

    resp = client.get(f"/analysis/export/{sa.id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"

    disposition = resp.headers["content-disposition"]
    assert "attachment" in disposition
    assert "alice@example.edu" in disposition

    # Body is a real PDF and the rendered text includes the student email.
    assert resp.content.startswith(b"%PDF-")
    assert "alice@example.edu" in _pdf_text(resp.content)


def test_export_homework_analyses_returns_404_when_no_analyses(client):
    resp = client.get("/analysis/export-homework/", params={"homework_id": "missing-hw"})
    assert resp.status_code == 404
    assert "No analyses found" in resp.json()["detail"]


def test_export_homework_analyses_returns_zip_with_one_pdf_per_student(client, db_session):
    hw = TutorHomework(group_id="g-zip", model_id="m-zip", question_data="q", topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.flush()

    _seed_analysis(db_session, student_id="s1", email="alice@example.edu", homework_id=hw.id)
    _seed_analysis(db_session, student_id="s2", email="bob@example.edu",   homework_id=hw.id)

    resp = client.get("/analysis/export-homework/", params={"homework_id": hw.id})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert len(names) == 2
        assert any("alice@example.edu" in n for n in names)
        assert any("bob@example.edu" in n for n in names)
        # Each member is a valid PDF.
        for name in names:
            with zf.open(name) as fh:
                assert fh.read(5) == b"%PDF-"


def test_export_homework_analyses_handles_single_student(client, db_session):
    hw = TutorHomework(group_id="g-one", model_id="m-one", question_data="q", topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.flush()
    _seed_analysis(db_session, student_id="solo", email="solo@example.edu", homework_id=hw.id)

    resp = client.get("/analysis/export-homework/", params={"homework_id": hw.id})
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert len(zf.namelist()) == 1
