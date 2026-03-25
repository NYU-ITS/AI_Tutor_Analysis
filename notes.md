# Backend Run Notes

## Project
- Name: `Student Analysis Pipeline`
- Type: `FastAPI` backend server
- App entrypoint: `student_analysis_pipeline/app/main.py`

## What this backend does
- Exposes REST endpoints for:
- Homework PDF upload + markdown conversion/topic mapping
- Conversation export from OpenWebUI database
- Student analysis with LLM evaluation
- Practice problem generation + approval workflow

## Environment used
- Python available: `3.11.15` and `3.14.3`
- Existing virtualenv found: `student_analysis_pipeline/.venv`

## Setup steps that worked
1. Go to project folder:
   ```bash
   cd /Users/jiaqiyi/Documents/AI_Tutor_Analysis/student_analysis_pipeline
   ```
2. Activate virtualenv:
   ```bash
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install fastapi uvicorn sqlalchemy psycopg2-binary pymupdf python-dotenv requests pydantic python-multipart
   ```
4. Create env file from template:
   ```bash
   cp -n .env.example .env
   ```

## Startup behavior observed
- Without `.env`: app crashes with `PIPELINE_DATABASE_URL not set in .env`.
- After adding `.env`: app required extra package `python-multipart` for file upload endpoints.
- With default `.env` Postgres URLs, startup failed because local Postgres was not running:
  - `localhost:5432` connection refused (pipeline DB)
  - OpenWebUI DB on `localhost:5433` also not verified/running

## Quick local run (no Postgres, dev-only)
Use SQLite override for pipeline DB so server can boot:

```bash
cd /Users/jiaqiyi/Documents/AI_Tutor_Analysis/student_analysis_pipeline
source .venv/bin/activate
PIPELINE_DATABASE_URL=sqlite:///./student_analysis.db uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:
```bash
curl -sS http://127.0.0.1:8000/
```

Expected response:
```json
{"status":"ok"}
```

Swagger docs:
- `http://127.0.0.1:8000/docs`

## Full production-like run requirements
To run without SQLite override, these must be valid and reachable in `.env`:
- `PIPELINE_DATABASE_URL` (PostgreSQL for pipeline data)
- `DATABASE_URL` (OpenWebUI PostgreSQL, read-only)
- `PORTKEY_API_KEY` (needed for LLM-powered endpoints)

Then run:
```bash
cd /Users/jiaqiyi/Documents/AI_Tutor_Analysis/student_analysis_pipeline
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Notes
- A deprecation warning appears from FastAPI about `example` vs `examples`; it does not block startup.
- In this environment, `psql`, `pg_isready`, and Docker were not installed, so local Postgres was not provisioned during setup.
