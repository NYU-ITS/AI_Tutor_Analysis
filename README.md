# Student Analysis Pipeline

Automated homework analysis using LLM-as-judge to evaluate student performance and generate personalized practice problems.

## Overview

This is a **FastAPI REST API** that runs a 4-step pipeline:

1. **PDF Upload & Topic Mapping** – Convert homework PDFs to Markdown, map questions to topics
2. **Conversation Export** – Pull student chat histories from OpenWebUI
3. **Student Analysis** – LLM evaluates each student's work per question, aggregates by topic
4. **Practice Generation** – Identify class-wide weaknesses and generate targeted practice problems

## Prerequisites

- **Python 3.11+**
- **PostgreSQL** – Two databases required:
  - **Pipeline DB** (`student_analysis`) – Stores pipeline data (created automatically)
  - **OpenWebUI DB** – Existing OpenWebUI PostgreSQL instance (read-only access)
- **Portkey API Key** – Access to NYU's AI Gateway

## Setup

### 1. Create virtual environment

```bash
cd student_analysis_pipeline
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # or: pip install fastapi uvicorn sqlalchemy psycopg2-binary pymupdf python-dotenv requests pydantic
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | OpenWebUI PostgreSQL connection string | `postgresql://user:pass@127.0.0.1:5433/pilotgenai_qa_beta_pg` |
| `PIPELINE_DATABASE_URL` | Pipeline DB connection string | `postgresql://pipeline_user:pass@localhost:5432/student_analysis` |
| `PORTKEY_API_KEY` | Portkey AI Gateway API key | `your_api_key` |
| `PORTKEY_BASE_URL` | Portkey AI Gateway base URL | `https://ai-gateway.apps.cloud.rt.nyu.edu/v1` |

### 3. Create the pipeline database

```bash
psql -U postgres
CREATE DATABASE student_analysis;
CREATE USER pipeline_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE student_analysis TO pipeline_user;
\q
```

Tables are created automatically on server startup.

## Running the Server

```bash
cd student_analysis_pipeline
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.

- Health check: `GET http://localhost:8000/`
- Interactive docs: `http://localhost:8000/docs` (Swagger UI)

## Pipeline Workflow

Run these steps in order. Replace `GROUP_ID`, `MODEL_ID`, and `HOMEWORK_ID` with your actual values.

> **Tip:** Use the Swagger UI at `/docs` to run these interactively instead of curl.

### Step 1: Upload Homework Questions (PDF)

Converts homework PDF to Markdown and automatically runs topic mapping.

```bash
curl -X POST "http://localhost:8000/homework/pdf-to-markdown?doc_type=question&group_id=GROUP_ID&model_id=MODEL_ID" \
  -F "file=@homework.pdf"
```

Note the `homework_id` in the response — you'll need it for subsequent steps.

### Step 2: Upload Answer Key (Optional)

If you have a reference solution PDF, upload it. If skipped, the LLM will auto-generate answers during analysis.

```bash
curl -X POST "http://localhost:8000/homework/pdf-to-markdown?doc_type=answer&group_id=GROUP_ID&model_id=MODEL_ID" \
  -F "file=@answer_key.pdf"
```

### Step 3: Export Student Conversations

Pulls chat histories from OpenWebUI for all students in the group who used the specified model.

```bash
curl -X POST "http://localhost:8000/conversation/export?homework_id=HOMEWORK_ID"
```

### Step 4: Run Analysis

Evaluates each student's performance on every question. A single LLM call per student evaluates all questions at once.

```bash
# Analyze all students
curl -X POST "http://localhost:8000/analysis/run?homework_id=HOMEWORK_ID"

# Analyze a single student
curl -X POST "http://localhost:8000/analysis/run?homework_id=HOMEWORK_ID&student_id=STUDENT_ID"
```

### Step 5: View Class Weakness (Optional)

Preview which topics the class is struggling with before generating practice problems.

```bash
curl "http://localhost:8000/practice/class-weakness?homework_id=HOMEWORK_ID&weakness_threshold=0.5"
```

