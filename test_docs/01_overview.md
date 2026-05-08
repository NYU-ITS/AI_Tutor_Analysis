# 01 — Test Suite Overview

## Source under test

`student_analysis_pipeline/` is a FastAPI backend that:

- Consumes PDF homeworks, converts them to markdown via an LLM vision model, and extracts a topic map.
- Pulls student chat conversations out of the OpenWebUI PostgreSQL database and stores them.
- Runs per-student LLM evaluations of each question, aggregates topic performance, and stores per-student analyses.
- Generates class-wide practice problems for weak topics, assigns them back to students, and exports student PDF/ZIP reports.

All of this is orchestrated through background `PipelineJob` rows so long-running LLM/PDF work doesn't block HTTP requests.

## Test architecture

The `tests/` folder mirrors the three layers of risk in the codebase:

```
tests/
├── conftest.py                       # session-wide fixtures + PostgresContainer
├── helpers.py                        # FakeOwuiSession, FakeQuery, Obj, make_upload_file
├── requirements-testing.txt
├── unit/                             # fast, pure-Python, no DB, no network
│   ├── test_analysis_helpers.py
│   ├── test_analysis_prompt_helpers.py
│   ├── test_conversation_helpers.py
│   ├── test_homework_helpers.py
│   ├── test_llm_service.py
│   ├── test_models.py
│   └── test_pdf_generator.py         # NEW (2026-04)
├── integration/                      # FastAPI TestClient + real Postgres testcontainer
│   ├── test_analysis_export_endpoints.py    # NEW (2026-04)
│   ├── test_analysis_router_branches.py
│   ├── test_analysis_run_endpoint.py
│   ├── test_assignment_endpoints.py
│   ├── test_conversation_router.py
│   ├── test_error_types_endpoints.py
│   ├── test_health_endpoint.py
│   ├── test_homework_helpers.py
│   ├── test_homework_router.py
│   ├── test_pipeline_endpoints.py
│   ├── test_practice_endpoints.py
│   ├── test_practice_helpers.py
│   ├── test_practice_update_endpoint.py     # NEW (2026-04)
│   ├── test_prompt_endpoints.py
│   ├── test_prompt_service.py
│   └── test_seed.py
└── live/                             # require real external systems (skipped by default)
    ├── _runtime.py                   # strict OpenShift failure / local skip helpers
    ├── test_api_smoke.py             # deployed backend smoke + API contract checks
    ├── test_frontend_smoke.py        # lightweight deployed frontend route checks
    ├── test_openwebui_db.py          # OpenWebUI DB health/schema checks
    ├── test_pipeline_db.py           # pipeline DB health/schema checks
    └── test_portkey_llm.py           # Portkey gateway health + small functional checks
```

## Markers (declared in `pytest.ini`)

| Marker | When it runs | What it needs |
|---|---|---|
| `unit` | default | nothing external; pure Python |
| `integration` | default | Docker (Postgres testcontainer), all LLM/OpenWebUI calls monkeypatched |
| `smoke` | OpenShift post-deploy | deployed backend/frontend routes |
| `health` | OpenShift post-deploy | service readiness and dependency reachability |
| `external_service` | OpenShift post-deploy | Portkey, OpenWebUI DB, pipeline DB |
| `live` | explicit only | real Portkey API key, live OpenWebUI DB, live pipeline DB |

Every test file declares `pytestmark = pytest.mark.<marker>` so filtering works even if individual tests forget.

OpenShift uses this marker expression:

```bash
pytest --noconftest tests/live -m "live and (smoke or integration or health or external_service)"
```

`QUALITY_STRICT_LIVE_CHECKS=1` is set for the OpenShift job. Missing required secrets or unreachable dependencies fail the quality gate there; local live runs can still skip when optional deployed-environment configuration is absent.

## Key fixtures (`tests/conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `PostgresContainer("postgres:16")` | session (module-level) | Starts one Docker container for the whole session; its URL becomes `PIPELINE_DATABASE_URL` |
| `reset_database` (autouse) | per-test | Drops and recreates all tables, then re-seeds default prompts. Guarantees isolation. |
| `db_session` | per-test | Yields a fresh `SessionLocal()` bound to the Postgres testcontainer |
| `client` | per-test | Yields a `fastapi.testclient.TestClient(app)` using the same DB session |

## Helpers (`tests/helpers.py`)

| Helper | Purpose |
|---|---|
| `FakeQuery` | Chainable mock for SQLAlchemy `.query(...).filter(...).first()/.all()` |
| `FakeOwuiSession` | Stand-in for `OwuiSessionLocal()` so tests don't need the OpenWebUI DB |
| `Obj(**kwargs)` | Minimal generic object builder (used everywhere for fake user/chat/group rows) |
| `make_upload_file` | Wraps bytes into a `starlette.UploadFile` for PDF upload tests |
| `run_async` | Executes a coroutine in the current test thread |

## CI

`.github/workflows/tests.yml` runs:

```yaml
- run: pip install -r student_analysis_pipeline/requirements.txt -r tests/requirements-testing.txt
- run: bash scripts/run_pytest_with_reports.sh
```

The hosted GitHub runner already has Docker available, so `testcontainers[postgres]` works without any extra setup.

GitHub Actions is the owner for this non-live backend suite. The OpenShift backend quality BuildConfig intentionally runs only the deployed-environment live subset after backend image updates:

```bash
pytest --noconftest tests/live -m "live and (smoke or integration or health or external_service)"
```

OpenShift sets `QUALITY_STRICT_LIVE_CHECKS=1`, reads `portkey-api-key`, `pipeline-database-url`, and `database-url` from `open-webui-mastering-homework-secret`, and publishes quality metrics to the namespace Pushgateway. See `../AI_TUTOR_TESTING_OBSERVABILITY.md` and `../k8s/quality-checks/README.md` for the current OpenShift trigger, secret, resource, and dashboard details.
