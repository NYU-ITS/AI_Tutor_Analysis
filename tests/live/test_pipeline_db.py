"""Live tests for Pipeline database connectivity.

These tests verify that:
  - The PIPELINE_DATABASE_URL connection string is valid
  - Tables were created by the app startup
  - Seed prompts exist

Run with: pytest -m live
Requires: PIPELINE_DATABASE_URL set in .env or environment, and the DB must be reachable.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal, engine
from app.models import GeneralPrompt


pytestmark = pytest.mark.live


# Skip if Pipeline DB is unreachable
_skip_reason = None
try:
    _test_conn = engine.connect()
    _test_conn.execute(text("SELECT 1"))
    _test_conn.close()
except Exception as exc:
    _skip_reason = f"Pipeline DB not reachable: {exc}"

if _skip_reason:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason=_skip_reason)]


class TestPipelineDBConnectivity:
    """Verify the Pipeline database is reachable and has expected schema."""

    def test_db_connection_works(self):
        """Basic SELECT 1 to verify the connection is alive."""
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1

    def test_seed_prompts_exist(self):
        """Verify default prompts were seeded on app startup."""
        db = SessionLocal()
        try:
            count = db.query(GeneralPrompt).count()
            assert count >= 5, f"Expected at least 5 seeded prompts, found {count}"

            expected_names = {
                "pdf_to_markdown",
                "topic_mapping",
                "generate_answers",
                "evaluate_question",
                "generate_practice_problems",
            }
            actual_names = {p.name for p in db.query(GeneralPrompt).all()}
            missing = expected_names - actual_names
            assert not missing, f"Missing seeded prompts: {missing}"
        finally:
            db.close()

    def test_tables_exist(self):
        """Verify all expected tables were created."""
        with engine.connect() as conn:
            expected_tables = [
                "general_prompt",
                "tutor_prompt",
                "tutor_homework",
                "student_conversation",
                "student_analysis",
                "student_topic_performance",
                "student_question_evaluations",
                "tutor_error_type",
                "tutor_practice_problem",
            ]
            for table_name in expected_tables:
                result = conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT FROM information_schema.tables"
                        "  WHERE table_name = :tbl"
                        ")"
                    ),
                    {"tbl": table_name},
                )
                exists = result.scalar()
                assert exists, f"Table '{table_name}' does not exist"
