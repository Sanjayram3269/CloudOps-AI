# Domain Model and API Contracts

Status: Phase 0 design baseline; not implemented | Version 1.0 | 2026-11-02

## Design constraints
- Every tenant-owned record belongs to an organization/workspace boundary.
- Every read/write is authorized server-side; workspace IDs are selectors, not proof of access.
- Use UUIDs for new platform entities; preserve existing integer IDs during migration.
- Store UTC instants and accept timezone-aware timestamps.
- Secrets are hashed where verification is required and shown only once at creation.
- Preserve raw/normalized provenance and use idempotency for retryable writes.
- Integration adapters remain separate from domain logic.

## Entity catalogue
| Entity | Purpose / relationships |
|---|---|
| User | Human identity and account state |
| Organization | Tenant security and billing root; owns workspaces and memberships |
| Workspace | Operational data boundary |
| OrganizationMembership | User role and membership lifecycle |
| WorkspaceMembership | Optional narrower workspace access |
| Service | Workspace-owned software component |
| ServiceDependency | Directed relationship between same-workspace services |
| IngestionCredential | Scoped producer credential for a workspace |
| Event | Immutable telemetry observation linked to service and incident |
| Incident | Grouped operational failure |
| Deployment | Release/change observation |
| Investigation | Versioned analysis run |
| Hypothesis | Candidate explanation in an investigation |
| EvidenceReference | Provenance-preserving pointer to source observation |
| FailureScenario | Versioned declarative reproduction of a validated mechanism |
| ScenarioRun | Isolated execution record and artifacts |
| Safeguard | Proposed/adopted test, rule or policy |
| RecurrenceObservation | Later signal matching a known failure signature |
| AuditEvent | Append-only security/workflow activity |

## Ownership and authorization
Organization owns workspaces and organization memberships. Workspace owns services, dependencies, ingestion credentials, events, incidents, deployments, investigations, scenarios, runs, safeguards and recurrence observations. Users require active membership. Roles: owner (full organization control), admin (manage workspaces/integrations/members except ownership transfer), responder (operational and investigation workflows), viewer (read-only). Workspace restrictions may narrow but never silently elevate access. Ingestion credentials are service principals scoped to one workspace. Workers carry explicit tenant context. Deny by default.

## Relational constraints
- Unique normalized user email; unique organization slug; workspace slug unique within organization.
- Unique organization/user membership and workspace/user membership.
- Service key unique per workspace.
- Dependency endpoints must belong to the same workspace.
- Ingestion key stores secret hash, scopes, expiry, revocation and last-used metadata.
- Events and incidents require workspace_id; idempotency keys unique per workspace when supplied.
- Deployments unique by workspace/service/deployment ID.
- Investigation runs are versioned and immutable.
- Evidence references must resolve to source records in the same workspace.
- Scenario versions immutable once published; runs reference exact versions.
- Audit interface append-only.
- PostgreSQL row-level security may be defense in depth, not a replacement for application authorization.

## API conventions
Base path /api/v1. JSON bodies; RFC 3339 timestamps; normalized UTC. Standard error: {error:{code,message,request_id}}. Cursor pagination with bounded limit and stable timestamp/ID ordering. Use Idempotency-Key for retryable mutations. Workspace routes explicitly include workspace_id and check membership on every request. Secure HttpOnly SameSite browser sessions require CSRF protection; API clients use scoped short-lived credentials. Never expose stack traces or database internals.

## Proposed endpoint groups
### Identity and organization
- POST /api/v1/auth/register, /login, /logout
- GET /api/v1/me and /api/v1/organizations
- POST /api/v1/organizations
- GET /api/v1/organizations/{organization_id}/members
- POST /api/v1/organizations/{organization_id}/invitations
- PATCH /api/v1/organizations/{organization_id}/members/{user_id}

### Workspace and credentials
- GET/POST /api/v1/organizations/{organization_id}/workspaces
- GET /api/v1/workspaces/{workspace_id}
- GET /api/v1/workspaces/{workspace_id}/members
- GET/POST /api/v1/workspaces/{workspace_id}/ingestion-keys
- POST /api/v1/workspaces/{workspace_id}/ingestion-keys/{key_id}/rotate
- DELETE /api/v1/workspaces/{workspace_id}/ingestion-keys/{key_id}

### Operations and investigation
- GET /api/v1/workspaces/{workspace_id}/incidents
- POST /api/v1/workspaces/{workspace_id}/events and /deployments
- GET /api/v1/workspaces/{workspace_id}/incidents/{incident_id}
- PATCH /api/v1/workspaces/{workspace_id}/incidents/{incident_id}
- POST /api/v1/workspaces/{workspace_id}/incidents/{incident_id}/investigations

### Scenarios and safeguards
- POST /api/v1/workspaces/{workspace_id}/incidents/{incident_id}/scenarios
- GET /api/v1/workspaces/{workspace_id}/scenarios/{scenario_id}
- POST /api/v1/workspaces/{workspace_id}/scenarios/{scenario_id}/runs
- POST /api/v1/workspaces/{workspace_id}/scenarios/{scenario_id}/safeguards
- POST /api/v1/workspaces/{workspace_id}/safeguards/{safeguard_id}/approve or /reject
- GET /api/v1/organizations/{organization_id}/audit-events

## FailureScenario initial contract
Required conceptual fields: schema_version, title, description, source_incident_id, source_investigation_id, validated_mechanism, validated_by, preconditions, typed bounded trigger, expected_observations, failure_oracle, cleanup, safety_profile, generated_artifacts (type, digest, generator version), review_status and timestamps. Scenario is declarative, not arbitrary executable code. No production target. Runner later requires isolated allowlisted environment, resource/time limits, no ambient host credentials, bounded network and cleanup. First compiler milestone emits validated JSON only.

## Existing API compatibility
Current MVP routes include GET /api/v1/incidents, POST /api/v1/events, POST /api/v1/deployments, GET /api/v1/incidents/{id}, PATCH /api/v1/incidents/{id}/status, POST /api/v1/incidents/{id}/investigate, POST /api/v1/integrations/alertmanager and POST /v1/logs. General routes currently lack user authentication and tenant authorization; Alertmanager uses a configured shared bearer token. These are development MVP contracts, not multi-tenant secure APIs. Phase 1 must add scoped routes/credentials and a deliberate compatibility/deprecation plan. Never infer tenant from untrusted event attributes.

## Decisions required before implementation
Confirm strict data boundary semantics; session/password implementation; invitation delivery/expiry; role inheritance; key format/hash/rotation; RLS and connection pooling; retention/deletion/export; compatibility window; worker/outbox choice; scenario runner isolation technology.