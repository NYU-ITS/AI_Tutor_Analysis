import json

import pytest
from datetime import datetime, timedelta, timezone

from app.models import (
    PipelineJob,
    StudentAnalysis,
    StudentTopicPerformance,
    TutorHomework,
    TutorPracticeProblem,
)
from app.routers import practice as practice_router
from app.routers.practice import _run_generate_practice


pytestmark = pytest.mark.integration


def test_class_weakness_and_generate_practice(client, db_session, monkeypatch):
    hw = TutorHomework(
        group_id="group-practice",
        model_id="model-practice",
        question_data="**1.** Original question",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()

    s1 = StudentAnalysis(student_id="s1", homework_id=hw.id)
    s2 = StudentAnalysis(student_id="s2", homework_id=hw.id)
    db_session.add_all([s1, s2])
    db_session.flush()
    db_session.add_all(
        [
            StudentTopicPerformance(student_analysis_id=s1.id, topic_name="Derivatives", status="needs_practice"),
            StudentTopicPerformance(student_analysis_id=s2.id, topic_name="Derivatives", status="needs_practice"),
        ]
    )
    db_session.commit()

    # Step 1: Check class weakness endpoint
    weakness_resp = client.get("/practice/class-weakness", params={"homework_id": hw.id, "weakness_threshold": 0.5})
    assert weakness_resp.status_code == 200
    assert weakness_resp.json()["weak_topics_count"] == 1

    # Step 2: Generate practice — now returns queued
    monkeypatch.setattr(practice_router, "get_prompt", lambda db, name, group_id=None: "practice-system-prompt")
    monkeypatch.setattr(
        practice_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps({
            "problems": [{"number": 1, "text": "Practice derivative question", "topics": ["Derivatives"], "hint": "Use the chain rule", "answer": "f'(x)"}],
            "markdown": "**1.** Practice derivative question",
        }),
    )

    generate_resp = client.post("/practice/generate", params={"homework_id": hw.id, "weakness_threshold": 0.5})
    assert generate_resp.status_code == 200
    body = generate_resp.json()
    assert body["status"] == "queued"
    assert "job_id" in body

    # Verify PipelineJob was created
    job = db_session.query(PipelineJob).filter(PipelineJob.id == body["job_id"]).first()
    assert job is not None
    assert job.step == "generate_practice"


def test_generate_practice_background_worker_persists_results(db_session, monkeypatch):
    """Background worker _run_generate_practice saves practice problem with problem_items."""
    hw = TutorHomework(
        group_id="g-bg",
        model_id="m-bg",
        question_data="**1.** Original question",
        topic_mapping={"1": ["Derivatives"]},
    )
    db_session.add(hw)
    db_session.flush()

    sa = StudentAnalysis(student_id="s1", homework_id=hw.id)
    db_session.add(sa)
    db_session.flush()
    db_session.add(StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Derivatives", status="needs_practice"))
    db_session.commit()

    monkeypatch.setattr(practice_router, "get_prompt", lambda db, name, group_id=None: "prompt")
    monkeypatch.setattr(
        practice_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps({
            "problems": [{"number": 1, "text": "Practice Q", "topics": ["Derivatives"], "hint": "Hint text", "answer": "Answer text"}],
            "markdown": "**1.** Practice Q",
        }),
    )

    job = PipelineJob(step="generate_practice", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()

    _run_generate_practice(job.id, hw.id, None, 0.5)

    db_session.expire_all()
    job = db_session.query(PipelineJob).filter(PipelineJob.id == job.id).first()
    assert job.status == "done"

    saved = db_session.query(TutorPracticeProblem).filter(TutorPracticeProblem.homework_id == hw.id).first()
    assert saved is not None
    assert saved.status == "pending"
    assert saved.version_number == 1
    assert saved.problem_data == "**1.** Practice Q"
    assert saved.problem_items == [{"number": 1, "text": "Practice Q", "topics": ["Derivatives"], "hint": "Hint text", "answer": "Answer text"}]


def test_class_weakness_returns_404_when_homework_missing(client):
    resp = client.get("/practice/class-weakness", params={"homework_id": "missing"})
    assert resp.status_code == 404


def test_class_weakness_returns_empty_when_no_analyses(client, db_session):
    hw = TutorHomework(group_id="g-empty", model_id="m-empty", question_data="q", topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.commit()

    resp = client.get("/practice/class-weakness", params={"homework_id": hw.id, "weakness_threshold": 0.5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students_analyzed"] == 0
    assert body["weak_topics_count"] == 0


def test_generate_practice_returns_404_when_homework_missing(client):
    resp = client.post("/practice/generate", params={"homework_id": "missing"})
    assert resp.status_code == 404


def test_generate_practice_requires_question_data(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1", question_data=None, topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.commit()
    resp = client.post("/practice/generate", params={"homework_id": hw.id})
    assert resp.status_code == 400
    assert "no question data" in resp.json()["detail"]


def test_generate_practice_requires_topic_mapping(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1", question_data="q", topic_mapping=None)
    db_session.add(hw)
    db_session.commit()
    resp = client.post("/practice/generate", params={"homework_id": hw.id})
    assert resp.status_code == 400
    assert "no topic mapping" in resp.json()["detail"]


def test_generate_practice_returns_400_when_no_weak_topics(client, db_session):
    hw = TutorHomework(group_id="g-noweak", model_id="m-noweak", question_data="q", topic_mapping={"1": ["Derivatives"]})
    db_session.add(hw)
    db_session.flush()
    sa = StudentAnalysis(student_id="s1", homework_id=hw.id)
    db_session.add(sa)
    db_session.flush()
    db_session.add(StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Derivatives", status="mastered"))
    db_session.commit()

    resp = client.post("/practice/generate", params={"homework_id": hw.id, "weakness_threshold": 0.5})
    assert resp.status_code == 400
    assert "No weak topics found" in resp.json()["detail"]


def test_generate_practice_increments_version_number(db_session, monkeypatch):
    """Background worker increments version_number based on existing practice problems."""
    hw = TutorHomework(group_id="g-ver", model_id="m-ver", question_data="q", topic_mapping={"1": ["Derivatives"]})
    db_session.add(hw)
    db_session.flush()

    sa = StudentAnalysis(student_id="s1", homework_id=hw.id)
    db_session.add(sa)
    db_session.flush()
    db_session.add(StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Derivatives", status="needs_practice"))
    db_session.add(
        TutorPracticeProblem(
            homework_id=hw.id,
            group_id=hw.group_id,
            source="ai_generated",
            status="pending",
            version_number=1,
            problem_data="old",
            weakness_summary=[],
        )
    )
    db_session.commit()

    monkeypatch.setattr(practice_router, "get_prompt", lambda db, name, group_id=None: "prompt")
    monkeypatch.setattr(
        practice_router,
        "ask",
        lambda prompt, system=None, **kwargs: json.dumps({
            "problems": [{"number": 1, "text": "New Q", "topics": ["Derivatives"]}],
            "markdown": "**1.** New Q",
        }),
    )

    job = PipelineJob(step="generate_practice", homework_id=hw.id)
    db_session.add(job)
    db_session.commit()

    _run_generate_practice(job.id, hw.id, None, 0.5)

    db_session.expire_all()
    problems = (
        db_session.query(TutorPracticeProblem)
        .filter(TutorPracticeProblem.homework_id == hw.id)
        .order_by(TutorPracticeProblem.version_number.desc())
        .all()
    )
    assert len(problems) == 2
    assert problems[0].version_number == 2


def test_get_practice_problems_filters_and_orders_desc(client, db_session):
    hw1 = TutorHomework(group_id="g1", model_id="m1")
    hw2 = TutorHomework(group_id="g2", model_id="m2")
    db_session.add_all([hw1, hw2])
    db_session.flush()

    p1 = TutorPracticeProblem(homework_id=hw1.id, group_id="g1", status="approved", version_number=1, problem_data="p1")
    p2 = TutorPracticeProblem(homework_id=hw1.id, group_id="g1", status="pending", version_number=2, problem_data="p2")
    p3 = TutorPracticeProblem(homework_id=hw2.id, group_id="g2", status="rejected", version_number=1, problem_data="p3")
    now = datetime.now(timezone.utc)
    p1.created_at = now - timedelta(minutes=2)
    p2.created_at = now - timedelta(minutes=1)
    p3.created_at = now
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    all_rows = client.get("/practice/").json()
    assert len(all_rows) == 3
    assert all_rows[0]["id"] == p3.id
    assert all_rows[1]["id"] == p2.id
    assert all_rows[2]["id"] == p1.id

    by_homework = client.get("/practice/", params={"homework_id": hw1.id}).json()
    assert len(by_homework) == 2

    by_group = client.get("/practice/", params={"group_id": "g2"}).json()
    assert len(by_group) == 1
    assert by_group[0]["group_id"] == "g2"

    by_status = client.get("/practice/", params={"status": "pending"}).json()
    assert len(by_status) == 1
    assert by_status[0]["status"] == "pending"


def test_update_practice_status_success_and_not_found(client, db_session):
    hw = TutorHomework(group_id="g-upd", model_id="m-upd")
    db_session.add(hw)
    db_session.flush()
    p = TutorPracticeProblem(homework_id=hw.id, group_id=hw.group_id, status="pending", version_number=1, problem_data="x")
    db_session.add(p)
    db_session.commit()

    missing = client.patch("/practice/missing/status", params={"status": "approved"})
    assert missing.status_code == 404

    ok = client.patch(f"/practice/{p.id}/status", params={"status": "approved"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"
