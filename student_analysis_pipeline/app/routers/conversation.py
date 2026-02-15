import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TutorHomework, StudentConversation
from app.services.openwebui_db import (
    OwuiSessionLocal, OwuiUser, OwuiGroup, OwuiChat,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


def _chats_to_markdown(chats: list[dict], user_email: str) -> str:
    """Convert a list of raw chat dicts into a single markdown string.

    Merges messages from all conversations, sorts by timestamp,
    and formats as clean markdown (same logic as export_conversation.py).
    """
    messages = {}
    for chat_data in chats:
        chat_blob = chat_data.get("chat", {})
        if isinstance(chat_blob, str):
            try:
                chat_blob = json.loads(chat_blob)
            except (json.JSONDecodeError, TypeError):
                chat_blob = {}
        conv_messages = chat_blob.get("history", {}).get("messages", {})
        messages.update(conv_messages)

    if not messages:
        return ""

    # Flatten & sort by timestamp
    message_list = []
    for msg in messages.values():
        message_list.append({
            "role": msg.get("role", "unknown"),
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp", 0),
        })
    message_list.sort(key=lambda x: x["timestamp"])

    user_count = sum(1 for m in message_list if m["role"] == "user")
    assistant_count = sum(1 for m in message_list if m["role"] == "assistant")

    # Build markdown
    lines = [
        "# Student Conversation\n",
        f"**Student:** {user_email}",
        f"**Total Messages:** {len(message_list)} ({user_count} student, {assistant_count} assistant)\n",
        "---\n",
    ]
    for msg in message_list:
        role = msg["role"].upper()
        content = msg["content"]
        lines.append(f"**{role}:** {content}\n")

    return "\n".join(lines)


@router.post("/export")
def export_conversations(
    homework_id: str = Query(..., description="Homework ID to export conversations for"),
    db: Session = Depends(get_db),
):
    """Pipeline 2 – Export conversation history from OpenWebUI DB.

    1. Looks up the homework to get group_id and model_id.
    2. Queries OpenWebUI DB for the group's users and their chats with that model.
    3. Converts each student's chats to markdown.
    4. Saves the markdown into student_conversation rows in the pipeline DB.
    """

    # ── 1. Get homework ──
    hw = db.query(TutorHomework).filter(TutorHomework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail=f"Homework {homework_id} not found")
    if not hw.group_id or not hw.model_id:
        raise HTTPException(status_code=400, detail="Homework is missing group_id or model_id")

    # ── 2. Query OpenWebUI DB ──
    owui = OwuiSessionLocal()
    try:
        # Find group
        group = owui.query(OwuiGroup).filter(OwuiGroup.id == hw.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail=f"Group '{hw.group_id}' not found in OpenWebUI DB")

        # Get user IDs from group
        user_ids = group.user_ids
        if isinstance(user_ids, str):
            user_ids = json.loads(user_ids)
        if not user_ids:
            return {"status": "warning", "message": "Group has no members", "students": []}

        # Query chats for these users (non-archived)
        candidates = (
            owui.query(OwuiChat, OwuiUser)
            .join(OwuiUser, OwuiChat.user_id == OwuiUser.id)
            .filter(
                OwuiChat.user_id.in_(user_ids),
                OwuiChat.archived == False,
            )
            .all()
        )

        # Filter chats by model_id
        user_chats: dict[str, list[dict]] = {}  # user_id -> list of chat dicts
        user_info: dict[str, OwuiUser] = {}     # user_id -> user object

        for chat, user in candidates:
            # Check meta.models for model match
            meta = chat.meta
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            if meta is None:
                meta = {}

            chat_models = meta.get("models", [])

            # Fallback: check chat blob for models
            if not chat_models and chat.chat:
                chat_blob = chat.chat
                if isinstance(chat_blob, str):
                    try:
                        chat_blob = json.loads(chat_blob)
                    except (json.JSONDecodeError, TypeError):
                        chat_blob = {}
                if isinstance(chat_blob, dict):
                    chat_models = chat_blob.get("models", [])

            if hw.model_id in chat_models:
                chat_data = {
                    "id": chat.id,
                    "title": chat.title,
                    "chat": chat.chat,
                    "created_at": chat.created_at,
                }
                if user.id not in user_chats:
                    user_chats[user.id] = []
                    user_info[user.id] = user
                user_chats[user.id].append(chat_data)
    finally:
        owui.close()

    # ── 3 & 4. Convert to markdown and save ──
    now = datetime.now(timezone.utc)
    results = []

    for uid, chats in user_chats.items():
        user = user_info[uid]
        email = user.email or f"unknown_{uid}"
        markdown = _chats_to_markdown(chats, email)

        if not markdown:
            continue

        # Upsert: find existing conversation row for this student + homework
        conv = (
            db.query(StudentConversation)
            .filter(
                StudentConversation.student_id == uid,
                StudentConversation.homework_id == homework_id,
            )
            .first()
        )
        if not conv:
            conv = StudentConversation(
                student_id=uid,
                student_email=email,
                homework_id=homework_id,
            )
            db.add(conv)

        conv.conversation_markdown = markdown
        conv.exported_at = now

        results.append({
            "student_id": uid,
            "student_email": email,
            "conversation_count": len(chats),
            "message_count": markdown.count("**USER:**") + markdown.count("**ASSISTANT:**"),
        })

    db.commit()

    return {
        "status": "success",
        "homework_id": homework_id,
        "group_id": hw.group_id,
        "model_id": hw.model_id,
        "total_students": len(results),
        "students": results,
    }


@router.get("/")
def get_conversations(
    homework_id: Optional[str] = Query(None, description="Filter by homework ID"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    db: Session = Depends(get_db),
):
    """List exported conversations."""
    q = db.query(StudentConversation)
    if homework_id is not None:
        q = q.filter(StudentConversation.homework_id == homework_id)
    if student_id is not None:
        q = q.filter(StudentConversation.student_id == student_id)

    results = []
    for sc in q.all():
        results.append({
            "id": sc.id,
            "student_id": sc.student_id,
            "student_email": sc.student_email,
            "homework_id": sc.homework_id,
            "exported_at": sc.exported_at,
            "conversation_markdown": sc.conversation_markdown,
        })
    return results
