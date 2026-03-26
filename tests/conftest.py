import os
import sys
import types
import atexit
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "student_analysis_pipeline"

# Ensure `from app...` imports resolve in tests.
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Start a real PostgreSQL container (same DB engine as production).
# The container is created once and shared across the entire test session.
_pg_container = PostgresContainer("postgres:16")
_pg_container.start()
atexit.register(_pg_container.stop)

os.environ["PIPELINE_DATABASE_URL"] = _pg_container.get_connection_url()
# OpenWebUI DB is a separate system we don't own — keep as SQLite stub.
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("PORTKEY_API_KEY", "test-portkey-key")

# Optional dependencies in this workspace snapshot. Provide light stubs only when unavailable.
try:  # pragma: no cover - runtime environment guard
    import fitz as _fitz  # noqa: F401
except ModuleNotFoundError:
    fake_fitz = types.SimpleNamespace(open=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fitz not installed")))
    sys.modules["fitz"] = fake_fitz

try:  # pragma: no cover - runtime environment guard
    import python_multipart as _python_multipart  # noqa: F401
except ModuleNotFoundError:
    fake_python_multipart = types.ModuleType("python_multipart")
    fake_python_multipart.__version__ = "1.0.0"
    fake_python_multipart_multipart = types.ModuleType("python_multipart.multipart")
    fake_python_multipart_multipart.parse_options_header = lambda value: ("", {})
    sys.modules["python_multipart"] = fake_python_multipart
    sys.modules["python_multipart.multipart"] = fake_python_multipart_multipart

from app.main import app  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed_default_prompts  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    """Reset pipeline DB between tests for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_prompts(db)
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
