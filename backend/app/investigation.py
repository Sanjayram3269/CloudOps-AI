"""Evidence-linked baseline investigation (no external model required)."""
from __future__ import annotations

from typing import Any


PATTERNS: list[tuple[tuple[str, ...], str, str, list[str]]] = [
    (
        ("timeout", "timed out", "deadline exceeded"),
        "Dependency or downstream timeout",
        "The event text contains timeout indicators. This points to a slow or unreachable dependency, but the affected dependency is not yet identified.",
        ["Inspect dependency latency and timeout metrics for the same time window.",
         "Check traces for the first slow span and compare upstream versus downstream duration."],
    ),
    (
        ("connection refused", "connection reset", "could not connect"),
        "Service connectivity or availability failure",
        "The event text indicates a failed network connection. The destination and network path need confirmation.",
        ["Check target service health and recent restarts.",
         "Inspect network, DNS, and connection-pool errors around the event timestamp."],
    ),
    (
        ("out of memory", "oom", "memory limit"),
        "Memory pressure or process termination",
        "The event text contains a memory-pressure indicator; resource telemetry is needed to confirm the mechanism.",
        ["Compare memory usage with container or host limits.",
         "Inspect restart counts and runtime memory profiles."],
    ),
    (
        ("permission denied", "unauthorized", "forbidden", "401", "403"),
        "Authentication or authorization failure",
        "The event text suggests an access-control failure. The identity, permission, or credential change is not established by this event alone.",
        ["Review the principal and permission scope involved in the failed request.",
         "Check recent identity, secret, and policy changes without exposing secret values."],
    ),
    (
        ("migration", "schema", "column does not exist", "relation does not exist"),
        "Database schema or migration mismatch",
        "The event text suggests the application and database schema may be out of sync.",
        ["Compare the deployed application version with the applied migration version.",
         "Inspect database errors and deployment ordering for this service."],
    ),
]


def investigate(incident: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return conservative hypotheses whose evidence IDs point to stored events."""
    if not events:
        return {
            "incident_id": incident["id"],
            "method": "deterministic-baseline",
            "summary": "No event evidence is available for this incident yet.",
            "hypotheses": [],
            "evidence": [],
            "limitations": ["No evidence was available; no root cause can be inferred."],
        }

    matching: list[dict[str, Any]] = []
    all_text = " ".join(str(event.get("message", "")).lower() for event in events)
    for keywords, cause, rationale, checks in PATTERNS:
        event_ids = [
            int(event["event_id"])
            for event in events
            if any(keyword in str(event.get("message", "")).lower() for keyword in keywords)
        ]
        if event_ids:
            matching.append({
                "cause": cause,
                "confidence": round(min(0.78, 0.52 + 0.06 * (len(event_ids) - 1)), 2),
                "rationale": rationale,
                "evidence_event_ids": event_ids,
                "next_checks": checks,
            })

    if not matching:
        matching.append({
            "cause": "Unclassified application or infrastructure failure",
            "confidence": 0.25,
            "rationale": "No supported diagnostic pattern matched the available event text. This is a triage category, not a confirmed root cause.",
            "evidence_event_ids": [int(event["event_id"]) for event in events[:5]],
            "next_checks": [
                "Inspect adjacent logs and traces from the same service and time window.",
                "Compare the incident start with recent deployments and dependency health.",
            ],
        })

    matching.sort(key=lambda item: (item["confidence"], len(item["evidence_event_ids"])), reverse=True)
    return {
        "incident_id": incident["id"],
        "method": "deterministic-baseline",
        "summary": (
            f"Reviewed {len(events)} stored event(s) for {incident['service']}. "
            "These are evidence-linked triage hypotheses, not a verified root cause."
        ),
        "hypotheses": matching[:3],
        "evidence": events,
        "limitations": [
            "This baseline uses message-pattern heuristics; it does not call an LLM.",
            "Confidence values are heuristic ranking scores, not statistically calibrated probabilities.",
            "No metrics, traces, deployment diffs, or external dependency state are queried yet.",
        ],
    }
