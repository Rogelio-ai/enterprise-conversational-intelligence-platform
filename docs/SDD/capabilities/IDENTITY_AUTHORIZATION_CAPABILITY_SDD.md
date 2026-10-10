# RESTAURANT INTELLIGENCE PLATFORM
# IDENTITY & AUTHORIZATION CAPABILITY SOFTWARE DESIGN DOCUMENT

**Capability:** Identity & Authorization
**Document:** `IDENTITY_AUTHORIZATION_CAPABILITY_SDD.md`
**Template:** `CAPABILITY_SDD_TEMPLATE.md`
**Status:** APPROVED
**Version:** 0.1.0
**Owner:** Identity / Enterprise Core
**Last Updated:** 2026-10-10

---

# 1. PURPOSE

Define the authoritative technical design for the existing Identity & Authorization
foundation and the missing independent initialization of its canonical permission catalog.

The capability establishes Staff identity and authentication, Tenant and Location access,
roles and permission assignments, session enforcement, and credential administration. This
version adds only a permission-registration mechanism; it does not redesign existing identity
behavior or create Restaurant business authority.

---

# 2. AUTHORITY

## 2.1 Governing Sources

```text
Product Authority: N/A — this version introduces no product behavior
Domain Authority: N/A — this version introduces no Restaurant domain rule
Global Architectural Authority:
  - AGENTS.md
  - docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
Global SDD: docs/SDD/GLOBAL_SDD.md (APPROVED, version 0.2.0)
Applicable ADRs: None found for this capability
Security Baseline: docs/SDD/GLOBAL_SDD.md Section 18
Reuse Policy: docs/SDD/GLOBAL_SDD.md Section 32
Other executable/repository contracts:
  - apps/api/app/models/identity.py
  - apps/api/app/api/deps.py
  - apps/api/app/api/routes/auth.py
  - apps/api/app/identity/
  - apps/api/app/bootstrap_admin.py
  - apps/api/alembic/versions/0002_auth_tenant_foundation.py
  - apps/api/alembic/versions/0063_staff_username_login.py
  - apps/api/alembic/versions/0064_location_scoped_staff_rbac.py
  - apps/api/alembic/versions/0065_staff_auth_session_foundation.py
  - permission-seeding migrations through repository head 0068
```

This SDD inherits all applicable higher-authority rules. Repository implementation and tests
are evidence of existing contracts; this document is the approval candidate that preserves
those contracts and defines the new capability-specific initialization design.

## 2.2 Authority of This SDD

This approved document is authoritative for the technical design of Identity & Authorization
within its stated boundary. Prompts, conversations, implementation reports, and tests do not
independently redefine it. Approval does not imply implementation or certification.

## 2.3 Approval Record

```text
Document path: docs/SDD/capabilities/IDENTITY_AUTHORIZATION_CAPABILITY_SDD.md
Document version: 0.1.0
Approving authority/role: Project operator acting as Architecture Authority under the approved governance model
Explicit decision: APPROVED
Decision date: 2026-10-10
Approval evidence/reference: Explicit operator authorization in “P01 — CANONICAL PERMISSION INITIALIZATION — APPROVAL REGISTRATION + IMPLEMENTATION + CERTIFICATION + GIT — FINAL”, received 2026-10-10
Open conditions: NONE
```

This approval applies only to version 0.1.0 and the design boundary recorded here.

---

# 3. CAPABILITY BOUNDARY

## Owns

- Canonical Staff users, credentials, authentication, and Staff authentication sessions.
- Tenant Membership identity and its active/inactive status relationship to access.
- Tenant-scoped roles, the global canonical permission catalog, and role-permission relations.
- Membership-role, Tenant/Location grant, and Location-role assignment contracts.
- Server-side resolution and enforcement of Tenant- and Location-scoped Staff authority.
- Administrative credential changes and resulting Staff-session revocation.
- Canonical permission definitions and permission-only catalog initialization.

## Does Not Own

- Tenant, Organization, or Location business lifecycle beyond identity ownership references.
- Restaurant roles, operational profiles, Reception/Waiter responsibilities, or their business
  permission policy.
- Restaurant provisioning, onboarding workflow, commercial data, or business records.
- Capability-specific authorization decisions owned by Restaurant capabilities.
- Diner identity/session behavior, external connector identity, or payment credentials.
- Frontend navigation or presentation.

---

# 4. SCOPE, NON-GOALS AND DEFERRED

## 4.1 In Scope

- Preserve existing Staff authentication, session, credential, Tenant, and Location authority
  contracts.
- Establish one canonical source for all currently existing permission codes and descriptions.
- Initialize that catalog independently of users, roles, grants, Tenant/Location state, and
  Restaurant provisioning.
- Make administrative bootstrap consume the same definitions while preserving its current grant
  behavior.
