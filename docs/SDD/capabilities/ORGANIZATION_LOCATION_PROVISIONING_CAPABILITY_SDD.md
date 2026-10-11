# RESTAURANT INTELLIGENCE PLATFORM
# ORGANIZATION / LOCATION / MINIMAL PROVISIONING CAPABILITY SOFTWARE DESIGN DOCUMENT

**Capability:** Organization / Location / Minimal Provisioning
**Document:** `ORGANIZATION_LOCATION_PROVISIONING_CAPABILITY_SDD.md`
**Template:** `CAPABILITY_SDD_TEMPLATE.md`
**Status:** CERTIFIED AS-BUILT
**Version:** 0.1.0
**Owner:** Enterprise Core
**Last Updated:** 2026-10-10

---

# 1. PURPOSE

Define the capability-specific technical design for Tenant-safe Organization and Location
management, one current headquarters Location per operational Organization, and minimal
provisioning of Organization, Location, and Staff access without Restaurant commercial data.

This document defines the approved capability design from the five P02 decisions approved on
2026-10-10. Approval does not implement or certify the capability.

---

# 2. AUTHORITY

## 2.1 Governing Sources

```text
Product Authority:
  - P02-D01 through P02-D04, approved by the Project Operator acting as Product Owner and
    Architecture Authority on 2026-10-10; approval evidence is recorded in Section 2.3.
Domain Authority:
  - domain-packs/restaurant/RESTAURANT_DOMAIN_MODEL.md
  - domain-packs/restaurant/01_Restaurant_Organization.md
  - domain-packs/restaurant/02_Restaurant_Locations.md
  - domain-packs/restaurant/39_Restaurant_Business_Rules.md (BR-CORE-002..004,
    BR-ORG-001..003, BR-LOC-001..004)
Global Architectural Authority:
  - AGENTS.md
  - docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
Global SDD:
  - docs/SDD/GLOBAL_SDD.md (APPROVED, version 0.2.0)
Applicable ADRs: None found
Security Baseline: docs/SDD/GLOBAL_SDD.md Section 18
Reuse Policy: docs/SDD/GLOBAL_SDD.md Section 32
Related Capability SDD:
  - docs/SDD/capabilities/IDENTITY_AUTHORIZATION_CAPABILITY_SDD.md
Approved cross-capability architecture decision:
  - P02-D05 caller-owned Identity transaction participation, approved 2026-10-10
```

P02-D01 through P02-D05 are the approved decisions registered by this design. They supplement
the cited Domain Authority only within this capability boundary and do not authorize unrelated
Organization, Location, Identity, or Restaurant behavior.

## 2.2 Authority of This SDD

This approved document is authoritative only for the technical design of this capability.
Prompts, implementation, and tests do not independently redefine it.

## 2.3 Approval Record

```text
Document path: docs/SDD/capabilities/ORGANIZATION_LOCATION_PROVISIONING_CAPABILITY_SDD.md
Document version: 0.1.0
Approving authority/role: Project Operator acting as Architecture Authority
Explicit decision: APPROVED
Decision date: 2026-10-10
Approval evidence/reference: Explicit operator approval in “P02 — FORMAL APPROVAL
  REGISTRATION — IDENTITY TRANSACTION AMENDMENT — FINAL”, received 2026-10-10
Open conditions: NONE. The Identity & Authorization SDD transaction-participation amendment
  version 0.2.0 was explicitly approved on 2026-10-10 before P02 implementation.
```

This approval applies only to version 0.1.0. It authorizes the recorded design. The prerequisite
Identity amendment condition was satisfied by explicit approval of Identity & Authorization SDD
version 0.2.0 on 2026-10-10.

Approved decision registration:

```text
Decisions: P02-D01, P02-D02, P02-D03, P02-D04, P02-D05 — APPROVED
Approving role: Project Operator acting as Product Owner and Architecture Authority
Decision date: 2026-10-10
Evidence: Explicit operator approval in the conversation following the P02 SDD gap report
Open decision conditions: NONE
```

| Decision | Registered rule |
|---|---|
| P02-D01 | Every operational Organization has exactly one current same-Tenant, same-Organization headquarters Location. |
| P02-D02 | Initial configuration may temporarily lack headquarters; activation requires one ACTIVE headquarters; the first Location becomes headquarters and later Locations preserve it. |
| P02-D03 | Authorized replacement is atomic, scoped, concurrency-safe, and auditable; deactivating/retiring the current headquarters while operational requires an ACTIVE replacement in the same transition. |
| P02-D04 | Minimal provisioning runs only in an existing Tenant by an existing authorized administrator and creates no Tenant, initial administrator, new permission semantics, administrative role, or commercial data. |
| P02-D05 | Identity access provisioning supports caller-owned begin/commit/rollback without internal commit in participant mode while current consumers retain existing behavior. |

