import pytest

from app.models import GeneralPrompt
from app.seed import DEFAULT_PROMPTS, seed_default_prompts


pytestmark = pytest.mark.integration


def test_seed_default_prompts_inserts_expected_names(db_session):
    db_session.query(GeneralPrompt).delete()
    db_session.commit()

    seed_default_prompts(db_session)

    names = {p.name for p in db_session.query(GeneralPrompt).all()}
    expected = {p["name"] for p in DEFAULT_PROMPTS}
    assert names == expected


def test_seed_default_prompts_is_idempotent(db_session):
    seed_default_prompts(db_session)
    first_count = db_session.query(GeneralPrompt).count()

    seed_default_prompts(db_session)
    second_count = db_session.query(GeneralPrompt).count()

    assert first_count == second_count


def test_seed_upserts_existing_prompt_text(db_session):
    """Seed updates prompt text if the prompt already exists (upsert behavior)."""
    db_session.query(GeneralPrompt).delete()
    db_session.commit()

    # Insert a prompt with old text
    db_session.add(GeneralPrompt(name="pdf_to_markdown", prompt="old text"))
    db_session.commit()

    # Run seed — should update the prompt text to the default
    seed_default_prompts(db_session)

    row = db_session.query(GeneralPrompt).filter(GeneralPrompt.name == "pdf_to_markdown").first()
    expected_prompt = next(p["prompt"] for p in DEFAULT_PROMPTS if p["name"] == "pdf_to_markdown")
    assert row.prompt == expected_prompt
    assert row.prompt != "old text"

    # Should still be exactly 5 prompts (not 6)
    assert db_session.query(GeneralPrompt).count() == len(DEFAULT_PROMPTS)
