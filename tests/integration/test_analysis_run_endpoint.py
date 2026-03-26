import json

import pytest

from app.models import (
    PipelineJob,
    StudentAnalysis,
    StudentConversation,
    StudentQuestionEvaluation,
    StudentTopicPerformance,
    TutorHomework,
)
from app.routers import analysis as analysis_router
from app.routers.analysis import _run_analysis_job


pytestmark = pytest.mark.integration


def test_run_analysis_returns_queued_with_job_id(client, db_session, monkeypatch):
    """POST /analysis/run returns queued status with a job_id."""
    hw = TutorHomework(
        group_id="group-1",
        model_id="model-1",
        question_data="**1.** Q1 text\n**2.** Q2 text",
        answer_data="**1.** A1\n\n**2.** A2",
        topic_mapping={"1": ["Derivatives"], "2": ["Limits"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-1",
            student_email="student1@example.edu",
            homework_id=hw.id,
            conversation_markdown="**USER:** solve q1\n**ASSISTANT:** ...",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {
                "1": {"attempted": True, "solved": False, "error_type": "Conceptual"},
                "2": {"attempted": True, "solved": True, "error_type": None},
            }
        ),
    )

    resp = client.post("/analysis/run", params={"homework_id": hw.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert "job_id" in body

    # Verify PipelineJob was created
    job = db_session.query(PipelineJob).filter(PipelineJob.id == body["job_id"]).first()
    assert job is not None
    assert job.step == "run_analysis"
    assert job.homework_id == hw.id


def test_run_analysis_background_worker_persists_results(db_session, monkeypatch):
    """Background worker _run_analysis_job persists StudentAnalysis + evaluations + topic performances."""
    hw = TutorHomework(
        group_id="group-1",
        model_id="model-1",
        question_data="**1.** Q1 text\n**2.** Q2 text",
        answer_data="**1.** A1\n\n**2.** A2",
        topic_mapping={"1": ["Derivatives"], "2": ["Limits"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-1",
            student_email="student1@example.edu",
            homework_id=hw.id,
            conversation_markdown="**USER:** solve q1\n**ASSISTANT:** ...",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {
                "1": {"attempted": True, "solved": False, "error_type": "Conceptual"},
                "2": {"attempted": True, "solved": True, "error_type": None},
            }
        ),
    )

    # Create PipelineJob
    job = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    # Run background worker directly
    _run_analysis_job(job_id, hw.id, None)

    db_session.expire_all()

    # Job should be done
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "done"
    assert job.finished_at is not None

    # Analysis should be persisted
    analysis_row = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-1", StudentAnalysis.homework_id == hw.id)
        .first()
    )
    assert analysis_row is not None
    assert analysis_row.total_question == 2
    assert analysis_row.total_attempted == 2
    assert analysis_row.total_solved == 1
    assert analysis_row.total_errors == 1

    evaluations = (
        db_session.query(StudentQuestionEvaluation)
        .filter(StudentQuestionEvaluation.student_analysis_id == analysis_row.id)
        .all()
    )
    assert len(evaluations) == 2

    topics = (
        db_session.query(StudentTopicPerformance)
        .filter(StudentTopicPerformance.student_analysis_id == analysis_row.id)
        .all()
    )
    assert len(topics) == 2
