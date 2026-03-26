import pytest


pytestmark = pytest.mark.integration


def test_error_types_default_custom_and_delete(client):
    group_id = "group-error-types"

    get_default = client.get("/analysis/error-types", params={"group_id": group_id})
    assert get_default.status_code == 200
    assert get_default.json()["source"] == "default"
    assert len(get_default.json()["error_types"]) == 4

    custom_types = [
        {"name": "Conceptual", "description": "Wrong concept"},
        {"name": "Procedural", "description": "Wrong process"},
    ]
    set_resp = client.put("/analysis/error-types", params={"group_id": group_id}, json=custom_types)
    assert set_resp.status_code == 200
    assert set_resp.json()["error_types"] == custom_types

    get_custom = client.get("/analysis/error-types", params={"group_id": group_id})
    assert get_custom.status_code == 200
    assert get_custom.json()["source"] == "custom"
    assert get_custom.json()["error_types"] == custom_types

    delete_resp = client.delete("/analysis/error-types", params={"group_id": group_id})
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    get_after_delete = client.get("/analysis/error-types", params={"group_id": group_id})
    assert get_after_delete.status_code == 200
    assert get_after_delete.json()["source"] == "default"


def test_set_error_types_validates_required_fields(client):
    resp = client.put(
        "/analysis/error-types",
        params={"group_id": "group-invalid"},
        json=[{"name": "OnlyName"}],
    )
    assert resp.status_code == 400
    assert "must have 'name' and 'description'" in resp.json()["detail"]


def test_delete_error_types_returns_false_when_nothing_to_delete(client):
    resp = client.delete("/analysis/error-types", params={"group_id": "group-missing"})
    assert resp.status_code == 200
    assert resp.json()["deleted"] is False