- Focused isolated verification of initialization and affected authorization behavior.

## 4.2 Non-Goals / Out of Scope

- New permissions, roles, actors, user-management workflows, or authorization semantics.
- Staff Login, invitation, access-provisioning, Reception, or Waiter redesign.
- New API or frontend surface for permission initialization.
- New service, microservice, queue, event, table, or infrastructure dependency.
- Automatic changes to existing role-permission or membership assignments.
- Modification of historical migrations.

## 4.3 Deferred

| ID | Requirement | Reason | Dependency | Blocking |
|---|---|---|---|---|
| N/A | None | This version has no deferred requirement | N/A | NO |

---

# 5. EXISTING SYSTEM / DISCOVERY BASELINE

```text
Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Commit: 7fbfca2305a1287aa8c3141d103decfb90bf619e
Migration head: 0068_schema_collation_alignment

Relevant backend:
  - apps/api/app/api/deps.py
  - apps/api/app/api/routes/auth.py
  - apps/api/app/api/routes/identity_access.py
  - apps/api/app/api/routes/staff_credentials.py
  - apps/api/app/identity/
  - apps/api/app/bootstrap_admin.py
Relevant frontend: N/A — no frontend change or owned surface in this version
Relevant domain modules: app.identity
Relevant tables:
  users, staff_auth_sessions, tenant_memberships, roles, permissions,
  role_permissions, membership_roles, membership_location_grants,
  membership_location_roles
Relevant endpoints:
  /auth/login, /auth/logout, /auth/me, existing identity access and Staff credential routes
Relevant integrations: N/A
Relevant tests:
  test_auth_foundation.py, test_staff_auth_sessions.py,
  test_staff_credential_administration.py, test_staff_location_authorization.py,
  test_identity_access_provisioning.py, test_pilot_operational_profiles.py
Relevant documentation: GLOBAL_SDD.md Sections 5-9, 18, 29, 32 and 33
```

The existing foundation is `IMPLEMENTED_NOT_CERTIFIED` as one unified capability under this SDD.
Focused executable evidence covers its material security contracts.

Repository inspection confirms 83 unique existing permission definitions: 74 seeded by migrations
and nine currently dependent on `bootstrap_admin.py`. Fifty definitions overlap with identical
descriptions, and no conflicting definition was found. `bootstrap_admin.py` owns 59 definitions
but couples their registration to Tenant, user, membership, role, and grant creation. No
independent permission-only initializer exists.

---

# 6. REUSE ANALYSIS

| Component | Owner | Reuse | Required Change | Risk |
|---|---|---|---|---|
| `Permission` model and `uq_permissions_code` | Identity | Reuse as-is | None | Low |
| Existing migration definitions | Historical schema evolution | Reuse as evidence; do not edit | Reconcile into canonical source | Description drift if copied incorrectly |
| `bootstrap_admin` permission definitions | Identity bootstrap | Reuse with minimal extension | Consume canonical catalog and retain its existing 59-code grant subset | Accidental grant expansion |
| `DatabaseManager` / `AsyncSession` transactions | API persistence | Reuse as-is | Add an internal invocation wrapper | Low |
| Authentication and authorization dependencies | Identity | Reuse as-is | None | Security regression if touched |

The canonical definitions, initializer, and invocation wrapper belong in one bounded module,
proposed as `apps/api/app/identity/permission_catalog.py`. The definitions MUST NOT be duplicated
in administrative bootstrap or a second registry.

```text
Candidate: Canonical permission catalog initialization
Domain-independent: NO — codes describe this platform's capabilities
Likely reusable: YES — by clean installation and administrative bootstrap
Recommended boundary: Existing app.identity module
Extract now: YES
Reason: Two current initialization paths require one owned definition source; no runtime or
        ownership boundary justifies a service or microservice.
```

---

# 7. ACTORS AND DOMAIN CONCEPTS

## 7.1 Actors

| Actor | Responsibility | Relevant Authorization |
|---|---|---|
| Staff user | Authenticate and operate within assigned Tenant/Location authority | Active user, membership, session, grants, roles, and permissions |
| Authorized administrator | Administer existing Staff credentials/access | Existing server-enforced permissions and Tenant/Location scope |
| Installation operator | Invoke permission initialization during controlled installation | Infrastructure/database execution authority; not a Restaurant-user permission |
| Application bootstrap | Reuse canonical registration before its existing grant workflow | Internal process, not an authenticated business actor |

## 7.2 Domain Concepts

