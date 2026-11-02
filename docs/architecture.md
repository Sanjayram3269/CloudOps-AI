# Architecture — Current System and Target Platform

Status: Phase 0 architecture baseline | Version 1.0 | 2026-11-02

## 1. Decision summary
CloudOps AI is an early single-instance MVP. The target is a multi-tenant, evidence-first reliability platform with an incident-to-safeguard lifecycle. Target architecture is not shipped functionality. Phase 1 establishes the secure tenant foundation before customer data is used.

## 2. Current implementation
- FastAPI and Pydantic API.
- SQLite persistence initialized by the application.
- Event validation, normalization/fingerprinting and deterministic incident grouping.
- Incident lifecycle and event evidence retrieval.
- Deployment records and bounded temporal context.
- Deterministic investigation plus optional OpenAI hypothesis generation.
- Evidence graph for event, deployment, metric and hypothesis nodes.
- Prometheus read-only metric context.
- Alertmanager webhook protected by configured shared bearer token.
- OTLP/HTTP JSON log ingestion.
- Optional GitHub issue creation.
- Replay and labelled synthetic baseline evaluation.
- Next.js/React/TypeScript dashboard.
- Docker Compose and GitHub Actions CI.

### Current security and scale boundary
General event, deployment and incident routes do not have general user authentication or tenant authorization. Alertmanager uses a configured shared token. SQLite is a local single-instance store. The frontend is a single operational dashboard, not an organization/workspace app. Keep the MVP local or on a trusted development network; do not represent it as production-ready for customer telemetry.

## 3. Current event-to-investigation flow
Producer sends CloudOps event, OTLP JSON log or Alertmanager webhook → FastAPI validates/normalizes → correlation fingerprints service/environment/message → SQLite persists incident/event → incident detail retrieves evidence/deployments → deterministic investigation and optional model adapter → model citations validated against stored event IDs → evidence graph labels citations/context → dashboard displays output. Replay/evaluation scripts guard selected regression behavior.

## 4. Target logical architecture
### Ingestion plane
Authenticated gateway; per-workspace ingestion credentials; rate/size limits; OTLP, Alertmanager, Prometheus and engineering adapters; schema versioning, deduplication, idempotency and provenance. Tenant identity comes from validated credentials, never untrusted event attributes.

### Core data plane
PostgreSQL transactional system of record; tenant-aware repositories and authorization; immutable source evidence with retention/redaction; service catalogue/dependencies; incident correlation; versioned investigation, scenario, run and safeguard records; audit log and outbox for reliable background work.

### Investigation plane
Deterministic diagnostics; optional provider-neutral model adapter; tenant/time-bounded evidence retrieval; supporting, contradicting, contextual, missing and unassessed evidence; explicit uncertainty; replay with as-of cutoff and versioned evaluation datasets.

### Prevention plane
Compiler converts engineer-validated mechanism into declarative scenario; schema/static safety validation; isolated runner with allowlist, quotas, no ambient credentials and cleanup; safeguard proposal; human approval for external mutations; recurrence tracking.

### Experience plane
Organization/workspace web app; service inventory, incident explorer, evidence graph, investigation, deployment history, scenario/safeguard review, collaboration, audit and integration controls.

## 5. Proposed deployment
Next.js web; stateless FastAPI; PostgreSQL; Redis-backed worker only when asynchronous workloads justify it; worker process; object storage for artifacts if needed; TLS ingress; secrets management and observability. Docker Compose remains local path. Kubernetes is not a prerequisite.

## 6. Tenant boundary
Organization owns security, membership and billing; Workspace is operational data boundary. Every workspace-owned row has workspace_id and relevant foreign keys. Every access derives scope from authenticated principal. Cross-workspace references are rejected. Repository methods require explicit tenant context. PostgreSQL RLS may add defense in depth after pooling and transaction context are tested.

## 7. Reliability and consistency
Ingestion idempotency; transactions protect incident/event consistency; outbox for reliable asynchronous side effects; idempotent workers with explicit tenant context; bounded exponential retries and dead-letter state; strict external API timeouts; model failure cannot block deterministic incident access; separate liveness and readiness.

## 8. Security
Secure HttpOnly SameSite sessions and CSRF; scoped API/ingestion credentials; modern password hashing; deny-by-default authorization; hashed secrets, rotation and revocation; TLS and rate limits; telemetry is untrusted data; no autonomous production execution; isolated scenario runner; redaction/retention before third-party model processing. See threat-model.md.

## 9. Technology decisions
| Concern | Baseline | Decision rule |
|---|---|---|
| API | FastAPI/Pydantic | Preserve working contracts |
| Web | Next.js/React/TypeScript | Workspace experience |
| Shared store | PostgreSQL | Multi-user transactional persistence |
| Local demo | SQLite may remain | Never shared multi-tenant production |
| Background work | Redis + worker when needed | Add for real async/retry needs |
| Evidence graph | Relational records/indexed edges | Graph DB only if query patterns justify |
| Telemetry | OpenTelemetry/Prometheus | Vendor-neutral adapters |
| AI | Optional provider-neutral adapter | Deterministic path remains functional |
| Runtime | Docker Compose | Kubernetes only when needed |

## 10. Migration strategy
1. Freeze current behavior with characterization tests. 2. Add PostgreSQL and migration tooling while retaining SQLite local development. 3. Add users, organizations, workspaces and memberships. 4. Add workspace ownership to records/repositories. 5. Import existing SQLite incidents/events/deployments into a selected workspace. 6. Enforce auth on user-facing routes. 7. Add scoped ingestion/integration credentials. 8. Pass adversarial cross-tenant tests. 9. Migrate dashboard to authenticated workspaces. 10. Deprecate unscoped MVP routes through a documented compatibility window.

## 11. Open decisions
Tenant boundary semantics; session/CSRF implementation; migration tooling and SQLite import; credential hashing/rotation; retention/deletion/export; worker/outbox; graph query/indexing; scenario runner isolation; model data governance and evaluation; topology freshness.