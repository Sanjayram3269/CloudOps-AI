"""Read-only Prometheus range-query integration for incident context."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class PrometheusConfigurationError(ValueError):
    """Prometheus integration is not configured or its query config is invalid."""


class PrometheusQueryError(RuntimeError):
    """The configured Prometheus endpoint did not return a valid query response."""


def _configuration() -> tuple[str, dict[str, str]]:
    base_url = os.getenv("CLOUDOPS_PROMETHEUS_URL", "").strip().rstrip("/")
    raw_queries = os.getenv("CLOUDOPS_PROMETHEUS_QUERIES", "").strip()
    if not base_url or not raw_queries:
        raise PrometheusConfigurationError(
            "Prometheus context is disabled; configure CLOUDOPS_PROMETHEUS_URL and CLOUDOPS_PROMETHEUS_QUERIES."
        )
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PrometheusConfigurationError("CLOUDOPS_PROMETHEUS_URL must be an absolute HTTP(S) URL.")
    try:
        queries = json.loads(raw_queries)
    except json.JSONDecodeError as exc:
        raise PrometheusConfigurationError("CLOUDOPS_PROMETHEUS_QUERIES must be a JSON object.") from exc
    if not isinstance(queries, dict) or not queries or len(queries) > 8:
        raise PrometheusConfigurationError("Configure between 1 and 8 named Prometheus query templates.")
    cleaned: dict[str, str] = {}
    for name, query in queries.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(query, str) or not query.strip():
            raise PrometheusConfigurationError("Each Prometheus query needs a non-empty name and string template.")
        cleaned[name[:80]] = query[:2_000]
    return base_url, cleaned


def _promql_string(value: Any) -> str:
    """Escape a value for insertion inside a PromQL quoted string."""
    text = str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def query_incident_metrics(
    incident: dict[str, Any],
    *,
    lookback_minutes: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run configured, read-only range queries and bound the returned series."""
    base_url, queries = _configuration()
    current = now or datetime.now(timezone.utc)
    incident_time = datetime.fromisoformat(str(incident["last_seen"]).replace("Z", "+00:00"))
    if incident_time.tzinfo is None:
        incident_time = incident_time.replace(tzinfo=timezone.utc)
    end_dt = max(current, incident_time)
    start_dt = end_dt - timedelta(minutes=lookback_minutes)
    start, end = start_dt.timestamp(), end_dt.timestamp()
    step = max(15, min(60, int((end - start) / 120) or 15))
    context: dict[str, Any] = {
        "source": "prometheus",
        "window": {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "step_seconds": step},
        "query_count": len(queries),
        "queries": [],
        "limitations": [
            "Metric names and labels are operator-configured PromQL templates.",
            "Metric correlation is temporal context, not proof of root cause.",
            "Returned series are bounded to 10 per query and 120 samples per series.",
        ],
    }
    for name, template in queries.items():
        query = template.replace("{service}", _promql_string(incident["service"]))
        query = query.replace("{environment}", _promql_string(incident["environment"]))
        params = urlencode({"query": query, "start": str(start), "end": str(end), "step": str(step)})
        request = Request(
            f"{base_url}/api/v1/query_range?{params}",
            headers={"Accept": "application/json", "User-Agent": "CloudOps-AI/0.2"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=4) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise PrometheusQueryError("Prometheus query failed or returned invalid JSON.") from exc
        if not isinstance(body, dict) or body.get("status") != "success":
            raise PrometheusQueryError("Prometheus returned an unsuccessful query response.")
        data = body.get("data", {})
        raw_series = data.get("result", []) if isinstance(data, dict) else []
        series = []
        for item in raw_series[:10] if isinstance(raw_series, list) else []:
            if not isinstance(item, dict):
                continue
            values = item.get("values", [])
            series.append({
                "metric": item.get("metric", {}) if isinstance(item.get("metric", {}), dict) else {},
                "values": values[-120:] if isinstance(values, list) else [],
            })
        context["queries"].append({
            "name": name,
            "promql": query,
            "result_type": data.get("resultType", "unknown") if isinstance(data, dict) else "unknown",
            "series": series,
            "series_count_returned": len(series),
        })
    return context
