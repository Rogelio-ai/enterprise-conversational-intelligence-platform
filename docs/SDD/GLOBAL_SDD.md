# RESTAURANT INTELLIGENCE PLATFORM
# GLOBAL SOFTWARE DESIGN DOCUMENT

**Document:** `docs/SDD/GLOBAL_SDD.md`
**Status:** APPROVED
**Version:** 0.2.0
**Scope:** Platform-wide Technical Design
**Last Updated:** 2026-10-08

---

# 1. PURPOSE AND AUTHORITY

This document defines the authoritative cross-cutting technical design for the Restaurant Intelligence Platform (RIP).

It answers:

> What technical rules must all platform capabilities follow?

It is governed by:

`docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md`

Applicable higher authority includes, where relevant:

- `PRODUCT_CONSTITUTION.md`;
- Product Authority;
- Domain Authority;
- approved ADRs.

No approved standalone security, reuse, or development-principles document exists in
the current repository baseline. Until an approved standalone authority explicitly
supersedes them, Section 18 is the platform Security Baseline and Section 32 is the
platform Reuse Policy.

Capability-specific technical design belongs in:

`docs/SDD/capabilities/<CAPABILITY_NAME>_SDD.md`

This document references rather than duplicates higher authority.

## 1.1 Approval Record

```text
Document path: docs/SDD/GLOBAL_SDD.md
Document version: 0.2.0
Approving authority/role: Project operator acting as Architecture Authority under the approved governance model
Explicit decision: APPROVED
Decision date: 2026-10-08
Approval evidence/reference: Explicit operator authorization in “SDD FORMAL APPROVAL REGISTRATION — GLOBAL SDD + MYSQL BACKUP RECOVERY — FINAL”, received 2026-10-08
Open conditions: NONE
```

This approved version governs applicable cross-capability technical design. Approval
does not imply implementation or certification.

---

# 2. SYSTEM CONTEXT

The Restaurant Intelligence Platform is an enterprise-grade platform supporting restaurant operations, intelligence, integrations, automation, and future AI/agent capabilities.

The platform is designed to support:

- multiple tenants;
- multiple organizations;
- multiple restaurant locations;
- Staff and diner interactions;
- operational restaurant capabilities;
- financial capabilities;
- inventory and purchasing;
- external integrations;
- multiple interaction channels.

Conceptually:

```text id="7y6f6h"
CHANNELS / USERS
       ↓
FRONTEND / INTERACTION
       ↓
API
       ↓
APPLICATION / DOMAIN CAPABILITIES
       ↓
PERSISTENCE
       ↓
EXTERNAL INTEGRATIONS
```

Capability boundaries define ownership inside this architecture.

---

# 3. ARCHITECTURAL PRINCIPLES

## 3.1 Explicit Ownership

Authoritative state and mutations SHALL have explicit ownership.

Ambiguous ownership is an architectural defect.

## 3.2 Server Authority

The backend SHALL remain authoritative for:

- domain invariants;
- authorization;
- persistent business state;
- transactions;
- concurrency;
- monetary truth;
- auditable business transitions.

## 3.3 Minimal Change

Changes SHALL modify only what is required by approved design.

## 3.4 Reuse Before Duplication

Existing authoritative responsibility SHALL be evaluated before introducing competing implementation.

## 3.5 Transactional Correctness

Atomic business operations SHALL NOT leave unauthorized partial committed state.

## 3.6 Deterministic Behavior

Business-critical operations SHOULD produce deterministic outcomes for equivalent authoritative inputs.

## 3.7 Auditability

Material business transitions SHALL preserve sufficient evidence to reconstruct relevant historical behavior.

## 3.8 Simplicity Before Distribution

Distributed architecture SHALL be introduced only when justified by real ownership, reuse, scalability, isolation, or runtime requirements.

Microservices are not a default objective.

---

# 4. PLATFORM BOUNDARIES

The platform SHALL preserve explicit boundaries between:

```text id="ydtudn"
Interaction / Frontend
API
Application Services
Domain
Persistence
External Integrations
Infrastructure
```

Capabilities MAY depend on public/application contracts owned by other capabilities.

A capability SHOULD NOT directly mutate another capability's internal state unless explicitly authorized by design.

Shared utilities MUST NOT become hidden owners of domain state.

