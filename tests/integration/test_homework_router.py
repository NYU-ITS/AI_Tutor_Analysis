import json

import pytest
from fastapi import HTTPException

from app.models import TutorHomework, PipelineJob
from app.routers import homework as homework_router
from app.routers.homework import convert_pdf_to_markdown, _run_pdf_to_markdown
from tests.helpers import make_upload_file, run_async


pytestmark = pytest.mark.integration


def test_get_homework_filters_by_homework_group_and_model(client, db_session):
    hw1 = TutorHomework(group_id="g1", model_id="m1", question_data="q1")
    hw2 = TutorHomework(group_id="g2", model_id="m2", question_data="q2")
    db_session.add_all([hw1, hw2])
    db_session.commit()

    all_rows = client.get("/homework/").json()
    assert len(all_rows) == 2

    by_group = client.get("/homework/", params={"group_id": "g1"}).json()
    assert len(by_group) == 1
    assert by_group[0]["group_id"] == "g1"

    by_model = client.get("/homework/", params={"model_id": "m2"}).json()
    assert len(by_model) == 1
    assert by_model[0]["model_id"] == "m2"

    by_id = client.get("/homework/", params={"homework_id": hw1.id}).json()
    assert len(by_id) == 1
    assert by_id[0]["id"] == hw1.id


# ── Validation tests (via HTTP client — validation happens before queuing) ──