---

# 3. CAPABILITY BOUNDARY

## Owns

- Organization and Location persistence lifecycle within a Tenant.
- The Organization-to-current-headquarters relationship and its integrity.
- Atomic first-Location/headquarters establishment and headquarters replacement.
- Guarding Organization/Location state changes that could invalidate headquarters.
- A controlled minimal provisioning transaction and its non-sensitive execution evidence.

## Does Not Own

- Authentication, credential hashing, sessions, memberships, roles, permissions, or Location
  grants; these remain owned by Identity & Authorization.
- Restaurant commercial configuration or operational records.
- Restaurant onboarding imports or `bootstrap_pilot_minimum`.
- Role policy, role-permission composition, or automatic administrator grants.
- Frontend workflows, external integrations, or cross-Tenant relationships.

---

# 4. SCOPE, NON-GOALS AND DEFERRED

## 4.1 In Scope

- One current headquarters reference for each Organization in the authority-defined operational
  state.
- First Location creation, additional Location creation, headquarters replacement, and relevant
  deactivation guards.
- Minimal deterministic provisioning that composes existing Enterprise Core services.
- Forward-only migration and focused isolated certification.

## 4.2 Non-Goals / Out of Scope

- Restaurant tables, groups, registers, cash activation, products, menus, pricing, recipes,
  inventory, warehouses, purchasing, sales, payments, fiscal data, preparation, printing,
  connectors, payment executors, or synthetic commercial records.
- New permission semantics, role policy, Staff Login redesign, general onboarding redesign,
  frontend work, or new runtime infrastructure.

## 4.3 Deferred

| ID | Requirement | Reason | Dependency | Blocking |
|---|---|---|---|---|
| D-001 | User-facing headquarters administration | Not required for controlled provisioning | Future approved UX scope | NO |
| D-002 | General Organization onboarding workflow | Broader than minimal provisioning | Separate approved capability | NO |

---

# 5. EXISTING SYSTEM / DISCOVERY BASELINE

```text
Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Commit: d6810e98f2b2fc7c871afe507f15c34446dd628b
Migration head: 0068_schema_collation_alignment

Relevant backend:
  apps/api/app/models/organization.py
  apps/api/app/api/routes/organizations.py
  apps/api/app/api/routes/locations.py
  apps/api/app/bootstrap_admin.py
  apps/api/app/identity/access_provisioning.py
  apps/api/app/identity/permission_catalog.py
Relevant frontend: N/A
Relevant tables:
  tenants, organizations, locations, users, tenant_memberships, roles, permissions,
  role_permissions, membership_roles, membership_location_grants, membership_location_roles
Relevant endpoints:
  /organizations, /locations, /identity/access-provisioning, /identity/access-provisioning/staff
Relevant tests:
  test_organization_location_foundation.py, test_identity_access_provisioning.py,
  test_auth_foundation.py, test_staff_auth_sessions.py,
  test_staff_credential_administration.py, test_staff_location_authorization.py
```

The Organization/Location foundation is `IMPLEMENTED_NOT_CERTIFIED` under this SDD. A Location
already has composite Tenant/Organization ownership. Location creation locks its Organization
and grants the creator Location access. No headquarters state or operation exists. Identity
access provisioning already validates active Tenant, Organization, Location, actor authority,
delegation bounds, and conflicting identities.

Material discrepancy: current APIs permit an active Organization with zero active Locations and
permit deactivation of any Location; therefore current implementation does not enforce the
reported headquarters rule.

---

# 6. REUSE ANALYSIS

| Component | Owner | Reuse | Required Change | Risk |
|---|---|---|---|---|
| Organization/Location models and composite scope keys | Enterprise Core | Reuse with extension | Add headquarters relationship | Medium |
| Organization/Location routes | Enterprise Core | Reuse with extension | Delegate mutations to capability service | Medium |
| Canonical permission catalog | Identity | Reuse as-is | None | Low |
| Admin Tenant bootstrap | Identity | Reuse as-is | Optional prerequisite only | Low |
| Staff/access provisioning | Identity | Reuse as-is in caller transaction after contract adaptation if required | Preserve least-privilege checks and no credential overwrite | Medium |
| Stage 0 onboarding importer | Restaurant onboarding | Do not reuse | It owns broader commercial import behavior | High if coupled |
| `bootstrap_pilot_minimum` | Pilot operations | Do not reuse | Creates prohibited records | High |

No new microservice, queue, or parallel identity/provisioning architecture is justified.

---