---

# 5. MULTI-TENANCY

Multi-tenancy is a fundamental platform invariant.

The primary business ownership hierarchy is conceptually:

```text id="hr6u3f"
Tenant
  ↓
Organization
  ↓
Location
```

Business entities SHALL preserve the appropriate ownership scope.

Cross-tenant business relationships are prohibited unless explicitly authorized by higher authority.

Where practical, tenant consistency SHOULD be enforced through both:

- application validation;
- relational/database integrity.

Application filtering alone SHOULD NOT be the only protection when stronger structural enforcement is appropriate.

---

# 6. ORGANIZATION AND LOCATION

Organization and Location are distinct concepts.

A Location represents an operational business/restaurant location within the applicable organizational structure.

Capabilities SHALL explicitly determine whether state is:

```text id="y5q1va"
TENANT-SCOPED
ORGANIZATION-SCOPED
LOCATION-SCOPED
RESOURCE / SESSION / AGGREGATE-SCOPED
```

Location-scoped business state MUST NOT silently cross Location boundaries.

Cross-location behavior requires an explicit contract.

---

# 7. IDENTITY AND AUTHENTICATION

Authentication establishes identity.

Authentication and authorization SHALL remain separate concerns.

Staff identity MAY have access to one or multiple Locations.

Credential lifecycle and authentication-session behavior SHALL follow applicable approved capability/domain contracts.

Authentication mechanisms MUST NOT implicitly grant business authorization.

Sensitive authentication credentials SHALL remain protected according to Section 18.

---

# 8. AUTHORIZATION

Authorization SHALL be enforced server-side.

Authorization MAY consider:

- authenticated identity;
- Tenant Membership;
- active Tenant;
- Organization;
- active Location;
- Location grants;
- roles;
- capabilities;
- resource ownership;
- operational responsibility.

Permissions MAY differ by Location for the same Staff identity.

Frontend visibility MAY improve usability but MUST NOT serve as authorization enforcement.

Every material mutation SHALL verify applicable authorization before commit.

---

# 9. OWNERSHIP MODEL

Every authoritative mutable entity SHALL have determinable ownership.

Ownership MAY include:

```text id="tvcm6n"
Tenant
Organization
Location
Parent Aggregate
Service Session
Resource
Membership
Capability
```

Capability SDDs SHALL identify ownership for their state.

Where ownership integrity is relational, database constraints SHOULD enforce it when practical.

Deletion behavior MUST preserve required historical and referential integrity.

---

# 10. DATA ARCHITECTURE

The platform uses a relational transactional persistence model for authoritative operational state.

The current primary database technology is MySQL.

Persistence design SHOULD use explicit:

- primary keys;
- foreign keys;
- composite ownership relationships where required;
- unique constraints;
- check constraints;
- indexes based on actual access patterns;
- explicit nullability;
- audit/history structures where required.

ORM validation MUST NOT substitute for database integrity where database enforcement is appropriate.

Database-specific behavior SHALL respect established portability requirements.

---

# 11. SCHEMA MIGRATIONS

Schema evolution SHALL use the repository's established migration mechanism.

Current architecture uses Alembic.

Migrations SHALL:

- preserve migration ordering;
- consider existing persisted data;
- preserve ownership integrity;
- avoid unauthorized destructive changes;
- remain coherent with ORM/schema definitions.

Current migration head is repository state and MUST be discovered rather than permanently encoded in this document.

Historical migrations SHOULD NOT be rewritten casually.

---

# 12. TRANSACTIONS

The application/service layer SHOULD coordinate business transaction boundaries.

An operation representing one atomic business transition SHALL execute atomically.

Conceptually:

```text id="kwud6e"
BEGIN
  ↓
READ / LOCK
  ↓
AUTHORIZE
  ↓
VALIDATE
  ↓
MUTATE
  ↓
AUDIT
  ↓
COMMIT
```

On transactional failure:

```text id="if2u99"
ROLLBACK
```

Repositories or persistence helpers SHOULD NOT independently commit pieces of a larger atomic business operation unless explicitly designed.

External effects SHALL have explicitly designed relationship to transaction boundaries.

---

# 13. CONCURRENCY AND LOCKING

Concurrency-sensitive operations SHALL define their specific behavior in the applicable Capability SDD.

Global principles:

