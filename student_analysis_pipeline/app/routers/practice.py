import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import (
    PipelineJob, TutorHomework, StudentAnalysis, StudentTopicPerformance,
    TutorPracticeProblem,
)
from app.services.llm import ask
from app.services.prompt import get_prompt

router = APIRouter(prefix="/practice", tags=["practice"])


# ── Request Models ──

class UpdatePracticeProblemRequest(BaseModel):
    problem_items: Optional[list] = None
    problem_data: Optional[str] = None
    status: Optional[str] = None  # approved / rejected / pending


# ── Helpers ──

def _aggregate_class_weakness(
    db: Session,
    homework_id: str,
    weakness_threshold: float = 0.5,
) -> list[dict]:
    """Aggregate topic performance across all students for a homework.

    Returns topics where the proportion of students with needs_practice
    status meets or exceeds the threshold, sorted by weakness_rate descending.
    """
    analyses = (
        db.query(StudentAnalysis)
        .filter(StudentAnalysis.homework_id == homework_id)
        .all()
    )
    if not analyses:
        return []

    analysis_ids = [a.id for a in analyses]

    topic_rows = (
        db.query(StudentTopicPerformance)
        .filter(StudentTopicPerformance.student_analysis_id.in_(analysis_ids))
        .all()
    )

    # Aggregate by topic_name
    topic_agg: dict[str, dict] = {}
    for tp in topic_rows:
        if tp.topic_name not in topic_agg:
            topic_agg[tp.topic_name] = {"total": 0, "needs_practice": 0, "mastered": 0}

        bucket = topic_agg[tp.topic_name]
        bucket["total"] += 1
        if tp.status == "needs_practice":
            bucket["needs_practice"] += 1
        elif tp.status == "mastered":
            bucket["mastered"] += 1

    # Filter to weak topics
    weak_topics = []
    for topic_name, stats in topic_agg.items():
        weakness_rate = stats["needs_practice"] / stats["total"] if stats["total"] > 0 else 0
        if weakness_rate >= weakness_threshold:
            weak_topics.append({
                "topic_name": topic_name,
                "students_tested": stats["total"],
                "students_weak": stats["needs_practice"],
                "students_mastered": stats["mastered"],
                "weakness_rate": round(weakness_rate, 3),
            })

    weak_topics.sort(key=lambda x: x["weakness_rate"], reverse=True)
    return weak_topics


# ── Endpoints ──

@router.get("/class-weakness")
def get_class_weakness(
    homework_id: str = Query(..., description="Homework ID to analyze"),
    weakness_threshold: float = Query(0.5, ge=0.0, le=1.0, description="Min weakness proportion"),
    db: Session = Depends(get_db),
):
    """Preview class-level weakness aggregation without generating problems."""
    hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail=f"Homework {homework_id} not found")

    weak_topics = _aggregate_class_weakness(db, homework_id, weakness_threshold)

    analyses = (
        db.query(StudentAnalysis)
        .filter(StudentAnalysis.homework_id == homework_id)
        .all()
    )

    return {
        "homework_id": homework_id,
        "group_id": hw.group_id,
        "total_students_analyzed": len(analyses),
        "weakness_threshold": weakness_threshold,
        "weak_topics_count": len(weak_topics),
        "weak_topics": weak_topics,
    }


def _run_generate_practice(
    job_id: str, homework_id: str, user_id: Optional[str], weakness_threshold: float
) -> None:
    """Runs in the background. Opens its own DB session independent of the request."""
    db = SessionLocal()
    try:
        job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        job.status = "running"
        db.commit()

        hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
        weak_topics = _aggregate_class_weakness(db, homework_id, weakness_threshold)

        system_prompt = get_prompt(db, "generate_practice_problems", group_id=hw.group_id)

        weakness_block = ""
        for wt in weak_topics:
            weakness_block += (
                f"- **{wt['topic_name']}**: {wt['students_weak']}/{wt['students_tested']} students "
                f"need practice ({wt['weakness_rate']*100:.0f}% weakness rate)\n"
            )

        user_prompt = (
            f"## Original Homework Questions\n\n"
            f"{hw.question_data}\n\n"
            f"## Topic Mapping\n\n"
            f"{json.dumps(hw.topic_mapping, indent=2)}\n\n"
            f"## Class Weakness Analysis\n\n"
            f"The following topics were identified as weak across the class:\n\n"
            f"{weakness_block}\n"
            f"Generate practice problems that target these weak topics. "
            f"Focus more problems on topics with higher weakness rates."
        )

        raw = ask(prompt=user_prompt, system=system_prompt, response_format={"type": "json_object"})
        parsed = json.loads(raw)
        problem_items = parsed.get("problems", [])
        problem_markdown = parsed.get("markdown", "")

        existing_count = (
            db.query(TutorPracticeProblem)
            .filter(TutorPracticeProblem.homework_id == homework_id)
            .count()
        )

        practice = TutorPracticeProblem(
            user_id=user_id,
            homework_id=homework_id,
            group_id=hw.group_id,
            source="ai_generated",
            status="pending",
            version_number=existing_count + 1,
            problem_data=problem_markdown,
            problem_items=problem_items,
            weakness_summary=weak_topics,
        )
        db.add(practice)
        db.commit()

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