# 7. ACTORS AND DOMAIN CONCEPTS

## 7.1 Actors

| Actor | Responsibility | Relevant Authorization |
|---|---|---|
| Tenant administrator | Manage Organization/Location headquarters | Existing `organization.manage` plus `location.manage` at current and replacement Locations |
| Authorized provisioning operator | Invoke controlled minimal provisioning | Existing authenticated administrator or controlled CLI identity; no public anonymous access |
| Staff member | Receive approved Location access | Existing active User/Membership and assigned Location role |

## 7.2 Domain Concepts

| Concept | Meaning | Authoritative Source | Technical Representation |
|---|---|---|---|
| Organization | Tenant-owned restaurant organizational entity | RDM-001, BR-ORG-* | `organizations` |
| Location | Physical/operational branch owned by an Organization | RDM-002, BR-ORG-001 | `locations` |
| Headquarters | Current distinguished ACTIVE Location for an operational Organization | P02-D01, P02-D03 | Organization-owned reference to one Location |
| Operational Organization | Organization with `status = ACTIVE`, a non-null headquarters reference, and a referenced ACTIVE Location | P02-D01, P02-D02 | Service-enforced effective state over existing fields plus headquarters reference |
| Initial configuration | Non-operational Organization that may temporarily lack headquarters | P02-D02 | Existing `INACTIVE` Organization status; no new lifecycle value |
| Minimal provisioning | Controlled creation/convergence in an existing Tenant by an existing authorized administrator | P02-D04 | Enterprise Core application service |

---

# 8. INVARIANTS

```text
OLP-INV-001
Rule: An Organization in the authority-defined operational state references exactly one current
      headquarters Location.
Authority: P02-D01, P02-D02.
Enforcement: Organization-owned non-ambiguous reference plus application lifecycle guard.
Failure behavior: Reject atomically with conflict; retain prior state.
Verification: Persistence, service, API/CLI, and concurrency tests.

OLP-INV-002
Rule: Headquarters belongs to the same Tenant and Organization.
Authority: BR-CORE-002..004 and BR-ORG-001.
Enforcement: Composite foreign key and server-side validation.
Failure behavior: Reject without mutation.
Verification: Cross-Tenant and cross-Organization tests.

OLP-INV-003
Rule: A headquarters Location must satisfy the authority-defined current/valid status.
Authority: P02-D02, P02-D03.
Enforcement: Locked application validation; deactivation guard.
Failure behavior: Reject without mutation.
Verification: inactive/replacement/deactivation tests.

OLP-INV-004
Rule: Minimal provisioning never creates Restaurant commercial or synthetic operational data.
Authority: Capability boundary.
Enforcement: Explicit service dependencies and forbidden table assertions.
Failure behavior: Entire transaction rolls back.
Verification: zero-commercial-record certification query.

OLP-INV-005
Rule: Staff provisioning cannot grant permissions the actor lacks at the target Location.
Authority: Identity & Authorization Capability SDD.
Enforcement: Existing access-provisioning service.
Failure behavior: deny and roll back.
Verification: delegation and cross-scope regressions.
```

---

# 9. LIFECYCLE AND KEY FLOWS

## 9.1 State Model

No new persisted Organization status is introduced. `INACTIVE` is non-operational and may be
used during initial configuration. `ACTIVE` is accepted as operational only when the
headquarters reference is non-null and resolves to an ACTIVE same-scope Location. Activation
without that condition is rejected.

| From | Action | To | Preconditions | Actor |
|---|---|---|---|---|
| INACTIVE, no headquarters | Create first ACTIVE Location | INACTIVE with headquarters | Same Tenant/Organization | Authorized administrator/operator |
| INACTIVE with valid headquarters | Activate Organization | ACTIVE/operational | Headquarters remains ACTIVE and same-scope | Authorized administrator |
| Headquarters A | Create Location B | Headquarters A unchanged | A remains valid | Authorized administrator/operator |
| Headquarters A | Replace with B | Headquarters B | B is valid and same Tenant/Organization | Authorized administrator |
| Headquarters A | Deactivate/retire A and replace with B | Headquarters B; A inactive/retired | B is ACTIVE and replacement is in the same transaction | Authorized administrator |
| Headquarters A | Deactivate/retire A without replacement while Organization remains operational | Rejected | Forbidden transition | Authorized administrator |

## 9.2 Key Use Cases