1. use deterministic lock ordering;
2. lock authoritative ownership/parent state where required;
3. revalidate relevant invariants after acquiring locks;
4. reject stale or conflicting mutations explicitly;
5. minimize lock duration;
6. avoid unnecessary external network operations while holding database locks.

Existing certified lock ordering SHALL NOT be changed casually.

Concurrency mechanisms SHALL be introduced only where a real concurrent mutation risk exists.

---

# 14. IDEMPOTENCY

Operations subject to retries or replay and capable of creating duplicate business effects SHALL define idempotency where required.

Typical candidates include:

- payment execution;
- external submissions;
- webhook processing;
- retryable commands;
- irreversible external effects.

An idempotent operation SHOULD distinguish:

```text id="3hjdu6"
FIRST EXECUTION
SAFE REPLAY
CONFLICTING DUPLICATE
```

Persisted evidence SHOULD be used when durable replay protection is required.

Capability SDDs define concrete mechanisms.

---

# 15. API AND CONTRACT ARCHITECTURE

The platform is API-first.

API contracts SHALL explicitly define applicable:

- ownership scope;
- request contract;
- response contract;
- authorization;
- validation;
- success semantics;
- error semantics;
- concurrency/conflict behavior.

Routes SHOULD communicate ownership context consistently with established API conventions.

DTOs SHALL represent explicit contracts rather than accidentally expose persistence models.

Integration contracts SHOULD remain vendor-neutral when vendor independence is an approved requirement.

---

# 16. ERROR MODEL

The platform SHALL distinguish at minimum:

```text id="j6u8ss"
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
NOT_FOUND
CONFLICT
DOMAIN_INVARIANT_VIOLATION
DEPENDENCY_FAILURE
INTERNAL_ERROR
```

Expected business conflicts MUST NOT be represented as arbitrary internal failures.

Error responses MUST NOT expose:

- secrets;
- credentials;
- inappropriate internal details;
- sensitive information.

Capability SDDs MAY define capability-specific error contracts consistent with this model.

---

# 17. AUDIT ARCHITECTURE

Material business transitions SHOULD preserve durable audit evidence where required.

Evidence MAY include:

```text id="03vjbl"
Tenant
Location
Actor
Operation
Timestamp
Affected Entity
Previous State
Resulting State
Transition / Version
Reason
```

Historical evidence MUST NOT be silently rewritten because current:

- responsibility;
- configuration;
- assignment;
- ownership relationship

later changes.

Audit requirements SHALL be proportional to business, financial, security, and operational importance.

---

# 18. SECURITY

This section is the platform Security Baseline unless an approved higher-authority or
standalone security document explicitly supersedes it and this Global SDD is reconciled.

All capabilities SHALL preserve:

- authentication security;
- tenant isolation;
- server-side authorization;
- secret protection;
- credential protection;
- encryption and appropriate transport security;
- sensitive-log restrictions;
- least necessary data exposure.
- least privilege;
- appropriate data classification, retention, and deletion controls;
- backup and recovery confidentiality, integrity, and access control;
- security-event evidence where material.

Credentials MUST NOT be committed to source.

Secrets MUST NOT be hardcoded, emitted in logs, exposed in client-delivered
configuration, or placed in evidence that does not require them.

Tenant, organization, location, and resource ownership checks MUST survive every API,
integration, background process, backup, restore, and operational boundary.

Security controls MUST NOT be disabled merely to simplify implementation or make tests pass.

Capability-specific security requirements belong in the applicable Capability SDD.

---

# 19. EXTERNAL INTEGRATIONS

External systems SHOULD be isolated behind explicit integration boundaries.

Preferred structure:

```text id="jvt7y0"
APPLICATION / DOMAIN
        ↓
PORT / PROTOCOL
        ↓
ADAPTER
        ↓
EXTERNAL SYSTEM
```

Integrations SHALL define as applicable:

- ownership;
- credential handling;
- timeout;
- failure behavior;
- retry;
- idempotency;
- reconciliation;
- persisted evidence.

External systems MUST NOT silently become authoritative for internal domain state unless explicitly designed.

---

# 20. FRONTEND / BACKEND BOUNDARY

## Backend Owns

- authoritative business state;
- domain invariants;
- authorization;
- transactions;
- concurrency;
- persistence;
- monetary truth;
- auditable transitions.

