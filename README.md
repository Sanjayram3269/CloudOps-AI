# CloudOps AI
### Evidence-first incident intelligence for modern software systems

> **Your monitoring tells you something broke. CloudOps AI helps you investigate why.**

CloudOps AI is an early-stage incident intelligence platform focused on turning noisy application events into traceable incidents and evidence-linked investigation hypotheses. The project is being built around a practical engineering principle: an incident explanation should point back to the observations that support it.

**Status: early MVP.** Event ingestion, deterministic incident correlation, SQLite persistence, the Next.js dashboard, evidence-linked baseline triage, optional OpenAI-backed hypothesis generation, and configurable GitHub issue creation are implemented. OpenTelemetry ingestion, a richer evidence graph, replay-based evaluation, multi-tenant production controls, and AWS deployment remain planned work.

## What works today

- **Event ingestion API** with Pydantic validation, timezone-aware timestamps, severity, service, environment, trace/deployment identifiers, and attributes.
- **OTLP/HTTP JSON logs ingestion** at `/v1/logs` (plus a namespaced alias), mapping OpenTelemetry resource, scope, severity, timestamp, trace, and attribute fields into the normal correlation pipeline. Requests are capped at 500 records.
- **Deterministic event fingerprinting** that normalizes common high-cardinality values before hashing.
- **Incident grouping** for matching events from the same service and environment inside a configurable time window.
- **Incident lifecycle** with open, investigating, and resolved states.
- **Evidence retention** that links ingested events to their incident and keeps timestamps and trace/deployment context.
- **Evidence-linked investigation** with deterministic fallback heuristics and optional OpenAI-powered hypotheses. Model-supplied evidence IDs are validated against stored events; LLM conclusions remain unverified.
- **Next.js dashboard** showing incident counts and queue details, with a sample-event form, an evidence timeline, and trace/deployment context.
- **Docker Compose setup** for local API and web development.
- **Optional GitHub issue creation** using an explicitly configured token and repository, with incident markers to reuse an existing issue on repeat requests.
- **Seeded evaluation harness** that runs labelled deterministic-triage regression cases and reports Top-1/Top-3 fixture agreement. This is a regression check, not a production root-cause accuracy claim.
- **Temporal incident replay** that applies an explicit investigation cutoff, withholds later events, and checks that returned evidence references do not include future event IDs.
- **Backend tests and GitHub Actions CI** for core API flows.

## Product direction

Production incidents rarely reveal their cause in one log line. A latency spike may be a downstream timeout; an error burst may follow a deployment; many alerts may describe one underlying failure.

CloudOps AI is being designed as a vendor-neutral investigation layer that brings operational signals and engineering context together. Its longer-term goal is to correlate events, compare plausible failure hypotheses, gather supporting and contradictory evidence, and produce reviewable next steps.

The differentiator is **not just asking an LLM to summarize logs**. It is making investigations inspectable and testable.

## Current architecture

~~~mermaid
flowchart LR
    A[Sample event / API client] --> B[FastAPI validation]
    B --> C[Normalize and fingerprint]
    C --> D[SQLite persistence]
    D --> E[Incident correlation]
    E --> F[Incident queue API]
    D --> G[Evidence-linked baseline triage]
    F --> H[Next.js dashboard]
    G --> I[Hypotheses + evidence IDs + next checks]
~~~

The current vertical slice is intentionally small and runnable. The broader target architecture adds telemetry adapters, deployment/commit context, an evidence graph, LLM-assisted hypothesis evaluation, replay-based benchmarking, and reviewed engineering integrations.

## Technology stack

| Layer | Current implementation | Planned extension |
|---|---|---|
| API | Python, FastAPI, Pydantic | Authenticated ingestion and integration adapters |
| Persistence | SQLite for local MVP | PostgreSQL for multi-user deployment |
| Correlation | Deterministic message fingerprint + service/environment + time window; nearby deployment context by service/environment/time | Trace, topology, and semantic correlation |
| Investigation | Deterministic message-pattern baseline and optional OpenAI adapter with linked evidence IDs | Provider-neutral investigation, counter-evidence, and measured calibration |
| Telemetry intake | CloudOps event JSON + OTLP/HTTP JSON logs | Collector deployment and traces/metrics ingestion |
| Evaluation | Six labelled synthetic regression fixtures | Versioned incident replay with time-cutoff enforcement and broader ground-truth datasets |
| Web | Next.js, React, TypeScript | Incident details, timeline, evidence and evaluation views |
| Local runtime | Docker Compose | Hardened cloud deployment |
| CI | GitHub Actions, pytest | Frontend build, security checks and broader integration tests |

## Quick start

### Requirements

- Python 3.11+
- Node.js 22+ and npm
- Docker Desktop (optional, for Compose)

### 1. Start the API

From the repository root:

~~~bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
~~~

The API creates a local SQLite database at data/cloudops.db on startup by default. Override CLOUDOPS_DB_PATH to change its location.

