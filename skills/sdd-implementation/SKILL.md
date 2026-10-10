# SKILL — SDD IMPLEMENTATION

**Skill ID:** `sdd-implementation`
**Version:** 1.0.0
**Status:** ACTIVE
**Type:** Controlled Software Implementation
**Repository Mutation:** ALLOWED WITHIN AUTHORIZED SCOPE
**Design Authority:** NONE

---

# 1. PURPOSE

Implement an approved Capability SDD, or an explicitly selected Implementation Unit within it, using verified repository reality and Minimal Change.

This Skill answers:

> How should an implementation agent transform the current repository into the approved SDD design without introducing unauthorized decisions or unrelated changes?

This Skill implements approved design.

It does NOT:

- create product requirements;
- create domain rules;
- redesign the capability;
- approve design changes;
- certify the completed capability.

---

# 2. CORE CONTRACT

```text id="3sqyyk"
APPROVED CAPABILITY SDD
          +
GLOBAL SDD
          +
REPOSITORY REALITY
          +
AUTHORIZED IMPLEMENTATION UNIT
          ↓
      MINIMAL CHANGE
          ↓
     IMPLEMENTATION
          ↓
 TARGETED VERIFICATION
          ↓
 IMPLEMENTATION REPORT
```

The SDD defines what must exist.

This Skill defines how to implement it safely.

---

# 3. REQUIRED SOURCES

Read:

```text id="44kbp7"
AGENTS.md
docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
docs/SDD/GLOBAL_SDD.md
<APPLICABLE_CAPABILITY_SDD>
```

Read the applicable:

```text id="eugm79"
skills/sdd-implementation/SKILL.md
```

Read additionally only when required by the SDD:

- Product Authority;
- Domain Authority;
- ADRs;
- Security Baseline;
- Reuse Policy;
- related Capability SDDs;
- executable contracts.

Do not load unrelated documentation by default.

---

# 4. PRECONDITIONS

Before implementation verify:

```text id="1kttr8"
[ ] Capability SDD exists
[ ] Capability SDD status is APPROVED or implementation is otherwise explicitly authorized
[ ] Requested implementation scope is identifiable
[ ] Required authority is available
[ ] Repository is accessible
[ ] Blocking SDD questions are resolved
```

If the SDD has not passed the required design/governance process:

```text id="pyi6q1"
STOP
```

Do not implement an unapproved material design merely because it appears complete.

---

# 5. INPUTS

Expected:

```text id="c9mb1n"
Repository:
Capability:
Capability SDD:
Implementation Unit / scope:
Required verification:
Optional certification boundary:
```

The task prompt SHOULD identify the Implementation Unit when the SDD divides work into units.

If no unit exists, use the smallest coherent authorized scope.

---

# 6. AUTHORITY RULE

Follow:

`docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md`

Implementation MUST conform to applicable:

```text id="f9ezub"
Product Authority
        ↓
Domain Authority
        ↓
Global Architecture
        ↓
GLOBAL_SDD.md
        ↓
Capability SDD
```

This Skill has **no authority to create permanent design**.

---

# 7. REPOSITORY BASELINE

Before mutation, establish current:

```text id="m7gjzz"
Repository root:
Branch:
HEAD:
Working tree:
Migration head:
```

Compare current reality with the baseline referenced by the SDD when applicable.

Do not assume the repository has remained unchanged since SDD approval.

---

# 8. BASELINE DRIFT

If repository state changed after SDD approval, determine whether the drift affects implementation.

Classify:

```text id="pxkrk7"
NO_MATERIAL_IMPACT
MATERIAL_COMPATIBLE_CHANGE
MATERIAL_CONFLICT
UNKNOWN
```

For `MATERIAL_CONFLICT` or material `UNKNOWN`:

```text id="2zvs8a"
STOP
→ REPORT
```

Do not implement against an invalid baseline.

---

# 9. PRESERVE EXISTING WORK

Respect `AGENTS.md`.

Existing unrelated working-tree changes MUST be preserved.

Do not:

- reset;
- clean;
- overwrite;
- discard;
- stash without authorization.

If current changes overlap the authorized implementation surface, inspect carefully.

If safe ownership of overlapping changes cannot be determined:

```text id="mqkn0c"
STOP
```

---

# 10. IMPLEMENTATION SCOPE

Before modifying files, establish:

```text id="w65fnm"
IN SCOPE:
- ...

EXPECTED FILE/COMPONENT SURFACE:
- ...

CONDITIONALLY ALLOWED:
- ...

PROHIBITED:
- ...
```

Use the Capability SDD as authority.

Do not expand scope because nearby improvements are attractive.

---

# 11. INSPECT BEFORE MODIFYING

Before creating or changing a component, inspect:

- existing owner;
- existing implementation;
- repository conventions;
- reusable abstractions;
- related tests;
- relevant migrations/contracts.

The implementation agent MUST understand the affected surface before mutation.

Do not create duplicate responsibility.

---

# 12. REUSE RULE

Prefer, in order where appropriate:

```text id="0kgr1x"
REUSE AS-IS
      ↓
REUSE WITH MINIMAL EXTENSION
      ↓
REUSE THROUGH EXISTING ABSTRACTION
      ↓
CREATE NEW COMPONENT
```

Create a new component only when the approved SDD requires it or existing ownership cannot correctly provide the responsibility.

Do not redesign reuse boundaries during implementation.

---

# 13. MINIMAL CHANGE

Implement the smallest coherent change satisfying the authorized SDD scope.

Unless explicitly authorized, do NOT perform:

- unrelated refactoring;
- unrelated cleanup;
- broad renaming;
- formatting sweeps;
- dependency upgrades;
- architecture redesign;
- unrelated schema changes;
- unrelated API changes;
- unrelated frontend redesign.

Minimal Change applies to code, tests, migrations, and documentation.

---

# 14. IMPLEMENTATION ORDER

Follow the dependency order defined by the Capability SDD.

Within an Implementation Unit, a typical order MAY be:

```text id="cbbgwv"
Existing contracts / ownership
        ↓
Persistence
        ↓
Application behavior
        ↓
API / integration
        ↓
Frontend
        ↓
Tests
        ↓
Verification
```

This is not mandatory.

Repository architecture and the SDD determine the actual order.

---

# 15. PERSISTENCE

When persistence changes are authorized:

- inspect current migration head;
- inspect related models/tables;
- preserve ownership constraints;
- preserve relational integrity;
- consider existing data;
- follow established migration conventions.

Do not:

- rewrite historical migrations casually;
- create redundant tables;
- weaken tenant/location integrity;
- perform destructive migration without explicit authority.

Schema and ORM definitions must remain coherent.

---

# 16. TRANSACTIONS

Implement transaction boundaries exactly as required by the SDD.

Preserve:

- atomicity;
- commit ownership;
- rollback behavior;
- audit consistency.

Do not introduce partial commits into an atomic business operation.

External side effects must respect the approved transaction/failure design.

---

# 17. CONCURRENCY

For concurrency-sensitive operations:

- follow approved locking strategy;
- preserve lock order;
- revalidate required invariants;
- return approved conflict behavior;
- preserve stale-state protection.

Do not introduce a new locking strategy merely because it appears cleaner.

A required change to approved concurrency design is a design issue.

---

# 18. IDEMPOTENCY

Where required by the SDD, implement:

- idempotency mechanism;
- persisted evidence;
- safe replay;
- conflicting duplicate handling;
- duplicate external-side-effect prevention.

Do not add idempotency machinery to unrelated operations without design authority.

---

# 19. API AND DTOs

Implement approved API/DTO contracts.

Preserve:

- path semantics;
- ownership scope;
- authorization;
- validation;
- status/error semantics;
- compatibility.

Do not change an approved API contract merely to simplify implementation.

If repository constraints make the approved contract unsafe or impossible:

```text id="l8j0eu"
STOP
→ REPORT DESIGN / REPOSITORY CONFLICT
```

---

# 20. AUTHORIZATION

Authorization MUST be enforced server-side according to approved design.

Implement and verify:

- tenant scope;
- location scope;
- membership;
- capabilities/permissions;
- ownership;
- actor restrictions.

Do not weaken authorization to make tests or UI flows work.

---

# 21. AUDIT

Implement required audit evidence together with the authoritative business mutation where required.

Preserve historical truth.

Later responsibility/configuration changes MUST NOT silently rewrite completed historical evidence.

Do not introduce unrelated audit infrastructure.

---

# 22. INTEGRATIONS AND EXTERNAL EFFECTS

Follow approved ports, protocols, adapters, and ownership.

For business-critical external effects preserve applicable:

- timeout;
- retry;
- idempotency;
- failure behavior;
- reconciliation;
- evidence.

Do not bypass an approved integration boundary through direct vendor-specific coupling.

---

# 23. FRONTEND

When frontend work is in scope:

- use established application patterns;
- consume approved backend contracts;
- preserve backend authority;
- implement required loading/error/empty states;
- handle approved conflicts;
- invalidate/refetch authoritative server state where required;
- preserve accessibility;
- preserve localization.

Do not duplicate backend business logic into frontend state.

---

# 24. UX SCOPE

Implement functional UX requirements defined by the approved design.

Do not introduce unrelated visual redesign.

If UI implementation exposes a missing business/domain decision:

```text id="4wd0j9"
STOP
→ REPORT MISSING DECISION
```

Do not decide business behavior from UI convenience.

---

# 25. TEST IMPLEMENTATION

Add or update tests required by the SDD and directly affected behavior.

Tests SHOULD prove:

- approved behavior;
- critical invariants;
- authorization;
- failure/conflict behavior;
- integration behavior where relevant.

Do not change tests merely to accommodate incorrect implementation.

Do not encode new undocumented domain rules in tests.

---

# 26. VERIFICATION LOOP

After implementing the smallest coherent change:

```text id="gcdxln"
IMPLEMENT
   ↓
RUN TARGETED VERIFICATION
   ↓
PASS?
 ┌─┴─┐
NO   YES
│     │
▼     ▼
CLASSIFY   CONTINUE /
FAILURE    COMPLETE UNIT
```

When verification fails, determine whether the cause is:

```text id="mz7t6x"
IMPLEMENTATION_DEFECT
TEST_DEFECT
ENVIRONMENT_FAILURE
DESIGN_CONFLICT
BASELINE_DRIFT
UNKNOWN
```

Do not automatically edit code until the failure is classified.

---

# 27. BOUNDED REMEDIATION

This Skill MAY remediate a verification failure without new approval only when all are true:

1. the failure is directly caused by the current implementation;
2. the approved SDD already defines the correct behavior;
3. the correction remains inside authorized scope;
4. no new permanent design decision is required.

Then:

```text id="d1c4m0"
FIX
 ↓
REVERIFY
```

Otherwise:

```text id="azlfmm"
STOP
→ REPORT
```

---

# 28. REGRESSION

Run the regression scope defined by the SDD.

Distinguish:

```text id="xyfg6k"
DIRECT
SECONDARY
COLLATERAL
```

Do not mechanically run the entire test universe when unnecessary.

Do not omit broader regression when shared architecture or behavior requires it.

---

# 29. DOCUMENTATION DURING IMPLEMENTATION

Do not modify authoritative design merely because implementation diverged.

If implementation reveals a legitimate required design change:

```text id="2h3fbq"
STOP
  ↓
REPORT
  ↓
UPDATE / APPROVE CORRECT AUTHORITY
  ↓
RESUME
```

Implementation reports are not substitutes for SDD updates.

Implementation-only corrections that do not change design do not require SDD modification.

---

# 30. STOP CONDITIONS

Stop and report when:

1. required Product/Domain behavior is missing;
2. authority materially conflicts;
3. Global SDD and Capability SDD conflict;
4. repository reality materially invalidates the approved design;
5. ownership is ambiguous;
6. implementation requires unauthorized scope expansion;
7. a new permanent design decision is required;
8. destructive persistence behavior lacks authority;
9. security requirements cannot be preserved;
10. required external contract/credential is unavailable;
11. overlapping user work cannot be safely preserved;
12. safe verification cannot be completed.

Do not guess.

---

# 31. STOP REPORT

Use:

```text id="26xmtu"
STOP CONDITION:

Capability:
Implementation Unit:
Observed:
Expected:
Authority affected:
Repository evidence:
Why implementation cannot safely continue:
Changes already made:
Verification already run:
Required decision/action:
```

Preserve repository state.

Do not attempt broad remediation after stopping.

---

# 32. COMPLETION CRITERIA

An Implementation Unit is complete when:

```text id="q9u08h"
[ ] Authorized scope implemented
[ ] Approved design preserved
[ ] Critical invariants enforced
[ ] Ownership preserved
[ ] Authorization preserved
[ ] Persistence/migration coherent where applicable
[ ] Transaction behavior correct
[ ] Concurrency/idempotency correct where applicable
[ ] API contracts implemented where applicable
[ ] Frontend behavior implemented where applicable
[ ] Required targeted tests pass
[ ] Required regression passes
[ ] No unauthorized scope expansion occurred
[ ] No unresolved blocking design deviation remains
```