| Concept | Meaning | Authoritative Source | Technical Representation |
|---|---|---|---|
| User | Canonical Staff identity record | This SDD after approval; existing contract | `users` / `User` |
| Tenant Membership | A user's membership in one Tenant | Global SDD Sections 5, 7-9; this SDD | `tenant_memberships` |
| Role | Tenant-owned grouping of permissions | This SDD after approval; existing contract | `roles` |
| Permission | Stable global authorization code and description; registration is not a grant | This SDD after approval | `permissions` |
| Role Permission | Assignment of a registered permission to a Tenant role | This SDD after approval | `role_permissions` |
| Location authority | Role/permission composition for one granted Location | Global SDD Sections 6-8; this SDD | grants and `membership_location_roles` |
| Staff session | Server-verifiable active authentication session | This SDD after approval | `staff_auth_sessions` |

---

# 8. INVARIANTS

## IA-INV-001 — Tenant Isolation

Rule: Identity authority and assignments from one Tenant MUST NOT authorize another Tenant.
Authority: Global SDD `GLOBAL-INV-001` and Sections 5-9.
Enforcement: Composite foreign keys, Tenant-scoped queries, token context, and server checks.
Failure behavior: Deny without cross-Tenant disclosure or mutation.
Verification: Existing cross-Tenant authentication, credential, grant, and access tests.

## IA-INV-002 — Location-Scoped Authority

Rule: Location operations require both a valid Location grant and the required permission at that
Location; permissions from another Location do not compose into the target Location.
Authority: Global SDD Sections 6 and 8; this SDD after approval.
Enforcement: `membership_location_grants`, `membership_location_roles`, and server dependencies.
Failure behavior: Not-found for ungranted resources or forbidden for missing permission according
to the existing endpoint contract.
Verification: `test_staff_location_authorization.py`.

## IA-INV-003 — One Active Staff Session

Rule: A Staff user has at most one ACTIVE session; a concurrent or repeated login while active is
rejected, and logout invalidates that session.
Authority: This SDD after approval; existing migration 0065 contract.
Enforcement: Session lifecycle checks, unique active slot, transactional user locking.
Failure behavior: Login conflict; closed/replaced tokens authenticate as unauthorized.
Verification: `test_staff_auth_sessions.py`.

## IA-INV-004 — Credential Administration

Rule: Administrative password change requires existing Tenant-scoped authority and atomically
revokes all active target sessions without affecting other Staff sessions.
Authority: Global SDD Sections 8, 12, and 18; this SDD after approval.
Enforcement: `staff_credentials.manage`, Tenant-scoped target lookup, locks, one transaction.
Failure behavior: Rollback password and session changes together.
Verification: `test_staff_credential_administration.py`.

## IA-INV-005 — Canonical Permission Identity

Rule: Every canonical permission has one stable code and canonical description. Existing rows and
their numeric identifiers MUST NOT be replaced during initialization.
Authority: This SDD after approval.
Enforcement: One catalog source, unique `permissions.code`, insert-missing behavior, description
validation.
Failure behavior: Conflicting existing description fails the invocation and rolls back.
Verification: V1-V4 and V9.

## IA-INV-006 — Registration Does Not Grant

Rule: Permission initialization creates or validates only `permissions` rows and MUST create or
modify no role, RolePermission, membership, Tenant/Location grant, identity, or business record.
Authority: Global SDD Sections 7, 8, and 18; this SDD after approval.
Enforcement: Bounded initializer dependency and transaction writes restricted to `permissions`.
Failure behavior: Any unauthorized side effect is a certification failure.
Verification: V5 and V6.

---

# 9. LIFECYCLE AND KEY FLOWS

## 9.1 State Model

Permission registration has no business lifecycle.

```text
MISSING CATALOG ROW
        ↓ initialize
REGISTERED CANONICAL ROW
        ↓ repeated initialize
UNCHANGED CANONICAL ROW
```

An existing row with a non-canonical description is `CONFLICTING`; it is not silently rewritten.

## 9.2 Key Use Cases

### UC-001 — Initialize Canonical Permissions

Actor: Installation operator or internal bootstrap.
Preconditions: Schema through the current Alembic head; database connection available.
Trigger: Permission initialization entry point.
Main flow: Load the canonical catalog, validate uniqueness, insert missing rows, verify all stored
descriptions, and commit through the transaction owner.
Postconditions: All canonical codes exist exactly once; no grant or business state changed.
Failure cases: Catalog invalidity, database failure, or description conflict rolls back the unit.

### UC-002 — Administrative Bootstrap Reuse

Actor: Existing application bootstrap.
Preconditions: Existing validated bootstrap input and transaction.
Trigger: `bootstrap_admin` execution.
Main flow: Invoke the shared permission initializer, then execute existing provisioning and grant
only the same 59 permission codes granted before this design.
Postconditions: Existing bootstrap behavior remains compatible; catalog definitions are shared.
Failure cases: Existing bootstrap rollback behavior remains authoritative.

---

# 10. OWNERSHIP