```text
UC-001 — MINIMAL ORGANIZATION PROVISIONING
Actor: Authorized provisioning operator.
Preconditions: Existing active Tenant, existing active authorized administrator, and existing
approved non-administrator role for the Staff assignment.
Main flow: validate all inputs; create or converge Organization; create or converge first
Location and set it as headquarters; provision Staff identity/access through Identity-owned
services; activate the Organization after headquarters validity; commit once.
Postconditions: one headquarters, approved Staff grant/role, no commercial records.
Failure cases: conflict, unauthorized scope/delegation, invalid identity, or persistence error
rolls back the complete operation.

UC-002 — HEADQUARTERS REPLACEMENT
Actor: Authorized administrator.
Main flow: lock Organization; validate and lock target Location; revalidate scopes/status;
record audit evidence; replace the reference; commit once.
Postconditions: exactly one current headquarters and preserved Location identities.
```

---

# 10. OWNERSHIP

| Entity / State | Owner | Scope | Cross-Owner Access |
|---|---|---|---|
| Organization | This capability / Enterprise Core | Tenant | Identity reads ownership references |
| Location | This capability / Enterprise Core | Tenant + Organization | Business capabilities reference it |
| Headquarters reference/history | This capability | Tenant + Organization | Read by consumers; mutated only here |
| User/Membership/Role/Grant | Identity & Authorization | Global identity / Tenant / Location | This capability calls Identity service |
| Commercial data | Respective Restaurant capability | Organization/Location | No creation by this capability |

---

# 11. DATA MODEL AND INTEGRITY

## 11.1 Persistence

Approved technical design:

```text
Entity/Table: organizations
Purpose: Own the single current headquarters selection.
Important field: headquarters_location_id (nullable while the Organization is non-operational).
Foreign key: (headquarters_location_id, tenant_id, id) references
             locations(id, tenant_id, organization_id), ON DELETE RESTRICT.
Integrity: one scalar reference prevents two current headquarters; composite FK prevents
           cross-Tenant and cross-Organization selection.

Entity/Table: organization_headquarters_changes
Purpose: Durable append-only evidence of initial assignment and replacement.
Tenant ownership: tenant_id; Organization ownership: organization_id.
Important fields: previous_location_id nullable, new_location_id, actor_membership_id,
                  changed_at, operation_id.
Integrity: composite ownership FKs; unique (tenant_id, operation_id).
Deletion behavior: RESTRICT for referenced business identities.

Entity/Table: minimal_provisioning_runs
Purpose: Durable idempotency and non-sensitive result evidence for the controlled workflow.
Tenant ownership: tenant_id; actor ownership evidence: actor_membership_id.
Important fields: operation_id, manifest_version, request_fingerprint, organization_id,
                  location_id, staff_user_id, completed_at.
Integrity: unique (tenant_id, operation_id); composite Tenant ownership FKs.
Deletion behavior: preserve as provisioning evidence under platform retention policy.
```

No parallel headquarters registry or Location boolean designation is permitted.

## 11.2 Relationships

```text
Tenant 1 ── * Organization 1 ── * Location
                         └──── 1 current headquarters Location
Organization 1 ── * headquarters change evidence
```

## 11.3 Integrity

The database enforces headquarters Tenant/Organization ownership and single-reference shape.
Application services enforce Location status, activation eligibility, and the rule prohibiting
an operational Organization from having a null/invalid headquarters. The owning service is the
only supported headquarters mutation boundary.

## 11.4 Migration

```text
Current migration head: 0068_schema_collation_alignment
Migration required: YES, after SDD approval
Expected revision: next repository head discovered at implementation time; not preassigned here
Affected tables: organizations; new organization_headquarters_changes and
                 minimal_provisioning_runs tables
Data migration required: YES; classify and backfill only unambiguous existing records
Destructive change: NO
Backward compatibility: existing reads remain valid; response additions, if any, are additive
Production considerations: preserve all IDs/history. An existing Organization with exactly one
                         ACTIVE Location may use that sole unambiguous Location. Zero or multiple
                         ACTIVE Locations remain configuration-incomplete with a null reference,
                         cannot initiate normal operations, and require an authorized initial
                         designation. Never invent a Location or select by row order/lowest ID.
```

The migration is forward-only and additive. Existing `ACTIVE` rows with no determinable
headquarters are treated as legacy configuration-incomplete, not operational, until an
authorized administrator designates an ACTIVE same-scope Location. Migration and deployment
evidence must report these rows; it must not silently change their status or create data.

---

# 12. APPLICATION / SERVICE DESIGN

| Component | Responsibility | Inputs / Outputs | Dependencies |
|---|---|---|---|
| OrganizationLocationService | Own Organization/Location/headquarters mutations | Scoped commands/results | SQLAlchemy models/session |
| MinimalProvisioningService | Validate a manifest and coordinate one transaction in an existing Tenant | Manifest/result with created/unchanged operations | OrganizationLocationService, Identity transaction participant |
| Controlled CLI | Operator invocation without public provisioning | Environment/file input; non-sensitive summary | MinimalProvisioningService |