Completion of an Implementation Unit does NOT automatically mean the whole capability is certified.

---

# 33. OUTPUT CONTRACT

Return:

## A. Result

```text id="7rfak4"
RESULT:
IMPLEMENTED | PARTIALLY_IMPLEMENTED | BLOCKED | FAILED

Capability:
Implementation Unit:
Repository:
Branch:
Baseline HEAD:
Final HEAD:
Migration head:
```

## B. Changes

Summarize only material changes.

Prefer:

```text id="22qyd8"
Persistence:
Application:
API:
Authorization:
Integrations:
Frontend:
Tests:
Documentation:
```

Include only applicable categories.

## C. Files Changed

List relevant files.

Distinguish pre-existing unrelated changes when necessary.

## D. Verification

Report actual results:

```text id="mv0t53"
Targeted tests:
Direct regression:
Secondary regression:
Collateral regression:
Frontend tests:
Typecheck:
Build:
Migration verification:
Other:
```

Use:

```text id="pr03ql"
PASS
FAIL
NOT_RUN
NOT_APPLICABLE
BLOCKED
```

Do not claim verification that was not executed.

## E. Deviations

Report:

- approved deviations;
- unresolved deviations;
- none.

## F. Stop Conditions / Remaining Work

Identify any remaining work without converting it into unauthorized implementation.

## G. Recommended Next Step

Normally one of:

```text id="tug0kn"
IMPLEMENT NEXT UNIT
RESOLVE DESIGN DECISION
UPDATE / RE-APPROVE SDD
RUN ADDITIONAL VERIFICATION
BEGIN CAPABILITY CERTIFICATION
```

---

# 34. COMMIT RULE

Do not create a commit unless:

- explicitly requested by the user/task; or
- the established workflow explicitly authorizes it.

When committing:

- include only intended implementation changes;
- preserve unrelated working-tree changes;
- use repository commit conventions where established.

Do not push unless explicitly authorized.

---

# 35. EFFICIENCY RULE

Do not repeat in the implementation prompt what already exists in:

- `AGENTS.md`;
- this Skill;
- `GLOBAL_SDD.md`;
- the Capability SDD;
- referenced authority.

Use those artifacts directly.

Avoid:

- unnecessary repository-wide searches;
- repeated identical tests;
- speculative implementation;
- duplicated documentation;
- unrelated cleanup.

The objective is:

```text id="0g6p6c"
APPROVED DESIGN
       +
MINIMAL CHANGE
       +
SUFFICIENT VERIFICATION
       =
SAFE IMPLEMENTATION
```

---

# 36. RELATIONSHIP WITH OTHER SKILLS

```text id="q3n1ql"
repository-discover
→ establishes repository reality

capability-sdd-authoring
→ creates capability technical design

sdd-gap-review
→ validates design readiness

sdd-implementation
→ implements approved design

capability-certification
→ independently proves conformity
```

This Skill MUST NOT absorb certification responsibility.

---

# 37. DEFINITION OF DONE

This Skill is done when:

```text id="op3a9z"
[ ] Baseline inspected
[ ] Authorized scope identified
[ ] Existing ownership/reuse inspected
[ ] Minimal Change applied
[ ] Approved design implemented for requested scope
[ ] Required tests added/updated
[ ] Targeted verification executed
[ ] Required regression executed
[ ] Failures classified and resolved or reported
[ ] No permanent design decision invented
[ ] Existing user work preserved
[ ] Implementation report produced
```

---

# 38. FINAL RULE

The contract of `sdd-implementation` is:

```text id="4fzj3i"
READ AUTHORITY
      ↓
READ APPROVED SDD
      ↓
VERIFY REPOSITORY BASELINE
      ↓
INSPECT BEFORE MODIFYING
      ↓
REUSE
      ↓
IMPLEMENT MINIMAL CHANGE
      ↓
VERIFY
      ↓
REMEDIATE ONLY WITHIN APPROVED DESIGN
      ↓
REPORT EVIDENCE
      ↓
STOP
```

When correct implementation requires a permanent decision not already authorized:

> **STOP AND REPORT. DO NOT DESIGN INSIDE THE IMPLEMENTATION.**