| Entity / State | Owner | Scope | Cross-Owner Access |
|---|---|---|---|
| User and credential | Identity & Authorization | Global identity with Tenant memberships | Other capabilities consume authenticated context only |
| StaffAuthSession | Identity & Authorization | User/Tenant membership | Authentication dependency validates it |
| TenantMembership | Identity & Authorization | Tenant | Other capabilities consume membership identity/status |
| Role | Identity & Authorization | Tenant | Assigned only through Identity contracts |
| Permission catalog | Identity & Authorization | Platform-global reference catalog | Capabilities reference stable codes; they do not register grants |
| RolePermission | Identity & Authorization | Tenant role | Authorization resolution reads it |
| MembershipRole | Identity & Authorization | Tenant membership | Authorization resolution reads it |
| MembershipLocationGrant/Role | Identity & Authorization | Tenant and Location | Location-scoped capabilities consume resolved authority |

Permission initialization owns no Tenant-, Organization-, Location-, or Restaurant-scoped state.

---

# 11. DATA MODEL AND INTEGRITY

## 11.1 Persistence

```text
Entity/Table: permissions
Purpose: Global canonical authorization-code registry
Primary key: id (stable surrogate; existing values preserved)
Tenant ownership: N/A — global reference data
Location ownership: N/A
Important fields: code, description, created_at, updated_at
Foreign keys: Referenced by role_permissions.permission_id
Unique constraints: uq_permissions_code
Check constraints: None
Indexes: Unique code index
Deletion behavior: Existing role_permissions use ON DELETE CASCADE; initialization never deletes
```

Other existing identity tables and constraints remain unchanged.

## 11.2 Relationships

```text
User → TenantMembership → MembershipRole → Tenant Role → RolePermission → Permission
                         → MembershipLocationGrant → MembershipLocationRole → Tenant Role
User + TenantMembership → StaffAuthSession
```

## 11.3 Integrity

- Database uniqueness on `permissions.code` prevents duplicate codes.
- The canonical catalog MUST contain unique codes before database access.
- Stored descriptions MUST equal the canonical description; initialization does not overwrite a
  conflict.
- Existing composite Tenant and Location foreign keys remain authoritative.
- Initializer writes are restricted to missing `permissions` rows.

## 11.4 Migration

```text
Current migration head: 0068_schema_collation_alignment
Migration required: NO
Affected tables: permissions (data insertion only at explicit invocation)
Data migration required: NO
Destructive change: NO
Backward compatibility: Existing rows, IDs, descriptions, and grants are preserved
Production considerations: Run the explicit initializer under normal change control; do not edit
                         historical migrations
```

A future schema requirement would require separate design approval and migration treatment.

---

# 12. APPLICATION / SERVICE DESIGN

| Component | Responsibility | Inputs / Outputs | Dependencies |
|---|---|---|---|
| Canonical permission catalog | Immutable mapping of the 83 verified codes to existing descriptions | Definitions | None |
| `initialize_canonical_permissions` | Validate catalog, insert missing rows, validate stored rows, report created codes/count | `AsyncSession`; structured result | `Permission`, SQLAlchemy |
| Permission initialization command | Controlled non-API invocation and transaction ownership | Settings/database; status summary | `DatabaseManager`, initializer |
| Administrative bootstrap adapter | Initialize catalog, then preserve existing 59-code grant selection | Existing bootstrap inputs/results | Initializer and existing bootstrap flow |

The proposed owned module is `app.identity.permission_catalog`. It contains definitions and the
internal initializer. Its command entry point MAY reside in the same module or a thin adjacent
wrapper; either form MUST call the same initializer and MUST NOT duplicate definitions.

Transaction ownership: The command wrapper owns one transaction. A caller with an existing
transaction, including `bootstrap_admin`, owns commit/rollback and passes its session.
Side effects: Missing `permissions` rows and non-sensitive summary logging only.
Failure behavior: Raise a typed initialization error; transaction owner rolls back.

---

# 13. TRANSACTIONS, CONCURRENCY AND IDEMPOTENCY

## 13.1 Transaction Boundaries

```text
Operation: Canonical permission initialization
Reads / locks: Existing Permission rows for canonical codes
Writes: Missing Permission rows only
Commit point: Once, after every code and description has been validated
Rollback behavior: Any failure rolls back all rows created by that invocation
External side effects: Non-sensitive completion/failure logging only
```

Administrative bootstrap retains its current single transaction; permission registration and its
existing provisioning/grants succeed or roll back together.

## 13.2 Concurrency

```text
Operation: Concurrent equivalent initialization
Risk: Two callers observe the same missing code
Locking strategy: Database unique code constraint is authoritative duplicate prevention
Lock order: Canonical codes are processed in deterministic sorted order
Revalidation: Validate the complete stored catalog and descriptions before commit
Conflict behavior: A duplicate-key race rolls back safely; a retry converges without duplicate
                   state. A description mismatch always fails closed.
```

No new global lock or infrastructure is introduced.

