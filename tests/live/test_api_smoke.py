"""Live smoke tests for the deployed tutor dashboard backend API.

These tests hit the real deployed API through a local port-forward.
They are intentionally read-only so they are safe to run on a schedule.

Run with: pytest --noconftest tests/live/test_api_smoke.py -m live
Requires:
  - LIVE_API_BASE_URL set or default port-forward at http://127.0.0.1:8000
  - `oc port-forward deployment/open-webui-mastering-homework 8000:8000 -n rit-genai-naga-dev`
"""

from __future__ import annotations

import os

import pytest
import requests


pytestmark = pytest.mark.live

BASE_URL = os.getenv("LIVE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _request(path: str, *, expected_content_type: str | None = None) -> requests.Response:
    response = requests.get(f"{BASE_URL}{path}", timeout=30)
    assert response.status_code == 200, f"{path} returned {response.status_code}: {response.text[:400]}"
    if expected_content_type:
        content_type = response.headers.get("content-type", "")
        assert expected_content_type in content_type, (
            f"{path} content-type was {content_type!r}, expected to include {expected_content_type!r}"
        )
    return response


_skip_reason = None
try:
    health_response = requests.get(f"{BASE_URL}/", timeout=10)
    if health_response.status_code != 200:
        _skip_reason = f"Live API not healthy at {BASE_URL}: {health_response.status_code}"
except Exception as exc:
    _skip_reason = f"Live API not reachable at {BASE_URL}: {exc}"

if _skip_reason:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason=_skip_reason)]


class TestTutorDashboardAPISmoke:
    """Read-only smoke checks for the tutor dashboard backend API."""

    def test_health_endpoint_returns_ok(self):
        response = _request("/", expected_content_type="application/json")
        assert response.json() == {"status": "ok"}

    def test_docs_ui_loads(self):
        response = _request("/docs", expected_content_type="text/html")
        assert "Swagger UI" in response.text

    def test_openapi_document_loads(self):
        response = _request("/openapi.json", expected_content_type="application/json")
        body = response.json()
        assert body["info"]["title"] == "Student Analysis Pipeline API"
        assert "/analysis/run" in body["paths"]

    def test_general_prompts_endpoint_responds(self):
        response = _request("/prompts/general", expected_content_type="application/json")
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 5

    def test_pipeline_jobs_endpoint_responds(self):
        response = _request("/pipeline/jobs", expected_content_type="application/json")
        assert isinstance(response.json(), list)

    def test_homework_endpoint_responds(self):
        response = _request("/homework/", expected_content_type="application/json")
        assert isinstance(response.json(), list)

    def test_conversation_endpoint_responds(self):
        response = _request("/conversation/", expected_content_type="application/json")
        assert isinstance(response.json(), list)

    def test_analysis_endpoint_responds(self):
        response = _request("/analysis/", expected_content_type="application/json")
        assert isinstance(response.json(), list)

    def test_practice_endpoint_responds(self):
        response = _request("/practice/", expected_content_type="application/json")
        assert isinstance(response.json(), list)

    def test_assignment_endpoint_responds(self):
        response = _request("/assignment/", expected_content_type="application/json")
        assert isinstance(response.json(), list)
