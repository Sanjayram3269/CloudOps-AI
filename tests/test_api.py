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



def test_temporal_replay_withholds_future_events():
    from pathlib import Path
    from scripts.replay_incident import replay
    report = replay(Path("samples/replay-scenario.json"))
    assert report["visible_event_ids"] == [1, 2, 3]
    assert report["withheld_future_event_ids"] == [4]
    assert report["future_leakage_detected"] is False
    assert report["top1_correct"] is True
    assert 4 not in report["investigation_evidence_ids"]



def test_llm_redaction_removes_common_secret_values():
    from backend.app.llm_investigation import redact_for_model
    source = "request failed api_key=sk-test-secret password=hunter2 Authorization: Bearer abcdefghijklmnop"
    redacted = redact_for_model(source)
    assert "sk-test-secret" not in redacted
    assert "hunter2" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert redacted.count("[REDACTED]") >= 3



def test_deployment_context_is_linked_to_incident(tmp_path, monkeypatch):
    from datetime import timedelta
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "deployments.db"))
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        incident_id = created.json()["incident_id"]
        deployed_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        deployment = {
            "service": "checkout-api",
            "environment": "test",
            "deployment_id": "deploy-abc123",
            "version": "1.4.2",
            "commit_sha": "abc123def456",
            "actor": "ci",
            "outcome": "succeeded",
            "deployed_at": deployed_at,
            "metadata": {"pipeline": "github-actions"}
        }
        response = client.post("/api/v1/deployments", json=deployment)
        assert response.status_code == 201
        assert response.json()["deployment_id"] == "deploy-abc123"
        incident = client.get(f"/api/v1/incidents/{incident_id}").json()
        assert len(incident["related_deployments"]) == 1
        assert incident["related_deployments"][0]["commit_sha"] == "abc123def456"
        investigation = client.post(f"/api/v1/incidents/{incident_id}/investigate").json()
        assert investigation["deployment_context"][0]["deployment_id"] == "deploy-abc123"


def test_deployment_upsert_and_timezone_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "deployment-upsert.db"))
    database.init_db()
    with TestClient(app) as client:
        payload = {
            "service": "checkout-api", "environment": "test",
            "deployment_id": "deploy-repeat", "version": "1.0.0",
            "outcome": "succeeded", "deployed_at": datetime.now(timezone.utc).isoformat()
        }
        first = client.post("/api/v1/deployments", json=payload)
        payload["version"] = "1.0.1"
        second = client.post("/api/v1/deployments", json=payload)
        assert first.status_code == second.status_code == 201
        assert second.json()["version"] == "1.0.1"
        payload["deployed_at"] = "2026-10-28T12:00:00"
        assert client.post("/api/v1/deployments", json=payload).status_code == 422


def test_alertmanager_webhook_requires_configured_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "alertmanager.db"))
    monkeypatch.delenv("CLOUDOPS_ALERTMANAGER_WEBHOOK_TOKEN", raising=False)
    database.init_db()
    with TestClient(app) as client:
        response = client.post("/api/v1/integrations/alertmanager", json={"alerts": [{"status": "firing"}]})
        assert response.status_code == 503


def test_alertmanager_webhook_authenticates_and_ingests_real_alert_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "alertmanager.db"))
    monkeypatch.setenv("CLOUDOPS_ALERTMANAGER_WEBHOOK_TOKEN", "test-webhook-secret")
    database.init_db()
    payload = {
        "receiver": "cloudops-ai",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighErrorRate", "service": "checkout-api", "environment": "staging", "severity": "critical"},
                "annotations": {"summary": "Checkout error rate exceeded threshold", "description": "5xx rate stayed above 10 percent for 5 minutes"},
                "startsAt": "2026-10-28T09:30:00Z",
                "generatorURL": "http://prometheus.example/graph?g0.expr=up",
                "fingerprint": "alert-fingerprint-123"
            },
            {
                "status": "resolved",
                "labels": {"alertname": "Recovered", "service": "checkout-api"},
                "annotations": {"summary": "Recovered"},
                "startsAt": "2026-10-28T09:20:00Z"
            }
        ]
    }
    with TestClient(app) as client:
        unauthorized = client.post("/api/v1/integrations/alertmanager", json=payload)
        assert unauthorized.status_code == 401
        response = client.post("/api/v1/integrations/alertmanager", json=payload, headers={"Authorization": "Bearer test-webhook-secret"})
        assert response.status_code == 202
        body = response.json()
        assert body["accepted"] == 1
        assert body["resolved_notifications_ignored"] == 1
        incident = client.get(f"/api/v1/incidents/{body['items'][0]['incident_id']}").json()
        assert incident["service"] == "checkout-api"
        assert incident["environment"] == "staging"
        assert incident["severity"] == "critical"
        assert incident["evidence"][0]["message"] == "Checkout error rate exceeded threshold"


def test_alertmanager_rejects_invalid_payload_and_naive_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "alertmanager-invalid.db"))
    monkeypatch.setenv("CLOUDOPS_ALERTMANAGER_WEBHOOK_TOKEN", "test-webhook-secret")
    database.init_db()
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-webhook-secret"}
        assert client.post("/api/v1/integrations/alertmanager", json={}, headers=headers).status_code == 422
        payload = {"alerts": [{"status": "firing", "labels": {"alertname": "BadTimestamp", "service": "api"}, "annotations": {"summary": "failure"}, "startsAt": "2026-10-28T09:30:00"}]}
        assert client.post("/api/v1/integrations/alertmanager", json=payload, headers=headers).status_code == 422