## 13.3 Idempotency

```text
Operation: Canonical permission initialization
Required: YES
Idempotency mechanism: Insert missing rows by stable unique code; validate existing rows
Persisted evidence: permissions rows and uq_permissions_code
Replay behavior: Creates zero rows and leaves all rows unchanged
Duplicate side-effect prevention: No grants or external effects; database uniqueness
```

---

# 14. API AND DTO CONTRACTS

## 14.1 API

No new HTTP API is authorized. Permission initialization is an internal service/controlled command,
not a Restaurant-user operation.

Existing authentication and identity endpoints remain unchanged.

## 14.2 DTOs / Schemas

No network DTO is required. The initializer returns an internal structured result sufficient to
report created count/codes and replay status without exposing secrets or credentials.

---

# 15. AUTHENTICATION AND AUTHORIZATION

General architecture is inherited from Global SDD Sections 7 and 8.

## 15.1 Authentication

- Staff login uses canonical username/password credentials and exactly one active server session.
- Concurrent second login is rejected.
- Logout closes the active session and invalidates its token context.
- Administrative password change replaces target active sessions atomically.
- Permission initialization does not authenticate Restaurant users and is not exposed by HTTP.

## 15.2 Authorization

| Operation | Required Capability | Scope | Additional Rule |
|---|---|---|---|
| Resolve current Staff authority | Existing assigned permissions | Tenant and assigned Locations | Active user, membership, Tenant, and session required |
| Change Staff password | `staff_credentials.manage` | Actor and target in same Tenant | Target active; revoke target sessions atomically |
| Provision access | Existing `user.manage`, `role.manage`, `location.manage` combination | Each target Location | Actor cannot delegate permissions it lacks |
| Initialize permissions | N/A — controlled installation authority | Platform database | Not reachable by Restaurant API; creates no grants |

Reception and Waiter operational authority and all existing role assignments remain unchanged.

---

# 16. AUDIT

| Operation | Actor | Evidence | Before/After Required |
|---|---|---|---|
| Staff credential change | Authorized Staff administrator | Existing structured security log | Target IDs and sessions revoked; never credential value |
| Permission initialization | Installation process | Non-sensitive structured summary | Counts/status; permission codes MAY be diagnostic, no secrets |

No new persistent audit table is required for idempotent global reference-data initialization.

---

# 17. INTEGRATIONS AND CROSS-CAPABILITY DEPENDENCIES

## 17.1 External Integrations

N/A — no external integration is introduced.

## 17.2 Internal Capability Dependencies

| Capability | Dependency | Direction | Contract | Failure Impact |
|---|---|---|---|---|
| All protected backend capabilities | Stable permission codes and resolved authority | Consumers read Identity context | `AuthenticatedContext` and permission dependencies | Requests deny if authority absent |
| Tenant/Organization/Location | Ownership references used by grants | Identity references Enterprise Core state | Existing composite ownership constraints | Invalid cross-scope assignment rejected |
| Administrative bootstrap | Canonical definitions and initializer | Bootstrap consumes Identity service | Internal function call in caller transaction | Bootstrap rolls back |
| Restaurant operations | Existing roles/grants only | Restaurant consumes resolved authority | No initializer coupling | No behavior change |

## 17.3 Events / Async Processing

N/A — synchronous database initialization is sufficient.

---

# 18. FRONTEND AND UX

## 18.1 Frontend Responsibility

N/A — this version introduces no frontend screen, route, or interaction.

## 18.2 Frontend / Backend Boundary

Inherited from Global SDD Section 20. Backend authorization remains authoritative.

## 18.3 UX Requirements

N/A — controlled operator command only.

## 18.4 Validation

Catalog validation and server/database constraints are authoritative. No client validation applies.

---

# 19. INTERNATIONALIZATION AND GENERATED OUTPUTS

N/A — permission codes and stored descriptions are invariant system contracts in their existing
language. This version introduces no translated UI, printing, or generated business output.

---

# 20. SECURITY AND PRIVACY

Security authority is Global SDD Section 18.

```text
Security concerns:
  privilege escalation, cross-Tenant authority, unauthorized grants, credential/session exposure,
  and exposing initialization to Restaurant users
Required controls:
  server-side Tenant/Location authorization; database scope constraints; one-active-session
  enforcement; command-only initialization; permission-only writes; no automatic grants
Personal data:
  existing Staff usernames, optional email, display name, and credential hash; initializer handles
  none of these
Visibility:
  permission catalog may be read only through existing authorized behavior; initializer has no API
Logging restrictions:
  never log passwords, hashes, tokens, session IDs, invitation secrets, or other credentials
```

Registering a permission is not granting it. Initialization MUST NOT change effective authority.

---

# 21. FAILURE AND RECOVERY

