"""End-to-end HTTP tests against the FastAPI app."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_observe_then_get_beliefs(client):
    r = client.post(
        "/observe",
        json={"subject": "cpu", "value": 0.7, "source": "test"},
    )
    assert r.status_code in (200, 201), r.text
    belief = r.json()["belief"]
    assert belief["subject"] == "cpu"
    assert belief["last_value"] == 0.7
    assert belief["strength"] >= 0.0

    r2 = client.get("/beliefs")
    assert r2.status_code == 200
    subjects = {b["subject"] for b in r2.json()}
    assert "cpu" in subjects


def test_observe_validates_value_range(client):
    r = client.post("/observe", json={"subject": "cpu", "value": 1.5})
    assert r.status_code == 422


def test_world_state_endpoint_returns_summary(client):
    client.post("/observe", json={"subject": "cpu", "value": 0.8})
    client.post("/observe", json={"subject": "error_rate", "value": 0.9})
    r = client.get("/world-state")
    assert r.status_code == 200
    body = r.json()
    assert "overall_strength" in body
    assert 0.0 <= body["overall_strength"] <= 1.0


def test_decide_endpoint(client):
    for _ in range(5):
        client.post("/observe", json={"subject": "error_rate", "value": 0.95})
    r = client.get("/decide")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("stable", "watch", "alert", "critical")
    assert body["action"]


def test_full_report(client):
    client.post("/observe", json={"subject": "cpu", "value": 0.5})
    r = client.get("/report")
    assert r.status_code == 200
    body = r.json()
    assert "beliefs" in body
    assert "world_state" in body
    assert "decision" in body
