import pytest

from app.routers.conversation import _chats_to_markdown


pytestmark = pytest.mark.unit


def test_chats_to_markdown_merges_and_sorts_messages():
    chats = [
        {
            "chat": {
                "history": {
                    "messages": {
                        "m2": {"role": "assistant", "content": "second", "timestamp": 200},
                    }
                }
            }
        },
        {
            "chat": '{"history":{"messages":{"m1":{"role":"user","content":"first","timestamp":100}}}}'
        },
    ]

    markdown = _chats_to_markdown(chats, "student@example.edu")

    assert "# Student Conversation" in markdown
    assert "**Student:** student@example.edu" in markdown
    assert markdown.index("**USER:** first") < markdown.index("**ASSISTANT:** second")


def test_chats_to_markdown_returns_empty_when_no_messages():
    markdown = _chats_to_markdown([{"chat": {}}], "student@example.edu")
    assert markdown == ""


def test_chats_to_markdown_handles_invalid_json_blob():
    chats = [{"chat": "{not-valid-json"}]
    markdown = _chats_to_markdown(chats, "student@example.edu")
    assert markdown == ""


def test_chats_to_markdown_handles_unknown_roles():
    chats = [
        {
            "chat": {
                "history": {
                    "messages": {
                        "m1": {"role": "system", "content": "hello", "timestamp": 1},
                    }
                }
            }
        }
    ]
    markdown = _chats_to_markdown(chats, "student@example.edu")
    assert "**SYSTEM:** hello" in markdown
