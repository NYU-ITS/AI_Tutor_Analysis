# AI_Tutor_Analysis Startup Notes

## Setup Steps Completed

1. **Recreated `.venv`** — The existing `.venv` had a broken interpreter path pointing to the old project location (`/Users/jiaqiyi/Documents/...`). Deleted and recreated with `python3 -m venv .venv`.
2. **Installed dependencies** — Ran `pip install fastapi uvicorn sqlalchemy psycopg2-binary pymupdf python-dotenv requests pydantic python-multipart` successfully.

## Error: PostgreSQL Not Running

The server crashes on startup because it cannot connect to the Pipeline Database (PostgreSQL):

```
psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

### Root Cause

`PIPELINE_DATABASE_URL` in `.env` points to `localhost:5432/student_analysis`, but no PostgreSQL instance is running locally. No brew service, no system process, no Docker container found.

### What Needs to Be Done

The app requires **two PostgreSQL databases** to start:

| Database | URL in `.env` | Purpose |
|---|---|---|
| Pipeline DB | `postgresql://pipeline_user:password@localhost:5432/student_analysis` | Stores analysis results (auto-creates tables) |
| OpenWebUI DB | `postgresql://user:password@localhost:5433/pilotgenai_dev_pg` | Read-only access to student chats |

**Steps to fix:**
1. Start a PostgreSQL instance on port 5432 (e.g., via Docker or Homebrew)
2. Create the `student_analysis` database and `pipeline_user` user (see README for exact SQL)
3. Update `.env` with the correct credentials
4. Make sure the OpenWebUI DB is also accessible on port 5433
5. Then run: `cd student_analysis_pipeline && .venv/bin/uvicorn app.main:app --reload --port 8000`

### Minor Warning (non-blocking, will appear after DB is fixed)

```
FastAPIDeprecationWarning: `example` has been deprecated, please use `examples` instead
```
This is a FastAPI version mismatch in `app/main.py:2` — cosmetic only, won't break anything.
