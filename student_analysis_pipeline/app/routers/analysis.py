import json
import re
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    TutorHomework, StudentConversation, StudentAnalysis,
    StudentQuestionEvaluation, StudentTopicPerformance, TutorErrorType,
)
from app.services.llm import ask
from app.services.prompt import get_prompt

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ── Default error types (used when user hasn't defined custom ones) ──

DEFAULT_ERROR_TYPES = [
    {"name": "Conceptual", "description": "Wrong formula, misunderstood question, fundamental misunderstanding."},
    {"name": "Procedural", "description": "Correct formula but wrong order, skipped steps, algebraic errors."},
    {"name": "Computational", "description": "Arithmetic errors, sign errors."},
    {"name": "Incomplete", "description": "Stopped working, conversation ended mid-problem."},
]


# ── Helpers ──

def _parse_questions_from_markdown(markdown: str) -> dict[str, str]:
    """Extract individual questions from homework markdown.

    Handles multiple formats:
      - **1.** question text       (bold numbered, at start of line)
      - 1. question text           (plain numbered, at start of line)

    Returns {question_number: question_text}.
    """
    questions = {}

    # Try **N.** pattern first (must be at start of line)
    pattern = r'^\*\*(\d+)\.\*\*\s+(.*?)(?=\n\*\*\d+\.\*\*|\Z)'
    for match in re.finditer(pattern, markdown, re.DOTALL | re.MULTILINE):
        questions[match.group(1)] = match.group(2).strip()

    if questions:
        return questions

    # Try plain "N." at start of line (e.g. "1. Find f'(x)...")
    pattern = r'^(\d+)\.\s+(.*?)(?=\n\d+\.\s|\n---|\Z)'
    for match in re.finditer(pattern, markdown, re.DOTALL | re.MULTILINE):
        text = match.group(2).strip()
        # Remove [Answer box] / [Answer space] markers
        text = re.sub(r'\[Answer\s+(?:box|space)\]', '', text).strip()
        questions[match.group(1)] = text

    return questions


def _parse_answers_from_markdown(markdown: str) -> dict[str, str]:
    """Extract individual answers from answer-key markdown.

    Tries common patterns: **N.** or ### Problem N
    Returns {question_number: answer_text}.
    """
    answers = {}

    # Try **N.** pattern first
    pattern = r'\*\*(\d+)\.\*\*\s+(.*?)(?=\n\n\*\*\d+\.\*\*|\Z)'
    for match in re.finditer(pattern, markdown, re.DOTALL):
        answers[match.group(1)] = match.group(2).strip()

    if answers:
        return answers

    # Try ### Problem N pattern
    pattern = r'###\s*Problem\s*(\d+)\n(.*?)(?=\n###\s*Problem|\Z)'
    for match in re.finditer(pattern, markdown, re.DOTALL):
        answers[match.group(1)] = match.group(2).strip()

    return answers


def _build_error_type_prompt_section(error_types: list[dict]) -> str:
    """Build the error type section for the evaluation prompt."""
    lines = []
    for et in error_types:
        lines.append(f"- **{et['name']}**: {et['description']}")
    return "\n".join(lines)


def _build_eval_prompt(base_prompt: str, error_types: list[dict]) -> str:
    """Inject user-defined error types into the evaluation system prompt."""
    error_type_names = [et["name"] for et in error_types]
    names_str = ", ".join(f'"{n}"' for n in error_type_names)

    error_section = _build_error_type_prompt_section(error_types)

    return (
        f"{base_prompt}\n\n"
        f"### Error Type Classification (IMPORTANT)\n"
        f"When Attempted=True AND Solved=False, you MUST classify the error using "
        f"the most specific type that applies. Carefully analyze the student's work "
        f"and reasoning in the chat to determine the root cause of the error.\n\n"
        f"Available error types:\n"
        f"{error_section}\n\n"
        f"Classification rules:\n"
        f"- Analyze the student's actual work and reasoning, not just whether they finished.\n"
        f"- If the student showed work but used a wrong approach, classify by the type of mistake.\n"
        f"- If Attempted=False, set error_type to \"Not Attempted\".\n"
        f"- If Solved=True, set error_type to null.\n\n"
        f"error_type must be one of: {names_str}, \"Not Attempted\", or null (only when solved)."
    )


def _evaluate_all_questions(
    questions: dict[str, str],
    answers: dict[str, str],
    chat_history: str,
    system_prompt: str,
) -> dict[str, dict]:
    """Call LLM once to evaluate all questions for a student."""
    # Build the questions + solutions block
    qa_block = ""
    for q_num in sorted(questions.keys(), key=int):
        solution = answers.get(q_num, "No reference solution available.")
        qa_block += (
            f"**Question {q_num}:**\n{questions[q_num]}\n"
            f"**Reference Solution:**\n{solution}\n\n"
        )

    user_prompt = (
        f"{qa_block}"
        f"**Chat History:**\n{chat_history}"
    )
    response = ask(
        prompt=user_prompt,
        system=system_prompt,
        response_format={"type": "json_object"},
    )
    return json.loads(response)


def _aggregate_metrics(
    evaluations: dict[str, dict],
    topic_mapping: dict[str, list[str]],
) -> dict:
    """Aggregate per-question evaluations into summary + topic performance."""
    total_questions = 0
    total_attempted = 0
    total_solved = 0
    total_errors = 0

    # topic -> stats
    topic_stats: dict[str, dict] = {}

    for q_num, eval_result in evaluations.items():
        topics = topic_mapping.get(q_num, [])
        is_visual = any("Visual/Image-based" in t for t in topics)
        if is_visual:
            continue

        total_questions += 1

        if eval_result["attempted"]:
            total_attempted += 1
            if eval_result["solved"]:
                total_solved += 1
            else:
                total_errors += 1

        for topic in topics:
            if topic not in topic_stats:
                topic_stats[topic] = {"total": 0, "attempted": 0, "solved": 0, "questions": []}

            topic_stats[topic]["total"] += 1
            topic_stats[topic]["questions"].append({
                "q_num": q_num,
                "attempted": eval_result["attempted"],
                "solved": eval_result["solved"],
                "error_type": eval_result.get("error_type"),
            })
            if eval_result["attempted"]:
                topic_stats[topic]["attempted"] += 1
            if eval_result["solved"]:
                topic_stats[topic]["solved"] += 1

    # Build topic performance list
    topic_performances = []
    for topic, stats in topic_stats.items():
        details_parts = []
        for q in stats["questions"]:
            status = "Solved" if q["solved"] else ("Attempted" if q["attempted"] else "Not Attempted")
            if q["error_type"]:
                status += f" ({q['error_type']})"
            details_parts.append(f"Q{q['q_num']}: {status}")

        if stats["attempted"] == stats["total"] and stats["solved"] == stats["total"]:
            mastery = "mastered"
            reason = "All questions attempted and solved correctly"
        else:
            mastery = "needs_practice"
            reasons = []
            if stats["attempted"] < stats["total"]:
                reasons.append(f"{stats['total'] - stats['attempted']} question(s) not attempted")
            if stats["solved"] < stats["attempted"]:
                reasons.append(f"{stats['attempted'] - stats['solved']} question(s) attempted but not solved")
            reason = "; ".join(reasons)

        topic_performances.append({
            "topic_name": topic,
            "status": mastery,
            "question_tested": stats["total"],
            "questions_solved": stats["solved"],
            "details": "; ".join(details_parts),
            "reason": reason,
        })

    return {
        "total_question": total_questions,
        "total_attempted": total_attempted,
        "total_solved": total_solved,
        "total_errors": total_errors,
        "topic_performances": topic_performances,
    }


# ── Error Type Endpoints ──

@router.get("/error-types")
def get_error_types(
    group_id: str = Query(..., description="Group ID"),
    db: Session = Depends(get_db),
):
    """Get error types for a group. Returns defaults if none defined."""
    row = db.query(TutorErrorType).filter(TutorErrorType.group_id == group_id).first()
    return {
        "group_id": group_id,
        "source": "custom" if row else "default",
        "error_types": row.data if row else DEFAULT_ERROR_TYPES,
    }


@router.put("/error-types")
def set_error_types(
    group_id: str = Query(..., description="Group ID"),
    error_types: list = Body(..., example=[
        {"name": "Conceptual", "description": "Wrong formula, misunderstood question"},
        {"name": "Procedural", "description": "Correct formula but wrong execution"},
    ]),
    db: Session = Depends(get_db),
):
    """Set custom error types for a group. Each item needs 'name' and 'description'."""
    for et in error_types:
        if "name" not in et or "description" not in et:
            raise HTTPException(status_code=400, detail="Each error type must have 'name' and 'description'")

    row = db.query(TutorErrorType).filter(TutorErrorType.group_id == group_id).first()
    if not row:
        row = TutorErrorType(group_id=group_id)
        db.add(row)
    row.data = error_types
    db.commit()
    db.refresh(row)

    return {"group_id": group_id, "error_types": row.data}


@router.delete("/error-types")
def delete_error_types(
    group_id: str = Query(..., description="Group ID"),
    db: Session = Depends(get_db),
):
    """Delete custom error types for a group (reverts to defaults)."""
    deleted = db.query(TutorErrorType).filter(TutorErrorType.group_id == group_id).delete()
    db.commit()
    return {"deleted": deleted > 0, "message": "Reverted to default error types"}


# ── Analysis Endpoints ──

@router.post("/run")
def run_analysis(
    homework_id: str = Query(..., description="Homework ID to analyze"),
    student_id: Optional[str] = Query(None, description="Analyze a single student. Omit to analyze all."),
    db: Session = Depends(get_db),
):
    """Pipeline 3 – Evaluate student performance per question, aggregate by topic.

    For each student with a conversation for this homework:
    1. Parse questions and answers from homework markdown.
    2. LLM evaluates each question (attempted, solved, error_type).
    3. Aggregate into summary stats and topic performance.
    4. Save to student_analysis, student_question_evaluations, student_topic_performance.
    """

    # ── 1. Get homework data ──
    hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail=f"Homework {homework_id} not found")
    if not hw.question_data:
        raise HTTPException(status_code=400, detail="Homework has no question data. Upload questions first.")
    if not hw.topic_mapping:
        raise HTTPException(status_code=400, detail="Homework has no topic mapping. Upload questions first.")

    # Auto-generate answers if not uploaded
    if not hw.answer_data:
        gen_prompt = get_prompt(db, "generate_answers", group_id=hw.group_id)
        hw.answer_data = ask(
            prompt=hw.question_data,
            system=gen_prompt,
        )
        hw.answer_source = "ai_generated"
        hw.answer_uploaded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(hw)

    all_questions = _parse_questions_from_markdown(hw.question_data)
    answers = _parse_answers_from_markdown(hw.answer_data)
    topic_mapping = hw.topic_mapping  # {q_num_str: [topics]}

    if not all_questions:
        raise HTTPException(status_code=400, detail="Could not parse questions from homework markdown")

    # Filter out visual/image-based questions — LLM can't evaluate them
    questions = {}
    skipped_visual = []
    for q_num, q_text in all_questions.items():
        topics = topic_mapping.get(q_num, [])
        if any("Visual/Image-based" in t for t in topics):
            skipped_visual.append(q_num)
        else:
            questions[q_num] = q_text

    # ── 2. Get student conversations ──
    conv_query = db.query(StudentConversation).filter(
        StudentConversation.homework_id == homework_id,
    )
    if student_id:
        conv_query = conv_query.filter(StudentConversation.student_id == student_id)

    conversations = conv_query.all()
    if not conversations:
        raise HTTPException(status_code=404, detail="No student conversations found for this homework")

    # ── 3. Build evaluation prompt with error types ──
    base_prompt = get_prompt(db, "evaluate_question", group_id=hw.group_id)

    # Load user-defined error types for this group, or use defaults
    error_type_row = db.query(TutorErrorType).filter(TutorErrorType.group_id == hw.group_id).first()
    error_types = error_type_row.data if error_type_row else DEFAULT_ERROR_TYPES

    eval_prompt = _build_eval_prompt(base_prompt, error_types)

    # ── 4. Process each student ──
    now = datetime.now(timezone.utc)
    results = []

    for conv in conversations:
        chat_history = conv.conversation_markdown or ""

        # Evaluate all questions in a single LLM call
        evaluations = _evaluate_all_questions(questions, answers, chat_history, eval_prompt)

        # Aggregate metrics
        metrics = _aggregate_metrics(evaluations, topic_mapping)

        # ── 5. Save to DB (upsert) ──
        analysis = (
            db.query(StudentAnalysis)
            .filter(
                StudentAnalysis.student_id == conv.student_id,
                StudentAnalysis.homework_id == homework_id,
            )
            .first()
        )
        if not analysis:
            analysis = StudentAnalysis(
                student_id=conv.student_id,
                student_email=conv.student_email,
                homework_id=homework_id,
            )
            db.add(analysis)

        analysis.total_question = metrics["total_question"]
        analysis.total_attempted = metrics["total_attempted"]
        analysis.total_solved = metrics["total_solved"]
        analysis.total_errors = metrics["total_errors"]
        analysis.created_at = now

        db.flush()  # get analysis.id for child rows

        # Clear old evaluations and topic performances for this analysis
        db.query(StudentQuestionEvaluation).filter(
            StudentQuestionEvaluation.student_analysis_id == analysis.id
        ).delete()
        db.query(StudentTopicPerformance).filter(
            StudentTopicPerformance.student_analysis_id == analysis.id
        ).delete()

        # Insert question evaluations
        for q_num, eval_result in evaluations.items():
            attempted = eval_result.get("attempted", False)
            solved = eval_result.get("solved", False)
            error_type = eval_result.get("error_type")

            # Ensure unattempted questions always show "Not Attempted"
            if not attempted:
                error_type = "Not Attempted"

            db.add(StudentQuestionEvaluation(
                student_analysis_id=analysis.id,
                question_number=int(q_num),
                attempted=attempted,
                solved=solved,
                error_type=error_type,
            ))

        # Insert topic performances
        for tp in metrics["topic_performances"]:
            db.add(StudentTopicPerformance(
                student_analysis_id=analysis.id,
                topic_name=tp["topic_name"],
                status=tp["status"],
                question_tested=tp["question_tested"],
                questions_solved=tp["questions_solved"],
                details=tp["details"],
                reason=tp["reason"],
            ))

        results.append({
            "student_id": conv.student_id,
            "student_email": conv.student_email,
            "total_question": metrics["total_question"],
            "total_attempted": metrics["total_attempted"],
            "total_solved": metrics["total_solved"],
            "total_errors": metrics["total_errors"],
            "topics_mastered": sum(1 for t in metrics["topic_performances"] if t["status"] == "mastered"),
            "topics_needs_practice": sum(1 for t in metrics["topic_performances"] if t["status"] == "needs_practice"),
        })

    db.commit()

    return {
        "status": "success",
        "homework_id": homework_id,
        "students_analyzed": len(results),
        "questions_evaluated": len(questions),
        "questions_skipped_visual": skipped_visual,
        "error_types_used": [et["name"] for et in error_types],
        "students": results,
    }


