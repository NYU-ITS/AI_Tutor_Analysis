
import os
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models import Base, User, Group, Chat

from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Environment Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL not set in environment or .env file")
    # You can set a safe default here for local dev if needed, 
    # but never include a password in the code.

# Database Setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="OpenWebUI Connector API")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health_check():
    return {"status": "ok", "service": "connector-api"}

@app.get("/export", response_model=Dict[str, Any])
def export_conversations(
    group_id: str = Query(..., description="ID of the Group"),
    model_id: str = Query(..., description="ID of the Model"),
    start_date: Optional[int] = Query(None, description="Start timestamp (Unix epoch)"),
    end_date: Optional[int] = Query(None, description="End timestamp (Unix epoch)")
):
    """
    Exports conversation history for a specific Group and Model.
    Saves files to disk and returns metadata.
    """
    session = SessionLocal()
    try:
        logger.info(f"Export Request: Group ID='{group_id}', Model ID='{model_id}'")

        # 1. Get Group
        group_obj = session.query(Group).filter(Group.id == group_id).first()
        if not group_obj:
            raise HTTPException(status_code=404, detail=f"Group with ID '{group_id}' not found")

        # 2. Get Users in Group
        group_user_ids = []
        if group_obj.user_ids:
             if isinstance(group_obj.user_ids, str):
                 group_user_ids = json.loads(group_obj.user_ids)
             else:
                 group_user_ids = group_obj.user_ids 
        
        if not group_user_ids:
            return {"status": "warning", "message": "Group has no members", "files_saved": []}

        # 3. Query Chats + User (for filename generation)
        # We assume email/name are needed for the filename convention
        query = session.query(Chat, User).join(User, Chat.user_id == User.id).filter(
            Chat.user_id.in_(group_user_ids),
            Chat.archived == False
        )

        # 3.1 Time Filters
        if start_date:
            query = query.filter(Chat.created_at >= start_date)
        if end_date:
            query = query.filter(Chat.created_at <= end_date)

        candidates = query.all()
        matches = []

        # Prepare Output Directory
        # Sanitize folder name
        safe_group = "".join([c if c.isalnum() else "_" for c in group_id])
        safe_model = "".join([c if c.isalnum() else "_" for c in model_id])
        output_dir = os.path.join("extracted_data", f"{safe_group}__{safe_model}")
        os.makedirs(output_dir, exist_ok=True)

        saved_files = []

        # 4. Filter by Model & Group by User
        user_chats_map = {} # email -> list of chat_data
        user_email_map = {} # email -> user_object (for prefix)

        for chat, user in candidates:
            # Parse 'meta' safely
            meta = chat.meta
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except: meta = {}
            if meta is None: meta = {}
            
            chat_models = meta.get('models', [])
            
            # Fallback to chat blob
            if not chat_models and chat.chat:
                c_content = chat.chat
                if isinstance(c_content, str):
                    try: c_content = json.loads(c_content)
                    except: c_content = {}
                if isinstance(c_content, dict):
                    chat_models = c_content.get('models', [])
            
            # Check for exact match
            if model_id in chat_models:
                # --- MATCH FOUND ---
                chat_data = {
                    "id": chat.id,
                    "user_id": chat.user_id,
                    "title": chat.title,
                    "chat": chat.chat,
                    "meta": chat.meta,
                    "created_at": chat.created_at,
                    "updated_at": chat.updated_at,
                    "share_id": chat.share_id,
                    "archived": chat.archived,
                    "pinned": chat.pinned
                }
                
                email = user.email if user.email else f"unknown_{user.id}"
                if email not in user_chats_map:
                    user_chats_map[email] = []
                    user_email_map[email] = user
                
                user_chats_map[email].append(chat_data)

        # 5. Save Files (One per User)
        saved_files = []
        for email, chats in user_chats_map.items():
            user = user_email_map[email]
            user_prefix = email.split('@')[0]
            
            filename = f"{user_prefix}_{safe_model}_chats.json"
            file_path = os.path.join(output_dir, filename)

            # Write all chats for this user to disk
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=4)

            saved_files.append({
                "user": email,
                "count": len(chats),
                "path": file_path
            })

        logger.info(f"Saved {len(saved_files)} user files to {output_dir}")

        return {
            "status": "success",
            "group_id": group_id,
            "model_id": model_id,
            "total_users": len(user_chats_map),
            "total_conversations": sum(len(c) for c in user_chats_map.values()),
            "output_directory": os.path.abspath(output_dir),
            "files": saved_files
        }

    except Exception as e:
        logger.error(f"Error exporting conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

if __name__ == "__main__":
    import uvicorn
    # Run server locally for testing
    uvicorn.run(app, host="0.0.0.0", port=8000)
