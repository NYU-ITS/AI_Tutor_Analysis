import json

import pytest

from app.routers import analysis as analysis_router
from app.routers.analysis import (
    _build_error_type_prompt_section,
    _build_eval_prompt,
    _evaluate_all_questions,
)


pytestmark = pytest.mark.unit


def test_build_error_type_prompt_section_formats_all_rows():
    section = _build_error_type_prompt_section(
        [
            {"name": "Conceptual", "description": "wrong approach"},
            {"name": "Procedural", "description": "wrong steps"},
        ]
    )

    assert "- **Conceptual**: wrong approach" in section
    assert "- **Procedural**: wrong steps" in section


def test_build_eval_prompt_includes_classification_rules():
    prompt = _build_eval_prompt(
        base_prompt="base eval",
        error_types=[
            {"name": "Conceptual", "description": "wrong approach"},
            {"name": "Procedural", "description": "wrong steps"},
        ],
    )

    assert "base eval" in prompt
    assert "Error Type Classification" in prompt
    assert '"Conceptual", "Procedural"' in prompt
    assert '"Not Attempted"' in prompt


def test_evaluate_all_questions_calls_llm_once_and_parses_json(monkeypatch):
    captured = {}

    def fake_ask(prompt, system=None, **kwargs):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["kwargs"] = kwargs
        return json.dumps(
            {
                "1": {"attempted": True, "solved": False, "error_type": "Conceptual"},
                "2": {"attempted": False, "solved": False, "error_type": "Not Attempted"},
            }
        )

    monkeypatch.setattr(analysis_router, "ask", fake_ask)

    result = _evaluate_all_questions(
        questions={"1": "Q1 text", "2": "Q2 text"},
        answers={"1": "A1 text"},
        chat_history="chat history block",
        system_prompt="system prompt block",
    )

    assert result["1"]["attempted"] is True
    assert result["2"]["attempted"] is False
    assert captured["system"] == "system prompt block"
    assert captured["kwargs"]["response_format"] == {"type": "json_object"}
    assert "**Question 1:**" in captured["prompt"]
    assert "**Reference Solution:**" in captured["prompt"]
    assert "No reference solution available." in captured["prompt"]
    assert "**Chat History:**" in captured["prompt"]