The outer provisioning service owns begin/commit/rollback. Identity adds one internal
transaction-participating operation that validates, locks, flushes, and returns without commit.
Existing HTTP/service wrappers retain their current commit behavior by calling that participant
and committing themselves. This is one Identity service, not a competing implementation. The
approved Identity SDD must record this cross-capability contract before implementation; see
Section 17.2. No credentials or credential-derived values are logged.

---

# 13. TRANSACTIONS, CONCURRENCY AND IDEMPOTENCY

## 13.1 Transaction Boundaries

| Operation | Reads / Locks | Writes | Commit / Rollback |
|---|---|---|---|
| First Location | Organization, then Location state | Location, headquarters reference, creator grants, audit evidence | One commit; total rollback |
| Replace headquarters | Organization, then target/previous Locations in ascending ID | Reference and audit evidence | One commit; total rollback |
| Minimal provisioning | Tenant, natural keys, Organization, Locations, Identity prerequisites | Approved core entities only | One outer commit; total rollback |

## 13.2 Concurrency

All headquarters mutations lock the Organization first. Location rows are then locked in
ascending ID order. Invariants are revalidated after locks. Concurrent replacements serialize;
the later request either observes the new state and applies an authorized transition or returns
a conflict. Unique/FK violations are mapped to stable conflicts.

## 13.3 Idempotency

Minimal provisioning requires an operator-supplied stable `operation_id` and canonical
non-secret manifest fingerprint. The immutable completion row is inserted in the same transaction
as the provisioned entities. Failure rolls it back with all other writes; no partial or failed
run row is committed. Exact replay returns the recorded result without duplicate entities or
side effects. Reuse of an operation ID with a different fingerprint fails. Existing
identity/natural-key records not proven to belong to the exact replay are conflicts and are
never overwritten. Passwords, hashes, and credential-derived values are excluded from the
fingerprint and evidence.

Evidence is owned by this capability in `minimal_provisioning_runs`; it is not folded into
Restaurant onboarding evidence.

---

# 14. API AND DTO CONTRACTS

## 14.1 API

No new public HTTP provisioning endpoint is approved.

The additive authenticated headquarters designation/replacement endpoint is:

```text
Method: PUT
Path: /organizations/{organization_id}/headquarters
Purpose: Designate an initial headquarters for a legacy/configuration-incomplete Organization or
         replace the current headquarters; optionally deactivate the previous headquarters in
         the same transition.
Authorization: active Tenant Membership with `organization.manage`; `location.manage` at the
               target Location and, when one exists, the current Location; server-side
               same-scope checks.
Request: { "location_id": positive integer, "deactivate_previous": boolean = false }
Response: Organization representation including current headquarters identifier.
Success status: 200
Errors: 403 unauthorized; 404 scoped resource absent; 409 invalid status/stale conflict.
Concurrency: Organization row lock and revalidation.
Audit effect: append headquarters change evidence.
```

Setting the current headquarters to `INACTIVE` through the existing Location update endpoint is
rejected. When deactivation is required, the headquarters endpoint with
`deactivate_previous=true` performs replacement, audit insertion, and prior-Location
deactivation atomically. Creating the first ACTIVE Location for an Organization with no
headquarters assigns it automatically. Organization activation remains an explicit mutation and
is rejected until the headquarters validity predicate passes.

Existing Organization and Location response DTOs may add `headquarters_location_id` and/or
`is_headquarters` only as backward-compatible optional/additive fields.

## 14.2 Provisioning Manifest

```text
DTO: MinimalProvisioningManifest
Direction: controlled CLI to service
Required: operation_id, Tenant selector, Organization code/name, first Location fields,
          Staff username/display name, existing approved role name
Optional: Staff email
Validation: canonical existing validators; strict extra-field rejection
Immutability: operation_id/fingerprint cannot be reused for different content
Compatibility: versioned manifest contract
```

Secrets are supplied separately from the persisted/logged manifest.

---

# 15. AUTHENTICATION AND AUTHORIZATION

## 15.1 Authentication

Inherits the Global SDD and Identity & Authorization SDD without exception.

## 15.2 Authorization

| Operation | Required Capability | Scope | Additional Rule |
|---|---|---|---|
| Organization mutation | `organization.manage` | Tenant | Existing server-side Tenant check |
| Location creation/update | `location.manage` | Tenant/Location as applicable | Existing scope checks |
| Headquarters replacement | `organization.manage` + `location.manage` | Tenant + Organization + current/target Locations | Same Tenant/Organization; active membership |
| Staff provisioning | Existing Identity contract | Target Locations | Actor may delegate no absent permission |
| Controlled CLI provisioning | Existing administrator permissions | Explicit existing Tenant | Actor must already be authorized; no Tenant/admin/role creation |

