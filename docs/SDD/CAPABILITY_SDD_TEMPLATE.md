# RESTAURANT INTELLIGENCE PLATFORM
# CAPABILITY SOFTWARE DESIGN DOCUMENT TEMPLATE

**Capability:** `<CAPABILITY_NAME>`
**Document:** `<CAPABILITY_NAME>_SDD.md`
**Template:** `CAPABILITY_SDD_TEMPLATE.md`
**Status:** DRAFT | REVIEWED | APPROVED | IMPLEMENTED | CERTIFIED | SUPERSEDED
**Version:** `<version>`
**Last Updated:** `<date>`

---

# 1. PURPOSE

Define the authoritative technical design for `<CAPABILITY_NAME>`.

Describe briefly:

- what the capability does;
- why it exists;
- its technical responsibility within the platform.

This document defines technical design, not product strategy or independent domain truth.

---

# 2. AUTHORITY

## 2.1 Governing Sources

Reference only applicable authoritative sources.

```text
Product Authority:
Domain Authority:
Global Architectural Authority:
Global SDD:
Applicable ADRs:
Security Baseline:
Reuse Policy:
Other:
```

When no approved standalone security or reuse document exists, reference
`GLOBAL_SDD.md` Section 18 for the Security Baseline and Section 32 for the Reuse
Policy.

This SDD inherits all applicable higher-authority rules.

Conflict handling follows `DOCUMENT_AUTHORITY_HIERARCHY.md`.

## 2.2 Authority of This SDD

This document is authoritative for the technical design of `<CAPABILITY_NAME>`.

Codex prompts, conversations, implementation reports, temporary plans, and tests do not independently redefine this design.

## 2.3 Approval Record

```text
Document path:
Document version:
Approving authority/role:
Explicit decision: PENDING | APPROVED | REJECTED
Decision date:
Approval evidence/reference:
Open conditions:
```

`REVIEWED` means `READY_FOR_APPROVAL`; it is not approval. Complete this record before
changing status to `APPROVED`. A Git commit, test result, certification report, or Codex
report is not approval evidence by itself.

---

# 3. CAPABILITY BOUNDARY

Define explicit ownership.

## Owns

- `<responsibility>`
- `<responsibility>`

## Does Not Own

- `<responsibility>`
- `<responsibility>`

Cover where applicable:

- domain/application responsibility;
- persistence;
- API;
- frontend;
- integrations;
- audit evidence.

Avoid duplicated or ambiguous ownership.

---

# 4. SCOPE, NON-GOALS AND DEFERRED

## 4.1 In Scope

- `<behavior>`
- `<behavior>`

## 4.2 Non-Goals / Out of Scope

- `<excluded behavior>`
- `<excluded behavior>`

Out-of-scope functionality MUST NOT be introduced opportunistically.

## 4.3 Deferred

| ID | Requirement | Reason | Dependency | Blocking |
|---|---|---|---|---|
| | | | | YES / NO |

Deferred requirements remain governed by their original authoritative source.

---

# 5. EXISTING SYSTEM / DISCOVERY BASELINE

Complete this section for an existing capability.

```text
Repository:
Branch:
Commit:
Migration head:

Relevant backend:
Relevant frontend:
Relevant domain modules:
Relevant tables:
Relevant endpoints:
Relevant integrations:
Relevant tests:
Relevant documentation:
```

Summarize relevant existing behavior.

Classify important existing components where useful as:

```text
CERTIFIED
IMPLEMENTED_NOT_CERTIFIED
LEGACY
PARTIAL
DEPRECATED
UNKNOWN
```

Record material discrepancies between documentation, executable contracts, implementation, and tests.

Do NOT silently resolve authority conflicts.

For a completely new capability:

```text
NO EXISTING CAPABILITY IMPLEMENTATION
```

---

# 6. REUSE ANALYSIS

Identify existing functionality that should be reused.

| Component | Owner | Reuse | Required Change | Risk |
|---|---|---|---|---|
| | | | | |