## Frontend Owns

- presentation;
- interaction;
- navigation;
- accessibility;
- visual state;
- usability validation;
- loading/error/empty states.

Client-side validation improves usability.

It MUST NOT replace authoritative server validation.

Cached frontend state MUST NOT become independent business truth.

---

# 21. FRONTEND ARCHITECTURE

Frontend capabilities SHOULD:

- consume explicit backend contracts;
- reuse established application patterns;
- avoid duplicating backend domain rules;
- handle conflict responses;
- refresh/invalidate authoritative server state after relevant mutations;
- provide loading, empty, error, and unavailable states;
- preserve accessibility;
- preserve responsive behavior.

Visual quality is a product requirement but MUST NOT compromise:

- correctness;
- clarity;
- speed;
- accessibility.

Capability-specific navigation and UX belong in Capability SDDs.

---

# 22. INTERNATIONALIZATION AND LOCALIZATION

Each Location has an applicable native language according to Domain Authority.

A user/session MAY operate in a current language different from the Location native language.

Session-facing UI and conversational interaction SHOULD use the current session language according to applicable domain rules.

Authoritative business values remain invariant across language changes.

In particular:

```text id="y44s35"
LANGUAGE CHANGE
      ≠
MONETARY VALUE CHANGE
```

Operational and generated outputs SHALL follow their applicable language contract.

Capability-specific behavior belongs in Capability SDDs.

---

# 23. MONETARY INTEGRITY

Monetary operations SHALL preserve exact business values and approved precision.

Floating-point arithmetic MUST NOT be used where it can introduce unacceptable monetary error.

Capability-specific rules SHALL define as applicable:

- pricing;
- discounts;
- promotions;
- taxes;
- gratuity;
- checks;
- payments;
- settlements;
- cash movements;
- expenses.

Display formatting MUST NOT modify authoritative monetary value.

Financial history SHALL remain auditable.

---

# 24. TIME AND TIMEZONE

The platform SHALL distinguish:

```text id="05k4g7"
Absolute timestamp
Location-local time
Date-only business value
Business-day interpretation
```

Stored timestamps SHOULD use an unambiguous canonical representation.

User-facing operational time SHOULD respect the applicable Location timezone.

Capability SDDs SHALL define special time semantics where required.

Business-critical timestamps MUST NOT rely on ambiguous timezone interpretation.

---

# 25. FILE AND OBJECT STORAGE

When capabilities require files or binary objects, design SHALL identify:

- business owner;
- tenant/location scope;
- metadata ownership;
- access authorization;
- storage mechanism;
- retention/deletion;
- integrity requirements.

Object storage MUST NOT independently become business authority.

Relational/application state SHOULD preserve authoritative ownership relationships.

Current object-storage technology and usage MUST be verified from repository reality before relying on it.

---

# 26. CACHE AND REDIS

Caching MAY be used for non-authoritative runtime concerns.

A cache MUST NOT become the sole durable source of business truth.

Capabilities using cache SHALL define where relevant:

- authoritative source;
- key ownership;
- expiration;
- invalidation;
- failure behavior;
- stale-data tolerance.

Current Redis usage MUST be established from repository reality rather than assumed globally.

---

# 27. OBSERVABILITY

The platform SHALL provide sufficient operational visibility to diagnose runtime and business-processing failures.

Applicable mechanisms MAY include:

- structured logs;
- correlation identifiers;
- health checks;
- metrics;
- dependency health;
- tracing where justified.

Telemetry MUST NOT expose:

- secrets;
- credentials;
- prohibited payment data;
- inappropriate personal information.

Capability-specific business/operational metrics belong in Capability SDDs.

---

# 28. FAILURE AND RECOVERY

Business-critical operations SHALL resolve to a determinable state.

Expected outcomes SHOULD be classifiable as:

```text id="mt2q57"
COMMITTED
ROLLED_BACK
PERSISTED_RECOVERABLE_STATE
EXPLICIT_FAILURE_REQUIRING_ACTION
```

Ambiguous partial business state SHOULD be prevented wherever technically practical.

Capabilities SHALL define material recovery behavior for:

- transaction failure;
- dependency failure;
- interrupted workflow;
- stale state;
- duplicate request;
- partial external effect.

