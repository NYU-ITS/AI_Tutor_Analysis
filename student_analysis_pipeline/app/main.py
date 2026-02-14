from fastapi import FastAPI
from app.routers import homework, prompt
from app.database import engine, SessionLocal
from app.models import Base
from app.seed import seed_default_prompts

Base.metadata.create_all(bind=engine)

# Seed default prompts
with SessionLocal() as db:
    seed_default_prompts(db)

app = FastAPI(title="Student Analysis Pipeline API")

app.include_router(homework.router)
app.include_router(prompt.router)


@app.get("/")
def health():
    return {"status": "ok"}
