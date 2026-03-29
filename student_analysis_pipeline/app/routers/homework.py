import base64
import json
from datetime import datetime, timezone
import fitz  # pymupdf
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.services.llm import ask, ask_with_images
from app.services.prompt import get_prompt
from app.database import get_db, SessionLocal
from app.models import PipelineJob, TutorHomework

router = APIRouter(prefix="/homework", tags=["homework"])


@router.get("/")
def get_homework(
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
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
            "answer_source": hw.answer_source,
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
        pix = page.get_pixmap(dpi=150)
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


def _run_pdf_to_markdown(
    job_id: str, pdf_bytes: bytes, doc_type: str, group_id: str, model_id: str
) -> None:
    """Runs in the background. Opens its own DB session independent of the request."""
    db = SessionLocal()
    try:
        job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        job.status = "running"
        db.commit()

        images = pdf_to_images(pdf_bytes)
        system_prompt = get_prompt(db, "pdf_to_markdown", group_id=group_id)

        chunk_size = 5
        if len(images) <= chunk_size:
            # Small PDF: send all pages in one call
            markdown = ask_with_images(
                prompt="Convert this document to Markdown. Reproduce every question exactly.",
                image_urls=images,
                system=system_prompt,
            )
        else:
            # Large PDF: process in chunks with 1-page overlap to preserve cross-page questions.
            # Each non-first chunk includes the last page of the previous chunk as context only.
            markdown_parts = []
            i = 0
            while i < len(images):
                if i == 0:
                    chunk = images[0:chunk_size]
                    prompt = "Convert this document to Markdown. Reproduce every question exactly."
                else:
                    # Include 1 overlap page from the previous chunk for context
                    chunk = images[i - 1:i + chunk_size]
                    prompt = (
                        "The FIRST image is an overlap page already transcribed in the previous section. "
                        "Use it ONLY as context to complete any question that continues from it. "
                        "Output ONLY the content from the SECOND image onwards. "
                        "Reproduce every question exactly."
                    )
                part = ask_with_images(prompt=prompt, image_urls=chunk, system=system_prompt)
                markdown_parts.append(part)
                i += chunk_size
            markdown = "\n\n".join(markdown_parts)

        now = datetime.now(timezone.utc)
        hw = (
            db.query(TutorHomework)
            .filter(TutorHomework.group_id == group_id, TutorHomework.model_id == model_id)
            .first()
        )
        if not hw:
            hw = TutorHomework(group_id=group_id, model_id=model_id)
            db.add(hw)

        if doc_type == "question":
            hw.question_data = markdown
            hw.question_uploaded_at = now
        else:
            hw.answer_data = markdown
            hw.answer_source = "uploaded"
            hw.answer_uploaded_at = now

        db.commit()
        db.refresh(hw)

        if doc_type == "question":
            _run_topic_mapping(hw, db)

        job.homework_id = hw.id
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/pdf-to-markdown")
async def convert_pdf_to_markdown(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Query(..., pattern="^(question|answer)$", description="Type of document: 'question' or 'answer'"),
    group_id: str = Query(..., description="Group ID (required)."),
    model_id: str = Query(..., description="Model ID (required)."),
    db: Session = Depends(get_db),
):
    """Upload a homework or answer PDF -> LLM converts to Markdown in background.

    Returns a job_id immediately. Poll GET /pipeline/status/{job_id} for progress.
    Upserts by group_id + model_id (one homework per group+model).
    When doc_type=question, topic mapping runs automatically after conversion.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Read bytes now — UploadFile is request-scoped and unavailable in background
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    job = PipelineJob(step="pdf_to_markdown")
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_pdf_to_markdown, job.id, pdf_bytes, doc_type, group_id, model_id)

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "PDF conversion started. Poll GET /pipeline/status/{job_id} for progress.",
    }
