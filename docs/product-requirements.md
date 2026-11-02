# Product Requirements — CloudOps AI

Status: Phase 0 baseline | Version 1.0 | 2026-11-02

## Product thesis
CloudOps AI will help engineering teams turn production incidents into verified, reusable reliability safeguards. It reconstructs incidents from operational and engineering evidence, compares competing explanations, makes uncertainty and contradictory evidence visible, and converts engineer-validated failure mechanisms into reproducible scenarios and reviewed safeguards. Scenario execution must be isolated; external changes require human approval.

Core loop: incident → evidence → validated mechanism → reproducible scenario → verified safeguard → recurrence tracking.

This is a differentiated product direction, not a claim that no competitor offers similar individual capabilities. Our differentiation must be earned through provenance, replayability, explicit uncertainty and lifecycle continuity.

## Problem
Teams manually correlate alerts, logs, metrics, traces, deployments, configuration changes, revisions and service dependencies. Plausible explanations can be mistaken for proven causes. Postmortems often fail to produce reproducible tests or verified controls, allowing failure mechanisms to recur.

## Target users
- On-call engineers and SREs investigating production incidents.
- Platform engineering teams responsible for reliability.
- Engineering leads responsible for incident review.
- Initial customer profile: small and mid-sized SaaS teams with multiple services, telemetry and Git-based delivery. DevOps consultancies are a secondary segment.

## Jobs to be done
1. Reconstruct the incident timeline.
2. Identify potentially affected services and changes.
3. Compare explanations against inspectable evidence.
4. Understand what is unknown or contradictory.
5. Preserve a confirmed failure mechanism.
6. Reproduce it safely.
7. Validate a safeguard before merge/deployment.
8. Track recurrence and safeguard effectiveness.

## Product principles
1. Evidence before confidence; material claims link to source evidence.
2. Correlation is not causation; temporal proximity is context only.
3. Inconclusive is a valid outcome.
4. Human approval for production changes.
5. Reproducible artifacts over generated prose.
6. Tenant isolation enforced by backend authorization.
7. Core deterministic workflows work without an LLM.
8. Vendor-neutral adapters and stable contracts.
9. UI and docs distinguish shipped, experimental and planned.
10. Secure defaults for secrets and customer telemetry.

## Capability requirements
### Platform foundation (P0)
- Users, authentication and session lifecycle.
- Organizations, workspaces, memberships and invitations.
- Owner, admin, responder and viewer roles with centrally enforced permissions.
- Tenant-scoped operational records.
- Workspace-scoped ingestion credentials with revocation and rotation.
- Audit events.
- PostgreSQL, migrations, backup and restore.

### Operational intelligence (P1)
- Service catalogue, ownership and dependencies.
- Incident explorer, search, filters and pagination.
- Evidence timeline with provenance.
- Deployment, revision and configuration context.
- Explicit blast-radius coverage and limitations.
- Integration health and ingestion lag.

### Investigation (P1)
- Multiple structured hypotheses.
- Evidence references with source, timestamp and identity.
- Supporting, contradicting, contextual, missing and unassessed evidence represented separately.
- Relationship labels that do not imply causality.
- Human review states: unreviewed, accepted, rejected, inconclusive.
- Documented confidence semantics; no uncalibrated probability claims.
- As-of replay and versioned evaluation datasets.

### Failure-to-safeguard (P1)
- Compile only engineer-validated mechanisms into versioned declarative scenarios.
- Scenarios specify preconditions, trigger, expected observations, failure oracle, cleanup and safety boundary.
- Generate proposed regression tests, detection rules or policy checks.
- Preserve source incident, evidence and compiler version.
- Validate in an isolated, allowlisted environment with resource limits.
- Require human approval before PRs or external mutations.
- Track safeguard status and recurrence.

### Collaboration and learning (P2)
- Assignments, comments, ownership and activity history.
- OpenTelemetry logs/metrics/traces; Prometheus and Alertmanager.
- GitHub commits, deployments and PR workflows; Slack notifications.
- Plugin SDK, recurrence detection and safeguard effectiveness analytics.

## Non-goals for first release
- Autonomous production remediation.
- Claims of deterministic root-cause accuracy from synthetic fixtures.
- Replacing observability or paging systems.
- Collecting every telemetry type before customer validation.
- Kafka, Kubernetes or a graph database without measured need.
- Treating model output as confirmed cause.
- Executing arbitrary generated code on the host.
- Multi-region HA or compliance certification before design and validation.

## Success measures
Measure against a pilot baseline: time to first useful evidence-backed hypothesis; time to engineer-confirmed mechanism; evidence validity/coverage; appropriate inconclusive rate; scenario conversion rate; reproducibility; safeguard review/merge rate; recurrence after adoption; retained active teams; contributor activity. Do not claim MTTR or recurrence reduction until measured.

## Release gates
### Internal alpha
One workspace can ingest, investigate and replay a seeded incident; all evidence references resolve; future-evidence leakage is zero; scenario compiler emits schema-valid declarative artifacts without execution; existing regression suite remains green.

### Multi-user beta
Authentication, memberships, RBAC, tenant isolation, revocable ingestion keys, PostgreSQL migrations and backup/restore pass adversarial tests.

### Customer pilot
Secure deployment, operational runbooks, real integration and controlled incident-to-safeguard demonstration; outcomes and limitations documented.

### Public release
Security review, load/recovery testing, retention/deletion/export policies, upgrade policy, release provenance and vulnerability reporting.

## Positioning
Evidence-first incident reconstruction that turns validated production failures into tested reliability safeguards. Avoid claims such as autonomous RCA, guaranteed prevention, 100% accuracy, first or only platform unless independently demonstrated.