| Failure | Persisted State | User/System Result | Recovery |
|---|---|---|---|
| Invalid/duplicate catalog definition | Unchanged | Explicit initialization failure | Correct approved source before retry |
| Existing description conflict | Unchanged by initializer | Explicit conflict; no overwrite | Reconcile authority/repository discrepancy |
| Database failure mid-initialization | Transaction rolled back | Explicit failure | Restore dependency and retry |
| Duplicate-key race | Failed transaction leaves no partial initializer state | Explicit retryable failure | Retry; unique code converges |
| Bootstrap failure after initialization call | Whole bootstrap transaction rolled back | Existing bootstrap failure contract | Correct cause and rerun |

Failures leave determinate state and no partial grants.

---

# 22. COMPATIBILITY AND LEGACY

- Preserve all 74 migration-seeded permissions and nine bootstrap-dependent definitions.
- Preserve the 50 overlapping definitions and their matching descriptions without duplicate rows.
- Do not rename permission codes or replace existing Permission IDs.
- Do not add, remove, or rewrite existing RolePermission, MembershipRole, or Location grants.
- Administrative bootstrap continues granting exactly its existing 59-code set; extraction of
  definitions MUST NOT expand that grant set to all 83 codes.
- Preserve Staff Login, credential administration, Location authority, Reception/Waiter authority,
  and Restaurant workflows.
- Historical migrations remain immutable; the canonical source governs runtime initialization
  after approval and implementation, not historical revision behavior.

---

# 23. PERFORMANCE AND SCALABILITY

```text
Expected load: 83 catalog rows at the verified baseline
Latency-sensitive operations: None; installation-time command
Expected list/data size: Small, bounded canonical catalog
Concurrency considerations: Rare equivalent operator/bootstrap invocation
Polling/batch constraints: None
Known scale threshold: N/A; process deterministic sorted catalog in one transaction
```

No optimization infrastructure is justified.

---

# 24. IMPLEMENTATION BOUNDARIES

## Allowed

- One Identity-owned canonical permission-definition source and initializer.
- One controlled internal/CLI invocation boundary.
- Minimal `bootstrap_admin` reuse wiring preserving its existing grant subset.
- Directly related focused tests.

## Conditionally Allowed

- A new migration only if implementation proves the existing schema cannot satisfy this approved
  design and separate migration authority is obtained.
- Minimal operational invocation documentation only when required to make clean-install execution
  unambiguous.

## Prohibited

- New permission codes, descriptions, roles, grants, or business semantics.
- Historical migration modification.
- Staff Login, Reception, Waiter, onboarding, or Restaurant behavior redesign.
- New HTTP API, frontend, service, microservice, queue, or infrastructure dependency.
- Unrelated refactoring, renaming, formatting, dependency upgrades, schema/API changes, or frontend
  changes.

```text
Backend: YES
Frontend: NO
Database: NO schema change; controlled catalog data initialization only
API: NO
Infrastructure: NO
External integration: NO
```

---

# 25. IMPLEMENTATION SEQUENCE

```text
1. Establish the canonical catalog from verified existing definitions.
2. Implement the transaction-aware permission-only initializer and controlled command.
3. Adapt administrative bootstrap to reuse the catalog while retaining its 59-code grant subset.
4. Add focused initialization and regression tests.
5. Verify in an isolated MySQL 8.4 database.
6. Certify the defined scenarios and regression boundary.
```

```text
UNIT: P01 — Canonical Permission Initialization
Objective: Independently initialize the complete existing permission catalog without grants or
           business provisioning.
Depends on: Explicit approval of SDD version 0.1.0
Allowed changes: Section 24 Allowed boundary
Verification: Sections 26-29
Exit condition: Focused certification PASS with no unauthorized design deviation
```

---

# 26. TEST STRATEGY

| Requirement / Invariant | Test Level | Required Verification |
|---|---|---|
| Complete canonical catalog | Service + MySQL persistence | 83 unique codes after initialization at verified baseline |
| Idempotent replay | Service + MySQL persistence | Second run creates zero rows and changes no descriptions/IDs |
| No automatic grants/business data | MySQL persistence | Before/after counts and row sets for protected tables |
| Description conflict rollback | Service + MySQL persistence | Explicit failure and no partial inserts |
| Bootstrap compatibility | Focused bootstrap integration | Existing provisioning/grant set remains idempotent and unchanged |
| Staff session preservation | Focused API/integration regression | One active session, conflict, logout, relogin |
| Credential preservation | Focused API/integration regression | Authorized change/revocation and cross-Tenant denial |
| Location authority preservation | Focused API/integration regression | Grant plus per-Location permission enforcement |
| Tenant isolation | Focused authorization regression | Cross-Tenant token/assignment/target denied |

Use an isolated MySQL 8.4 database. Do not use the normal development database, reserved pilot
candidate, or historical volumes. Sequential focused execution is sufficient.

---

