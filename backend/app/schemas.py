"""Validated API contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class IncidentStatus(str, Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"


class EventIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    service: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=8_000)
    severity: Severity = Severity.error
    environment: str = Field(default="production", min_length=1, max_length=80)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = Field(default=None, max_length=128)
    deployment_id: str | None = Field(default=None, max_length=128)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class EventAccepted(BaseModel):
    event_id: int
    incident_id: int
    grouped_into_existing_incident: bool
    incident: dict[str, Any]


class IncidentOut(BaseModel):
    id: int
    title: str
    service: str
    environment: str
    severity: Severity
    status: IncidentStatus
    fingerprint: str
    first_seen: datetime
    last_seen: datetime
    event_count: int


class EvidenceOut(BaseModel):
    event_id: int
    occurred_at: datetime
    service: str
    severity: Severity
    message: str
    trace_id: str | None = None
    deployment_id: str | None = None


class HypothesisOut(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence_event_ids: list[int]
    next_checks: list[str]


class InvestigationOut(BaseModel):
    incident_id: int
    method: str
    summary: str
    hypotheses: list[HypothesisOut]
    evidence: list[EvidenceOut]
    limitations: list[str]
