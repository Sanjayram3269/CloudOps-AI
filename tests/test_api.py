from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import database
from backend.app.github_issues import redact_message


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



def test_github_issue_redaction_removes_bearer_and_key_values():
    message = "Authorization: Bearer top-secret-token api_key=abc123 password=hunter2"
    redacted = redact_message(message)
    assert "top-secret-token" not in redacted
    assert "abc123" not in redacted
    assert "hunter2" not in redacted
    assert "[REDACTED]" in redacted



def test_otlp_json_logs_ingest_and_correlate(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "otel.db"))
    database.init_db()
    payload = {
        "resourceLogs": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "checkout-api"}},
                {"key": "deployment.environment.name", "value": {"stringValue": "test"}},
                {"key": "deployment.id", "value": {"stringValue": "deploy-42"}}
            ]},
            "scopeLogs": [{
                "scope": {"name": "checkout-logger", "version": "1.0"},
                "logRecords": [
                    {
                        "timeUnixNano": "1767225600000000000",
                        "severityNumber": 17,
                        "severityText": "ERROR",
                        "body": {"stringValue": "upstream request timeout after 30 seconds"},
                        "traceId": "0123456789abcdef0123456789abcdef",
                        "attributes": [{"key": "http.route", "value": {"stringValue": "/checkout"}}]
                    },
                    {
                        "timeUnixNano": "1767225601000000000",
                        "severityNumber": 21,
                        "severityText": "FATAL",
                        "body": {"stringValue": "upstream request timeout after 45 seconds"}
                    }
                ]
            }]
        }]
    }
    with TestClient(app) as client:
        response = client.post("/v1/logs", json=payload)
        assert response.status_code == 202
        body = response.json()
        assert body["accepted"] == 2
        assert body["grouped"] == 1
        assert body["items"][0]["incident_id"] == body["items"][1]["incident_id"]
        incident = client.get(f"/api/v1/incidents/{body['items'][0]['incident_id']}").json()
        assert incident["event_count"] == 2
        assert incident["severity"] == "critical"
        assert incident["evidence"][0]["deployment_id"] == "deploy-42"


def test_otlp_rejects_malformed_or_empty_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "otel.db"))
    database.init_db()
    with TestClient(app) as client:
        assert client.post("/v1/logs", json={}).status_code == 422
        assert client.post("/v1/logs", json={"resourceLogs": []}).status_code == 422


def test_otlp_rejects_invalid_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "otel.db"))
    database.init_db()
    payload = {"resourceLogs": [{"resource": {"attributes": []}, "scopeLogs": [{
        "logRecords": [{"timeUnixNano": "not-a-timestamp", "body": {"stringValue": "boom"}}]
    }]}]}
    with TestClient(app) as client:
        response = client.post("/api/v1/telemetry/otlp/v1/logs", json=payload)
        assert response.status_code == 422


def test_seeded_evaluation_dataset_covers_known_rules():
    from pathlib import Path
    from scripts.evaluate_baseline import evaluate
    report = evaluate(Path("samples/incident-evaluation.json"))
    assert report["cases"] == 6
    assert report["top1_accuracy"] == 1.0
    assert report["top3_accuracy"] == 1.0
    assert "not production" in report["evaluation_type"]
