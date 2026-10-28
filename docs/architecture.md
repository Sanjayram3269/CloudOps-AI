# Architecture Notes

## Current vertical slice

The MVP intentionally prioritizes a reproducible path from an event to a visible incident.

1. **API boundary** — FastAPI accepts JSON and validates it with Pydantic. Invalid fields and timezone-naive timestamps are rejected before persistence.
2. **Normalization and fingerprinting** — service, environment, and normalized message text are hashed to a stable fingerprint. Common high-cardinality values such as numbers, UUIDs, and hexadecimal addresses are normalized.
3. **Correlation** — the API looks for a non-resolved incident with the same service, environment, and fingerprint whose last event falls inside the configured correlation window.
4. **Persistence** — SQLite stores incident metadata and each event separately. Each event references its incident, preserving the evidence used for later investigation.
5. **Deployment context** — deployment events can be ingested with service, environment, deployment ID, version, commit SHA, actor, outcome, and timestamp. Incident detail and investigation responses include deployments near the incident start for the same service/environment; temporal proximity is context, not proof of cause.\n6. **Baseline triage** — a deterministic ruleset matches common message patterns and returns hypotheses with the event IDs that matched. This does not prove causality.
7. **Alertmanager integration** — a bearer-token-protected webhook normalizes firing Prometheus Alertmanager notifications into validated events; resolved notifications are acknowledged but do not silently close incidents. The endpoint is disabled unless a shared token is configured.\n8. **OTLP ingestion** — `/v1/logs` maps OTLP/HTTP JSON resource attributes, severity, timestamps, trace IDs, and deployment metadata into the same validated event/correlation path. A request is capped at 500 records.
9. **Dashboard** — the Next.js app reads the incident list, submits sample events, and loads an incident evidence timeline.
10. **Regression evaluation** — a small labelled synthetic fixture set checks whether deterministic rules continue to produce expected triage categories; it is not a production accuracy benchmark.
11. **Temporal replay** — a seeded CLI scenario applies an explicit as-of cutoff, withholds later events, and verifies that returned evidence IDs are drawn only from events visible at that time.

## Important behavior and trade-offs

- The local SQLite implementation is for a single-instance development environment, not multi-tenant production use.
- Correlation is deliberately deterministic and explainable. It will miss incidents whose messages differ substantially, and it may group messages that normalize to the same fingerprint even when their causes differ.
- The correlation window is configured with CLOUDOPS_CORRELATION_WINDOW_SECONDS; the default is 300 seconds.
- The general event, deployment, and incident APIs do not authenticate callers. The Alertmanager webhook alone requires a configured bearer token. Keep the API local or on a trusted development network.
- Investigation scores are heuristic ranking scores, not calibrated probabilities.
- The current dashboard refreshes on demand; it does not yet use WebSockets or server-sent events.\n- Deployment correlation uses a one-hour lookback and five-minute lookahead around incident first-seen time. It deliberately does not claim causal attribution.

## Planned evolution

### External alert intake\nThe Alertmanager adapter consumes webhook JSON rather than polling Prometheus. Firing alerts are mapped from labels, annotations, start time, generator URL, and fingerprint into the shared event pipeline. Resolved alerts are reported as ignored notifications and require an operator to close the incident; this avoids treating a delivery as proof that all related symptoms have recovered. The shared token is a minimal integration guard, not a replacement for network controls, TLS, rotation, or a full authentication model.\n\n### Evidence model
Introduce stable evidence records for logs, traces, metrics, deployment events, source revisions, runbooks, and historical incidents. Each record should preserve source, timestamp, tenant, service, and retrieval metadata.

### Investigation engine (partial)
An optional OpenAI adapter is available when OPENAI_API_KEY is configured. The current adapter sends incident metadata and a bounded set of stored events, requests JSON hypotheses, and rejects hypotheses that do not cite valid stored event IDs. If the provider fails, the API falls back to deterministic heuristics. The model does not yet query metrics, traces, deployment history, or service topology. Next steps include a provider-neutral interface, richer schema validation, counter-evidence, and reproducible model evaluation.

### Evaluation
A six-case labelled regression dataset and CLI evaluator now exist for deterministic triage rules. A separate as-of replay fixture verifies that a later event is excluded from investigation evidence. These checks are regression guards only, not production accuracy. Next, create diverse labelled incident scenarios and replay them with a time cutoff. The investigator must not see events or deployment data that arrived after the simulated investigation time. Publish dataset version, baseline, trial count, metric definitions, and known limitations with any score.

### Production storage and services
Move transactional state to PostgreSQL, add authenticated ingestion, background workers, retry/dead-letter handling, tenant-aware authorization, retention policies, rate limits, and audit events before exposing the service to real operational data.
