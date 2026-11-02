# Acceptance Criteria and Test Strategy

Status: Phase 0 baseline | Version 1.0 | 2026-11-02

## Phase 0 completion
- Product thesis, users, problem, principles, scope and non-goals documented.
- Current implementation audited and separated from planned capabilities.
- Domain entities, ownership, tenant boundaries and authorization documented.
- API conventions and endpoint groups documented.
- Acceptance gates and test strategy defined.
- Existing MVP behavior preserved by documentation-only changes.

## Existing behavior preservation baseline
### Ingestion and correlation
- Valid event accepted and persisted; malformed payload and naive timestamp rejected.
- Fingerprint normalization and correlation window behavior remain stable.
- Different services/environments do not share incidents incorrectly.
- Severity aggregation and incident lifecycle remain consistent.
- OTLP JSON resource/scope/severity/time/trace/deployment metadata preserved; malformed and empty payloads rejected; record limit enforced.
- Alertmanager disabled without configured token; invalid token rejected; resolved notification does not silently resolve incident.

### Investigation and evidence
- Incident detail returns stored evidence.
- Deterministic investigation works without model provider.
- Model citations must reference event IDs belonging to the incident.
- Provider failure falls back safely.
- Evidence graph preserves source identity and relationship semantics.
- Temporal deployment and metric context are not causal proof.
- Counter-evidence remains explicitly not evaluated until implemented.
- As-of replay excludes future event IDs.
- Synthetic evaluation is not marketed as production accuracy.

### Deployments, metrics and integrations
- Deployment upsert and bounded temporal context remain stable.
- Prometheus calls remain read-only, bounded and non-blocking to baseline investigation.
- GitHub issue creation requires explicit configuration and redacts secrets.
- Dashboard API response contracts remain compatible.

### Frontend and runtime
- Dashboard load, API error, search, filters and lifecycle actions work.
- Evidence timeline, investigation, metrics and GitHub issue action retain error handling.
- Frontend lint and production build pass.
- Docker images build.
- CI runtime snapshot still verifies Alertmanager-to-dashboard flow.

## Phase 1 identity acceptance
- Registration validates email and duplicate normalized addresses.
- Passwords use a modern password hash; plaintext never persisted or logged.
- Login errors do not disclose account existence; rate limits apply.
- Secure HttpOnly SameSite cookies and CSRF protection for browser mutations.
- Logout invalidates session; expiry/revocation tested.

## Phase 1 authorization and tenant isolation
- Organization creation and owner membership are atomic.
- Workspaces are only visible/manageable to authorized members.
- Invitations expire, are single-use and revocable.
- Owner/admin/responder/viewer matrix is enforced server-side.
- Viewer cannot mutate; responder cannot administer membership or credentials.
- Membership removal immediately revokes access.
- Two tenants are seeded; tenant A cannot read/write/investigate tenant B by changing IDs, query or payload.
- Ingestion credentials cannot write cross-tenant; cross-tenant service references rejected.
- Background jobs require tenant context.
- No endpoint relies on frontend filtering for security.

## Credential and PostgreSQL acceptance
- Ingestion secret shown only once, stored hashed, scoped, expiring, revocable and rotatable.
- Old key invalid after rotation/revocation; authorization headers never logged.
- Sensitive changes create audit events.
- Fresh migration and supported SQLite import preserve incidents/events/deployments.
- Foreign keys, unique constraints and indexes tested.
- Backup and restore exercised; failed migration does not silently discard data.

## Investigation evaluation
Versioned labelled cases include timelines, as-of cutoffs, relevant evidence, expected hypothesis classes, alternatives, contradictory evidence and inconclusive cases. Report evidence precision/recall, top-k agreement, unsupported-claim rate, inconclusive handling, future leakage (must be zero) and reproducibility. Never present synthetic fixture scores as production accuracy.

## Scenario and safeguard acceptance
- Only engineer-validated mechanisms compile.
- Output conforms to versioned declarative schema and retains source provenance/compiler version.
- Unsafe/incomplete scenarios rejected; first compiler does not execute host commands.
- Future runner is isolated, allowlisted, bounded and cleans up.
- Runs retain environment and artifact digests.
- External PR/policy changes require human approval and audit.
- Recurrence matching exposes features/threshold and distinguishes similarity from identity.

## Quality attributes
Security: authorization matrix, tenant isolation, redaction and threat review. Reliability: idempotency, bounded retries, graceful dependency failure, backup/restore. Performance: define workload and measure before publishing SLOs. Accessibility: keyboard, labels, focus, contrast and screen-reader checks. Observability: request IDs, metrics, readiness and worker failures. Maintainability: type checks, lint, migrations, API contract tests and upgrade docs.

## Required CI gates
1. Backend unit/API tests. 2. PostgreSQL migration/integration tests. 3. Tenant isolation tests. 4. Replay/evaluation checks. 5. Frontend lint/typecheck/build. 6. API contract compatibility. 7. Container build. 8. Dependency/security scanning. 9. End-to-end ingestion-to-investigation. 10. Scenario schema/safety validation.

## Definition of done
Document domain behavior and API contract; enforce and test server authorization; cover malformed input and failure paths; understand migration/recovery; implement frontend loading/empty/success/error states; pass local and CI tests; review security/observability; update docs/demo; ensure claims match shipped behavior.