Explicitly identify functionality that MUST NOT be duplicated.

For potentially cross-project functionality, evaluate:

```text
Candidate:
Domain-independent: YES / NO
Likely reusable: YES / NO
Recommended boundary:
Extract now: YES / NO
Reason:
```

Follow `GLOBAL_SDD.md` Section 32 and any approved standalone reuse authority it
explicitly references.

Do not introduce a service or microservice without a justified ownership, reuse, or runtime boundary.

---

# 7. ACTORS AND DOMAIN CONCEPTS

## 7.1 Actors

| Actor | Responsibility | Relevant Authorization |
|---|---|---|
| | | |

Include only actors relevant to this capability.

## 7.2 Domain Concepts

| Concept | Meaning | Authoritative Source | Technical Representation |
|---|---|---|---|
| | | | |

Do NOT redefine established domain truth.

Missing domain decisions MUST be resolved in Domain Authority before implementation depends on them.

---

# 8. INVARIANTS

Define critical capability invariants.

```text
CAP-INV-001

Rule:
Authority:
Enforcement:
Failure behavior:
Verification:
```

Repeat as required.

Critical business invariants SHOULD be enforced server-side where technically applicable.

Frontend behavior MUST NOT be the sole enforcement of authoritative invariants.

---

# 9. LIFECYCLE AND KEY FLOWS

## 9.1 State Model

If applicable:

```text
STATE_A
   ↓
STATE_B
   ↓
STATE_C
```

Define allowed transitions:

| From | Action | To | Preconditions | Actor |
|---|---|---|---|---|
| | | | | |

Identify:

- initial states;
- terminal states;
- forbidden transitions;
- irreversible transitions.

If no lifecycle exists:

```text
NOT APPLICABLE
```

## 9.2 Key Use Cases

For material workflows:

```text
UC-001 — <NAME>

Actor:
Preconditions:
Trigger:
Main flow:
Postconditions:
Failure cases:
```

Focus on behavior that affects design.

---

# 10. OWNERSHIP

Define ownership of persisted and operational state.

| Entity / State | Owner | Scope | Cross-Owner Access |
|---|---|---|---|
| | | | |

Address where applicable:

- Tenant;
- Organization;
- Location;
- Service Session;
- Resource;
- Membership;
- capability aggregate.

Cross-tenant ownership ambiguity is prohibited.

---

# 11. DATA MODEL AND INTEGRITY

## 11.1 Persistence

For each important entity/table:

```text
Entity/Table:
Purpose:
Primary key:
Tenant ownership:
Location ownership:
Important fields:
Foreign keys:
Unique constraints:
Check constraints:
Indexes:
Deletion behavior:
```

Do not reproduce every ORM implementation detail.

## 11.2 Relationships

Describe or diagram important relationships.

## 11.3 Integrity

Identify database-enforced integrity:

- foreign keys;
- composite ownership constraints;
- uniqueness;
- checks;
- nullability;
- deletion restrictions.

Identify invariants requiring application-level enforcement.

## 11.4 Migration

```text
Current migration head:
Migration required: YES / NO
Affected tables:
Data migration required:
Destructive change: YES / NO
Backward compatibility:
Production considerations:
```

Persisted business history MUST NOT be destroyed or reinterpreted without explicit authority.

---

# 12. APPLICATION / SERVICE DESIGN

Define material application components.

| Component | Responsibility | Inputs / Outputs | Dependencies |
|---|---|---|---|
| | | | |

For important services specify:

```text
Transaction ownership:
Side effects:
Failure behavior:
```

Responsibilities should remain explicit and bounded.

---

# 13. TRANSACTIONS, CONCURRENCY AND IDEMPOTENCY

## 13.1 Transaction Boundaries

For important mutations:

```text
Operation:
Reads / locks:
Writes:
Commit point:
Rollback behavior:
External side effects:
```

Operations requiring atomicity MUST remain atomic.

## 13.2 Concurrency

For concurrency-sensitive operations:

```text
Operation:
Risk:
Locking strategy:
Lock order:
Revalidation:
Conflict behavior:
```

