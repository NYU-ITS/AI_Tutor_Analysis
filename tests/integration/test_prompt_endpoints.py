import pytest


pytestmark = pytest.mark.integration


def test_create_general_prompt_and_reject_duplicate(client):
    payload = {"name": "custom_prompt", "prompt": "hello"}

    first = client.post("/prompts/general", json=payload)
    assert first.status_code == 200
    assert first.json()["name"] == "custom_prompt"

    second = client.post("/prompts/general", json=payload)
    assert second.status_code == 409


def test_create_and_list_tutor_prompt(client):
    payload = {"name": "topic_mapping", "group_id": "group-1", "prompt": "group override"}

    create_resp = client.post("/prompts/tutor", json=payload)
    assert create_resp.status_code == 200

    list_resp = client.get("/prompts/tutor", params={"group_id": "group-1"})
    assert list_resp.status_code == 200
    rows = list_resp.json()
    assert any(r["group_id"] == "group-1" and r["name"] == "topic_mapping" for r in rows)


def test_update_general_prompt_success_and_not_found(client):
    create = client.post("/prompts/general", json={"name": "update_general", "prompt": "v1"})
    assert create.status_code == 200
    prompt_id = create.json()["id"]

    updated = client.put(f"/prompts/general/{prompt_id}", json={"prompt": "v2", "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["prompt"] == "v2"
    assert updated.json()["is_active"] is False

    missing = client.put("/prompts/general/missing-id", json={"prompt": "x"})
    assert missing.status_code == 404


def test_update_tutor_prompt_success_and_not_found(client):
    create = client.post(
        "/prompts/tutor",
        json={"name": "topic_mapping", "group_id": "group-upd", "prompt": "v1"},
    )
    assert create.status_code == 200
    prompt_id = create.json()["id"]

    updated = client.put(f"/prompts/tutor/{prompt_id}", json={"prompt": "v2", "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["prompt"] == "v2"
    assert updated.json()["is_active"] is False

    missing = client.put("/prompts/tutor/missing-id", json={"prompt": "x"})
    assert missing.status_code == 404
