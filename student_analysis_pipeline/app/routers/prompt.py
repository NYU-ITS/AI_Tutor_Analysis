from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import GeneralPrompt, TutorPrompt

router = APIRouter(prefix="/prompts", tags=["prompts"])


# ── Schemas ──

class GeneralPromptCreate(BaseModel):
    name: str
    prompt: str

class TutorPromptCreate(BaseModel):
    name: str
    group_id: str
    prompt: str

class PromptUpdate(BaseModel):
    prompt: Optional[str] = None
    is_active: Optional[bool] = None


# ── General Prompts ──

@router.get("/general")
def list_general_prompts(db: Session = Depends(get_db)):
    return db.query(GeneralPrompt).all()


@router.post("/general")
def create_general_prompt(body: GeneralPromptCreate, db: Session = Depends(get_db)):
    existing = db.query(GeneralPrompt).filter(GeneralPrompt.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"General prompt '{body.name}' already exists")
    p = GeneralPrompt(name=body.name, prompt=body.prompt)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/general/{prompt_id}")
def update_general_prompt(prompt_id: str, body: PromptUpdate, db: Session = Depends(get_db)):
    p = db.query(GeneralPrompt).filter(GeneralPrompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if body.prompt is not None:
        p.prompt = body.prompt
    if body.is_active is not None:
        p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return p


# ── Tutor Prompts (per group) ──

@router.get("/tutor")
def list_tutor_prompts(
    group_id: str = Query(None, description="Filter by group"),
    db: Session = Depends(get_db),
):
    q = db.query(TutorPrompt)
    if group_id is not None:
        q = q.filter(TutorPrompt.group_id == group_id)
    return q.all()


@router.post("/tutor")
def create_tutor_prompt(body: TutorPromptCreate, db: Session = Depends(get_db)):
    p = TutorPrompt(name=body.name, group_id=body.group_id, prompt=body.prompt)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/tutor/{prompt_id}")
def update_tutor_prompt(prompt_id: str, body: PromptUpdate, db: Session = Depends(get_db)):
    p = db.query(TutorPrompt).filter(TutorPrompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if body.prompt is not None:
        p.prompt = body.prompt
    if body.is_active is not None:
        p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return p
