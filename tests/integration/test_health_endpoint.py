import pytest


pytestmark = pytest.mark.integration


def test_health_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