Recovery MUST preserve authoritative history.

---

# 29. COMPATIBILITY

Existing certified behavior SHALL be preserved unless explicitly changed by approved authority.

Material changes SHALL consider compatibility with:

- persisted data;
- active workflows;
- API consumers;
- frontend;
- external integrations;
- active sessions.

SDD adoption itself is NOT justification for rewriting working certified functionality.

Breaking changes require explicit authority and a defined transition strategy where applicable.

---

# 30. DEPLOYMENT

The platform SHALL preserve containerized deployment compatibility according to repository/deployment configuration.

Runtime components MAY currently include technologies such as:

```text id="w8t61k"
API
MySQL
Redis
MinIO
Nginx
Prometheus
Grafana
```

This list is descriptive, not authoritative deployment inventory.

Actual topology MUST be verified from repository/runtime configuration.

A capability SHALL NOT introduce a new:

- service;
- container;
- database;
- queue;
- cache;
- infrastructure dependency

without justified technical need and approved design.

---

# 31. PERFORMANCE AND SCALABILITY

Capabilities SHOULD avoid:

- obvious N+1 access patterns;
- unbounded queries;
- unnecessary polling;
- unnecessary external calls;
- uncontrolled batch sizes;
- avoidable serialization overhead.

Optimization SHOULD be driven by measured or credible operational requirements.

Scalability decisions SHALL identify the actual growth dimension.

Examples:

- tenants;
- locations;
- concurrent users;
- service sessions;
- orders;
- payments;
- inventory movements;
- operational requests.

Correctness, ownership, security, and auditability take precedence over speculative optimization.

---

# 32. REUSE AND DEPENDENCY DIRECTION

This section is the platform Reuse Policy unless an approved higher-authority or
standalone reuse document explicitly supersedes it and this Global SDD is reconciled.

Functionality that is genuinely domain-independent and likely to be reused SHOULD be considered for a reusable boundary.

Reuse MUST be demonstrated or strongly justified. Similar names or data shapes do not
establish shared ownership. Prefer extracting a proven reusable pattern over predicting
a hypothetical abstraction.

Preferred evolution:

```text id="4h74ri"
LOCAL CAPABILITY
      ↓
REUSABLE MODULE
      ↓
REUSABLE PACKAGE / SERVICE
      ↓
MICROSERVICE
```

Progression is not automatic.

A more distributed boundary requires justification.

Logical reuse does not require a microservice. Prefer the smallest boundary that
preserves ownership, security, runtime simplicity, backward compatibility, and Minimal
Change. Existing consumers and certified contracts MUST be considered before moving or
generalizing shared behavior.

Capability dependencies SHALL remain explicit.

Circular ownership SHOULD be avoided.

A capability SHOULD consume another capability's approved contract rather than mutate its internals directly.

---

# 33. GLOBAL INVARIANTS

## GLOBAL-INV-001 — Tenant Isolation

Business state belonging to one Tenant MUST NOT be accessed or mutated as another Tenant's state.

## GLOBAL-INV-002 — Explicit Ownership

Authoritative mutable state MUST have determinable ownership.

## GLOBAL-INV-003 — Server Enforcement

Critical domain invariants and authorization MUST NOT rely solely on frontend enforcement.

## GLOBAL-INV-004 — Transactional Integrity

Atomic business operations MUST NOT leave unauthorized partial committed state.

## GLOBAL-INV-005 — Historical Integrity

Required historical/audit evidence MUST NOT be silently rewritten by later operational changes.

## GLOBAL-INV-006 — Reuse Before Duplication

Existing authoritative ownership MUST be evaluated before introducing competing implementation.

## GLOBAL-INV-007 — No Silent Technical Drift

Capability implementation MUST NOT silently contradict approved Global or Capability SDD design.

## GLOBAL-INV-008 — Minimal Change

Implementation SHALL avoid unrelated modifications.

## GLOBAL-INV-009 — Determinate Failure

Material failures SHALL leave authoritative business state determinable.

## GLOBAL-INV-010 — Financial Integrity

Authoritative monetary state SHALL preserve exact approved values and auditable history.

---

# 34. CAPABILITY SDD RELATIONSHIP

Capability SDDs inherit this document.

They SHALL define capability-specific:

- ownership;
- invariants;
- lifecycle implementation;
- persistence;
- transactions;
- concurrency;
- APIs;
- authorization;
- audit;
- integrations;
- frontend behavior;
- failure/recovery;
- verification.

They SHOULD reference rather than duplicate global rules.

A Capability SDD MUST NOT silently override this document.

An approved global exception/change must be resolved through the authority hierarchy before implementation.

---

# 35. OPEN GLOBAL DESIGN DECISIONS

Only unresolved decisions with genuine cross-capability impact belong here.

Format:

```text
GLOBAL-QUESTION-<NNN>

Question:
Affected capabilities:
Authority required:
Blocking: YES / NO
Status:

```

Do NOT populate this section with speculative future architecture.
Capability-specific questions belong in the applicable Capability SDD.
Resolved questions SHALL be incorporated into the appropriate authoritative section rather than retained here as historical discussion.

# 36. APPROVAL READINESS

Before this document moves from DRAFT to APPROVED, verify its material assumptions against current repository reality.
At minimum:

[x] Higher-authority document paths verified
[x] Current platform/module boundaries verified
[x] Tenant / Organization / Location model verified
[x] Staff identity/membership model verified
[x] Authentication architecture verified
[x] Authorization architecture verified
[x] Persistence conventions verified
[x] Current migration architecture verified
[x] Transaction conventions verified
[x] Concurrency/locking conventions verified
[x] API architecture verified
[x] Audit architecture verified
[x] External integration architecture verified
[x] Frontend/backend boundary verified
[x] Localization architecture verified
[x] Monetary representation verified
[x] Redis usage verified where relevant
[x] Object-storage usage verified where relevant
[x] Observability architecture verified
[x] Deployment assumptions verified
[x] Existing certified behavior checked for material conflicts
[x] Blocking global design questions resolved

An item MAY be:
N/A — <reason>

when genuinely not applicable.
When this review is complete, the document MAY move to `REVIEWED`, which means
`READY_FOR_APPROVAL`. It MUST remain short of `APPROVED` until the Architecture
Authority completes the approval record.

Repository discovery MAY be used to obtain the required evidence.

## 36.1 Approval Roles and Mechanism

Approval roles and record requirements are defined by
`DOCUMENT_AUTHORITY_HIERARCHY.md` Section 16. The approved model assigns approval of
this Global SDD to the Architecture Authority. Product Owner approval is additionally
required if a revision changes product/domain truth. Codex, test results, certification
evidence, and Git history do not provide approval.

# 37. CHANGE MANAGEMENT

GLOBAL_SDD.md is a living technical-design document.
Update it when an approved permanent technical decision has cross-capability scope.
Examples include material changes to:
- tenancy;
- ownership;
- authentication;
- authorization;
- persistence architecture;
- transaction policy;
- concurrency policy;
- API architecture;
- audit architecture;
- security integration;
- frontend/backend responsibility;
- localization architecture;
- integration architecture.
Do NOT update this document for:
- capability-only design;
- implementation-only corrections;
- isolated bug fixes;
- temporary execution decisions;
- prompt instructions.
Those belong at their appropriate authority level.

For a material change to an approved version:

1. identify affected capabilities and consumers;
2. assess backward compatibility, security, ownership, and data impact;
3. preserve the previous approval/certification record;
4. update the version and obtain the required reapproval;
5. implement only after approval;
6. recertify the changed behavior and affected regression boundary.

# 38. VERSIONING

Meaningful design changes SHOULD update the document version.
Conceptually:
PATCH
Clarification without material technical-design change

MINOR
Backward-compatible cross-capability design extension

MAJOR
Material incompatible cross-capability design change

Repository governance MAY define a different versioning policy.
Git remains the detailed historical record.
Do not turn this document into a development diary.

# 39. AS-DESIGNED / AS-BUILT

Approved global design and implemented platform reality SHOULD remain aligned.
When implementation or repository discovery reveals a material cross-capability discrepancy:
DISCOVER DISCREPANCY
        ↓
CLASSIFY
        ↓
DESIGN CHANGE REQUIRED?
   ┌────┴────┐
   NO        YES
   │          │
   ▼          ▼
FIX        UPDATE CORRECT
IMPLEMENTATION   AUTHORITY
                 ↓
              APPROVE
                 ↓
              IMPLEMENT
        ↓
