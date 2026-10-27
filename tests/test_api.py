from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import database


def event(message: str = "upstream request timeout after 30 seconds", **overrides):
    payload = {
        "service": "checkout-api",
        "environment": "test",
        "severity": "error",
        "message": message,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": "trace-demo-001",
        "attributes": {"source": "pytest"},
    }
    payload.update(overrides)
    return payload


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_event_ingestion_and_correlation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    with TestClient(app) as client:
        first = client.post("/api/v1/events", json=event())
        second = client.post(
            "/api/v1/events",
            json=event("upstream request timeout after 45 seconds", severity="critical"),
        )
        assert first.status_code == 201
        assert second.status_code == 201
        first_body, second_body = first.json(), second.json()
        assert first_body["incident_id"] == second_body["incident_id"]
        assert second_body["grouped_into_existing_incident"] is True
        assert second_body["incident"]["event_count"] == 2
        assert second_body["incident"]["severity"] == "critical"


def test_different_services_create_separate_incidents(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    with TestClient(app) as client:
        one = client.post("/api/v1/events", json=event())
        two = client.post("/api/v1/events", json=event(service="billing-api"))
        assert one.json()["incident_id"] != two.json()["incident_id"]


def test_investigation_links_hypothesis_to_event_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        incident_id = created.json()["incident_id"]
        result = client.post(f"/api/v1/incidents/{incident_id}/investigate")
        assert result.status_code == 200
        body = result.json()
        assert body["method"] == "deterministic-baseline"
        assert body["hypotheses"][0]["cause"] == "Dependency or downstream timeout"
        assert created.json()["event_id"] in body["hypotheses"][0]["evidence_event_ids"]


def test_status_update_and_missing_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        incident_id = created.json()["incident_id"]
        updated = client.patch(
            f"/api/v1/incidents/{incident_id}/status", json={"status": "investigating"}
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "investigating"
        missing = client.get("/api/v1/incidents/99999")
        assert missing.status_code == 404


def test_invalid_event_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/v1/events", json={"service": "", "message": ""})
        assert response.status_code == 422



def test_github_issue_endpoint_requires_explicit_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        response = client.post(
            f"/api/v1/incidents/{created.json()['incident_id']}/github-issue"
        )
        assert response.status_code == 503