@router.get("/")
def get_analyses(
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    db: Session = Depends(get_db),
):
    """List student analyses with question evaluations and topic performances."""
    q = db.query(StudentAnalysis)
    if homework_id is not None:
        q = q.filter(StudentAnalysis.homework_id == homework_id)
    if student_id is not None:
        q = q.filter(StudentAnalysis.student_id == student_id)

    results = []
    for sa in q.all():
        results.append({
            "id": sa.id,
            "student_id": sa.student_id,
            "student_email": sa.student_email,
            "homework_id": sa.homework_id,
            "total_question": sa.total_question,
            "total_attempted": sa.total_attempted,
            "total_solved": sa.total_solved,
            "total_errors": sa.total_errors,
            "created_at": sa.created_at,
            "question_evaluations": [
                {
                    "question_number": qe.question_number,
                    "attempted": qe.attempted,
                    "solved": qe.solved,
                    "error_type": qe.error_type,
                }
                for qe in sa.question_evaluations
            ],
            "topic_performances": [
                {
                    "topic_name": tp.topic_name,
                    "status": tp.status,
                    "question_tested": tp.question_tested,
                    "questions_solved": tp.questions_solved,
                    "details": tp.details,
                    "reason": tp.reason,
                }
                for tp in sa.topic_performances
            ],
        })
    return results
