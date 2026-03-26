import uuid

import pytest

from app.models import generate_uuid, PipelineJob, StudentPracticeAssignment


pytestmark = pytest.mark.unit


def test_generate_uuid_returns_valid_uuid_string():
    result = generate_uuid()
    assert isinstance(result, str)
    # Verify it's a valid UUID (will raise ValueError if not)
    parsed = uuid.UUID(result)
    assert str(parsed) == result


def test_generate_uuid_returns_unique_values():
    results = {generate_uuid() for _ in range(100)}
    assert len(results) == 100


def test_pipeline_job_model_has_correct_fields():
    job = PipelineJob(step="run_analysis", status="queued", homework_id="hw1")
    assert job.step == "run_analysis"
    assert job.status == "queued"
    assert job.homework_id == "hw1"
    assert job.error is None
    assert job.student_id is None
    assert job.finished_at is None


def test_student_practice_assignment_model_fields():
    assignment = StudentPracticeAssignment(
        student_id="s1",
        student_email="s1@example.edu",
        homework_id="hw1",
        practice_problem_id="pp1",
        assigned_items=[{"number": 1, "text": "Q1", "topics": ["T"]}],
    )
    assert assignment.student_id == "s1"
    assert assignment.student_email == "s1@example.edu"
    assert assignment.homework_id == "hw1"
    assert assignment.practice_problem_id == "pp1"
    assert len(assignment.assigned_items) == 1
