from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import homework, prompt, conversation, analysis, practice, pipeline, assignment
from app.database import engine, SessionLocal
from app.models import Base
from app.seed import seed_default_prompts

Base.metadata.create_all(bind=engine)

# Seed default prompts
with SessionLocal() as db:
    seed_default_prompts(db)

app = FastAPI(title="Student Analysis Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(homework.router)
app.include_router(prompt.router)
app.include_router(conversation.router)
app.include_router(analysis.router)
app.include_router(practice.router)
app.include_router(pipeline.router)
app.include_router(assignment.router)


@app.get("/")
def health():
    return {"status": "ok"}
