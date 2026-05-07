from __future__ import annotations

import os

import pytest


PLACEHOLDER_VALUES = {
    "",
    "test-portkey-key",
    "mock-portkey-key",
    "your_api_key_here",
}


def strict_live_checks_enabled() -> bool:
    return (
        os.getenv("QUALITY_STRICT_LIVE_CHECKS", "").strip() == "1"
        or os.getenv("QUALITY_ENVIRONMENT", "").strip().startswith("openshift")
    )


def skip_or_fail(reason: str) -> None:
    if strict_live_checks_enabled():
        pytest.fail(reason)
    pytest.skip(reason)


def require_non_placeholder_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value in PLACEHOLDER_VALUES:
        skip_or_fail(f"Required live-check environment variable {name} is missing or placeholder")
    return value
