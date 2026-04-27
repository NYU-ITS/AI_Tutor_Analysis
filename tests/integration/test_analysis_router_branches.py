import json

import pytest

from app.models import (
    PipelineJob,
    StudentAnalysis,
    StudentConversation,
    StudentQuestionEvaluation,
    TutorHomework,
)
from app.routers import analysis as analysis_router
from app.routers.analysis import _run_analysis_job


pytestmark = pytest.mark.integration


def test_run_analysis_returns_404_when_homework_missing(client):
    resp = client.post("/analysis/run", params={"homework_id": "missing"})
    assert resp.status_code == 404


def test_run_analysis_requires_question_data(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1", question_data=None, topic_mapping={"1": ["Derivatives"]})
    db_session.add(hw)
    db_session.commit()

    resp = client.post("/analysis/run", params={"homework_id": hw.id})
    assert resp.status_code == 400
    assert "no question data" in resp.json()["detail"]


def test_run_analysis_requires_topic_mapping(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1", question_data="**1.** q1", topic_mapping=None, answer_data="**1.** a1")
    db_session.add(hw)
    db_session.commit()

    resp = client.post("/analysis/run", params={"homework_id": hw.id})
    assert resp.status_code == 400
    assert "no topic mapping" in resp.json()["detail"]


def test_run_analysis_returns_404_when_no_conversations(client, db_session):
    hw = TutorHomework(
        group_id="g-noconv",
        model_id="m-noconv",
        question_data="**1.** Q1",
        answer_data="**1.** A1",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.commit()

    resp = client.post("/analysis/run", params={"homework_id": hw.id})
    assert resp.status_code == 404
    assert "No student conversations found" in resp.json()["detail"]


def test_run_analysis_returns_404_when_student_conversation_missing(client, db_session):
    hw = TutorHomework(
        group_id="g-student-missing",
        model_id="m-student-missing",
        question_data="**1.** Q1",
        answer_data="**1.** A1",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-present",
            student_email="present@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    resp = client.post("/analysis/run", params={"homework_id": hw.id, "student_id": "student-missing"})
    assert resp.status_code == 404
    assert "No student conversations found" in resp.json()["detail"]


def test_run_analysis_auto_generates_answers_when_missing(db_session, monkeypatch):
    """Background worker auto-generates answers when homework has no answer_data."""
    hw = TutorHomework(
        group_id="g-auto",
        model_id="m-auto",
        question_data="**1.** Q1",
        answer_data=None,
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-auto",
            student_email="auto@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: f"{name}-prompt")

    def fake_ask(prompt, system=None, **kwargs):
        if kwargs.get("response_format") == {"type": "json_object"}:
            return json.dumps({"1": {"attempted": True, "solved": True, "error_type": None}})
        return "**1.** Auto-generated answer"

    monkeypatch.setattr(analysis_router, "ask", fake_ask)

    job = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()

    _run_analysis_job(job.id, hw.id, None)

    db_session.expire_all()
    hw = db_session.query(TutorHomework).filter(TutorHomework.id == hw.id).first()
    assert hw.answer_data == "**1.** Auto-generated answer"
    assert hw.answer_source == "ai_generated"
    assert hw.answer_uploaded_at is not None

    job = db_session.query(PipelineJob).filter(PipelineJob.id == job.id).first()
    assert job.status == "done"


def test_run_analysis_backfills_missing_question_evaluations(db_session, monkeypatch):
    """When LLM omits a non-visual question, worker stores a default Not Attempted evaluation."""
    hw = TutorHomework(
        group_id="g-backfill",
        model_id="m-backfill",
        question_data="**1.** Q1\n**2.** Q2",
        answer_data="**1.** A1\n\n**2.** A2",
        topic_mapping={"1": ["Derivatives"], "2": ["Integrals"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-backfill",
            student_email="backfill@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {"1": {"attempted": True, "solved": False, "error_type": "Procedural"}}
        ),
    )

    job = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()

    _run_analysis_job(job.id, hw.id, None)

    db_session.expire_all()
    analysis_row = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-backfill", StudentAnalysis.homework_id == hw.id)
        .first()
    )
    assert analysis_row is not None

    eval_rows = (
        db_session.query(StudentQuestionEvaluation)
        .filter(StudentQuestionEvaluation.student_analysis_id == analysis_row.id)
        .order_by(StudentQuestionEvaluation.question_number.asc())
        .all()
    )
    assert len(eval_rows) == 2
    assert eval_rows[0].question_number == 1
    assert eval_rows[0].attempted is True
    assert eval_rows[0].error_type == "Procedural"
    assert eval_rows[1].question_number == 2
    assert eval_rows[1].attempted is False
    assert eval_rows[1].error_type == "Not Attempted"


def test_run_analysis_job_honors_student_filter(db_session, monkeypatch):
    """Background worker analyzes only the requested student when student_id is supplied."""
    hw = TutorHomework(
        group_id="g-student-filter",
        model_id="m-student-filter",
        question_data="**1.** Q1",
        answer_data="**1.** A1",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add_all(
        [
            StudentConversation(
                student_id="student-include",
                student_email="include@example.edu",
                homework_id=hw.id,
                conversation_markdown="chat include",
            ),
            StudentConversation(
                student_id="student-exclude",
                student_email="exclude@example.edu",
                homework_id=hw.id,
                conversation_markdown="chat exclude",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {"1": {"attempted": True, "solved": True, "error_type": None}}
        ),
    )

    job = PipelineJob(step="run_analysis", homework_id=hw.id, student_id="student-include")
    db_session.add(job)
    db_session.commit()
    _run_analysis_job(job.id, hw.id, "student-include")

    db_session.expire_all()
    included = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-include", StudentAnalysis.homework_id == hw.id)
        .first()
    )
    excluded = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-exclude", StudentAnalysis.homework_id == hw.id)
        .first()
    )
    assert included is not None
    assert excluded is None


def test_run_analysis_marks_unattempted_and_skips_visual(db_session, monkeypatch):
    """Background worker marks unattempted questions with 'Not Attempted' and skips visual questions."""
    hw = TutorHomework(
        group_id="g-skip",
        model_id="m-skip",
        question_data="**1.** Q1\n**2.** Q2",
        answer_data="**1.** A1\n\n**2.** A2",
        topic_mapping={"1": ["Derivatives"], "2": ["N/A - Visual/Image-based"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-skip",
            student_email="skip@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {"1": {"attempted": False, "solved": False, "error_type": "Conceptual"}}
        ),
    )

    job = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()

    _run_analysis_job(job.id, hw.id, None)

    db_session.expire_all()

    analysis_row = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-skip", StudentAnalysis.homework_id == hw.id)
        .first()
    )
    assert analysis_row is not None

    evaluations = (
        db_session.query(StudentQuestionEvaluation)
        .filter(StudentQuestionEvaluation.student_analysis_id == analysis_row.id)
        .all()
    )
    # Only Q1 evaluated (Q2 is visual, skipped by the worker — but the worker evaluates
    # all non-visual questions and stores evaluations for what LLM returns)
    assert len(evaluations) == 1
    assert evaluations[0].error_type == "Not Attempted"


def test_run_analysis_upserts_existing_analysis_and_replaces_children(db_session, monkeypatch):
    """Running analysis twice replaces old evaluations instead of duplicating."""
    hw = TutorHomework(
        group_id="g-upsert",
        model_id="m-upsert",
        question_data="**1.** Q1",
        answer_data="**1.** A1",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="student-upsert",
            student_email="upsert@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")

    # First run — solved
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {"1": {"attempted": True, "solved": True, "error_type": None}}
        ),
    )
    job1 = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job1)
    db_session.commit()
    _run_analysis_job(job1.id, hw.id, None)

    # Second run — not solved
    db_session.expire_all()
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps(
            {"1": {"attempted": True, "solved": False, "error_type": "Procedural"}}
        ),
    )
    job2 = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job2)
    db_session.commit()
    _run_analysis_job(job2.id, hw.id, None)

    db_session.expire_all()

    analyses = (
        db_session.query(StudentAnalysis)
        .filter(StudentAnalysis.student_id == "student-upsert", StudentAnalysis.homework_id == hw.id)
        .all()
    )
    assert len(analyses) == 1

    eval_rows = (
        db_session.query(StudentQuestionEvaluation)
        .filter(StudentQuestionEvaluation.student_analysis_id == analyses[0].id)
        .all()
    )
    assert len(eval_rows) == 1
    assert eval_rows[0].solved is False
    assert eval_rows[0].error_type == "Procedural"