# 27. REGRESSION SCOPE

## Direct

```text
Affected: Canonical definitions, initializer, invocation, administrative bootstrap
Risk: Missing/duplicate definitions, altered descriptions, unintended grants
Verification: New focused permission-initialization tests and existing bootstrap idempotency test
```

## Secondary

```text
Affected: Authentication, credential administration, authorization resolution
Dependency: Permission rows and role-permission relations
Verification: Focused Staff session, credential, Tenant, and Location authorization tests
```

## Collateral

```text
Affected: Existing pilot operational profiles including Reception/Waiter-facing authority
Shared dependency: bootstrap definitions and permission codes
Verification: Operational-profile contract test; no full repository suite required
```

---

# 28. CERTIFICATION SCENARIOS

## V1 — Clean Installation Catalog

Setup: Isolated MySQL 8.4 database upgraded through migration head 0068, with no business
provisioning.
Action: Invoke canonical permission initialization once.
Expected result: All current canonical definitions exist; at repository baseline this is exactly
83 unique codes, with existing migration rows preserved and the nine missing rows created.
Evidence: Catalog query, uniqueness query, created-result summary, and ID snapshot.

## V2 — Safe Replay

Setup: V1 completed.
Action: Invoke initialization again.
Expected result: Zero rows created or changed; IDs and descriptions match the V1 snapshot.
Evidence: Initializer result and before/after queries.

## V3 — Description Consistency

Setup: V1 completed.
Action: Compare every stored canonical row with the owned catalog.
Expected result: Code and description pairs match exactly; no duplicate code exists.
Evidence: Deterministic comparison output.

## V4 — Conflict Rollback

Setup: Isolated database containing a conflicting description plus at least one missing canonical
row, created only inside the test transaction/environment.
Action: Invoke initialization.
Expected result: Explicit conflict; missing row is not committed and conflict is not overwritten.
Evidence: Error assertion and post-failure queries.

## V5 — No Identity or Business Provisioning

Setup: Capture row counts/sets after migrations and before initialization.
Action: Run V1.
Expected result: No users, roles, memberships, organizations, locations, grants, sessions, or
Restaurant business records are created.
Evidence: Protected-table before/after comparison.

## V6 — No Automatic Grants

Setup: V1 environment.
Action: Compare assignment tables before and after initialization.
Expected result: No RolePermission, MembershipRole, MembershipLocationGrant, or
MembershipLocationRole row is created, deleted, or changed.
Evidence: Assignment-table snapshots.

## V7 — Administrative Bootstrap Compatibility

Setup: Isolated database with catalog initialization available.
Action: Run existing administrative bootstrap twice.
Expected result: Existing bootstrap remains idempotent and grants only its established 59-code
set; it does not grant all canonical permissions merely because they are registered.
Evidence: Bootstrap results and exact role-permission query.

## V8 — Staff Session and Location Authorization Preservation

Setup: Existing focused test fixtures.
Action: Run Staff session, credential, Tenant, Location, and operational-profile focused tests.
Expected result: One-active-session, logout, credential revocation, cross-Tenant denial,
Location-scoped authority, and Reception/Waiter authority remain correct.
Evidence: Passing focused test commands.

## V9 — Existing-ID Preservation

Setup: Snapshot IDs for the 74 migration-seeded permissions.
Action: Run initialization and replay.
Expected result: Every pre-existing code retains its original ID; only missing codes receive new
IDs.
Evidence: Before/after ID comparison.

---

# 29. ACCEPTANCE AND PASS / FAIL

## AC-001 — Complete, Unique Catalog

Requirement: The initializer produces the complete existing canonical catalog exactly once.
Verification: V1-V3.
PASS: 83 unique matching codes at the verified baseline and no duplicate.
FAIL: Missing, extra, duplicate, or mismatched definition.

## AC-002 — Permission-Only Side Effects

Requirement: Initialization registers permissions and grants nothing.
Verification: V5-V6.
PASS: Only missing Permission rows are created.
FAIL: Any identity, role, assignment, Tenant/Location, or business row changes.

## AC-003 — Idempotency and Atomic Failure

Requirement: Replay is a no-op and failures leave no partial initialization.
Verification: V2 and V4.
PASS: Replay creates zero; conflict rolls back all invocation writes.
FAIL: Duplicate, overwrite, or partial commit.

## AC-004 — Compatibility and Security

Requirement: Existing identifiers, bootstrap grants, authentication, sessions, credentials,
Tenant isolation, and Location authority are preserved.
Verification: V7-V9 and focused regression.
PASS: All evidence passes with no unauthorized grant or behavior change.
FAIL: Any identifier replacement, grant expansion, authorization regression, or security failure.

Overall `PASS` requires all applicable criteria and certification scenarios to pass, no
unauthorized deviation, and no blocking security issue. `NOT_RUN` is not `PASS`.