def test_prometheus_metrics_requires_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "prometheus.db"))
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_QUERIES", raising=False)
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        response = client.get(f"/api/v1/incidents/{created.json()['incident_id']}/metrics")
        assert response.status_code == 503


def test_prometheus_metrics_queries_configured_backend(tmp_path, monkeypatch):
    import json
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlparse
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "prometheus.db"))
    monkeypatch.setenv("CLOUDOPS_PROMETHEUS_URL", "http://prometheus.test")
    monkeypatch.setenv("CLOUDOPS_PROMETHEUS_QUERIES", json.dumps({
        "request_rate": 'sum(rate(http_requests_total{service="{service}",environment="{environment}"}[5m]))'
    }))
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        incident_id = created.json()["incident_id"]
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return json.dumps({"status": "success", "data": {"resultType": "matrix", "result": [{
                    "metric": {"service": "checkout-api"},
                    "values": [[1793179800, "12.5"], [1793179860, "18.0"]]
                }]}}).encode()
        with patch("backend.app.prometheus_metrics.urlopen", return_value=FakeResponse()) as mocked:
            response = client.get(f"/api/v1/incidents/{incident_id}/metrics?lookback_minutes=15")
        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "prometheus"
        assert body["query_count"] == 1
        assert body["queries"][0]["name"] == "request_rate"
        assert len(body["queries"][0]["series"]) == 1
        assert body["queries"][0]["series"][0]["values"][1][1] == "18.0"
        request_url = mocked.call_args.args[0].full_url
        parsed = parse_qs(urlparse(request_url).query)
        assert "/api/v1/query_range?" in request_url
        assert 'service="checkout-api"' in parsed["query"][0]
        assert 'environment="test"' in parsed["query"][0]


def test_prometheus_metrics_rejects_invalid_query_config(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "prometheus-invalid.db"))
    monkeypatch.setenv("CLOUDOPS_PROMETHEUS_URL", "http://prometheus.test")
    monkeypatch.setenv("CLOUDOPS_PROMETHEUS_QUERIES", json.dumps({"": "up"}))
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        response = client.get(f"/api/v1/incidents/{created.json()['incident_id']}/metrics")
        assert response.status_code == 503


def test_investigation_returns_graceful_metric_status_when_prometheus_is_not_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "investigation-metrics.db"))
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_QUERIES", raising=False)
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        response = client.post(f"/api/v1/incidents/{created.json()['incident_id']}/investigate")
        assert response.status_code == 200
        body = response.json()
        assert body["method"] == "deterministic-baseline"
        assert body["metric_context"]["status"] == "not_configured"
        assert body["metric_context"]["signals"] == []


def test_metric_signal_summary_reports_change_without_claiming_causality():
    from backend.app.prometheus_metrics import summarize_metric_signals
    summary = summarize_metric_signals({"queries": [{"name": "request_rate", "series": [
        {"metric": {"service": "checkout-api"}, "values": [[1, "10"], [2, "15"], [3, "20"]]},
        {"metric": {"service": "empty"}, "values": [[1, "NaN"]]}
    ]}]})
    assert len(summary) == 1
    assert summary[0]["first_value"] == 10
    assert summary[0]["latest_value"] == 20
    assert summary[0]["percent_change"] == 100.0
    assert "no anomaly threshold" in summary[0]["interpretation"]


def test_investigation_builds_explainable_evidence_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDOPS_DB_PATH", str(tmp_path / "evidence-graph.db"))
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("CLOUDOPS_PROMETHEUS_QUERIES", raising=False)
    database.init_db()
    with TestClient(app) as client:
        created = client.post("/api/v1/events", json=event())
        incident_id = created.json()["incident_id"]
        response = client.post(f"/api/v1/incidents/{incident_id}/investigate")
        assert response.status_code == 200
        graph = response.json()["evidence_graph"]
        assert graph["version"] == "1.0"
        assert graph["summary"]["event_count"] == 1
        assert graph["summary"]["hypothesis_count"] >= 1
        assessment = graph["hypothesis_assessments"][0]
        assert created.json()["event_id"] in assessment["supporting_event_ids"]
        assert assessment["counter_evidence_status"] == "not_evaluated"
        assert any(edge["relation"] == "supports_by_citation" for edge in graph["edges"])
        assert any("not prove causality" in item for item in graph["limitations"])


def test_evidence_graph_separates_citations_from_context():
    from backend.app.evidence_graph import build_evidence_graph
    graph = build_evidence_graph(
        [{"cause": "Possible timeout", "evidence_event_ids": [1]}],
        [{"event_id": 1, "message": "timeout", "occurred_at": "2026-10-31T00:00:00Z"}],
        [{"deployment_id": "deploy-1", "deployed_at": "2026-10-31T00:01:00Z", "outcome": "succeeded"}],
        [{"query_name": "request_rate", "latest_value": 12, "sample_count": 2}],
    )
    relations = {edge["relation"] for edge in graph["edges"]}
    assert {"supports_by_citation", "temporal_context", "observational_context"} <= relations
    assert graph["hypothesis_assessments"][0]["counter_evidence_ids"] == []
