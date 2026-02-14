from sqlalchemy.orm import Session
from app.models import GeneralPrompt, TutorPrompt


def get_prompt(db: Session, name: str, group_id: str = None) -> str:
    """Look up a prompt by name.

    Resolution order:
      1. Active tutor_prompt for this group_id + name
      2. Active general_prompt for this name
      3. Raise if nothing found
    """
    if group_id is not None:
        tutor = (
            db.query(TutorPrompt)
            .filter(
                TutorPrompt.name == name,
                TutorPrompt.group_id == group_id,
                TutorPrompt.is_active == True,
            )
            .first()
        )
        if tutor:
            return tutor.prompt

    general = (
        db.query(GeneralPrompt)
        .filter(GeneralPrompt.name == name, GeneralPrompt.is_active == True)
        .first()
    )
    if general:
        return general.prompt

    raise ValueError(f"No active prompt found for name='{name}', group_id={group_id}")
