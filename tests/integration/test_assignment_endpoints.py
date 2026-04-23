import pytest

from app.models import (
    StudentAnalysis,
    StudentPracticeAssignment,
    StudentTopicPerformance,
    TutorHomework,
    TutorPracticeProblem,
)


pytestmark = pytest.mark.integration


def _setup_practice_with_items(db_session):
    """Helper: creates homework, analyses, topic performances, and a practice set with problem_items."""
    hw = TutorHomework(group_id="g-assign", model_id="m-assign", question_data="q", topic_mapping={"1": ["Derivatives"], "2": ["Limits"]})
    db_session.add(hw)
    db_session.flush()

    s1 = StudentAnalysis(student_id="s1", student_email="s1@example.edu", homework_id=hw.id)
    s2 = StudentAnalysis(student_id="s2", student_email="s2@example.edu", homework_id=hw.id)
    db_session.add_all([s1, s2])
    db_session.flush()

    # s1 weak on Derivatives, mastered Limits
    db_session.add_all([
        StudentTopicPerformance(student_analysis_id=s1.id, topic_name="Derivatives", status="needs_practice"),
        StudentTopicPerformance(student_analysis_id=s1.id, topic_name="Limits", status="mastered"),
    ])
    # s2 weak on Limits, mastered Derivatives
    db_session.add_all([
        StudentTopicPerformance(student_analysis_id=s2.id, topic_name="Derivatives", status="mastered"),
        StudentTopicPerformance(student_analysis_id=s2.id, topic_name="Limits", status="needs_practice"),
    ])

    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        source="ai_generated",
        status="approved",
        version_number=1,
        problem_data="**1.** Deriv Q\n**2.** Limits Q",
        problem_items=[
            {"number": 1, "text": "Deriv Q", "topics": ["Derivatives"], "hint": "Use the power rule", "answer": "2x"},
            {"number": 2, "text": "Limits Q", "topics": ["Limits"], "hint": "Substitute directly", "answer": "5"},
        ],
        weakness_summary=[],
    )
    db_session.add(practice)
    db_session.commit()
    return hw, practice, s1, s2


def test_assign_practice_returns_404_when_practice_missing(client):
    resp = client.post("/assignment/assign", params={"practice_id": "nonexistent"})
    assert resp.status_code == 404


def test_assign_practice_returns_400_when_no_problem_items(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1")
    db_session.add(hw)
    db_session.flush()
    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        status="approved",
        version_number=1,
        problem_data="text",
        problem_items=None,
    )
    db_session.add(practice)
    db_session.commit()

    resp = client.post("/assignment/assign", params={"practice_id": practice.id})
    assert resp.status_code == 400
    assert "no structured problem_items" in resp.json()["detail"]


def test_assign_practice_returns_400_when_no_analyses(client, db_session):
    hw = TutorHomework(group_id="g1", model_id="m1")
    db_session.add(hw)
    db_session.flush()
    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        status="approved",
        version_number=1,
        problem_data="text",
        problem_items=[{"number": 1, "text": "Q", "topics": ["T"], "hint": "Hint", "answer": "A"}],
    )
    db_session.add(practice)
    db_session.commit()

    resp = client.post("/assignment/assign", params={"practice_id": practice.id})
    assert resp.status_code == 400
    assert "No student analyses found" in resp.json()["detail"]


