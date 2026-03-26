import pytest

from app.models import GeneralPrompt, TutorPrompt
from app.services.prompt import get_prompt


pytestmark = pytest.mark.integration


def test_get_prompt_prefers_group_override(db_session):
    db_session.add(GeneralPrompt(name="custom_eval_prompt", prompt="general"))
    db_session.add(TutorPrompt(name="custom_eval_prompt", group_id="g1", prompt="group-specific"))
    db_session.commit()

    value = get_prompt(db_session, "custom_eval_prompt", group_id="g1")
    assert value == "group-specific"


def test_get_prompt_falls_back_to_general(db_session):
    db_session.add(GeneralPrompt(name="custom_topic_prompt", prompt="general-topic-prompt"))
    db_session.commit()

    value = get_prompt(db_session, "custom_topic_prompt", group_id="missing-group")
    assert value == "general-topic-prompt"


def test_get_prompt_raises_if_no_active_prompt(db_session):
    with pytest.raises(ValueError, match="No active prompt found"):
        get_prompt(db_session, "does_not_exist", group_id="g1")


def test_get_prompt_ignores_inactive_tutor_and_uses_general(db_session):
    db_session.add(GeneralPrompt(name="mixed_prompt", prompt="general-active", is_active=True))
    db_session.add(TutorPrompt(name="mixed_prompt", group_id="g1", prompt="group-inactive", is_active=False))
    db_session.commit()

    value = get_prompt(db_session, "mixed_prompt", group_id="g1")
    assert value == "general-active"
