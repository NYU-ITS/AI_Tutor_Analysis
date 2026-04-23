import pytest

from app.routers.analysis import (
    _aggregate_metrics,
    _parse_answers_from_markdown,
    _parse_questions_from_markdown,
)


pytestmark = pytest.mark.unit


def test_parse_questions_from_bold_markdown():
    markdown = """
**1.** Find the derivative of $x^2$.
**2.** Evaluate $$\\int_0^1 x\\,dx$$.
""".strip()

    parsed = _parse_questions_from_markdown(markdown)

    assert parsed == {
        "1": "Find the derivative of $x^2$.",
        "2": "Evaluate $$\\int_0^1 x\\,dx$$.",
    }


def test_parse_questions_from_plain_markdown_and_strip_answer_box():
    markdown = """
1. Solve for x. [Answer box]
2. Explain your steps. [Answer space]
---
""".strip()

    parsed = _parse_questions_from_markdown(markdown)

    assert parsed == {
        "1": "Solve for x.",
        "2": "Explain your steps.",
    }


def test_parse_answers_from_problem_headers():
    markdown = """
### Problem 1
Answer for one
### Problem 2
Answer for two
""".strip()

    parsed = _parse_answers_from_markdown(markdown)

    assert parsed == {
        "1": "Answer for one",
        "2": "Answer for two",
    }


def test_parse_answers_from_bold_numbered_sections():
    markdown = """
**1.** First answer

**2.** Second answer
""".strip()
    parsed = _parse_answers_from_markdown(markdown)
    assert parsed == {"1": "First answer", "2": "Second answer"}


def test_aggregate_metrics_counts_topics_and_skips_visual_questions():
    evaluations = {
        "1": {"attempted": True, "solved": False, "error_type": "Conceptual"},
        "2": {"attempted": False, "solved": False, "error_type": "Not Attempted"},
        "3": {"attempted": True, "solved": True, "error_type": None},
        "4": {"attempted": True, "solved": False, "error_type": "Incomplete"},
    }
    topic_mapping = {
        "1": ["Derivatives"],
        "2": ["Derivatives"],
        "3": ["Limits"],
        "4": ["N/A - Visual/Image-based"],
    }

    result = _aggregate_metrics(evaluations, topic_mapping)

    assert result["total_question"] == 3
    assert result["total_attempted"] == 2
    assert result["total_solved"] == 1
    assert result["total_errors"] == 1

    topics = {t["topic_name"]: t for t in result["topic_performances"]}
    assert topics["Derivatives"]["status"] == "needs_practice"
    assert topics["Derivatives"]["question_tested"] == 2
    assert topics["Derivatives"]["questions_solved"] == 0
    assert topics["Limits"]["status"] == "mastered"


def test_aggregate_metrics_handles_question_with_no_topics():
    result = _aggregate_metrics(
        evaluations={"1": {"attempted": True, "solved": True, "error_type": None}},
        topic_mapping={"1": []},
    )
    assert result["total_question"] == 1
    assert result["total_attempted"] == 1
    assert result["total_solved"] == 1
    assert result["topic_performances"] == []


def test_parse_questions_returns_empty_on_empty_markdown():
    assert _parse_questions_from_markdown("") == {}


def test_parse_questions_returns_empty_when_no_numbered_pattern_matches():
    markdown = "Just some prose with no numbering at all.\nAnother paragraph."
    assert _parse_questions_from_markdown(markdown) == {}


def test_parse_answers_returns_empty_when_no_pattern_matches():
    assert _parse_answers_from_markdown("") == {}
    assert _parse_answers_from_markdown("no answer structure here") == {}


def test_aggregate_metrics_marks_topic_as_mastered_when_all_solved():
    """Topic with every mapped question solved is classified 'mastered' with the
    reason 'All questions attempted and solved correctly'."""
    result = _aggregate_metrics(
        evaluations={
            "1": {"attempted": True, "solved": True, "error_type": None},
            "2": {"attempted": True, "solved": True, "error_type": None},
        },
        topic_mapping={"1": ["Derivatives"], "2": ["Derivatives"]},
    )
    topics = {t["topic_name"]: t for t in result["topic_performances"]}
    assert topics["Derivatives"]["status"] == "mastered"
    assert topics["Derivatives"]["question_tested"] == 2
    assert topics["Derivatives"]["questions_solved"] == 2
    assert "All questions attempted and solved correctly" in topics["Derivatives"]["reason"]
