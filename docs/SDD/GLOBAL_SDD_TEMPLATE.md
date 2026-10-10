# RESTAURANT INTELLIGENCE PLATFORM
# GLOBAL SOFTWARE DESIGN DOCUMENT

**Document:** `GLOBAL_SDD.md`
**Template:** `GLOBAL_SDD_TEMPLATE.md`
**Status:** DRAFT | REVIEWED | APPROVED | IMPLEMENTED | CERTIFIED
**Version:** `<version>`
**Last Updated:** `<date>`

---

# 1. PURPOSE

Define the platform-wide technical design that every Restaurant Intelligence Platform capability must respect.

This document contains cross-cutting technical design.

It MUST NOT become a collection of detailed domain-specific behavior.

---

# 2. AUTHORITY AND REFERENCES

## 2.1 Higher-authority sources

List applicable:

- Product Constitution
- Product Vision
- Domain Model
- Development Principles
- `GLOBAL_SDD.md` Section 32 as the Reuse Policy, unless superseded by an approved
  standalone authority
- `GLOBAL_SDD.md` Section 18 as the Security Baseline, unless superseded by an approved
  standalone authority
- ADRs
- other architectural authorities

## 2.2 Relationship to Capability SDDs

All Capability SDDs inherit this Global SDD.

A Capability SDD MUST NOT silently contradict this document.

## 2.3 Approval Record

```text
Document path:
Document version:
Approving authority/role: Architecture Authority
Explicit decision: PENDING | APPROVED | REJECTED
Decision date:
Approval evidence/reference:
Open conditions:
```

`REVIEWED` means `READY_FOR_APPROVAL`; it is not approval. The record must be complete
before status becomes `APPROVED`.

---

# 3. SYSTEM CONTEXT

Describe:

- platform purpose;
- major actors;
- major systems;
- external dependencies;
- trust boundaries.

Include diagrams when they materially improve understanding.

---

# 4. ARCHITECTURAL PRINCIPLES

Define enforceable technical principles.

For each principle:

```text
ID:
Rule:
Rationale:
Enforcement:
Exceptions:
```

Examples:

- multi-tenant isolation;
- API-first behavior;
- minimal change;
- explicit ownership;
- deterministic behavior;
- transactional correctness;
- portability;
- auditability;
- observability;
- reusable capability boundaries;
- avoidance of premature distributed complexity.

---

# 5. SYSTEM BOUNDARIES

Define:

- platform boundary;
- backend boundary;
- frontend boundary;
- infrastructure boundary;
- external integration boundary;
- reusable Enterprise Core boundary;
- domain application boundary.

---

# 6. TENANCY MODEL

Define:

- Tenant;
- Organization;
- Location;
- tenant context;
- location context;
- cross-tenant restrictions;
- tenant-scoped identifiers;
- database isolation rules;
- API propagation;
- background-process propagation.

State explicit invariants.

---

# 7. IDENTITY, AUTHENTICATION AND SESSION MODEL

Define platform-wide:

- identity concepts;
- authentication boundaries;
- session behavior;
- staff vs diner identity where applicable;
- credential ownership;
- authentication context propagation.

Do not duplicate capability-specific login UX.

---

# 8. AUTHORIZATION MODEL

Define:

- roles;
- capabilities;
- grants;
- location scope;
- membership;
- authorization evaluation;
- backend enforcement;
- frontend responsibility.

Include global authorization invariants.

---

# 9. OWNERSHIP MODEL

Define:

- aggregate ownership;
- tenant ownership;
- location ownership;
- service/domain ownership;
- rules preventing ambiguous ownership.

---

# 10. DATA ARCHITECTURE

Define global persistence principles:

- relational database authority;
- MySQL expectations;
- ORM conventions;
- migrations;
- foreign-key strategy;
- composite ownership constraints;
- deletion behavior;
- CHECK/UNIQUE constraints;
- portability requirements;
- JSON usage;
- timestamps;
- identifiers.

---

# 11. TRANSACTION MODEL

Define:

- transaction boundaries;
- atomicity expectations;
- commit ownership;
- rollback behavior;
- service/repository responsibilities;
- external-side-effect boundaries.

---

# 12. CONCURRENCY AND LOCKING

Define platform-wide rules for:

- pessimistic locking;
- optimistic concurrency where applicable;
- lock ordering;
- stale-write prevention;
- revalidation before commit;
- deadlock minimization.

Capability-specific locking sequences belong in Capability SDDs.

---

# 13. IDEMPOTENCY

Define:

- operations requiring idempotency;
- idempotency keys;
- replay behavior;
- duplicate prevention;
- persisted evidence.

---

# 14. API DESIGN

Define common:

- route conventions;
- tenant/location scoping;
- DTO rules;
- status codes;
- pagination;
- filtering;
- versioning;
- mutation behavior;
- error representation.

---

# 15. ERROR AND CONFLICT CONTRACT

Define platform error categories.

Examples:

```text
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
NOT_FOUND
CONFLICT
DOMAIN_INVARIANT_VIOLATION
DEPENDENCY_FAILURE
INTERNAL_ERROR
```

Define frontend expectations for each category.

---

# 16. AUDIT ARCHITECTURE

Define:

- what requires auditing;
- actor identity;
- timestamps;
- before/after state;
- reason/evidence;
- immutable historical requirements;
- audit ownership.

---

# 17. SECURITY ARCHITECTURE

This section is the platform Security Baseline unless an approved standalone authority
is explicitly referenced and reconciled here.

Define only technical integration points necessary for implementation.

Include:

- secrets;
- credentials;
- encryption;
- transport security;
- authorization enforcement;
- sensitive logging restrictions;
- external credential handling.

---

# 18. EXTERNAL INTEGRATION ARCHITECTURE

Define:

- adapters;
- ports/protocols;
- vendor-neutral boundaries;
- retries;
- timeouts;
- failure isolation;
- credentials;
- external side effects.

---

# 19. EVENT AND ASYNCHRONOUS PROCESSING

If applicable, define:

- event ownership;
- delivery guarantees;
- retries;
- ordering;
- duplicate handling;
- background job ownership.

If not currently required:

```text
NOT CURRENTLY APPLICABLE
```

Do not design speculative infrastructure.

---

# 20. FRONTEND / BACKEND RESPONSIBILITY BOUNDARY

Define globally:

## Backend owns

- domain authority;
- authorization;
- invariants;
- monetary truth;
- persistence;
- concurrency;
- audit evidence.

## Frontend owns

- presentation;
- interaction;
- navigation;
- client-side usability;
- visual state;
- accessibility.

Client validation MUST NOT replace server authority.

---

# 21. FRONTEND ARCHITECTURE PRINCIPLES

Define:

- routing;
- session context;
- API access;
- cache/state ownership;
- invalidation;
- conflict refresh;
- polling/realtime principles;
- reusable components;
- error presentation.

Avoid capability-specific UI layouts here.

---

# 22. INTERNATIONALIZATION AND LOCALIZATION

Define platform-wide:

- native location language;
- session current language;
- translation responsibility;
- invariant monetary values;
- operational-language behavior;
- generated-document language;
- fallback rules.

---

# 23. OBSERVABILITY

Define platform-wide observability requirements.

Include:

- structured logging;
- log levels;
- request correlation identifiers;
- tenant/location context in operational telemetry;
- metrics;
- health checks;
- readiness/liveness behavior;
- tracing where justified;
- external dependency visibility;
- failure visibility.

Sensitive information MUST NOT be exposed through logs, metrics, traces, or diagnostic endpoints.

Capability-specific business metrics belong in the corresponding Capability SDD.

---

# 24. CONFIGURATION MANAGEMENT

Define:

- environment configuration;
- runtime configuration;
- secrets separation;
- tenant/location configuration;
- default behavior;
- validation;
- startup failure behavior;
- configuration ownership.

Configuration MUST NOT silently override domain invariants.

---

# 25. TIME AND DATE MODEL

Define:

