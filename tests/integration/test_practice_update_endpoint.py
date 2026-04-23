"""Integration tests for PATCH /practice/{practice_id} (update_practice_problems).

This endpoint lets instructors edit generated practice problems — updating
problem_items, problem_data, and/or status (approved / rejected / pending).
All three fields are optional.
"""

import pytest

from app.models import TutorHomework, TutorPracticeProblem


pytestmark = pytest.mark.integration


def _create_practice(db_session):
    hw = TutorHomework(group_id="g-upd-full", model_id="m-upd-full")
    db_session.add(hw)
    db_session.flush()

    practice = TutorPracticeProblem(
        homework_id=hw.id,
        group_id=hw.group_id,
        source="ai_generated",
        status="pending",
        version_number=1,
        problem_data="**1.** Original Q",
        problem_items=[
            {"number": 1, "text": "Original Q", "topics": ["Derivatives"], "hint": "h", "answer": "a"},
        ],
        weakness_summary=[],
    )
    db_session.add(practice)
    db_session.commit()
    return practice


def test_update_practice_problems_returns_404_when_missing(client):
    resp = client.patch("/practice/nonexistent", json={"status": "approved"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_update_practice_problems_updates_problem_items_only(client, db_session):
    practice = _create_practice(db_session)

    new_items = [
        {"number": 1, "text": "Edited Q1", "topics": ["Limits"], "hint": "edited-hint", "answer": "edited-ans"},
        {"number": 2, "text": "New Q2",    "topics": ["Derivatives"], "hint": "h2",      "answer": "a2"},
    ]
    resp = client.patch(f"/practice/{practice.id}", json={"problem_items": new_items})
    assert resp.status_code == 200

    body = resp.json()
    assert body["problem_items"] == new_items
    # Unchanged fields preserved.
    assert body["problem_data"] == "**1.** Original Q"
    assert body["status"] == "pending"

    db_session.expire_all()
    fresh = db_session.query(TutorPracticeProblem).filter(TutorPracticeProblem.id == practice.id).first()
    assert fresh.problem_items == new_items


def test_update_practice_problems_updates_problem_data_only(client, db_session):
    practice = _create_practice(db_session)

    resp = client.patch(f"/practice/{practice.id}", json={"problem_data": "**1.** Rewritten markdown"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["problem_data"] == "**1.** Rewritten markdown"
    # Items unchanged.
    assert body["problem_items"][0]["text"] == "Original Q"


def test_update_practice_problems_updates_status_valid_values(client, db_session):
    practice = _create_practice(db_session)

    for new_status in ("approved", "rejected", "pending"):
        resp = client.patch(f"/practice/{practice.id}", json={"status": new_status})
        assert resp.status_code == 200, f"failed for status={new_status}"
        assert resp.json()["status"] == new_status


def test_update_practice_problems_rejects_invalid_status(client, db_session):
    practice = _create_practice(db_session)
    resp = client.patch(f"/practice/{practice.id}", json={"status": "bogus"})
    assert resp.status_code == 400
    assert "Status must be one of" in resp.json()["detail"]


def test_update_practice_problems_updates_all_fields_at_once(client, db_session):
    practice = _create_practice(db_session)

    resp = client.patch(
        f"/practice/{practice.id}",
        json={
            "problem_items": [{"number": 1, "text": "All-new Q", "topics": ["Integration"], "hint": "h", "answer": "a"}],
            "problem_data": "**1.** All-new markdown",
            "status": "approved",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["problem_data"] == "**1.** All-new markdown"
    assert body["problem_items"][0]["text"] == "All-new Q"
    # Response must echo all original metadata too.
    assert body["version_number"] == 1
    assert body["homework_id"] == practice.homework_id
