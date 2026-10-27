# Initial Threat Model

This is an early-stage checklist, not a completed security review.

## Assets to protect

- Operational logs and traces, which may contain secrets, user identifiers, internal URLs, or customer data.
- Incident evidence and investigation outputs.
- Model-provider credentials and future GitHub integration tokens.
- Incident state and any future external side effects.

## Trust boundaries

- External event producers → API validation boundary.
- Browser client → API origin and CORS boundary.
- API → local database.
- Future application → model provider.
- Future application → GitHub or other engineering systems.

## Current risks and limitations

| Risk | Current state | Required mitigation before production |
|---|---|---|
| Unauthenticated event ingestion | Present in MVP | Authentication, authorization, rate limits, request-size limits |
| Cross-tenant data exposure | No tenant model yet | Tenant identity on every row and query; isolation tests |
| Sensitive values in event messages | Not automatically redacted | Redaction pipeline, configurable retention, restricted access |
| Public exposure of API | No production perimeter | TLS, ingress policy, authentication, monitoring, abuse controls |
| SQLite durability/concurrency limits | Local-only storage | Managed PostgreSQL, backups, migration and recovery testing |
| Model prompt injection via logs | No model call in MVP | Treat logs as untrusted data; isolate instructions, constrain tools, validate outputs |
| Unauthorized GitHub actions | GitHub integration not implemented | Least-privilege tokens, explicit approval, idempotency, audit records |
| Misleading root-cause confidence | Heuristic scores only | Label scores accurately; benchmark and calibrate before making accuracy claims |

## Security rules

1. Never commit real credentials or production telemetry.
2. Do not send sensitive logs to a third-party model until data handling, redaction, and provider retention are reviewed.
3. Treat all log text as untrusted input, not as instructions to an agent.
4. Never execute remediation commands automatically in the initial product.
5. Keep high-impact operations behind explicit human approval and record the decision.
6. Add tests for authorization failures, malformed payloads, oversized input, replay protection, and secret redaction before production use.
