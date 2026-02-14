import base64
import json
from datetime import datetime, timezone
import fitz  # pymupdf
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.services.llm import ask, ask_with_images
from app.services.prompt import get_prompt
from app.database import get_db
from app.models import TutorHomework

router = APIRouter(prefix="/homework", tags=["homework"])


@router.get("/")
def get_homework(
    homework_id: int = Query(None, description="Filter by homework ID"),
    group_id: str = Query(None, description="Filter by group ID"),
    model_id: str = Query(None, description="Filter by model ID"),
    db: Session = Depends(get_db),
):
    """List homework entries with upload status for the frontend."""
    q = db.query(TutorHomework)
    if homework_id is not None:
        q = q.filter(TutorHomework.id == homework_id)
    if group_id is not None:
        q = q.filter(TutorHomework.group_id == group_id)
    if model_id is not None:
        q = q.filter(TutorHomework.model_id == model_id)

    results = []
    for hw in q.all():
        results.append({
            "id": hw.id,
            "group_id": hw.group_id,
            "model_id": hw.model_id,
            "question_uploaded": hw.question_uploaded_at is not None,
            "question_uploaded_at": hw.question_uploaded_at,
            "answer_uploaded": hw.answer_uploaded_at is not None,
            "answer_uploaded_at": hw.answer_uploaded_at,
            "topic_mapped": hw.topic_mapped_at is not None,
            "topic_mapped_at": hw.topic_mapped_at,
            "question_data": hw.question_data,
            "answer_data": hw.answer_data,
            "topic_mapping": hw.topic_mapping,
        })
    return results


def pdf_to_images(pdf_bytes: bytes) -> list[dict]:
    """Convert PDF bytes to a list of base64-encoded page images for the vision API."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        images.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    doc.close()
    return images


def _run_topic_mapping(hw: TutorHomework, db: Session) -> dict:
    """Internal: run topic mapping on a homework row and persist the result."""
    system_prompt = get_prompt(db, "topic_mapping", group_id=hw.group_id)
    response = ask(
        prompt=hw.question_data,
        system=system_prompt,
        response_format={"type": "json_object"},
    )
    topic_mapping = json.loads(response)
    hw.topic_mapping = topic_mapping
    hw.topic_mapped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(hw)
    return topic_mapping


@router.post("/pdf-to-markdown")
async def convert_pdf_to_markdown(
    file: UploadFile = File(...),
    doc_type: str = Query(..., pattern="^(question|answer)$", description="Type of document: 'question' or 'answer'"),
    group_id: str = Query(..., description="Group ID (required)."),
    model_id: str = Query(..., description="Model ID (required)."),
    homework_id: int = Query(None, description="Existing homework ID to update. Omit to create new."),
    db: Session = Depends(get_db),
):
    """Upload a homework or answer PDF -> LLM converts to Markdown -> saved to DB.

    When doc_type=question, topic mapping runs automatically after conversion.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    images = pdf_to_images(pdf_bytes)
    if not images:
        raise HTTPException(status_code=400, detail="Could not extract pages from PDF")

    system_prompt = get_prompt(db, "pdf_to_markdown", group_id=group_id)

    markdown = ask_with_images(
        prompt="Convert this document to Markdown. Reproduce every question exactly.",
        image_urls=images,
        system=system_prompt,
    )

    now = datetime.now(timezone.utc)

    # Save to database
    if homework_id:
        hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
        if not hw:
            raise HTTPException(status_code=404, detail=f"Homework {homework_id} not found")
    else:
        hw = TutorHomework(group_id=group_id, model_id=model_id)
        db.add(hw)

    if doc_type == "question":
        hw.question_data = markdown
        hw.question_uploaded_at = now
    else:
        hw.answer_data = markdown
        hw.answer_uploaded_at = now

    db.commit()
    db.refresh(hw)

    # Auto-run topic mapping after question upload
    topic_mapping = None
    if doc_type == "question":
        topic_mapping = _run_topic_mapping(hw, db)

    return {
        "homework_id": hw.id,
        "doc_type": doc_type,
        "markdown": markdown,
        "topic_mapping": topic_mapping,
        "question_uploaded_at": hw.question_uploaded_at,
        "answer_uploaded_at": hw.answer_uploaded_at,
        "topic_mapped_at": hw.topic_mapped_at,
    }
