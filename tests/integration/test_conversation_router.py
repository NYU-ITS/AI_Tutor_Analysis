import json

import pytest

from app.models import StudentConversation, TutorHomework
from app.routers import conversation as conversation_router
from tests.helpers import FakeOwuiSession, Obj


pytestmark = pytest.mark.integration


def test_export_conversations_returns_404_when_homework_missing(client):
    resp = client.post("/conversation/export", params={"homework_id": "missing-id"})
    assert resp.status_code == 404


def test_export_conversations_returns_400_when_homework_missing_group_or_model(client, db_session):
    hw = TutorHomework(group_id=None, model_id="m1")
    db_session.add(hw)
    db_session.commit()

    resp = client.post("/conversation/export", params={"homework_id": hw.id})
    assert resp.status_code == 400


def test_export_conversations_returns_404_when_group_not_found(client, db_session, monkeypatch):
    hw = TutorHomework(group_id="group-x", model_id="model-x")
    db_session.add(hw)
    db_session.commit()

    monkeypatch.setattr(
        conversation_router,
        "OwuiSessionLocal",
        lambda: FakeOwuiSession(group_obj=None, chat_user_rows=[]),
    )

    resp = client.post("/conversation/export", params={"homework_id": hw.id})
    assert resp.status_code == 404
    assert "not found in OpenWebUI DB" in resp.json()["detail"]


def test_export_conversations_returns_warning_when_group_has_no_members(client, db_session, monkeypatch):
    hw = TutorHomework(group_id="group-empty", model_id="model-empty")
    db_session.add(hw)
    db_session.commit()

    monkeypatch.setattr(
        conversation_router,
        "OwuiSessionLocal",
        lambda: FakeOwuiSession(group_obj=Obj(id="group-empty", user_ids=[]), chat_user_rows=[]),
    )

    resp = client.post("/conversation/export", params={"homework_id": hw.id})
    assert resp.status_code == 200
    assert resp.json()["status"] == "warning"


def test_export_conversations_handles_string_user_ids_and_fallback_chat_models(client, db_session, monkeypatch):
    hw = TutorHomework(group_id="group-s", model_id="model-s")
    db_session.add(hw)
    db_session.commit()

    group = Obj(id="group-s", user_ids=json.dumps(["student-1", "student-2"]))
    user1 = Obj(id="student-1", email="s1@example.edu")
    user2 = Obj(id="student-2", email="s2@example.edu")
    chat1 = Obj(
        id="chat-1",
        user_id="student-1",
        title="Chat 1",
        meta={"models": ["model-s"]},
        chat={"history": {"messages": {"m1": {"role": "user", "content": "u", "timestamp": 1}}}},
        created_at=1,
        archived=False,
    )
    chat2 = Obj(
        id="chat-2",
        user_id="student-2",
        title="Chat 2",
        meta={},
        chat={"models": ["model-s"], "history": {"messages": {"m2": {"role": "assistant", "content": "a", "timestamp": 2}}}},
        created_at=2,
        archived=False,
    )
    chat_other_model = Obj(
        id="chat-3",
        user_id="student-2",
        title="Chat other model",
        meta={"models": ["other-model"]},
        chat={"history": {"messages": {}}},
        created_at=3,
        archived=False,
    )

    monkeypatch.setattr(
        conversation_router,
        "OwuiSessionLocal",
        lambda: FakeOwuiSession(group_obj=group, chat_user_rows=[(chat1, user1), (chat2, user2), (chat_other_model, user2)]),
    )

    resp = client.post("/conversation/export", params={"homework_id": hw.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["total_students"] == 2

    rows = db_session.query(StudentConversation).filter(StudentConversation.homework_id == hw.id).all()
    assert len(rows) == 2


def test_export_conversations_upserts_existing_row(client, db_session, monkeypatch):
    hw = TutorHomework(group_id="group-u", model_id="model-u")
    db_session.add(hw)
    db_session.commit()

    group = Obj(id="group-u", user_ids=["student-1"])
    user = Obj(id="student-1", email="s1@example.edu")
    chat = Obj(
        id="chat-1",
        user_id="student-1",
        title="Chat 1",
        meta={"models": ["model-u"]},
        chat={"history": {"messages": {"m1": {"role": "user", "content": "v1", "timestamp": 1}}}},
        created_at=1,
        archived=False,
    )
    monkeypatch.setattr(
        conversation_router,
        "OwuiSessionLocal",
        lambda: FakeOwuiSession(group_obj=group, chat_user_rows=[(chat, user)]),
    )

    first = client.post("/conversation/export", params={"homework_id": hw.id})
    assert first.status_code == 200
    assert db_session.query(StudentConversation).filter(StudentConversation.homework_id == hw.id).count() == 1

    # Run again with modified content; should still be a single row.
    chat.chat = {"history": {"messages": {"m2": {"role": "assistant", "content": "v2", "timestamp": 2}}}}
    second = client.post("/conversation/export", params={"homework_id": hw.id})
    assert second.status_code == 200
    assert db_session.query(StudentConversation).filter(StudentConversation.homework_id == hw.id).count() == 1


def test_get_conversations_filters_by_homework_and_student(client, db_session):
    hw1 = TutorHomework(group_id="g1", model_id="m1")
    hw2 = TutorHomework(group_id="g2", model_id="m2")
    db_session.add_all([hw1, hw2])
    db_session.flush()
    db_session.add_all(
        [
            StudentConversation(student_id="s1", student_email="s1@example.edu", homework_id=hw1.id, conversation_markdown="A"),
            StudentConversation(student_id="s2", student_email="s2@example.edu", homework_id=hw1.id, conversation_markdown="B"),
            StudentConversation(student_id="s1", student_email="s1@example.edu", homework_id=hw2.id, conversation_markdown="C"),
        ]
    )
    db_session.commit()

    all_rows = client.get("/conversation/").json()
    assert len(all_rows) == 3

    by_homework = client.get("/conversation/", params={"homework_id": hw1.id}).json()
    assert len(by_homework) == 2

    by_student = client.get("/conversation/", params={"student_id": "s1"}).json()
    assert len(by_student) == 2