@router.post("/generate")
def generate_practice_problems(
    background_tasks: BackgroundTasks,
    homework_id: str = Query(..., description="Homework ID to generate practice problems for"),
    user_id: Optional[str] = Query(None, description="User ID of the instructor triggering generation"),
    weakness_threshold: float = Query(0.5, ge=0.0, le=1.0, description="Min proportion of students weak on a topic to include it"),
    db: Session = Depends(get_db),
):
    """Pipeline 4 -- Generate practice problems in the background.

    Returns a job_id immediately. Poll GET /pipeline/status/{job_id} for progress.
    """
    hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail=f"Homework {homework_id} not found")
    if not hw.question_data:
        raise HTTPException(status_code=400, detail="Homework has no question data. Upload questions first.")
    if not hw.topic_mapping:
        raise HTTPException(status_code=400, detail="Homework has no topic mapping. Upload questions first.")

    # Validate upfront — no point queuing if there's nothing to work with
    weak_topics = _aggregate_class_weakness(db, homework_id, weakness_threshold)
    if not weak_topics:
        raise HTTPException(
            status_code=400,
            detail="No weak topics found. Either no analyses exist or all topics are mastered.",
        )

    job = PipelineJob(step="generate_practice", homework_id=homework_id)
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_generate_practice, job.id, homework_id, user_id, weakness_threshold)

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Practice generation started. Poll GET /pipeline/status/{job_id} for progress.",
    }


@router.get("/")
def get_practice_problems(
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    status: Optional[str] = Query(None, description="Filter by status: pending / approved / rejected"),
    db: Session = Depends(get_db),
):
    """List practice problem sets with optional filters."""
    q = db.query(TutorPracticeProblem)
    if homework_id is not None:
        q = q.filter(TutorPracticeProblem.homework_id == homework_id)
    if group_id is not None:
        q = q.filter(TutorPracticeProblem.group_id == group_id)
    if status is not None:
        q = q.filter(TutorPracticeProblem.status == status)

    q = q.order_by(TutorPracticeProblem.created_at.desc())

    results = []
    for pp in q.all():
        results.append({
            "id": pp.id,
            "user_id": pp.user_id,
            "homework_id": pp.homework_id,
            "group_id": pp.group_id,
            "source": pp.source,
            "status": pp.status,
            "version_number": pp.version_number,
            "problem_data": pp.problem_data,
            "problem_items": pp.problem_items,
            "weakness_summary": pp.weakness_summary,
            "created_at": pp.created_at,
        })
    return results


@router.patch("/{practice_id}/status")
def update_practice_status(
    practice_id: str,
    status: str = Query(..., pattern="^(approved|rejected|pending)$", description="New status"),
    db: Session = Depends(get_db),
):
    """Update the approval status of a practice problem set."""
    practice = db.query(TutorPracticeProblem).filter(TutorPracticeProblem.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail=f"Practice problem {practice_id} not found")

    practice.status = status
    db.commit()
    db.refresh(practice)

    return {
        "id": practice.id,
        "status": practice.status,
        "homework_id": practice.homework_id,
        "version_number": practice.version_number,
    }


@router.patch("/{practice_id}")
def update_practice_problems(
    practice_id: str,
    request: UpdatePracticeProblemRequest,
    db: Session = Depends(get_db),
):
    """Update the problem_items, problem_data, and/or status for an existing practice problem set.

    This allows instructors to edit generated practice problems and persist the changes.
    All fields are optional—update only what needs to change.
    """
    practice = db.query(TutorPracticeProblem).filter(TutorPracticeProblem.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail=f"Practice problem {practice_id} not found")

    if request.problem_items is not None:
        practice.problem_items = request.problem_items
    if request.problem_data is not None:
        practice.problem_data = request.problem_data
    if request.status is not None:
        if request.status not in ("approved", "rejected", "pending"):
            raise HTTPException(status_code=400, detail="Status must be one of: approved, rejected, pending")
        practice.status = request.status

    db.commit()
    db.refresh(practice)

    return {
        "id": practice.id,
        "user_id": practice.user_id,
        "homework_id": practice.homework_id,
        "group_id": practice.group_id,
        "source": practice.source,
        "status": practice.status,
        "version_number": practice.version_number,
        "problem_data": practice.problem_data,
        "problem_items": practice.problem_items,
        "weakness_summary": practice.weakness_summary,
        "created_at": practice.created_at,
    }
