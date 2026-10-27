# CloudOps AI
### Evidence-first incident intelligence for modern software systems

> **Your monitoring tells you something broke. CloudOps AI helps you investigate why.**

CloudOps AI is an early-stage incident intelligence platform focused on turning noisy application events into traceable incidents and evidence-linked investigation hypotheses. The project is being built around a practical engineering principle: an incident explanation should point back to the observations that support it.

**Status: early MVP.** Event ingestion, deterministic incident correlation, SQLite persistence, an incident dashboard, and baseline evidence-linked triage are implemented. The LLM-powered investigation pipeline, OpenTelemetry ingestion, evidence graph, GitHub issue creation, and production AWS deployment remain planned work.

## What works today

- **Event ingestion API** with Pydantic validation, timezone-aware timestamps, severity, service, environment, trace/deployment identifiers, and attributes.
- **Deterministic event fingerprinting** that normalizes common high-cardinality values before hashing.
- **Incident grouping** for matching events from the same service and environment inside a configurable time window.
- **Incident lifecycle** with open, investigating, and resolved states.
- **Evidence retention** that links ingested events to their incident and keeps timestamps and trace/deployment context.
- **Evidence-linked investigation** with deterministic fallback heuristics and optional OpenAI-powered hypotheses. Model-supplied evidence IDs are validated against stored events; LLM conclusions remain unverified.
- **Next.js dashboard** showing incident counts and queue details, with a form to send sample events.
- **Docker Compose setup** for local API and web development.
- **Optional GitHub issue creation** using an explicitly configured token and repository, with incident markers to reuse an existing issue on repeat requests.
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
| Correlation | Deterministic message fingerprint + service/environment + time window | Trace, deployment, topology, and semantic correlation |
| Investigation | Deterministic message-pattern baseline with linked evidence IDs | Provider-agnostic LLM investigation with schema validation and counter-evidence |
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

## Tests

From the repository root:

~~~bash
pip install -r requirements.txt
pytest
~~~

The current tests cover health, event validation, event correlation, service isolation, evidence-linked baseline investigation, and incident status updates. CI runs the backend test suite on pushes and pull requests to main.

## Roadmap

### Phase 1 — Reliable vertical slice
- [x] Validated event ingestion API
- [x] Deterministic fingerprints and time-window incident grouping
- [x] Persist events and incidents locally
- [x] Incident queue UI and sample-event form
- [x] Evidence-linked deterministic triage endpoint
- [x] Backend tests and CI workflow
- [ ] Incident detail view with timeline and investigation output in the UI
- [ ] Improve event deduplication semantics and add explicit correlation explanations

### Phase 2 — Context-aware investigation
- [ ] OpenTelemetry-compatible logs/traces/metrics ingestion
- [ ] Deployment and GitHub commit metadata
- [ ] Service/dependency context and evidence graph
- [ ] Provider-agnostic LLM adapter with schema-validated outputs
- [ ] Multiple hypotheses, counter-evidence, and calibrated evaluation

### Phase 3 — Integrations and evaluation
- [ ] GitHub issue creation with idempotency and reviewable evidence
- [ ] Seeded incident scenarios and replay without future-data leakage
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

This is an early development project and is **not production-ready**. It currently has no user authentication or tenant isolation, and SQLite is intended for local development only. Do not connect it to sensitive production telemetry or expose it to the public internet without adding authentication, authorization, retention controls, secret redaction, rate limits, audit coverage, and a security review.

The deterministic fallback uses message-pattern heuristics. When enabled, the LLM receives only stored event messages and incident metadata; it does not inspect metrics, traces, deployments, source code, or external dependency state. Confidence values are heuristic/model-provided scores, not statistically calibrated probabilities. GitHub issue creation is an external side effect and must only be enabled in a trusted, authenticated environment.

## Contributing

Issues and pull requests are welcome. Include a clear problem statement, tests for changed behavior, and reproducible evidence for performance or accuracy claims. Never submit credentials, production logs, customer data, or other sensitive information.

## License

No license has been selected yet. Until a license file is added, reuse and redistribution permissions should not be assumed.
