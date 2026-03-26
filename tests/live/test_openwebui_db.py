"""Live tests for OpenWebUI database connectivity.

These tests query the real OpenWebUI database. They verify that:
  - The DATABASE_URL connection string is valid
  - The expected tables exist (user, group, chat)
  - Basic queries return data

Run with: pytest -m live
Requires: DATABASE_URL set in .env or environment, and the DB must be reachable
          (on server: direct access; locally: port-forward must be active).
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.services.openwebui_db import (
    OwuiChat,
    OwuiGroup,
    OwuiSessionLocal,
    OwuiUser,
    owui_engine,
)


pytestmark = pytest.mark.live


# Skip all tests if DB is unreachable at import time
_skip_reason = None
try:
    _test_conn = owui_engine.connect()
    _test_conn.execute(text("SELECT 1"))
    _test_conn.close()
except Exception as exc:
    _skip_reason = f"OpenWebUI DB not reachable: {exc}"

if _skip_reason:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason=_skip_reason)]


class TestOpenWebUIDBConnectivity:
    """Verify the OpenWebUI database is reachable and has expected schema."""

    def test_db_connection_works(self):
        """Basic SELECT 1 to verify the connection is alive."""
        with owui_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1

    def test_user_table_has_rows(self):
        """Verify the user table exists and has at least one row."""
        session = OwuiSessionLocal()
        try:
            count = session.query(OwuiUser).count()
            assert count > 0, "user table is empty"
        finally:
            session.close()

    def test_group_table_has_rows(self):
        """Verify the group table exists and has at least one row."""
        session = OwuiSessionLocal()
        try:
            count = session.query(OwuiGroup).count()
            assert count > 0, "group table is empty"
        finally:
            session.close()

    def test_chat_table_has_rows(self):
        """Verify the chat table exists and has at least one row."""
        session = OwuiSessionLocal()
        try:
            count = session.query(OwuiChat).count()
            assert count > 0, "chat table is empty"
        finally:
            session.close()

    def test_group_has_user_ids(self):
        """Verify at least one group has a non-empty user_ids list."""
        session = OwuiSessionLocal()
        try:
            groups = session.query(OwuiGroup).all()
            has_members = any(
                g.user_ids and len(g.user_ids) > 0
                for g in groups
            )
            assert has_members, "No group has any members"
        finally:
            session.close()

    def test_chat_has_expected_json_structure(self):
        """Verify at least one chat row has the expected JSON blob structure."""
        session = OwuiSessionLocal()
        try:
            chat = session.query(OwuiChat).filter(OwuiChat.archived == False).first()
            assert chat is not None, "No non-archived chats found"

            chat_blob = chat.chat
            assert isinstance(chat_blob, dict), f"chat blob is {type(chat_blob)}, expected dict"
            assert "history" in chat_blob or "messages" in chat_blob, (
                "chat blob missing expected 'history' or 'messages' key"
            )
        finally:
            session.close()