No role or administrator privilege is inferred from Organization ownership or Location creation.

---

# 16. AUDIT

| Operation | Actor | Evidence | Before/After Required |
|---|---|---|---|
| Initial headquarters assignment | Authorized actor/operator | Durable headquarters change row + structured log | null → Location ID |
| Headquarters replacement | Authorized administrator | Durable headquarters change row + structured log | prior → new Location ID |
| Minimal provisioning | Existing authorized administrator | Provisioning-run row + structured log | Created/unchanged entity types; no secrets |

Audit evidence is append-only and contains identifiers, not credentials.

---

# 17. INTEGRATIONS AND CROSS-CAPABILITY DEPENDENCIES

## 17.1 External Integrations

N/A — none introduced.

## 17.2 Internal Capability Dependencies

| Capability | Dependency | Direction | Contract | Failure Impact |
|---|---|---|---|---|
| Identity & Authorization | User, membership, role, grant provisioning | This capability calls Identity | Approved service and transaction contract | Entire provisioning rolls back |
| Restaurant operations | Valid Organization/Location context | Consumers read Enterprise Core | Existing composite ownership | Existing operations remain compatible |
| Stage 0 onboarding | None | Separate | Must not be invoked | No impact |

## 17.3 Events / Async Processing

N/A — synchronous transactions are sufficient. Domain events require separate authority.

Before implementation, Identity & Authorization Capability SDD must be amended narrowly to
authorize an internal non-committing transaction participant for existing access provisioning.
The amendment must preserve current consumer behavior, authorization, locking, error semantics,
and session/credential contracts. P02-D05 supplies the architectural decision; the amendment
reconciles Identity-owned design and is not an open product/domain decision.

---

# 18. FRONTEND AND UX

N/A — no frontend change is in scope. Backend remains authoritative.

---

# 19. INTERNATIONALIZATION AND GENERATED OUTPUTS

N/A — no user-facing text or generated output is introduced by this design version.

---

# 20. SECURITY AND PRIVACY

Security inherits Global SDD Section 18.

```text
Security concerns: cross-Tenant selection, privilege escalation, plaintext credentials,
                   provisioning replay, ambiguous existing identity.
Required controls: composite ownership integrity, server-side authorization, bounded role
                   delegation, secret separation, operation fingerprint, atomic rollback.
Personal data: Staff username, email, and display name remain Identity-owned.
Visibility: provisioning results are restricted to authorized operators.
Logging restrictions: never log passwords, hashes, tokens, or full secret-bearing manifests.
```

---

# 21. FAILURE AND RECOVERY

| Failure | Persisted State | Result | Recovery |
|---|---|---|---|
| Invalid/cross-scope headquarters | Unchanged | 404/409 as scoped contract requires | Correct request |
| Unauthorized mutation/delegation | Unchanged | 403 | Obtain authorized actor; do not bypass |
| Concurrent replacement | One serialized valid result | Success or conflict | Refresh and retry deliberately |
| Identity/natural-key conflict | Unchanged | Conflict | Resolve identity ownership explicitly |
| Process interruption before commit | Rolled back | Failed run | Replay same operation ID |
| Exact completed replay | Unchanged | Prior result | None |

No failure may leave partial core entities or commercial records.

---

# 22. COMPATIBILITY AND LEGACY

- Existing Organization/Location identifiers and history are preserved.
- Existing API consumers retain current fields and semantics except where an approved lifecycle
  decision requires a documented conflict response.
- Existing Staff authentication, sessions, credential administration, permission catalog, and
  Location authorization remain unchanged.
- A sole ACTIVE Location is an unambiguous headquarters migration candidate. Zero/multiple
  ACTIVE Locations require authorized designation and remain unable to initiate normal operations.
- Existing Organizations cannot be backfilled by row order, lowest ID, or invented Location.

---

# 23. PERFORMANCE AND SCALABILITY

Expected provisioning volume is low and administrative. Headquarters lookup is a direct indexed
reference. Lock scope is one Organization plus a small bounded Location set. No cache, batch
system, or asynchronous infrastructure is justified.

---

# 24. IMPLEMENTATION BOUNDARIES

## Allowed After Approval

- One forward migration implementing the approved relationship/evidence design.
- Minimal model/service/route or CLI extensions.
- Adapt existing Identity service transaction ownership without changing authorization meaning.
- Focused tests and certification evidence.

## Conditionally Allowed