VERIFY / CERTIFY

Do NOT modify this document merely to legitimize unauthorized implementation drift.
After applicable certification, this document SHOULD accurately represent approved global as-built technical design.

# 40. STATUS LIFECYCLE

The Global SDD lifecycle is:
DRAFT
  ↓
REVIEWED
  ↓
APPROVED
  ↓
IMPLEMENTED
  ↓
CERTIFIED

A later approved global design change MAY create a new version and repeat the lifecycle.
CERTIFIED does NOT mean permanently frozen.
It means the applicable implementation baseline has been demonstrated to conform to that version of the approved global design.

`REVIEWED` means ready for approval. `APPROVED` requires the explicit approval record
defined in Section 1.1 and the authority hierarchy. `IMPLEMENTED` and `CERTIFIED` are
separate evidence-backed transitions.

# 41. IMPLEMENTATION AND CERTIFICATION GATES

- Only an approved Global SDD and approved applicable Capability SDD may govern new
  implementation.
- Implementation completion requires repository evidence; approval alone does not
  prove implementation.
- Certification is independent verification against the approved version and exact
  implementation baseline.
- A certification report cannot approve design or silently remediate a failure.
- Material approved-design changes require reapproval before implementation and
  proportionate recertification afterward.

# 42. TRACEABILITY

Material cross-capability rules SHOULD trace from higher authority through this Global
SDD, applicable Capability SDDs, executable contracts, implementation, and verification.
Approval records and prior certification evidence MUST remain available when a later
version supersedes them.

# 43. DEFINITION OF READY

The Global SDD is ready for approval when:

[x] Applicable higher authority is identified
[x] Cross-capability boundaries are sufficiently defined
[x] Multi-tenancy is defined
[x] Identity/authentication principles are defined
[x] Authorization principles are defined
[x] Ownership principles are defined
[x] Data architecture is defined
[x] Migration principles are defined
[x] Transaction principles are defined
[x] Concurrency principles are defined
[x] Idempotency principles are defined
[x] API/contract architecture is defined
[x] Error model is defined
[x] Audit principles are defined
[x] Security authority is integrated
[x] External integration principles are defined
[x] Frontend/backend boundary is defined
[x] Localization principles are defined
[x] Monetary integrity is defined
[x] Time/timezone principles are defined
[x] Failure/recovery principles are defined
[x] Compatibility principles are defined
[x] Reuse/dependency direction is defined
[x] Global invariants are explicit
[x] Repository assumptions have been verified
[x] No blocking global design question remains

This checklist evaluates global technical-design completeness.
It does not replace capability-specific design.

# 44. DEFINITION OF DONE

The Global SDD governance baseline is operationally established when:

- higher-authority references resolve;
- global technical boundaries and invariants are explicit;
- security and reuse authority have one unambiguous home;
- approval roles, lifecycle, record, and change control are defined;
- implementation and certification gates are explicit;
- Capability SDDs can inherit the approved version without ambiguity;
- no permanent global rule depends exclusively on a prompt;
- the Architecture Authority has explicitly approved the recorded version.

All design/readiness and explicit approval conditions are complete for version 0.2.0.
Implementation and certification remain separate evidence-backed lifecycle states.

# 45. FINAL RULE

GLOBAL_SDD.md is the authoritative technical design for cross-cutting behavior of the Restaurant Intelligence Platform.
It answers:
What technical rules must every applicable capability respect?

It SHALL remain:
GLOBAL
TECHNICAL
AUTHORITATIVE
LIVING
CONCISE
REFERENCE-ORIENTED

It SHALL NOT become:
PRODUCT SPECIFICATION
DOMAIN MODEL
CAPABILITY SDD
AGENT INSTRUCTION MANUAL
SKILL
CODEX PROMPT
DEVELOPMENT DIARY
REPOSITORY DUMP

Use:
Higher Authority
      ↓
GLOBAL_SDD.md
      ↓
Capability SDD
      ↓
Executable Contracts
      ↓
Implementation

When a permanent technical decision affects multiple capabilities:
Place it in the appropriate global authority.

When a permanent technical decision affects only one capability:
Place it in that Capability SDD.

When implementation requires a permanent decision that has not been authorized:
STOP. UPDATE THE CORRECT SOURCE OF TRUTH. THEN CONTINUE.
