"""Live tests for Portkey LLM gateway connectivity.

These tests call the real Portkey API. They verify that:
  - The API key is valid and accepted
  - The gateway returns a well-formed response
  - JSON response format works correctly

Run with: pytest -m live
Requires: PORTKEY_API_KEY and PORTKEY_BASE_URL set in .env or environment.

Optional: LLM_TEST_MODEL — short name (e.g. gpt-4o-mini) or full Portkey id; defaults to app DEFAULT_MODEL.
"""

import json

import pytest
import requests

from app.services.llm import (
    PORTKEY_BASE_URL,
    ask,
    chat,
)
from tests.helpers import get_llm_test_model, portkey_model_id_for_tests
from tests.live._runtime import require_non_placeholder_env


pytestmark = [pytest.mark.live, pytest.mark.external_service]


class TestPortkeyConnectivity:
    """Verify Portkey gateway is reachable and API key is accepted."""

    @pytest.mark.health
    def test_portkey_api_key_is_valid(self):
        """Send a minimal request to verify the API key is accepted (not 401)."""
        portkey_api_key = require_non_placeholder_env("PORTKEY_API_KEY")
        headers = {
            "x-portkey-api-key": portkey_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": portkey_model_id_for_tests(),
            "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
            "temperature": 0,
            "max_tokens": 5,
        }
        response = requests.post(
            f"{PORTKEY_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

        assert response.status_code == 200, (
            f"Portkey returned {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "choices" in body
        assert len(body["choices"]) > 0
        assert body["choices"][0]["message"]["content"].strip() != ""

    def test_portkey_returns_nonempty_response_via_ask(self):
        """Verify the ask() helper returns a non-empty string from the real gateway."""
        result = ask(
            prompt="Reply with the single word: OK",
            model=get_llm_test_model(),
            max_tokens=5,
            max_retries=1,
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_portkey_json_response_format(self):
        """Verify response_format=json_object produces valid JSON."""
        result = chat(
            messages=[
                {"role": "system", "content": "You are a JSON-only responder."},
                {"role": "user", "content": 'Return this exact JSON: {"status": "ok"}'},
            ],
            model=get_llm_test_model(),
            max_tokens=20,
            max_retries=1,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_portkey_system_prompt_works(self):
        """Verify system prompt is respected."""
        result = ask(
            prompt="What is 2+2?",
            model=get_llm_test_model(),
            system="You must answer every question with the single word: PINEAPPLE",
            max_tokens=10,
            max_retries=1,
        )
        assert "PINEAPPLE" in result.upper()
