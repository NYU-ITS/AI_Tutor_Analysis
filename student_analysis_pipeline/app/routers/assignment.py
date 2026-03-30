from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    StudentPracticeAssignment,
    TutorPracticeProblem,
    StudentAnalysis,
    StudentTopicPerformance,
)

router = APIRouter(prefix="/assignment", tags=["assignment"])


@router.post("/assign")
def assign_practice_to_students(
    practice_id: str = Query(..., description="Practice problem set ID to assign"),
    db: Session = Depends(get_db),
):
    """Assign practice problems to each student based on their weak topics.

    For each student with an analysis for the same homework:
    - Computes their weak topics from StudentTopicPerformance (status == needs_practice)
    - Filters practice problem_items to those whose topics intersect the student's weak topics
    - Fallback: if no problems match (student mastered all topics), assigns all items
    - Upserts the assignment — safe to call multiple times

    Returns a summary with per-student assigned counts.
    """
    practice = db.query(TutorPracticeProblem).filter(TutorPracticeProblem.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail=f"Practice problem set {practice_id} not found")
    if not practice.problem_items:
        raise HTTPException(
            status_code=400,
            detail="This practice set has no structured problem_items. Re-generate it to get topic-tagged items.",
        )

    analyses = (
        db.query(StudentAnalysis)
        .filter(StudentAnalysis.homework_id == practice.homework_id)
        .all()
    )
    if not analyses:
        raise HTTPException(
            status_code=400,
            detail="No student analyses found for this homework. Run analysis first.",
        )

    student_summaries = []

    for analysis in analyses:
        weak_topics = {
            tp.topic_name
            for tp in db.query(StudentTopicPerformance)
            .filter(
                StudentTopicPerformance.student_analysis_id == analysis.id,
                StudentTopicPerformance.status == "needs_practice",
            )
            .all()
        }

        matched = [
            item for item in practice.problem_items
            if set(item.get("topics", [])) & weak_topics
        ]
        # Fallback: student mastered all topics → assign all problems
        assigned_items = matched if matched else practice.problem_items

        # Upsert: delete existing assignment for this student + practice, then re-insert
        db.query(StudentPracticeAssignment).filter(
            StudentPracticeAssignment.student_id == analysis.student_id,
            StudentPracticeAssignment.practice_problem_id == practice_id,
        ).delete()

        assignment = StudentPracticeAssignment(
            student_id=analysis.student_id,
            student_email=analysis.student_email,
            homework_id=practice.homework_id,
            practice_problem_id=practice_id,
            assigned_items=assigned_items,
        )
        db.add(assignment)

        student_summaries.append({
            "student_id": analysis.student_id,
            "student_email": analysis.student_email,
            "weak_topics_count": len(weak_topics),
            "assigned_count": len(assigned_items),
            "fallback_used": len(matched) == 0,
        })

    db.commit()

    return {
        "practice_id": practice_id,
        "homework_id": practice.homework_id,
        "assigned_count": len(student_summaries),
        "students": student_summaries,
    }


@router.get("/")
def get_assignments(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    practice_problem_id: Optional[str] = Query(None, description="Filter by practice problem set ID"),
    topic: Optional[str] = Query(None, description="Filter by topic name in assigned items"),
    db: Session = Depends(get_db),
):
    """List practice assignments with optional filters. Returns most recent first.

    The topic filter matches assignments that have at least one item covering that topic.
    """
    q = db.query(StudentPracticeAssignment)
    if student_id is not None:
        q = q.filter(StudentPracticeAssignment.student_id == student_id)
    if homework_id is not None:
        q = q.filter(StudentPracticeAssignment.homework_id == homework_id)
    if practice_problem_id is not None:
        q = q.filter(StudentPracticeAssignment.practice_problem_id == practice_problem_id)

    results = []
    for a in q.order_by(StudentPracticeAssignment.created_at.desc()).all():
        assigned_items = a.assigned_items if a.assigned_items else []

        # Apply topic filter if specified
        if topic is not None:
            filtered_items = [
                item for item in assigned_items
                if topic in item.get("topics", [])
            ]
            # Skip this assignment if no items match the topic
            if not filtered_items:
                continue
            assigned_items = filtered_items

        results.append({
            "id": a.id,
            "student_id": a.student_id,
            "student_email": a.student_email,
            "homework_id": a.homework_id,
            "practice_problem_id": a.practice_problem_id,
            "assigned_items": assigned_items,
            "assigned_count": len(assigned_items),
            "created_at": a.created_at,
        })
    return results
