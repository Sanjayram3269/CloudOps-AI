"""Translate OpenTelemetry Protocol (OTLP) JSON logs into CloudOps events."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from backend.app.schemas import EventIn, Severity

_MAX_RECORDS = 500
_MAX_ATTRIBUTES = 80

def _attribute_value(value: Any) -> Any:
    """Decode OTLP AnyValue JSON without evaluating its content."""
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "boolValue", "intValue", "doubleValue"):
        if key in value:
            return value[key]
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [_attribute_value(item.get("value", item)) for item in values[:50]]
    if "kvlistValue" in value:
        pairs = value["kvlistValue"].get("values", [])
        return {str(pair.get("key", ""))[:120]: _attribute_value(pair.get("value"))
                for pair in pairs[:50] if pair.get("key")}
    return None

def _attributes(items: Any) -> dict[str, Any]:
    if not isinstance(items, list):
        return {}
    result: dict[str, Any] = {}
    for item in items[:_MAX_ATTRIBUTES]:
        if isinstance(item, dict) and item.get("key"):
            result[str(item["key"])[:120]] = _attribute_value(item.get("value"))
    return result

def _timestamp(record: dict[str, Any]) -> datetime:
    raw = record.get("timeUnixNano") or record.get("observedTimeUnixNano")
    if raw in (None, "", 0, "0"):
        return datetime.now(timezone.utc)
    try:
        nanos = int(raw)
        if nanos <= 0:
            raise ValueError
        return datetime.fromtimestamp(nanos / 1_000_000_000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("OTLP timestamp must be a valid positive Unix-nanosecond value") from exc

def _body(record: dict[str, Any]) -> str:
    import json
    raw = _attribute_value(record.get("body", {}))
    if raw is None:
        return "(empty OTLP log body)"
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True)[:8000]
    return str(raw)[:8000] or "(empty OTLP log body)"

def _severity(record: dict[str, Any]) -> Severity:
    text = str(record.get("severityText", "")).strip().upper()
    if text in {"FATAL", "CRITICAL", "CRIT", "EMERGENCY", "ALERT", "FATAL2", "FATAL3", "FATAL4"}:
        return Severity.critical
    if text.startswith("ERROR"):
        return Severity.error
    if text.startswith("WARN"):
        return Severity.warning
    try:
        number = int(record.get("severityNumber", 0))
    except (TypeError, ValueError):
        number = 0
    if number >= 21:
        return Severity.critical
    if number >= 17:
        return Severity.error
    if number >= 13:
        return Severity.warning
    return Severity.info

def parse_otlp_logs(payload: dict[str, Any]) -> list[EventIn]:
    """Map an OTLP ExportLogsServiceRequest JSON payload into validated events."""
    resource_logs = payload.get("resourceLogs")
    if not isinstance(resource_logs, list):
        raise ValueError("Expected OTLP JSON with a resourceLogs array")
    events: list[EventIn] = []
    for resource_group in resource_logs:
        if not isinstance(resource_group, dict):
            raise ValueError("Each resourceLogs entry must be an object")
        resource = resource_group.get("resource") or {}
        resource_attrs = _attributes(resource.get("attributes", []))
        service = str(resource_attrs.get("service.name") or "unknown-service")[:120]
        environment = str(resource_attrs.get("deployment.environment.name")
                          or resource_attrs.get("deployment.environment") or "production")[:80]
        deployment_id = (resource_attrs.get("deployment.id")
                         or resource_attrs.get("k8s.deployment.name")
                         or resource_attrs.get("service.version"))
        scope_logs = resource_group.get("scopeLogs", resource_group.get("instrumentationLibraryLogs", []))
        if not isinstance(scope_logs, list):
            raise ValueError("scopeLogs must be an array")
        for scope_group in scope_logs:
            if not isinstance(scope_group, dict):
                raise ValueError("Each scopeLogs entry must be an object")
            records = scope_group.get("logRecords", [])
            if not isinstance(records, list):
                raise ValueError("logRecords must be an array")
            for record in records:
                if len(events) >= _MAX_RECORDS:
                    raise ValueError(f"At most {_MAX_RECORDS} OTLP log records are accepted per request")
                if not isinstance(record, dict):
                    raise ValueError("Each OTLP log record must be an object")
                attrs = _attributes(record.get("attributes", []))
                trace_id = str(record["traceId"])[:128] if record.get("traceId") else None
                event_deployment = attrs.pop("deployment.id", None) or deployment_id
                events.append(EventIn(
                    service=service, environment=environment, severity=_severity(record),
                    message=_body(record), occurred_at=_timestamp(record), trace_id=trace_id,
                    deployment_id=str(event_deployment)[:128] if event_deployment else None,
                    attributes={"otel": {
                        "severity_number": record.get("severityNumber"),
                        "severity_text": record.get("severityText"),
                        "resource": resource_attrs,
                        "scope": scope_group.get("scope", {}),
                        "attributes": attrs,
                    }},
                ))
    if not events:
        raise ValueError("OTLP request contained no log records")
    return events
