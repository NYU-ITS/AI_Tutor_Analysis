import pytest
from datetime import datetime, timezone

from app.models import PipelineJob


pytestmark = pytest.mark.integration


def test_get_pipeline_status_returns_job(client, db_session):
    job = PipelineJob(step="run_analysis", homework_id="hw1", status="done")
    job.finished_at = datetime.now(timezone.utc)
    db_session.add(job)
    db_session.commit()

    resp = client.get(f"/pipeline/status/{job.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job.id
    assert body["step"] == "run_analysis"
    assert body["homework_id"] == "hw1"
    assert body["status"] == "done"
    assert body["finished_at"] is not None


def test_get_pipeline_status_returns_404_for_missing(client):
    resp = client.get("/pipeline/status/nonexistent-id")
    assert resp.status_code == 404


def test_get_jobs_filters_by_homework_and_step(client, db_session):
    j1 = PipelineJob(step="pdf_to_markdown", homework_id="hw1")
    j2 = PipelineJob(step="run_analysis", homework_id="hw1")
    j3 = PipelineJob(step="run_analysis", homework_id="hw2")
    db_session.add_all([j1, j2, j3])
    db_session.commit()

    # All jobs
    all_resp = client.get("/pipeline/jobs")
    assert len(all_resp.json()) == 3

    # Filter by homework_id
    by_hw = client.get("/pipeline/jobs", params={"homework_id": "hw1"})
    assert len(by_hw.json()) == 2

    # Filter by step
    by_step = client.get("/pipeline/jobs", params={"step": "run_analysis"})
    assert len(by_step.json()) == 2

    # Filter by both
    by_both = client.get("/pipeline/jobs", params={"homework_id": "hw1", "step": "pdf_to_markdown"})
    assert len(by_both.json()) == 1
    assert by_both.json()[0]["step"] == "pdf_to_markdown"


def test_get_jobs_returns_empty_when_none(client):
    resp = client.get("/pipeline/jobs")
    assert resp.status_code == 200
    assert resp.json() == []