def test_assign_practice_assigns_based_on_weak_topics(client, db_session):
    hw, practice, s1, s2 = _setup_practice_with_items(db_session)

    resp = client.post("/assignment/assign", params={"practice_id": practice.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["assigned_count"] == 2

    # s1 weak on Derivatives → should get Deriv Q (problem 1)
    s1_summary = next(s for s in body["students"] if s["student_id"] == "s1")
    assert s1_summary["assigned_count"] == 1
    assert s1_summary["fallback_used"] is False

    # s2 weak on Limits → should get Limits Q (problem 2)
    s2_summary = next(s for s in body["students"] if s["student_id"] == "s2")
    assert s2_summary["assigned_count"] == 1
    assert s2_summary["fallback_used"] is False

    # Verify DB records
    assignments = db_session.query(StudentPracticeAssignment).all()
    assert len(assignments) == 2


def test_assign_practice_upserts_existing_assignment(client, db_session):
    hw, practice, s1, s2 = _setup_practice_with_items(db_session)

    # Assign twice
    client.post("/assignment/assign", params={"practice_id": practice.id})
    client.post("/assignment/assign", params={"practice_id": practice.id})

    # Should not duplicate — still 2 assignments (one per student)
    assignments = db_session.query(StudentPracticeAssignment).all()
    assert len(assignments) == 2


def test_assign_practice_fallback_when_student_mastered_all(client, db_session):
    hw = TutorHomework(group_id="g-fb", model_id="m-fb", question_data="q", topic_mapping={"1": ["T"]})
    db_session.add(hw)
    db_session.flush()

    sa = StudentAnalysis(student_id="s1", student_email="s1@example.edu", homework_id=hw.id)
    db_session.add(sa)
    db_session.flush()
    # Student mastered everything
    db_session.add(StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Derivatives", status="mastered"))

    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        status="approved",
        version_number=1,
        problem_data="text",
        problem_items=[
            {"number": 1, "text": "Q1", "topics": ["Derivatives"], "hint": "H1", "answer": "A1"},
            {"number": 2, "text": "Q2", "topics": ["Limits"], "hint": "H2", "answer": "A2"},
        ],
    )
    db_session.add(practice)
    db_session.commit()

    resp = client.post("/assignment/assign", params={"practice_id": practice.id})
    assert resp.status_code == 200
    body = resp.json()
    # Student mastered all topics → no weak topics → assigned_count is 0 (no fallback)
    assert body["students"][0]["fallback_used"] is False
    assert body["students"][0]["assigned_count"] == 0


def test_get_assignments_filters(client, db_session):
    hw, practice, s1, s2 = _setup_practice_with_items(db_session)

    # Create assignments
    client.post("/assignment/assign", params={"practice_id": practice.id})

    # Get all
    all_resp = client.get("/assignment/")
    assert len(all_resp.json()) == 2

    # Filter by student
    by_student = client.get("/assignment/", params={"student_id": "s1"})
    assert len(by_student.json()) == 1
    assert by_student.json()[0]["student_id"] == "s1"

    # Filter by homework
    by_hw = client.get("/assignment/", params={"homework_id": hw.id})
    assert len(by_hw.json()) == 2

    # Filter by practice_problem_id
    by_practice = client.get("/assignment/", params={"practice_problem_id": practice.id})
    assert len(by_practice.json()) == 2


def test_get_assignments_topic_filter_returns_only_assignments_with_matching_item(client, db_session):
    """The `topic` query param filters returned assignments to those containing
    at least one item that covers the requested topic. Non-matching assignments
    are skipped entirely."""
    hw, practice, s1, s2 = _setup_practice_with_items(db_session)
    client.post("/assignment/assign", params={"practice_id": practice.id})

    # s1 got the Derivatives item; s2 got the Limits item.
    derivs = client.get("/assignment/", params={"topic": "Derivatives"}).json()
    assert len(derivs) == 1
    assert derivs[0]["student_id"] == "s1"

    limits = client.get("/assignment/", params={"topic": "Limits"}).json()
    assert len(limits) == 1
    assert limits[0]["student_id"] == "s2"


def test_get_assignments_topic_filter_narrows_assigned_items_to_topic(client, db_session):
    """When a topic matches, the returned `assigned_items` must be narrowed to
    only items containing that topic (not the full assignment)."""
    hw = TutorHomework(group_id="g-tf", model_id="m-tf", question_data="q",
                       topic_mapping={"1": ["Derivatives"], "2": ["Limits"]})
    db_session.add(hw)
    db_session.flush()

    sa = StudentAnalysis(student_id="s1", student_email="s1@example.edu", homework_id=hw.id)
    db_session.add(sa)
    db_session.flush()
    db_session.add_all([
        StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Derivatives", status="needs_practice"),
        StudentTopicPerformance(student_analysis_id=sa.id, topic_name="Limits",       status="needs_practice"),
    ])

    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        status="approved",
        version_number=1,
        problem_data="x",
        problem_items=[
            {"number": 1, "text": "Deriv Q", "topics": ["Derivatives"],  "hint": "h", "answer": "a"},
            {"number": 2, "text": "Lim Q",   "topics": ["Limits"],       "hint": "h", "answer": "a"},
        ],
    )
    db_session.add(practice)
    db_session.commit()

    client.post("/assignment/assign", params={"practice_id": practice.id})

    resp = client.get("/assignment/", params={"topic": "Derivatives"}).json()
    assert len(resp) == 1
    assert resp[0]["assigned_count"] == 1
    assert len(resp[0]["assigned_items"]) == 1
    assert resp[0]["assigned_items"][0]["text"] == "Deriv Q"


def test_get_assignments_topic_filter_omits_assignments_with_no_matching_item(client, db_session):
    """A completely non-matching topic returns an empty list rather than
    assignments with empty assigned_items."""
    hw, practice, s1, s2 = _setup_practice_with_items(db_session)
    client.post("/assignment/assign", params={"practice_id": practice.id})

    resp = client.get("/assignment/", params={"topic": "Integration"}).json()
    assert resp == []