Follow Global SDD locking rules.

## 13.3 Idempotency

Where applicable:

```text
Operation:
Required: YES / NO
Idempotency mechanism:
Persisted evidence:
Replay behavior:
Duplicate side-effect prevention:
```

Use `NOT APPLICABLE` where appropriate.

---

# 14. API AND DTO CONTRACTS

## 14.1 API

For each material endpoint:

```text
Method:
Path:
Purpose:
Authorization:
Request:
Response:
Success status:
Error statuses:
Concurrency behavior:
Audit effect:
```

## 14.2 DTOs / Schemas

For important contracts:

```text
DTO:
Direction:
Required fields:
Optional fields:
Validation:
Immutability:
Compatibility:
```

Executable contracts MUST conform to this design.

Do not make implementation prompts the sole location of API decisions.

---

# 15. AUTHENTICATION AND AUTHORIZATION

General authentication/authorization architecture is inherited from `GLOBAL_SDD.md`.

Document capability-specific behavior only.

## 15.1 Authentication

```text
Special authentication behavior:
```

or:

```text
INHERITS GLOBAL SDD WITHOUT EXCEPTION
```

## 15.2 Authorization

| Operation | Required Capability | Scope | Additional Rule |
|---|---|---|---|
| | | | |

Address:

- tenant scope;
- location scope;
- membership;
- ownership;
- actor-specific restrictions.

Frontend visibility MUST NOT replace backend authorization.

---

# 16. AUDIT

Identify material auditable operations.

| Operation | Actor | Evidence | Before/After Required |
|---|---|---|---|
| | | | |

Audit design should preserve sufficient evidence to reconstruct important business transitions.

Do not duplicate Global SDD audit conventions.

---

# 17. INTEGRATIONS AND CROSS-CAPABILITY DEPENDENCIES

## 17.1 External Integrations

For each material integration:

```text
System:
Purpose:
Port / Adapter:
Credential ownership:
Timeout / Retry:
Failure behavior:
Idempotency:
Persisted evidence:
```

## 17.2 Internal Capability Dependencies

| Capability | Dependency | Direction | Contract | Failure Impact |
|---|---|---|---|---|
| | | | | |

Avoid circular ownership.

## 17.3 Events / Async Processing

If required:

```text
Event / Job:
Producer:
Consumer:
Delivery expectation:
Ordering:
Retry:
Duplicate handling:
```

Otherwise:

```text
NOT APPLICABLE
```

Do not introduce asynchronous infrastructure speculatively.

---

# 18. FRONTEND AND UX

Complete when the capability has user-facing behavior.

## 18.1 Frontend Responsibility

Define:

- screens/routes;
- information presented;
- primary actions;
- navigation;
- client state;
- invalidation/refetch;
- conflict handling.

Example:

```text
Screen:
Route:
Actor:
Primary information:
Primary actions:
Server-state refresh:
```

## 18.2 Frontend / Backend Boundary

Backend remains authoritative for:

- domain invariants;
- authorization;
- monetary truth;
- persistence;
- transactional correctness.

Frontend owns:

- presentation;
- interaction;
- navigation;
- usability validation;
- visual state;
- accessibility.

## 18.3 UX Requirements

Define only requirements with implementation impact:

- accessibility;
- responsive behavior;
- confirmations;
- destructive-action protection;
- empty/loading/error states;
- conflict recovery;
- polling/realtime behavior.

## 18.4 Validation

Define:

- platform-owned field validation;
- server validation;
- domain conflict presentation;
- localization of validation.

---

# 19. INTERNATIONALIZATION AND GENERATED OUTPUTS

Inherit global localization rules.

Document capability-specific behavior.

```text
Session language behavior:
Location-native language behavior:
Translated UI:
Invariant values:
```

For printing/generated output:

```text
Output:
Trigger:
Language:
Destination / Printer:
Authoritative data:
Failure behavior:
```

Use `NOT APPLICABLE` where appropriate.

---