- canonical timestamp storage;
- timezone handling;
- location-local time;
- UTC boundaries where applicable;
- date-only values;
- business-day interpretation;
- audit timestamp rules.

Avoid ambiguous local timestamps.

---

# 26. MONETARY MODEL

Define platform-wide:

- monetary representation;
- currency ownership;
- precision;
- rounding;
- calculation boundaries;
- display versus persisted monetary values.

Floating-point arithmetic MUST NOT be used where exact monetary behavior is required.

Capability-specific pricing, taxation, payment, gratuity, and settlement rules belong in their respective Capability SDDs/domain authority.

---

# 27. FILE AND OBJECT STORAGE

Where applicable, define:

- object-storage authority;
- metadata ownership;
- access control;
- tenant isolation;
- naming/key strategy;
- retention;
- deletion;
- integrity validation.

Do not introduce object storage when relational persistence is sufficient.

---

# 28. CACHING

Define:

- permitted cache categories;
- authoritative source;
- invalidation;
- tenant isolation;
- stale-data tolerance;
- failure behavior.

A cache MUST NOT become an independent source of business truth.

---

# 29. REUSABILITY AND EXTRACTION

This section is the platform Reuse Policy unless an approved standalone authority is
explicitly referenced and reconciled here.

Define the technical criteria for deciding whether functionality remains:

- inside the current application;
- a reusable internal module;
- a reusable package;
- a service;
- a microservice.

Extraction MUST be justified by genuine reuse or ownership/runtime boundaries.

Do not create distributed architecture solely for conceptual purity.

---

# 30. DEPENDENCY DIRECTION

Define permitted dependency direction between:

- API layer;
- application/service layer;
- domain layer;
- persistence;
- adapters/integrations;
- infrastructure.

Circular ownership MUST be avoided.

Capability SDDs MUST explicitly identify any exceptional dependency.

---

# 31. DATABASE MIGRATION POLICY

Define:

- Alembic ownership;
- forward migration rules;
- downgrade expectations where applicable;
- data migration strategy;
- production compatibility;
- destructive-change policy;
- deployment ordering;
- schema verification.

Existing production data MUST be considered before destructive schema changes.

---

# 32. BACKWARD COMPATIBILITY

Define when compatibility is required for:

- API consumers;
- persisted data;
- active sessions;
- external integrations;
- frontend/backend deployment sequencing.

Breaking changes require explicit design approval.

---

# 33. DEPLOYMENT ARCHITECTURE

Define current deployment assumptions without designing speculative infrastructure.

Include where applicable:

- containers;
- API runtime;
- database;
- Redis;
- object storage;
- reverse proxy;
- observability services;
- external services.

Capability SDDs SHOULD NOT redefine deployment topology unless the capability genuinely requires a new runtime component.

---

# 34. FAILURE AND RECOVERY PRINCIPLES

Define:

- transactional recovery;
- external dependency failures;
- retry boundaries;
- partial failure behavior;
- crash/restart expectations;
- persisted recovery evidence;
- operator-visible failure state.

Failures MUST NOT silently produce ambiguous business state.

---

# 35. TESTING ARCHITECTURE

Define expected layers:

```text
UNIT
  ↓
DOMAIN / SERVICE
  ↓
PERSISTENCE
  ↓
API CONTRACT
  ↓
INTEGRATION
  ↓
FRONTEND
  ↓
E2E
  ↓
TARGETED REGRESSION
```

Not every capability requires every layer.

Testing depth SHALL be proportional to risk.

---

# 36. CERTIFICATION MODEL

Certification demonstrates that implementation conforms to approved authority.

Certification SHOULD include:

- repository state;
- migration state;
- targeted tests;
- relevant regressions;
- frontend verification where applicable;
- executable contract verification;
- unresolved deviations;
- PASS/FAIL result.

A passing test suite alone does not automatically constitute architectural certification.

---

# 37. MINIMAL CHANGE POLICY

Implementation SHALL modify only what is necessary to satisfy the approved design.

Codex MUST NOT perform unrelated:

- refactoring;
- renaming;
- formatting sweeps;
- dependency upgrades;
- architecture redesign;
- cleanup.

Unless explicitly authorized.

---

# 38. REGRESSION POLICY

Changes must consider:

- direct regression;
- secondary regression;
- collateral regression.

Verification scope SHALL be based on actual dependency and behavior impact.

---

# 39. LEGACY COMPATIBILITY

Existing certified functionality remains valid unless:

- explicitly superseded;
- proven defective;
- incompatible with higher authority;
- modified by approved design.

SDD adoption itself is NOT justification for rewriting working functionality.

---

# 40. CAPABILITY SDD REQUIREMENTS

Every new material capability SHOULD have a Capability SDD before implementation.

A Capability SDD is required when a change introduces or materially changes one or more of:

- persistent entities;
- business lifecycle;
- authorization;
- externally visible API;
- transaction boundary;
- concurrency behavior;
- cross-capability integration;
- external integration;
- significant frontend workflow;
- security behavior.

Small implementation corrections do not require a new SDD.

---

# 41. DESIGN EXCEPTION PROCESS

If a Capability SDD requires behavior inconsistent with this Global SDD:

```text
DO NOT IMPLEMENT EXCEPTION
        ↓
DOCUMENT CONFLICT
        ↓
DETERMINE WHETHER:
- Global SDD changes
- Capability design changes
- ADR is required
        ↓
APPROVE
        ↓
IMPLEMENT
```

No implicit exceptions.

---

# 42. OPEN DESIGN QUESTIONS

Maintain only unresolved architectural questions that materially block or influence implementation.

For each:

```text
ID:
Question:
Affected capabilities:
Options:
Decision owner:
Blocking: YES | NO
Status:
```

Resolved questions MUST be converted into the appropriate authoritative section or ADR.

---

# 43. NON-GOALS

Explicitly identify architecture intentionally NOT being introduced.

Examples:

- unnecessary microservices;
- speculative event infrastructure;
- premature multi-region deployment;
- duplicate sources of truth.

---

# 44. GLOBAL INVARIANT REGISTER

Maintain important cross-platform invariants.

Format:

```text
GLOBAL-INV-001

Rule:
Rationale:
Enforcement:
Verification:
Affected components:
```

Capability-specific invariants MUST remain in Capability SDDs.

---

# 45. TRACEABILITY

For important cross-platform decisions:

```text
Requirement
    ↓
Architectural Rule
    ↓
Global SDD Section
    ↓
Capability SDD
    ↓
Implementation
    ↓
Verification
```

Avoid traceability bureaucracy for trivial implementation details.

---

# 46. SDD CHANGE LOG

Record meaningful design changes only.

| Version | Date | Change | Reason | Authority |
|---|---|---|---|---|
| | | | | |

Do NOT use this section as a substitute for Git history.

---

# 47. CERTIFICATION STATUS

```text
Global SDD version:
Implementation baseline:
Repository branch:
Repository commit:
Database migration head:
Certification status:
Known deviations:
```

Possible certification statuses:

```text
NOT_IMPLEMENTED
PARTIALLY_IMPLEMENTED
IMPLEMENTED_NOT_CERTIFIED
CERTIFIED
CERTIFIED_WITH_EXCEPTIONS
SUPERSEDED
```

---

# 48. FINAL GLOBAL DESIGN RULE

The Global SDD is the authoritative technical design for cross-cutting platform behavior.

It MUST:

- remain smaller than the total domain documentation;
- reference rather than duplicate higher authority;
- contain durable technical decisions;
- avoid capability-specific implementation detail;
- evolve when global architecture genuinely changes.

It MUST NOT become a development diary.

---

# 49. DEFINITION OF DONE

The Global SDD is considered operationally established when:

- higher-authority references are identified;
- global technical boundaries are explicit;
- cross-cutting invariants are documented;
- conflict rules are established;
- Capability SDDs can inherit it without ambiguity;
- no permanent global technical rule depends exclusively on a Codex prompt.
