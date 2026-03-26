import pytest
import requests

from app.services import llm


pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, payload=None, raise_error=None):
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}
        self._raise_error = raise_error

    def raise_for_status(self):
        if self._raise_error:
            raise self._raise_error

    def json(self):
        return self._payload


def test_chat_maps_known_model_id_and_returns_text(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(payload={"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)

    out = llm.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4o")

    assert out == "hello"
    assert captured["json"]["model"] == "@gpt-4o/gpt-4o"
    assert captured["timeout"] == 120


def test_chat_keeps_custom_model_when_not_in_map(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        captured["model"] = json["model"]
        return _FakeResponse(payload={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    llm.chat(messages=[{"role": "user", "content": "hi"}], model="my-custom-model")
    assert captured["model"] == "my-custom-model"


def test_chat_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    sleeps = []

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.Timeout("timeout")
        return _FakeResponse(payload={"choices": [{"message": {"content": "final"}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: sleeps.append(seconds))

    out = llm.chat(messages=[{"role": "user", "content": "hi"}], max_retries=3)
    assert out == "final"
    assert calls["count"] == 3
    assert sleeps == [1, 2]


def test_chat_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.exceptions.ConnectionError("down")),
    )
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)

    with pytest.raises(Exception, match="LLM call failed after 3 attempts"):
        llm.chat(messages=[{"role": "user", "content": "hi"}], max_retries=3)


def test_chat_rejects_empty_response_content(monkeypatch):
    monkeypatch.setattr(
        llm.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(payload={"choices": [{"message": {"content": "  "}}]}),
    )
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)

    with pytest.raises(Exception, match="LLM call failed after 3 attempts"):
        llm.chat(messages=[{"role": "user", "content": "hi"}], max_retries=3)


def test_ask_constructs_messages(monkeypatch):
    captured = {}

    def fake_chat(messages, model="gpt-4o", **kwargs):
        captured["messages"] = messages
        captured["model"] = model
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(llm, "chat", fake_chat)

    out = llm.ask(prompt="hello", model="gpt-4o-mini", system="sys", temperature=0.1)
    assert out == "ok"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    assert captured["kwargs"]["temperature"] == 0.1


def test_ask_with_images_constructs_multimodal_message(monkeypatch):
    captured = {}

    def fake_chat(messages, model="gpt-4o", **kwargs):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(llm, "chat", fake_chat)

    image_urls = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}]
    out = llm.ask_with_images(prompt="see image", image_urls=image_urls, system="sys")

    assert out == "ok"
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    user_message = captured["messages"][1]
    assert user_message["role"] == "user"
    assert user_message["content"][0] == {"type": "text", "text": "see image"}
    assert user_message["content"][1:] == image_urls