# 20. SECURITY AND PRIVACY

Reference `GLOBAL_SDD.md` Section 18 and any approved standalone security authority it
explicitly references.

Document only capability-specific concerns.

Consider:

- sensitive information;
- tenant isolation;
- privilege escalation;
- credential exposure;
- replay;
- external callbacks;
- personal data;
- logging restrictions.

```text
Security concerns:
Required controls:
Personal data:
Visibility:
Logging restrictions:
```

Do not duplicate global security policy.

---

# 21. FAILURE AND RECOVERY

For material failure modes:

| Failure | Persisted State | User/System Result | Recovery |
|---|---|---|---|
| | | | |

Address where applicable:

- transaction rollback;
- process interruption;
- stale client state;
- duplicate request;
- external dependency failure;
- partially completed workflow.

Failures MUST NOT silently leave ambiguous business state.

---

# 22. COMPATIBILITY AND LEGACY

Define required compatibility with:

- persisted data;
- existing API clients;
- frontend;
- active sessions;
- external integrations;
- certified workflows.

For retained legacy behavior:

```text
Behavior:
Reason retained:
Dependency:
Removal condition:
```

Breaking changes require explicit authority.

---

# 23. PERFORMANCE AND SCALABILITY

Document only meaningful constraints.

```text
Expected load:
Latency-sensitive operations:
Expected list/data size:
Concurrency considerations:
Polling/batch constraints:
Known scale threshold:
```

Do not introduce speculative optimization or infrastructure.

---

# 24. IMPLEMENTATION BOUNDARIES

Explicitly constrain implementation.

## Allowed

- `<change>`
- `<change>`

## Conditionally Allowed

- `<change requiring explicit condition>`

## Prohibited

- unrelated refactoring;
- unrelated renaming;
- formatting sweeps;
- dependency upgrades without need;
- unrelated architecture redesign;
- unrelated schema/API changes;
- unrelated frontend redesign.

Minimal Change applies.

Classify expected impact:

```text
Backend: YES / NO
Frontend: YES / NO
Database: YES / NO
API: YES / NO
Infrastructure: YES / NO
External integration: YES / NO
```

---

# 25. IMPLEMENTATION SEQUENCE

Define only the dependency-driven sequence required for this capability.

Example:

```text
1. Persistence
2. Application/domain integration
3. API
4. Frontend
5. Targeted verification
6. Regression
7. Certification
```

When useful, define implementation units:

```text
UNIT:
Objective:
Depends on:
Allowed changes:
Verification:
Exit condition:
```

Implementation units may map to individual Codex prompts.

They are not independent sources of truth.

---

# 26. TEST STRATEGY

Identify required test layers.

| Requirement / Invariant | Test Level | Required Verification |
|---|---|---|
| | | |

Consider as applicable:

- unit/domain;
- service;
- persistence;
- migration;
- API;
- authorization;
- concurrency;
- integration;
- frontend;
- E2E.

Testing depth SHALL be proportional to risk.

---

# 27. REGRESSION SCOPE

## Direct

Functionality directly modified.

```text
Affected:
Risk:
Verification:
```

## Secondary

Functionality depending on changed behavior.

```text
Affected:
Dependency:
Verification:
```

## Collateral

Functionality potentially affected through shared components.

```text
Affected:
Shared dependency:
Verification:
```

Do not execute broad regression mechanically when targeted evidence is sufficient.

Do not omit broad regression when architectural impact requires it.

---

# 28. CERTIFICATION SCENARIOS

Define concrete scenarios required for certification.

```text
V1 — <NAME>

Setup:
Action:
Expected result:
Evidence:
```

Repeat as necessary.

Include material:

- happy paths;
- invariant violations;
- authorization failures;
- concurrency/conflicts;
- stale state;
- integration failures;
- recovery paths.

---

# 29. ACCEPTANCE AND PASS / FAIL

For each material acceptance criterion:

```text
AC-001

Requirement:
Verification:
PASS:
FAIL:
```

Overall result:

```text
PASS
FAIL
PASS_WITH_APPROVED_EXCEPTIONS
BLOCKED
```

`PASS` requires:

- required behavior implemented;
- critical invariants satisfied;
- required tests passing;
- required regression passing;
- certification scenarios passing;
- no unauthorized design deviation;
- no blocking security issue.

---

# 30. STOP CONDITIONS

Implementation MUST stop and report instead of guessing when:

1. higher-authority requirements materially conflict;
2. a required domain decision is missing;
3. Global SDD and required capability behavior conflict;
4. ownership cannot be determined;
5. a new permanent architectural decision is required;
6. destructive persistence change lacks authority;
7. required security behavior cannot be satisfied;
8. implementation requires prohibited scope expansion;
9. repository reality materially contradicts the approved design;
10. safe certification cannot be established.

Report:

```text
STOP CONDITION:
Observed:
Expected:
Affected authority:
Affected components:
Reason:
Alternatives:
Recommended decision:
Changes already made:
```

Permanent decisions discovered during implementation MUST be promoted to the appropriate authoritative source before implementation continues.

---

# 31. OPEN QUESTIONS, RISKS AND DEFERRED ITEMS

## Open Questions

| Question | Impact | Blocking | Required Authority |
|---|---|---|---|
| | | YES / NO | |

All blocking questions MUST be resolved before implementation/certification as applicable.

## Risks

| Risk | Impact | Mitigation | Residual Risk |
|---|---|---|---|
| | | | |

Include only material risks.

## Deferred Items

Reference Section 4.3 rather than duplicating requirement definitions.

---

# 32. TRACEABILITY

Maintain traceability for material requirements only.

| Requirement / Rule | Authority | SDD Section | Implementation | Verification |
|---|---|---|---|---|
| | | | | |

Prioritize traceability for:

- critical domain rules;
- ownership;
- authorization;
- money;
- security;
- concurrency;
- external side effects.

Avoid line-by-line traceability bureaucracy.

---

# 33. CERTIFICATION EVIDENCE

Complete when certification occurs.

```text
SDD version:

Repository:
Branch:
Commit:
Working tree:
Migration head:

Backend targeted tests:
Backend regression:
Frontend tests:
E2E:
Typecheck:
Build:
Migration verification:

Certification scenarios:
V1:
V2:
V3:

Known deviations:
Approved exceptions:

Result:
Certification date:
```

Certification applies only to the defined capability and regression boundary.

Before certification, reconcile material differences between approved design and implemented reality.

The resulting document becomes the certified **as-built SDD**.

---

# 34. DEFINITION OF READY

The SDD is `READY FOR IMPLEMENTATION` when:

```text
[ ] Authority is identified
[ ] Capability boundary is explicit
[ ] Scope is bounded
[ ] Existing implementation was inspected where applicable
[ ] Reuse was evaluated
[ ] Critical domain concepts are known
[ ] Critical invariants are explicit
[ ] Ownership is unambiguous
[ ] Persistence is sufficiently designed where applicable
[ ] API contracts are sufficiently designed where applicable
[ ] Transactions/concurrency are defined where relevant
[ ] Authorization/security requirements are known
[ ] Implementation boundaries are explicit
[ ] Verification and certification criteria are defined
[ ] No blocking design question remains
```

Items may be `N/A` with justification.

Only after this state SHOULD implementation prompts be generated.

---

# 35. DEFINITION OF DONE

The capability is `DONE` when:

```text
[ ] Approved design is implemented
[ ] Executable contracts conform to the SDD
[ ] Critical invariants are verified
[ ] Required tests pass
[ ] Required regression passes
[ ] Required certification scenarios pass
[ ] No blocking security defect remains
[ ] Approved exceptions, if any, are recorded
[ ] Certification evidence identifies the exact design and implementation baseline
[ ] The SDD reflects certified as-built reality
```

`DONE` does not mean permanently frozen. A later material change returns the affected
design through review, explicit approval, implementation, and proportionate
recertification while preserving prior approval/certification evidence.
