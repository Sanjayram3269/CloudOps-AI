"""CloudOps AI API: ingest events, correlate incidents, and inspect evidence."""
from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app import database
from backend.app.config import correlation_window_seconds, cors_origins
from backend.app.correlation import fingerprint
from backend.app.investigation import investigate
from backend.app.otel_ingestion import parse_otlp_logs
from backend.app.github_issues import GitHubIssueConfigurationError, GitHubIssueError, create_or_get_github_issue
from backend.app.schemas import DeploymentIn, EventIn, IncidentStatus

app = FastAPI(
    title="CloudOps AI API",
    version="0.1.0",
    description="Evidence-first incident intake, correlation, and baseline investigation.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.on_event("startup")
def startup() -> None:
    database.init_db()


def serialize_incident(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "event_count": int(row["event_count"])}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cloudops-ai-api"}


@app.get("/api/v1/incidents")
def list_incidents(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    incidents = [serialize_incident(row) for row in database.list_incidents(limit)]
    return {"items": incidents, "count": len(incidents)}


def _persist_event(payload: EventIn) -> dict[str, Any]:
    event = payload.model_dump()
    event["occurred_at"] = event["occurred_at"].astimezone(timezone.utc).isoformat()
    event["severity"] = event["severity"].value
    event_fingerprint = fingerprint(event["service"], event["environment"], event["message"])
    event_id, incident_id, grouped = database.ingest_event(
        event, event_fingerprint, correlation_window_seconds()
    )
    incident = database.get_incident(incident_id)
    assert incident is not None
    return {
        "event_id": event_id,
        "incident_id": incident_id,
        "grouped_into_existing_incident": grouped,
        "incident": serialize_incident(incident),
    }


@app.post("/api/v1/events", status_code=201)
def ingest_event(payload: EventIn) -> dict[str, Any]:
    return _persist_event(payload)


@app.post("/v1/logs", status_code=202)
@app.post("/api/v1/telemetry/otlp/v1/logs", status_code=202)
def ingest_otlp_logs(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept OTLP JSON log exports and feed records through normal correlation."""
    try:
        events = parse_otlp_logs(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    results = [_persist_event(event) for event in events]
    return {
        "accepted": len(results),
        "grouped": sum(1 for item in results if item["grouped_into_existing_incident"]),
        "items": results,
    }


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: int) -> dict[str, Any]:
    incident = database.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        **serialize_incident(incident),
        "evidence": database.get_events(incident_id),
        "related_deployments": database.get_related_deployments(incident_id),
    }


class StatusUpdate(BaseModel):
    status: IncidentStatus


@app.patch("/api/v1/incidents/{incident_id}/status")
def update_status(incident_id: int, payload: StatusUpdate) -> dict[str, Any]:
    incident = database.update_incident_status(incident_id, payload.status.value)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return serialize_incident(incident)


@app.post("/api/v1/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: int) -> dict[str, Any]:
    incident = database.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    result = investigate(incident, database.get_events(incident_id))
    result["deployment_context"] = database.get_related_deployments(incident_id)
    return result



@app.post("/api/v1/incidents/{incident_id}/github-issue")
def create_github_issue(incident_id: int) -> dict[str, Any]:
    incident = database.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    investigation = investigate(incident, database.get_events(incident_id))
    try:
        result = create_or_get_github_issue(incident, investigation)
    except GitHubIssueConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubIssueError as exc:
        raise HTTPException(status_code=502, detail="GitHub issue creation failed") from exc
    return {"incident_id": incident_id, **result}



@app.post("/api/v1/deployments", status_code=201)
def ingest_deployment(payload: DeploymentIn) -> dict[str, Any]:
    """Record deployment metadata for incident correlation and investigation context."""
    deployment = payload.model_dump()
    deployment["deployed_at"] = deployment["deployed_at"].astimezone(timezone.utc).isoformat()
    deployment["outcome"] = deployment["outcome"].value
    return database.record_deployment(deployment)