### Step 6: Generate Practice Problems

Creates practice problems targeting weak topics. Stored with `status=pending` for instructor review.

```bash
curl -X POST "http://localhost:8000/practice/generate?homework_id=HOMEWORK_ID&weakness_threshold=0.5"
```

### Step 7: Approve or Reject Practice Problems

```bash
curl -X PATCH "http://localhost:8000/practice/PRACTICE_ID/status?status=approved"
```

## API Reference

### Homework (`/homework`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/homework/` | List homework entries. Filter by `homework_id`, `group_id`, `model_id` |
| `POST` | `/homework/pdf-to-markdown` | Upload PDF, convert to Markdown. Params: `file`, `doc_type` (question/answer), `group_id`, `model_id` |

### Conversation (`/conversation`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/conversation/` | List exported conversations. Filter by `homework_id`, `student_id` |
| `POST` | `/conversation/export` | Export conversations from OpenWebUI. Param: `homework_id` |

### Analysis (`/analysis`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analysis/` | List analyses with question evaluations and topic performances. Filter by `homework_id`, `student_id` |
| `POST` | `/analysis/run` | Run student analysis. Params: `homework_id`, `student_id` (optional) |
| `GET` | `/analysis/error-types` | Get error types for a group. Param: `group_id` |
| `PUT` | `/analysis/error-types` | Set custom error types. Params: `group_id`, body: `[{name, description}]` |
| `DELETE` | `/analysis/error-types` | Delete custom error types (revert to defaults). Param: `group_id` |

### Practice (`/practice`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/practice/` | List practice problem sets. Filter by `homework_id`, `group_id`, `status` |
| `GET` | `/practice/class-weakness` | Preview class weakness aggregation. Params: `homework_id`, `weakness_threshold` (default 0.5) |
| `POST` | `/practice/generate` | Generate practice problems. Params: `homework_id`, `weakness_threshold`, `user_id` (optional) |
| `PATCH` | `/practice/{practice_id}/status` | Update approval status. Param: `status` (approved/rejected/pending) |

### Prompts (`/prompts`)

Manage the 5 core prompt templates (pdf_to_markdown, topic_mapping, generate_answers, evaluate_question, generate_practice_problems). Group-specific overrides can be set via the API.

## Project Structure

```
student_analysis_pipeline/
├── app/
│   ├── main.py                  # FastAPI app, startup, router registration
│   ├── database.py              # PostgreSQL connection (pipeline DB)
│   ├── models.py                # SQLAlchemy ORM models
│   ├── seed.py                  # Default prompt seeding on startup
│   ├── routers/
│   │   ├── homework.py          # Pipeline 1: PDF upload & topic mapping
│   │   ├── conversation.py      # Pipeline 2: Export conversations from OpenWebUI
│   │   ├── analysis.py          # Pipeline 3: Student performance evaluation
│   │   ├── practice.py          # Pipeline 4: Practice problem generation
│   │   └── prompt.py            # Prompt template management
│   └── services/
│       ├── llm.py               # Portkey LLM client with retry logic
│       ├── openwebui_db.py      # OpenWebUI DB connection & models
│       └── prompt.py            # Prompt lookup & resolution
├── .env                         # Environment variables (not committed)
├── .env.example                 # Example env file
└── README.md                    # This file
```

## Adapting for Other Subjects

The pipeline is currently configured for **Calculus I**. To adapt for other subjects:

1. Update prompts via the **Prompts API** (`/prompts`) to set group-specific overrides, or
2. Edit the default prompts in `app/seed.py` (lines for `topic_mapping`, `generate_answers`, `generate_practice_problems`)

Replace subject-specific references (e.g., "Calculus tutor", "calculus concepts") with your target subject.

## Error Types

By default, student errors are classified as:

- **Conceptual** – Wrong formula, misunderstood question
- **Procedural** – Correct formula but wrong execution, skipped steps
- **Computational** – Arithmetic/sign errors
- **Incomplete** – Stopped working, conversation ended mid-problem

Custom error types can be configured per group via `PUT /analysis/error-types`.
