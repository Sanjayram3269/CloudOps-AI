# Architecture Notes

## Current vertical slice

The MVP intentionally prioritizes a reproducible path from an event to a visible incident.

1. **API boundary** — FastAPI accepts JSON and validates it with Pydantic. Invalid fields and timezone-naive timestamps are rejected before persistence.
2. **Normalization and fingerprinting** — service, environment, and normalized message text are hashed to a stable fingerprint. Common high-cardinality values such as numbers, UUIDs, and hexadecimal addresses are normalized.
3. **Correlation** — the API looks for a non-resolved incident with the same service, environment, and fingerprint whose last event falls inside the configured correlation window.
4. **Persistence** — SQLite stores incident metadata and each event separately. Each event references its incident, preserving the evidence used for later investigation.
5. **Baseline triage** — a deterministic ruleset matches common message patterns and returns hypotheses with the event IDs that matched. This does not prove causality.
6. **OTLP ingestion** — `/v1/logs` maps OTLP/HTTP JSON resource attributes, severity, timestamps, trace IDs, and deployment metadata into the same validated event/correlation path. A request is capped at 500 records.
7. **Dashboard** — the Next.js app reads the incident list, submits sample events, and loads an incident evidence timeline.
8. **Regression evaluation** — a small labelled synthetic fixture set checks whether deterministic rules continue to produce expected triage categories; it is not a production accuracy benchmark.

## Important behavior and trade-offs

- The local SQLite implementation is for a single-instance development environment, not multi-tenant production use.
- Correlation is deliberately deterministic and explainable. It will miss incidents whose messages differ substantially, and it may group messages that normalize to the same fingerprint even when their causes differ.
- The correlation window is configured with CLOUDOPS_CORRELATION_WINDOW_SECONDS; the default is 300 seconds.
- The current API does not authenticate callers. Keep it local or on a trusted development network.
- Investigation scores are heuristic ranking scores, not calibrated probabilities.
- The current dashboard refreshes on demand; it does not yet use WebSockets or server-sent events.

## Planned evolution

### Evidence model
Introduce stable evidence records for logs, traces, metrics, deployment events, source revisions, runbooks, and historical incidents. Each record should preserve source, timestamp, tenant, service, and retrieval metadata.

### Investigation engine (partial)
An optional OpenAI adapter is available when OPENAI_API_KEY is configured. The current adapter sends incident metadata and a bounded set of stored events, requests JSON hypotheses, and rejects hypotheses that do not cite valid stored event IDs. If the provider fails, the API falls back to deterministic heuristics. The model does not yet query metrics, traces, deployment history, or service topology. Next steps include a provider-neutral interface, richer schema validation, counter-evidence, and reproducible model evaluation.

### Evaluation
A six-case labelled regression dataset and CLI evaluator now exist for deterministic triage rules. These scores are only fixture agreement, not production accuracy. Next, create diverse labelled incident scenarios and replay them with a time cutoff. The investigator must not see events or deployment data that arrived after the simulated investigation time. Publish dataset version, baseline, trial count, metric definitions, and known limitations with any score.

### Production storage and services
Move transactional state to PostgreSQL, add authenticated ingestion, background workers, retry/dead-letter handling, tenant-aware authorization, retention policies, rate limits, and audit events before exposing the service to real operational data.