def test_convert_pdf_to_markdown_rejects_non_pdf(client):
    resp = client.post(
        "/homework/pdf-to-markdown",
        params={"doc_type": "question", "group_id": "g1", "model_id": "m1"},
        files={"file": ("text.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_convert_pdf_to_markdown_rejects_empty_pdf(client):
    resp = client.post(
        "/homework/pdf-to-markdown",
        params={"doc_type": "question", "group_id": "g1", "model_id": "m1"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_convert_pdf_to_markdown_returns_queued_with_job_id(client, db_session, monkeypatch):
    """Valid PDF upload returns queued status with a job_id."""
    monkeypatch.setattr(homework_router, "pdf_to_images", lambda pdf_bytes: [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}])
    monkeypatch.setattr(homework_router, "get_prompt", lambda db, name, group_id=None: f"{name}-prompt")
    monkeypatch.setattr(homework_router, "ask_with_images", lambda prompt, image_urls, system=None, **kwargs: "**1.** Mock question")
    monkeypatch.setattr(homework_router, "ask", lambda prompt, system=None, **kwargs: json.dumps({"1": ["Derivatives"]}))

    resp = client.post(
        "/homework/pdf-to-markdown",
        params={"doc_type": "question", "group_id": "g1", "model_id": "m1"},
        files={"file": ("questions.pdf", b"%PDF-data", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert "job_id" in body

    # Verify PipelineJob was created
    job = db_session.query(PipelineJob).filter(PipelineJob.id == body["job_id"]).first()
    assert job is not None
    assert job.step == "pdf_to_markdown"


# ── Background worker tests (call _run_pdf_to_markdown directly) ──


def test_run_pdf_to_markdown_question_creates_homework_and_topic_mapping(db_session, monkeypatch):
    """Background worker processes question PDF, creates homework, runs topic mapping."""
    monkeypatch.setattr(homework_router, "pdf_to_images", lambda pdf_bytes: [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}])
    monkeypatch.setattr(homework_router, "get_prompt", lambda db, name, group_id=None: f"{name}-prompt")
    monkeypatch.setattr(homework_router, "ask_with_images", lambda prompt, image_urls, system=None, **kwargs: "**1.** Mock question")
    monkeypatch.setattr(homework_router, "ask", lambda prompt, system=None, **kwargs: json.dumps({"1": ["Derivatives"]}))

    # Create a PipelineJob to pass to the worker
    job = PipelineJob(step="pdf_to_markdown")
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_pdf_to_markdown(job_id, b"%PDF-question", "question", "group-q", "model-q")

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "done"
    assert job.homework_id is not None
    assert job.finished_at is not None

    hw = db_session.query(TutorHomework).filter(
        TutorHomework.group_id == "group-q",
        TutorHomework.model_id == "model-q",
    ).first()
    assert hw is not None
    assert hw.question_data == "**1.** Mock question"
    assert hw.topic_mapping == {"1": ["Derivatives"]}
    assert hw.question_uploaded_at is not None
    assert hw.topic_mapped_at is not None


def test_run_pdf_to_markdown_answer_updates_existing_homework(db_session, monkeypatch):
    """Background worker processes answer PDF, updates existing homework."""
    hw = TutorHomework(group_id="group-a", model_id="model-a", question_data="**1.** Existing question")
    db_session.add(hw)
    db_session.commit()

    monkeypatch.setattr(homework_router, "pdf_to_images", lambda pdf_bytes: [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}])
    monkeypatch.setattr(homework_router, "get_prompt", lambda db, name, group_id=None: f"{name}-prompt")
    monkeypatch.setattr(homework_router, "ask_with_images", lambda prompt, image_urls, system=None, **kwargs: "**1.** Mock answer")

    job = PipelineJob(step="pdf_to_markdown")
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_pdf_to_markdown(job_id, b"%PDF-answer", "answer", "group-a", "model-a")

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "done"

    hw = db_session.query(TutorHomework).filter(
        TutorHomework.group_id == "group-a",
        TutorHomework.model_id == "model-a",
    ).first()
    assert hw.answer_data == "**1.** Mock answer"
    assert hw.answer_source == "uploaded"
    assert hw.answer_uploaded_at is not None


def test_run_pdf_to_markdown_chunks_large_pdf_with_overlap_prompt(db_session, monkeypatch):
    """PDFs with >5 pages must be processed in 5-page chunks, and every chunk
    after the first must receive an overlap page with the dedicated overlap
    prompt. Verifies the branch at lines 106-127 of homework.py."""
    fake_pages = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,PAGE_{n}"}}
        for n in range(7)  # 7 pages → 2 chunks: [0..4] then [4..6]
    ]
    monkeypatch.setattr(homework_router, "pdf_to_images", lambda pdf_bytes: fake_pages)
    monkeypatch.setattr(homework_router, "get_prompt", lambda db, name, group_id=None: f"{name}-prompt")
    monkeypatch.setattr(
        homework_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps({"1": ["Derivatives"]}),
    )

    captured_calls = []

    def fake_ask_with_images(prompt, image_urls, system=None, **kwargs):
        captured_calls.append({"prompt": prompt, "image_urls": image_urls})
        return f"chunk-of-{len(image_urls)}-pages"

    monkeypatch.setattr(homework_router, "ask_with_images", fake_ask_with_images)

    job = PipelineJob(step="pdf_to_markdown")
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_pdf_to_markdown(job_id, b"%PDF-big", "question", "group-big", "model-big")

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "done"

    # Two chunk calls for 7 pages at chunk_size=5 with overlap.
    assert len(captured_calls) == 2
    first, second = captured_calls

    # First chunk: pages 0..4 (5 pages), no overlap notice.
    assert len(first["image_urls"]) == 5
    assert first["image_urls"][0]["image_url"]["url"].endswith("PAGE_0")
    assert "overlap page" not in first["prompt"]

    # Second chunk: overlap page (page 4) + pages 5, 6 → 3 pages total.
    # Uses the dedicated overlap prompt that tells the LLM to treat the first image as context.
    assert len(second["image_urls"]) == 3
    assert second["image_urls"][0]["image_url"]["url"].endswith("PAGE_4")
    assert "overlap page" in second["prompt"]
    assert "SECOND image onwards" in second["prompt"]

    # Chunks are joined by blank lines in the final markdown.
    hw = db_session.query(TutorHomework).filter(
        TutorHomework.group_id == "group-big", TutorHomework.model_id == "model-big"
    ).first()
    assert hw.question_data == "chunk-of-5-pages\n\nchunk-of-3-pages"


def test_run_pdf_to_markdown_sets_failed_on_error(db_session, monkeypatch):
    """Background worker sets job to failed if an exception occurs."""
    monkeypatch.setattr(homework_router, "pdf_to_images", lambda pdf_bytes: (_ for _ in ()).throw(RuntimeError("PDF parse error")))

    job = PipelineJob(step="pdf_to_markdown")
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_pdf_to_markdown(job_id, b"%PDF-bad", "question", "g1", "m1")

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "failed"
    assert "PDF parse error" in job.error