- Identity code changes only after its approved SDD records the P02-D05 transaction contract.
- Existing-data backfill only for a sole unambiguous ACTIVE Location; all other cases require
  explicit authorized designation.

## Prohibited

- Commercial Restaurant records, new permission semantics, automatic administrator grants,
  public provisioning, historical migration edits, onboarding redesign, frontend work,
  microservices, queues, unrelated refactors, dependency upgrades, or protected-database writes.

```text
Backend: YES
Frontend: NO
Database: YES, after approval
API: CONDITIONAL
Infrastructure: NO
External integration: NO
```

---

# 25. IMPLEMENTATION SEQUENCE

```text
1. Explicitly approve this reviewed SDD version.
2. Register the P02-D05 participant contract in the Identity & Authorization SDD.
3. Implement forward migration and model integrity.
4. Implement Organization/Location service and mutation integration.
5. Implement controlled minimal provisioning using caller-owned transactions.
6. Add focused tests.
7. Certify clean install, upgrade, invariants, authorization, concurrency, and regressions in
   an isolated MySQL 8.4 environment.
```

---

# 26. TEST STRATEGY

| Requirement | Test Level | Required Verification |
|---|---|---|
| Composite headquarters ownership | Migration/persistence | Same scope accepted; cross-scope rejected |
| First/additional Location behavior | Service/API | First assignment; later creation preserves selection |
| Replacement/deactivation | Service/API | Authorized transition; invalid transition rejected |
| Concurrent changes | MySQL integration | Exactly one final reference and complete audit evidence |
| Minimal provisioning | Service/CLI integration | Required core entities only; one transaction |
| Replay/conflicts | Integration | Exact replay unchanged; drift/identity conflict rejected |
| Least privilege | Authorization | Unauthorized role/scope delegation denied |
| Commercial boundary | Database assertion | Prohibited table counts unchanged |
| Migration | MySQL 8.4 | Clean head install and upgrade from prior head |

---

# 27. REGRESSION SCOPE

## Direct

Organization/Location CRUD, headquarters operations, minimal provisioning, and migration tests.

## Secondary

Identity access provisioning, Staff Location authorization, Staff Login/session enforcement,
credential administration, and P01 permission initialization.

## Collateral

Focused Reception/Waiter authority and representative Location-owned Restaurant operation tests.
Do not run the full suite unless implementation changes shared foundations beyond this design.

---

# 28. CERTIFICATION SCENARIOS

```text
V1 — First and additional Locations
Expected: first valid Location becomes headquarters; additional Location does not replace it.

V2 — Replacement and isolation
Expected: authorized same-scope replacement succeeds atomically; cross-Tenant,
cross-Organization, inactive, and unauthorized targets fail unchanged.

V3 — Deactivation and concurrency
Expected: no successful operation leaves an operational Organization without exactly one valid
headquarters; concurrent replacements serialize and preserve evidence.

V3A — Existing-record compatibility
Expected: sole ACTIVE Location is selected only when unambiguous; zero/multiple candidates are
reported configuration-incomplete, remain non-operational, and require authorized designation.

V4 — Minimal provisioning and replay
Expected: Organization, first Location/headquarters, Staff membership/grant/approved role exist;
exact replay creates no duplicates; conflicting identity or manifest fails unchanged.

V5 — Strict boundary and regressions
Expected: no commercial records; P01 catalog remains 83 unique codes; Staff Login, sessions,
credentials, and Location authority remain conformant.

V6 — Migration
Expected: clean installation and approved upgrade both reach repository head in isolated MySQL
8.4; protected databases are untouched.
```

---

# 29. ACCEPTANCE AND PASS / FAIL

```text
AC-001: Every operational Organization has exactly one same-scope valid headquarters.
AC-002: Headquarters transitions are authorized, atomic, concurrency-safe, and auditable.
AC-003: Minimal provisioning is deterministic and creates only approved Enterprise Core state.
AC-004: Replays do not duplicate state and conflicts do not overwrite identity/access.
AC-005: Existing Identity, Staff, permission, and Restaurant Location authority remains intact.
AC-006: Clean install and upgrade pass in isolated MySQL 8.4 without protected-database writes.
```

Any failed critical invariant, unauthorized design deviation, commercial record creation, or
blocking security issue is `FAIL`. Missing authority or unsafe certification is `BLOCKED`.

---

# 30. STOP CONDITIONS

In addition to the canonical template stop conditions, implementation stops if existing data
cannot be classified without guessing, the Identity SDD has not registered the P02-D05
participant contract, that contract cannot remain atomic, or isolation from protected databases
cannot be proven.

---

# 31. OPEN QUESTIONS, RISKS AND DEFERRED ITEMS

## Open Questions