---

# 30. STOP CONDITIONS

Implementation MUST stop and report instead of guessing when:

1. a canonical code or description conflicts across approved/repository sources;
2. implementation would create a new permission semantic or change existing grants;
3. the 59-code administrative grant subset cannot be preserved;
4. a schema migration appears necessary without separate authority;
5. Tenant or Location isolation would be weakened;
6. permission-only initialization cannot be isolated from business provisioning;
7. the isolated MySQL 8.4 certification environment cannot be guaranteed;
8. repository reality materially differs from the baseline in a way affecting this design;
9. any higher-authority or security conflict appears.

Use the canonical stop report from `CAPABILITY_SDD_TEMPLATE.md`.

---

# 31. OPEN QUESTIONS, RISKS AND DEFERRED ITEMS

## Open Questions

| Question | Impact | Blocking | Required Authority |
|---|---|---|---|
| None | The design is complete for review | NO | N/A |

## Risks

| Risk | Impact | Mitigation | Residual Risk |
|---|---|---|---|
| Catalog extraction omits or changes an existing definition | Authorization code unavailable or semantic drift | Mechanical comparison against migrations and bootstrap; V1-V3 | Low |
| Bootstrap consumes all 83 codes as grants | Privilege escalation | Separate existing 59-code grant subset; V7 exact-set assertion | Low |
| Description conflict in an upgraded environment | Initialization cannot complete | Fail closed without overwrite; operator reconciliation | Low |
| Certification touches a protected database | Unsafe state mutation | Isolated MySQL 8.4 identity and pre-write isolation check | Low |

## Deferred Items

None; see Section 4.3.

---

# 32. TRACEABILITY

| Requirement / Rule | Authority | SDD Section | Implementation | Verification |
|---|---|---|---|---|
| Tenant/Location isolation | Global SDD Sections 5-9, 18 | 8, 10, 15, 20 | Existing models, `api/deps.py`, `identity/access_provisioning.py` | V8 |
| One active Staff session | This SDD after approval; migration 0065 evidence | 8, 15 | Existing `identity/auth_sessions.py` | V8 |
| Credential change revokes sessions | This SDD after approval; existing evidence | 8, 15, 21 | Existing `identity/credential_administration.py` | V8 |
| Complete canonical catalog | This SDD after approval; verified repository definitions | 8, 11-13 | Proposed `identity/permission_catalog.py` | V1-V4, V9 |
| Registration grants nothing | Global SDD Sections 7, 8, 18; this SDD | 8, 12, 20 | Proposed bounded initializer | V5-V6 |
| Bootstrap compatibility | Global SDD Sections 29, 32; this SDD | 6, 9, 22 | Existing `bootstrap_admin.py` using proposed initializer | V7 |

---

# 33. CERTIFICATION EVIDENCE

```text
SDD version: 0.1.0

Repository: /home/rogelio/proyectos/pryecip
Branch: PENDING IMPLEMENTATION BASELINE
Commit: PENDING
Working tree: PENDING
Migration head: 0068_schema_collation_alignment at design baseline; rediscover for certification

Backend targeted tests: NOT RUN — design phase
Backend regression: NOT RUN — design phase
Frontend tests: NOT APPLICABLE
E2E: NOT RUN — design phase
Typecheck: NOT RUN — design phase
Build: NOT RUN — design phase
Migration verification: NOT RUN — design phase

Certification scenarios:
V1-V9: NOT RUN — design phase

Known deviations: None identified in design
Approved exceptions: None

Result: NOT CERTIFIED
Certification date: N/A
```

---

# 34. DEFINITION OF READY

```text
[x] Authority is identified
[x] Capability boundary is explicit
[x] Scope is bounded
[x] Existing implementation was inspected
[x] Reuse was evaluated
[x] Critical domain concepts are known
[x] Critical invariants are explicit
[x] Ownership is unambiguous
[x] Persistence is sufficiently designed
[x] API contracts are sufficiently designed (no new API)
[x] Transactions/concurrency are defined where relevant
[x] Authorization/security requirements are known
[x] Implementation boundaries are explicit
[x] Verification and certification criteria are defined
[x] No blocking design question remains
```

Readiness means eligible for explicit approval, not approved or implemented.

---

# 35. DEFINITION OF DONE

The capability change is done only when:

```text
[ ] This exact SDD version is explicitly approved
[ ] Approved design is implemented
[ ] Executable contracts conform to the SDD
[ ] Critical invariants are verified
[ ] Required focused tests and regression pass
[ ] V1-V9 pass in an isolated MySQL 8.4 environment
[ ] No blocking security defect or unauthorized grant exists
[ ] Approved exceptions, if any, are recorded
[ ] Certification evidence identifies the exact design and implementation baseline
[ ] This SDD reflects the certified as-built implementation
```
