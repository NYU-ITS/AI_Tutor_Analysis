import json

import pytest

from app.models import TutorHomework
from app.routers import homework as homework_router
from app.routers.homework import _run_topic_mapping


pytestmark = pytest.mark.integration


def test_run_topic_mapping_persists_topic_data(db_session, monkeypatch):
    hw = TutorHomework(group_id="group-1", model_id="model-1", question_data="**1.** Q1")
    db_session.add(hw)
    db_session.commit()

    monkeypatch.setattr(homework_router, "get_prompt", lambda db, name, group_id=None: "topic-prompt")
    monkeypatch.setattr(homework_router, "ask", lambda prompt, system=None, **kwargs: json.dumps({"1": ["Limits"]}))

    result = _run_topic_mapping(hw, db_session)

    assert result == {"1": ["Limits"]}
    assert hw.topic_mapping == {"1": ["Limits"]}
    assert hw.topic_mapped_at is not None