NONE — P02-D01 through P02-D05 resolve the previously blocking decisions.

## Risks

| Risk | Impact | Mitigation | Residual Risk |
|---|---|---|---|
| Existing active Organizations have zero/multiple candidate Locations | Unsafe backfill | Assess isolated copy; require authorized designation | Medium until designation completes |
| Circular Organization/Location reference | Migration/order complexity | Nullable initialization window plus composite FK and service transaction | Low with defined sequencing |
| Reused Identity service commits internally | Partial provisioning | Adapt to caller-owned transaction without semantic change | Medium |
| Existing Location update lock order differs | Deadlock/invariant risk | Centralize mutations and enforce Organization-first order | Low after tests |

Deferred items are listed in Section 4.3.

---

# 32. TRACEABILITY

| Requirement / Rule | Authority | SDD Section | Implementation | Verification |
|---|---|---|---|---|
| Exactly one headquarters | P02-D01, P02-D02 | 8, 11, 13 | `models/organization.py`, `organization_location.py`, Organization/Location routes | V1–V3A PASS |
| Same Tenant/Organization | BR-CORE-002..004, BR-ORG-001 | 8, 11, 15 | Migration 0069 composite FKs and scoped services | V2 PASS |
| Atomic replacement/audit | P02-D03 | 9, 13, 16 | `organization_location.py`, headquarters endpoint and evidence model | V2–V3 PASS |
| Minimal core-only provisioning | P02-D04 | 3, 8, 12 | `minimal_provisioning.py`, controlled CLI | V4–V5 PASS |
| Caller-owned Identity transaction | P02-D05 | 12, 13, 17 | `identity/access_provisioning.py` transaction participants | V4–V5 PASS |
| Least-privilege Staff access | Identity SDD | 15 | Existing service reused | V4–V5 |
| Migration compatibility | Global SDD Sections 11, 29 | 11, 22 | `0069_organization_headquarters_provisioning.py` | V6 PASS |

---

# 33. CERTIFICATION EVIDENCE

```text
CERTIFIED AS-BUILT
Design version: 0.1.0 APPROVED
Certification baseline: d6810e98f2b2fc7c871afe507f15c34446dd628b plus the certified
  working-tree implementation; packaging commit is created only after PASS
Migration head: 0069_org_hq_provisioning (single head)
Environment: separately named Docker Compose project and isolated MySQL 8.4 volume/databases;
  protected databases were not modified

Focused capability and Identity transaction tests: PASS — 35 passed
Operational Organization-scope regression: PASS — 39 passed
Identity/catalog/Location-authority collateral regression: PASS — 36 passed
Migration/model verification: PASS — 2 passed, including populated 0068 → 0069 upgrade
Clean installation: PASS — empty isolated database upgraded through repository head
Syntax/build: PASS — compileall, Docker development image build, and alembic single-head check
Permission catalog evidence: PASS — 83 rows / 83 distinct canonical codes
Operational invariant evidence: PASS — no ACTIVE Organization with null headquarters after tests

Certification scenarios:
V1 PASS — first Location assigned; later Location preserved headquarters
V2 PASS — scoped authorized replacement; invalid scopes/statuses rejected
V3 PASS — concurrent replacements serialized with two ordered audit rows
V3A PASS — sole ACTIVE Location backfilled; zero/multiple candidates left null
V4 PASS — atomic minimal provisioning, exact replay, drift and identity conflict behavior
V5 PASS — commercial counts unchanged; Identity/catalog and Location authority regressions pass
V6 PASS — clean install and populated upgrade reach 0069 in isolated MySQL 8.4

Warnings: Starlette TestClient reports one upstream anyio alias deprecation warning
Known deviations: NONE
Approved exceptions: NONE
Result: PASS
Certification date: 2026-10-10
```

---

# 34. DEFINITION OF READY

```text
[x] Capability boundary and scope are explicit
[x] Repository baseline and reuse were inspected
[x] Persistence, transaction, concurrency, security, and verification design exists
[x] P02-D01 through P02-D05 are registered with approval evidence
[x] Organization/headquarters lifecycle is resolved
[x] Authorization policy is resolved without new permission semantics
[x] Minimal provisioning actor/Tenant/role/idempotency ownership is resolved
[x] No blocking question remains
[x] Exact reviewed version is explicitly approved
```

Current status: `CERTIFIED AS-BUILT`. The approved design is implemented and the required
isolated certification evidence is recorded in Section 33.

---

# 35. DEFINITION OF DONE

The capability is done only after the approved version is implemented, executable contracts
conform, required isolated migration and behavioral tests pass, focused regressions pass, no
blocking security issue remains, and this SDD is reconciled as certified as-built design.
