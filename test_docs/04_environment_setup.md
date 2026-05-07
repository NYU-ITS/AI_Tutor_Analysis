# 04 — Environment Setup & How to Run Tests

## Prerequisites

| Requirement | Why | How to check |
|---|---|---|
| Python 3.12 or 3.13 | Matches CI (`.github/workflows/tests.yml` uses 3.13) | `python --version` |
| Docker Desktop **running** | `tests/conftest.py` spins up a `testcontainers.postgres.PostgresContainer("postgres:16")` at import time. Without Docker, **no** test will even collect — not even unit tests. | `docker info` |
| ~2 GB free disk | Postgres image is cached on first run |  |
| Internet on first run only | Pulls `postgres:16` image |  |

You do **not** need a Portkey API key to run the default suite; LLM calls are
monkeypatched in every non-live test. You only need real credentials to run
the deployed-environment checks (see below).

## One-time setup

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r student_analysis_pipeline/requirements.txt
pip install -r tests/requirements-testing.txt
```

Or, if you prefer conda:

```bash
conda create -n ai_tutor python=3.12 -y
conda activate ai_tutor
pip install -r student_analysis_pipeline/requirements.txt -r tests/requirements-testing.txt
```

## Running the suite

```bash
# Default: all unit + integration, live skipped (matches CI)
pytest

# Everything including live (requires a real PORTKEY_API_KEY and
# the OWUI DB configured via env vars)
pytest -m "live and (smoke or integration or health or external_service)"
pytest -m ""        # ignore markers, run everything

# Narrower slices
pytest -m unit                              # fast, no Docker usable — but conftest still needs it
pytest -m integration                       # Docker required
pytest tests/unit/test_pdf_generator.py     # one file
pytest -k "assignment and topic"            # keyword filter

# With verbose names and short tracebacks
pytest -v --tb=short
```

## Why even unit tests require Docker today

`tests/conftest.py` starts the Postgres testcontainer at module import time,
before pytest decides which tests to run. That means:

- `pytest -m unit` still boots a container on collection.
- This is deliberate — it guarantees `PIPELINE_DATABASE_URL` is valid for *any*
  module that might import `app.database` transitively.
- Startup is ~3 s on a warm machine; the container is reused for the whole
  session (see `atexit.register(_pg_container.stop)` in `conftest.py`).

If you ever want to run only unit tests without Docker, move the
`PostgresContainer` setup into a session-scoped fixture gated on
`-m integration or -m live`. This is logged as a future improvement in
`06_coverage_roadmap.md`.

## Live tests: what they need

Located in `tests/live/`, marked `@pytest.mark.live`, deselected by default.

| Env var | Used by | Example |
|---|---|---|
| `LIVE_API_BASE_URL` | `test_api_smoke.py` | `http://127.0.0.1:8000` |
| `LIVE_FRONTEND_BASE_URL` | `test_frontend_smoke.py` | `http://localhost:8080` |
| `PORTKEY_API_KEY` | `test_portkey_llm.py` | `pk-...` |
| `PORTKEY_BASE_URL` | ↑ | `https://ai-gateway.apps.cloud.rt.nyu.edu/v1` |
| `DATABASE_URL` | `test_openwebui_db.py` | `postgresql://…/openwebui` |
| `PIPELINE_DATABASE_URL` | `test_pipeline_db.py` | `postgresql://…/pipeline` |
| `QUALITY_STRICT_LIVE_CHECKS` | all live checks | `1` in OpenShift, unset locally |

Put these in a `.env` file at the repo root — `load_dotenv()` picks it up.
In OpenShift, the quality Job injects them from Kubernetes Secrets and sets
`QUALITY_STRICT_LIVE_CHECKS=1` so missing values fail the quality gate.

## Environment differences at a glance

| Aspect | Unit | Integration | Live |
|---|---|---|---|
| DB | None (mocked or N/A) | `PostgresContainer("postgres:16")` | Real Postgres (PIPELINE + OpenWebUI) |
| LLM | `monkeypatch.setattr(..., "ask", lambda ...: json.dumps(...))` | Same | Real Portkey Gateway |
| OpenWebUI DB | `FakeOwuiSession` | `FakeOwuiSession` (monkey-patched into the router) | Real OpenWebUI Postgres |
| PDF backend | Real `reportlab`, real `fitz` (when present) | Same | Same |
| Speed | < 0.1 s per test | < 0.1 s per test (container reused) | Slow; depends on network |

## CI

`.github/workflows/tests.yml` runs on pushes to `auto_pipeline` and `main`:

1. Checkout the repo.
2. Set up Python 3.13.
3. Install `student_analysis_pipeline/requirements.txt` + `tests/requirements-testing.txt`.
4. `bash scripts/run_pytest_with_reports.sh`.
5. Upload JUnit, coverage, and quality metrics artifacts.

Docker is pre-installed on GitHub-hosted `ubuntu-latest` runners, so nothing
extra is required.

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectionRefusedError: Port is not open` during `PostgresContainer.start()` | Docker isn't running | Start Docker Desktop |
| `ModuleNotFoundError: No module named 'testcontainers'` | Missed `pip install -r tests/requirements-testing.txt` | Install the file above |
| `ModuleNotFoundError: No module named 'fitz'` | `PyMuPDF` not installed | `pip install PyMuPDF` (already in `student_analysis_pipeline/requirements.txt`) |
| Tests hang on first run | First time pulling `postgres:16` (~150 MB) | Wait — subsequent runs are instant |
| `sqlalchemy.exc.OperationalError: could not connect to server` mid-run | Docker container killed externally | Re-run `pytest` |
| `ConnectionError: Port mapping for container ... and port 8080 is not available` on macOS | Stale `testcontainers-ryuk` reaper container | Either disable it — `TESTCONTAINERS_RYUK_DISABLED=true pytest` — or `docker ps -a --filter "label=org.testcontainers=true" --format '{{.ID}}' \| xargs docker rm -f` |
