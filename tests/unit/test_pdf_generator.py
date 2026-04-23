"""Unit tests for app.services.pdf_generator.generate_analysis_pdf.

Verifies the PDF export service:
  - returns a seekable BytesIO containing a valid PDF document
  - embeds the student email and homework name into the content
  - handles mastered-only, needs-practice-only, mixed, and empty topic lists
  - tolerates missing/zero metric fields without raising
"""

from io import BytesIO

import fitz  # PyMuPDF — already pulled in by student_analysis_pipeline
import pytest

from app.services.pdf_generator import generate_analysis_pdf


pytestmark = pytest.mark.unit


def _extract_pdf_text(buffer: BytesIO) -> str:
    """Extract all visible text from the generated PDF.

    reportlab ASCII85/Flate-compresses the content streams, so raw-byte
    substring searches never work. We parse properly with fitz instead.
    """
    buffer.seek(0)
    with fitz.open(stream=buffer.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def _pdf_contains(buffer: BytesIO, needle: str) -> bool:
    return needle in _extract_pdf_text(buffer)


def _base_analysis_data(**overrides) -> dict:
    data = {
        "student_email": "student@example.edu",
        "total_question": 3,
        "total_attempted": 3,
        "total_solved": 2,
        "total_errors": 1,
        "topic_performances": [],
    }
    data.update(overrides)
    return data


def test_generate_analysis_pdf_returns_bytesio_with_pdf_header():
    buf = generate_analysis_pdf(_base_analysis_data())

    assert isinstance(buf, BytesIO)
    assert buf.tell() == 0  # The function seeks back to 0 before returning.
    assert buf.read(5) == b"%PDF-"


def test_generate_analysis_pdf_embeds_student_email_and_homework_name():
    buf = generate_analysis_pdf(
        _base_analysis_data(student_email="alice@nyu.edu"),
        homework_name="Homework 8",
    )
    assert _pdf_contains(buf, "alice@nyu.edu")
    assert _pdf_contains(buf, "Homework 8")


def test_generate_analysis_pdf_uses_default_homework_name_when_omitted():
    buf = generate_analysis_pdf(_base_analysis_data())
    assert _pdf_contains(buf, "Homework")


def test_generate_analysis_pdf_renders_none_placeholders_when_no_topic_performances():
    """Empty topic_performances must still render both topic sections with '● None'."""
    buf = generate_analysis_pdf(_base_analysis_data(topic_performances=[]))
    text = _extract_pdf_text(buf)
    # 'None' appears at least twice (mastered + needs-practice bullet sections).
    assert text.count("None") >= 2


def test_generate_analysis_pdf_renders_mastered_topics_section():
    data = _base_analysis_data(topic_performances=[
        {
            "topic_name": "DerivativesTopic",
            "status": "mastered",
            "question_tested": 2,
            "questions_solved": 2,
            "details": "Q1: Solved; Q2: Solved",
            "reason": "All questions attempted and solved correctly",
        }
    ])
    buf = generate_analysis_pdf(data, homework_name="Homework 3")
    assert _pdf_contains(buf, "DerivativesTopic")
    assert _pdf_contains(buf, "Topics Mastered by Student")


def test_generate_analysis_pdf_renders_needs_practice_section():
    data = _base_analysis_data(topic_performances=[
        {
            "topic_name": "LimitsTopic",
            "status": "needs_practice",
            "question_tested": 3,
            "questions_solved": 1,
            "details": "Q1: Solved; Q2: Attempted (Conceptual); Q3: Not Attempted",
            "reason": "1 not attempted; 1 attempted but not solved",
        }
    ])
    buf = generate_analysis_pdf(data)
    assert _pdf_contains(buf, "LimitsTopic")
    assert _pdf_contains(buf, "Need More Practice")


def test_generate_analysis_pdf_partitions_mixed_statuses_and_drops_unknown():
    data = _base_analysis_data(topic_performances=[
        {"topic_name": "MasteredA", "status": "mastered",       "question_tested": 1, "questions_solved": 1, "details": "Q1: Solved",        "reason": "ok"},
        {"topic_name": "WeakB",     "status": "needs_practice", "question_tested": 2, "questions_solved": 0, "details": "Q1: NA; Q2: NA",    "reason": "2 not attempted"},
        {"topic_name": "UnknownC",  "status": "pending_review", "question_tested": 1, "questions_solved": 0, "details": "Q1: ?",             "reason": "?"},
    ])
    buf = generate_analysis_pdf(data)
    assert _pdf_contains(buf, "MasteredA")
    assert _pdf_contains(buf, "WeakB")
    # Topics whose status isn't 'mastered' or 'needs_practice' are filtered out.
    assert not _pdf_contains(buf, "UnknownC")


def test_generate_analysis_pdf_tolerates_missing_metric_fields():
    """Missing total_* keys must default to 0 rather than raising KeyError."""
    buf = generate_analysis_pdf({"student_email": "s@e.com", "topic_performances": []})
    assert buf.getvalue().startswith(b"%PDF-")
