# Initial Threat Model

Status: Phase 0 baseline; not a completed security review | 2026-11-02

## Scope and assets
CloudOps AI handles telemetry that may contain secrets, personal data, internal URLs and customer identifiers. Assets: telemetry/evidence; incidents and investigations; identities, sessions and memberships; ingestion/integration/model credentials; scenarios and runner outputs; audit history and customer configuration.

## Trust boundaries
External producer → ingestion API; browser → web/API auth; identity → organization/workspace authorization; API/worker → PostgreSQL/queue; API/worker → model provider and external engineering systems; compiler → isolated runner; runner → test environment/artifact storage.

## Threat register
| Threat | Impact | Required controls |
|---|---|---|
| Cross-tenant object access / IDOR | Data exposure or mutation | Server authorization on every request; adversarial isolation tests |
| Forged ingestion identity | Misleading telemetry | Scoped credentials, rotation, TLS, rate limits, audit |
| Secret leakage in telemetry | Infrastructure compromise | Redaction, restricted access, retention, secret scanning |
| Session theft / CSRF | Unauthorized actions | Secure cookies, CSRF, expiry/revocation, rate limits |
| Oversized/malicious payload | Resource exhaustion/parser risk | Strict schema, byte/record limits, timeouts |
| Prompt injection in logs | Model manipulation | Untrusted-data boundary, no tools, schema and evidence validation |
| Hallucinated causal claim | Incorrect response | Provenance, uncertainty, human confirmation, evaluation |
| Malicious scenario | Host/environment compromise | Declarative schema, isolated runner, allowlists and quotas |
| Unauthorized external side effect | Unapproved PR/deploy | Least privilege, explicit approval, idempotency, audit |
| Worker tenant leakage | Cross-customer exposure | Explicit tenant context in every job/repository call |
| Data loss | Lost incident history | Backups, restore drills, migration validation |
| Supply-chain compromise | Malicious dependency/artifact | Dependency scanning, minimal permissions, release provenance |

## Current MVP exposure
General event, deployment and incident routes lack general authentication and tenant authorization. Alertmanager uses a shared configured bearer token. SQLite is local single-instance storage. Ingestion does not comprehensively redact telemetry. Optional model integration may process event text; provider data handling must be reviewed. GitHub issue creation is an external side effect. Scenario execution does not exist. Keep the MVP local/trusted and do not use production customer data.

## Phase 1 security invariants
1. Deny by default without active membership. 2. Every tenant query/mutation is scoped by authorized workspace. 3. Workspace ID is a selector, not proof of access. 4. Ingestion keys are scoped, hashed, revocable and never logged. 5. Role/key changes are audited. 6. No cross-workspace foreign keys. 7. Telemetry is data, never instructions. 8. Model claims are not verified causes. 9. No production execution of generated scenarios/remediation. 10. Workers preserve explicit tenant context.

## Validation plan
Authorization matrix; cross-tenant read/write/ID tests; key brute-force/rotation/revocation/expiry; CSRF/session lifecycle; payload size/parser/rate-limit/timeouts; secret redaction across logs/errors/model/issue content; prompt-injection fixtures; worker tenant context; scenario schema and sandbox escape tests before runner release; backup restore and deletion/export tests.