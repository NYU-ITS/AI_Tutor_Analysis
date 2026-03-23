from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PipelineJob

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _format_job(job: PipelineJob) -> dict:
    return {
        "job_id": job.id,
        "step": job.step,
        "homework_id": job.homework_id,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


@router.get("/status/{job_id}")
def get_pipeline_status(job_id: str, db: Session = Depends(get_db)):
    """Poll the status of any background pipeline job by job_id.

    Works for all steps: pdf_to_markdown, run_analysis, generate_practice.
    Status values: queued / running / done / failed
    """
    job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _format_job(job)


@router.get("/jobs")
def get_jobs_by_homework(
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    step: Optional[str] = Query(None, description="Filter by step: pdf_to_markdown / run_analysis / generate_practice"),
    db: Session = Depends(get_db),
):
    """List pipeline jobs, optionally filtered by homework_id and/or step.

    Returns most recent jobs first.
    """
    q = db.query(PipelineJob)
    if homework_id:
        q = q.filter(PipelineJob.homework_id == homework_id)
    if step:
        q = q.filter(PipelineJob.step == step)
    jobs = q.order_by(PipelineJob.created_at.desc()).all()
    return [_format_job(j) for j in jobs]
