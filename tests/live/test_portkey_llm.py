"""Live tests for Portkey LLM gateway connectivity.

These tests call the real Portkey API. They verify that:
  - The API key is valid and accepted
  - The gateway returns a well-formed response
  - JSON response format works correctly

Run with: pytest -m live
Requires: PORTKEY_API_KEY and PORTKEY_BASE_URL set in .env or environment.
"""

import json
import os

import pytest
import requests

from app.services.llm import (
    PORTKEY_API_KEY,
    PORTKEY_BASE_URL,
    ask,
    ask_with_images,
    chat,
)


pytestmark = pytest.mark.live


# Skip all tests in this module if credentials are missing or placeholder
_skip_reason = None
if not PORTKEY_API_KEY or PORTKEY_API_KEY in ("test-portkey-key", "mock-portkey-key", "your_api_key_here"):
    _skip_reason = "No valid PORTKEY_API_KEY configured"

if _skip_reason:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason=_skip_reason)]


class TestPortkeyConnectivity:
    """Verify Portkey gateway is reachable and API key is accepted."""

    def test_portkey_api_key_is_valid(self):
        """Send a minimal request to verify the API key is accepted (not 401)."""
        headers = {
            "x-portkey-api-key": PORTKEY_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "model": "@gpt-4o/gpt-4o",
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
            model="gpt-4o",
            max_tokens=5,
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
            model="gpt-4o",
            max_tokens=20,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_portkey_system_prompt_works(self):
        """Verify system prompt is respected."""
        result = ask(
            prompt="What is 2+2?",
            model="gpt-4o",
            system="You must answer every question with the single word: PINEAPPLE",
            max_tokens=10,
        )
        assert "PINEAPPLE" in result.upper()
