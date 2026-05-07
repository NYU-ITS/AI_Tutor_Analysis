"""Live smoke tests for the deployed Open WebUI frontend.

These checks are intentionally lightweight and read-only. They verify that the
frontend service is reachable from inside OpenShift and that important routes do
not return server errors. Full browser workflows need a dedicated test account.

Run with: pytest --noconftest tests/live/test_frontend_smoke.py -m live
Requires:
  - LIVE_FRONTEND_BASE_URL set, or the OpenShift service default below.
"""

from __future__ import annotations

import os

import pytest
import requests


pytestmark = [pytest.mark.live, pytest.mark.smoke, pytest.mark.health]

BASE_URL = os.getenv("LIVE_FRONTEND_BASE_URL", "http://open-webui.rit-genai-naga-dev.svc:80").rstrip("/")


def _request(path: str, *, expected_content_type: str | None = None) -> requests.Response:
    response = requests.get(f"{BASE_URL}{path}", timeout=30, allow_redirects=True)
    assert response.status_code < 500, f"{path} returned {response.status_code}: {response.text[:400]}"
    if expected_content_type and response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        assert expected_content_type in content_type, (
            f"{path} content-type was {content_type!r}, expected to include {expected_content_type!r}"
        )
    return response


class TestOpenWebUIFrontendSmoke:
    """Read-only checks for the deployed frontend service."""

    def test_frontend_home_page_serves_application(self):
        response = _request("/", expected_content_type="text/html")
        body = response.text.lower()
        assert "<html" in body

    def test_frontend_health_endpoint_responds(self):
        response = _request("/health")
        assert response.status_code in {200, 204, 401, 403, 404}

    def test_ai_tutor_dashboard_route_is_served(self):
        response = _request("/aitutordashboard/topicanalysis?group_id=group-nyu-101")
        assert response.status_code in {200, 401, 403, 404}

    def test_frontend_config_endpoint_responds(self):
        response = _request("/api/config")
        assert response.status_code in {200, 401, 403, 404}
        if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
            assert isinstance(response.json(), dict)