- Health: http://localhost:8000/health
- Interactive API docs: http://localhost:8000/docs

### 2. Start the web dashboard

In a second terminal:

~~~bash
cd frontend
npm install
npm run dev
~~~

Open http://localhost:3000. The browser app expects the API at http://localhost:8000 by default. To use a different API origin, set NEXT_PUBLIC_API_BASE_URL before building/running the frontend.

### 3. Or run with Docker Compose

From the repository root:

~~~bash
docker compose up --build
~~~

Then open the dashboard at http://localhost:3000 and API docs at http://localhost:8000/docs. Compose persists SQLite data in the cloudops-data volume.

## Try the API

Send an event:

~~~bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "service": "checkout-api",
    "environment": "demo",
    "severity": "error",
    "message": "upstream request timeout after 30 seconds",
    "trace_id": "trace-demo-001"
  }'
~~~

Send a second event with a similar message from the same service/environment. Within the correlation window, the API should group it with the existing open incident.

List incidents:

~~~bash
curl http://localhost:8000/api/v1/incidents
~~~

Fetch an incident and its event evidence:

~~~bash
curl http://localhost:8000/api/v1/incidents/1
~~~

Run baseline triage:

~~~bash
curl -X POST http://localhost:8000/api/v1/incidents/1/investigate
~~~

Update incident status:

~~~bash
curl -X PATCH http://localhost:8000/api/v1/incidents/1/status \
  -H "Content-Type: application/json" \
  -d '{"status":"investigating"}'
~~~

Use the incident ID returned by your own API response instead of assuming it is 1.

### Send OpenTelemetry logs (OTLP/HTTP JSON)

OpenTelemetry exporters commonly send an `ExportLogsServiceRequest` JSON body to `/v1/logs`. CloudOps AI also exposes `/api/v1/telemetry/otlp/v1/logs` as a namespaced alias.

~~~bash
curl -X POST http://localhost:8000/v1/logs \
  -H "Content-Type: application/json" \
  -d '{
    "resourceLogs": [{
      "resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "checkout-api"}},
        {"key": "deployment.environment.name", "value": {"stringValue": "demo"}}
      ]},
      "scopeLogs": [{
        "logRecords": [{
          "timeUnixNano": "1767225600000000000",
          "severityNumber": 17,
          "severityText": "ERROR",
          "body": {"stringValue": "upstream request timeout after 30 seconds"},
          "traceId": "0123456789abcdef0123456789abcdef"
        }]
      }]
    }]
  }'
~~~

The endpoint returns accepted-record counts and the incident IDs assigned by the normal correlation engine. The adapter currently supports OTLP JSON logs, not OTLP protobuf, traces, or metrics. An optional Collector pipeline example is in `examples/otel-collector.yaml`; its `api:8000` endpoint assumes the collector joins the same Compose network as the API.

### Record a deployment

~~~bash
curl -X POST http://localhost:8000/api/v1/deployments \
  -H "Content-Type: application/json" \
  -d '{
    "service": "checkout-api",
    "environment": "demo",
    "deployment_id": "deploy-2026-10-28-01",
    "version": "1.4.2",
    "commit_sha": "abc123def456",
    "actor": "github-actions",
    "outcome": "succeeded",
    "deployed_at": "2026-10-28T12:00:00Z",
    "metadata": {"pipeline": "release"}
  }'
~~~

Incident details and investigations include matching deployments from the same service/environment within one hour before through five minutes after the incident's first event. This is temporal context only; it does not establish that a deployment caused the incident. Re-sending the same service/environment/deployment ID updates the existing deployment record.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Health check |
| POST | /api/v1/events | Validate and ingest an event; create or update a correlated incident |
| GET | /api/v1/incidents | List recent incidents |
| GET | /api/v1/incidents/{id} | Retrieve incident and stored event evidence |
| PATCH | /api/v1/incidents/{id}/status | Change incident status |
| POST | /api/v1/incidents/{id}/investigate | Generate evidence-linked hypotheses; use OpenAI when configured, otherwise deterministic triage |
| POST | /api/v1/incidents/{id}/github-issue | Create or reuse a structured GitHub issue (requires explicit credentials) |

## Configuration

Copy .env.example to .env if you want to keep local settings in one place. Environment variables are read by the API process; a dotenv loader is not currently included, so export variables in your shell or configure them in your process manager/Compose environment.

| Variable | Default | Purpose |
|---|---|---|
| CLOUDOPS_DB_PATH | ./data/cloudops.db | SQLite database path |
| CLOUDOPS_CORS_ORIGINS | http://localhost:3000 | Comma-separated allowed browser origins |
| CLOUDOPS_CORRELATION_WINDOW_SECONDS | 300 | Maximum time gap for grouping matching events |
| NEXT_PUBLIC_API_BASE_URL | http://localhost:8000 | API base URL used by the web client |

