"""Prometheus Alertmanager webhook normalization.

Only firing alerts become evidence events. Resolved notifications are counted but
never automatically close incidents; closure remains an explicit operator action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.schemas import EventIn, Severity

MAX_ALERTS_PER_REQUEST = 500
MAX_LABELS = 40
MAX_TEXT = 4_000


def _bounded_labels(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in list(value.items())[:MAX_LABELS]:
        if isinstance(key, str) and isinstance(item, (str, int, float, bool)):
            result[key[:120]] = str(item)[:500]
    return result


def _timestamp(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ValueError("Alertmanager startsAt must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Alertmanager startsAt must include a timezone")
    return parsed


def parse_alertmanager_payload(payload: dict[str, Any]) -> tuple[list[EventIn], int]:
    """Return validated firing alerts and a count of resolved alerts ignored."""
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("Alertmanager payload must contain a non-empty alerts array")
    if len(alerts) > MAX_ALERTS_PER_REQUEST:
        raise ValueError(f"Alertmanager requests are limited to {MAX_ALERTS_PER_REQUEST} alerts")

    events: list[EventIn] = []
    resolved_count = 0
    for index, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            raise ValueError(f"Alert at index {index} must be an object")
        status = str(alert.get("status", "firing")).lower()
        if status == "resolved":
            resolved_count += 1
            continue
        if status != "firing":
            raise ValueError(f"Unsupported Alertmanager status at index {index}: {status}")

        labels = _bounded_labels(alert.get("labels"))
        annotations = _bounded_labels(alert.get("annotations"))
        alert_name = labels.get("alertname", "PrometheusAlert")
        service = labels.get("service") or labels.get("service_name") or labels.get("job") or "unknown-service"
        environment = labels.get("environment") or labels.get("env") or "production"
        raw_severity = labels.get("severity", "error").lower()
        severity = raw_severity if raw_severity in Severity.__members__ else "error"
        message = (annotations.get("summary") or annotations.get("description") or alert_name)[:MAX_TEXT]
        attributes = {
            "source": "prometheus-alertmanager",
            "alertmanager_fingerprint": str(alert.get("fingerprint", ""))[:160],
            "generator_url": str(alert.get("generatorURL", ""))[:1000],
            "alert_name": alert_name[:200],
            "labels": labels,
            "annotations": annotations,
        }
        events.append(EventIn(
            service=service[:120],
            environment=environment[:80],
            severity=severity,
            message=message,
            occurred_at=_timestamp(alert.get("startsAt")),
            attributes=attributes,
        ))
    return events, resolved_count