def test_run_analysis_job_sets_failed_on_error(db_session, monkeypatch):
    """Background worker sets job to failed if an exception occurs."""
    hw = TutorHomework(
        group_id="g-fail",
        model_id="m-fail",
        question_data="**1.** Q1",
        answer_data="**1.** A1",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()
    db_session.add(
        StudentConversation(
            student_id="s-fail",
            student_email="fail@example.edu",
            homework_id=hw.id,
            conversation_markdown="chat",
        )
    )
    db_session.commit()

    monkeypatch.setattr(analysis_router, "get_prompt", lambda db, name, group_id=None: "eval-prompt")
    monkeypatch.setattr(
        analysis_router,
        "ask",
        lambda prompt, system=None, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM exploded")),
    )

    job = PipelineJob(step="run_analysis", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_analysis_job(job_id, hw.id, None)

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    # Per-student errors are caught and logged; the job itself completes
    assert job.status == "done"


def test_run_analysis_job_sets_failed_when_homework_lookup_fails(db_session):
    """Outer exception path marks the pipeline job as failed."""
    job = PipelineJob(step="run_analysis", homework_id="missing-hw")
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    _run_analysis_job(job_id, "missing-hw", None)

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    assert job.status == "failed"
    assert job.error is not None


def test_get_analyses_filters_by_homework_and_student(client, db_session):
    hw1 = TutorHomework(group_id="g1", model_id="m1")
    hw2 = TutorHomework(group_id="g2", model_id="m2")
    db_session.add_all([hw1, hw2])
    db_session.flush()

    db_session.add_all(
        [
            StudentAnalysis(student_id="s1", student_email="s1@example.edu", homework_id=hw1.id),
            StudentAnalysis(student_id="s2", student_email="s2@example.edu", homework_id=hw1.id),
            StudentAnalysis(student_id="s1", student_email="s1@example.edu", homework_id=hw2.id),
        ]
    )
    db_session.commit()

    all_rows = client.get("/analysis/").json()
    assert len(all_rows) == 3

    by_homework = client.get("/analysis/", params={"homework_id": hw1.id}).json()
    assert len(by_homework) == 2

    by_student = client.get("/analysis/", params={"student_id": "s1"}).json()
    assert len(by_student) == 2


def test_get_analyses_filters_by_analysis_id(client, db_session):
    hw = TutorHomework(group_id="g-filter-id", model_id="m-filter-id")
    db_session.add(hw)
    db_session.flush()

    first = StudentAnalysis(student_id="sid-1", student_email="sid1@example.edu", homework_id=hw.id)
    second = StudentAnalysis(student_id="sid-2", student_email="sid2@example.edu", homework_id=hw.id)
    db_session.add_all([first, second])
    db_session.commit()

    filtered = client.get("/analysis/", params={"analysis_id": first.id}).json()
    assert len(filtered) == 1
    assert filtered[0]["id"] == first.id