OPENAI_API_KEY enables optional LLM-assisted investigation; OPENAI_MODEL defaults to gpt-4.1-mini. Without a key, the API uses deterministic heuristics. GITHUB_TOKEN and GITHUB_REPOSITORY (owner/repo) enable optional issue creation. Never commit real credentials. The API currently has no authentication, so keep it local; do not expose configured write credentials on a public instance.

## Baseline evaluation

Run the labelled synthetic regression set:

~~~bash
python scripts/evaluate_baseline.py
python scripts/evaluate_baseline.py --output artifacts/baseline-evaluation.json --min-top1 1.0
~~~

The report measures Top-1 and Top-3 agreement for six hand-labelled fixtures that exercise the current deterministic rules. These scores only verify that known rules still behave as expected on this small synthetic dataset. They are **not** estimates of real-world root-cause accuracy. A meaningful benchmark needs diverse labelled incidents, temporal replay, and blind evaluation.

### Replay an incident as of a timestamp

~~~bash
python scripts/replay_incident.py
python scripts/replay_incident.py --output artifacts/replay-report.json
~~~

The seeded scenario contains three events available at the investigation cutoff and one deliberately later event. The replay report shows which event IDs were visible, which were withheld, the resulting hypotheses, and whether future evidence leaked into the result. This is a temporal-correctness regression fixture—not a broad incident-reconstruction benchmark.

## Tests

From the repository root:

~~~bash
pip install -r requirements.txt
pytest
~~~

The current tests cover health, event validation, event correlation, service isolation, evidence-linked baseline investigation, incident status updates, GitHub configuration handling, and sensitive-value redaction. CI runs the backend test suite on pushes and pull requests to main.

## Roadmap

### Phase 1 — Reliable vertical slice
- [x] Validated event ingestion API
- [x] Deterministic fingerprints and time-window incident grouping
- [x] Persist events and incidents locally
- [x] Incident queue UI and sample-event form
- [x] Evidence-linked triage endpoint with deterministic fallback and optional LLM adapter
- [x] OTLP/HTTP JSON logs ingestion with bounded record count and metadata mapping
- [x] Incident evidence timeline in the dashboard
- [x] Seeded baseline regression evaluator
- [x] As-of incident replay with a future-evidence leakage check
- [x] Backend tests and CI workflow
- [x] Incident evidence timeline and investigation output in the dashboard queue
- [ ] Improve event deduplication semantics and add explicit correlation explanations

### Phase 2 — Context-aware investigation
- [x] OpenTelemetry-compatible OTLP/HTTP JSON log ingestion
- [ ] Collector example, traces/metrics ingestion, and protobuf transport
- [x] Deployment event intake, commit SHA capture, and nearby deployment context
- [ ] Service/dependency context and evidence graph
- [ ] Provider-agnostic LLM adapter with schema-validated outputs
- [ ] Multiple hypotheses, counter-evidence, and calibrated evaluation

### Phase 3 — Integrations and evaluation
- [x] GitHub issue creation with incident-marker reuse and reviewable evidence
- [x] Seeded deterministic-triage regression scenarios
- [x] Single-scenario replay with a time cutoff and future-evidence leakage check
- [ ] Broader multi-incident replay harness with richer ground truth and statistical reporting
- [ ] Root-cause Top-1/Top-3, evidence quality, grouping, latency, and cost metrics
- [ ] Multi-tenant authentication, authorization, audit trails, rate limits, and secret redaction
- [ ] AWS deployment and operational runbooks

## Engineering principles

1. **Evidence before assertion:** tie hypotheses to stored event IDs and source timestamps.
2. **Honest uncertainty:** baseline heuristics are triage aids, not proof of root cause.
3. **Deterministic core:** event validation, fingerprinting, persistence, and state changes should be testable without an LLM.
4. **Temporal correctness:** replay must never expose information that would not have been available at investigation time.
5. **Safe integrations:** use least privilege, idempotency, audit trails, and human approval before high-impact changes.
6. **Privacy by design:** logs can contain secrets and personal data; redact and minimize data before production use.

## Security and limitations

This is an early development project and is **not production-ready**. It currently has no user authentication or tenant isolation, and SQLite is intended for local development only. The LLM adapter redacts several common credential assignment patterns before sending log text, but that is not a comprehensive secret or PII scrubber. Do not connect it to sensitive production telemetry or expose it to the public internet without authentication, authorization, robust redaction, retention controls, rate limits, audit coverage, and a security review.

The deterministic fallback uses message-pattern heuristics. When enabled, the LLM receives redacted event messages and incident metadata; it does not inspect metrics, traces, deployments, source code, or external dependency state. Confidence values are heuristic/model-provided scores, not statistically calibrated probabilities. GitHub issue creation is an external side effect and must only be enabled in a trusted, authenticated environment.

## Contributing

Issues and pull requests are welcome. Include a clear problem statement, tests for changed behavior, and reproducible evidence for performance or accuracy claims. Never submit credentials, production logs, customer data, or other sensitive information.

## License

No license has been selected yet. Until a license file is added, reuse and redistribution permissions should not be assumed.
