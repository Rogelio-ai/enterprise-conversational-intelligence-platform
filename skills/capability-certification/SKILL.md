# SKILL — CAPABILITY CERTIFICATION

**Skill ID:** `capability-certification`
**Version:** 1.0.0
**Status:** ACTIVE
**Type:** Independent Capability Verification and Certification
**Repository Mutation:** PROHIBITED BY DEFAULT
**Design Authority:** NONE
**Implementation Authority:** NONE

---

# 1. PURPOSE

Independently verify and certify that an implemented capability conforms to its approved Capability SDD and applicable higher authority.

This Skill answers:

> Does the implementation actually satisfy the approved design, critical invariants, contracts, regression requirements, and certification scenarios?

Certification is evidence-based.

This Skill does NOT:

- design;
- implement;
- remediate;
- redefine requirements;
- change tests merely to obtain PASS;
- approve undocumented deviations.

---

# 2. CORE CONTRACT

```text id="8q0gsl"
APPROVED CAPABILITY SDD
          +
IMPLEMENTED REPOSITORY
          +
EXECUTABLE CONTRACTS
          +
TEST / RUNTIME EVIDENCE
          ↓
     CERTIFICATION
          ↓
PASS | PASS_WITH_APPROVED_EXCEPTIONS | FAIL | BLOCKED
```

Certification proves conformity.

It does not create conformity.

---

# 3. INDEPENDENCE PRINCIPLE

Treat implementation claims as unverified until supported by evidence.

Do not assume correctness because:

- implementation completed successfully;
- Codex reported success;
- code looks reasonable;
- targeted tests passed;
- an implementation report says `DONE`.

Certification independently checks the required evidence.

---

# 4. REQUIRED SOURCES

Read:

```text id="mfwtr1"
AGENTS.md
docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
docs/SDD/GLOBAL_SDD.md
<APPLICABLE_CAPABILITY_SDD>
skills/capability-certification/SKILL.md
```

Read additionally only when relevant:

- Product Authority;
- Domain Authority;
- ADRs;
- the approved security authority identified by `GLOBAL_SDD.md` Section 18;
- the approved reuse authority identified by `GLOBAL_SDD.md` Section 32;
- related Capability SDDs;
- implementation report;
- executable contracts;
- migrations;
- relevant tests;
- previous certification evidence.

Do not load unrelated documentation by default.

---

# 5. REQUIRED INPUTS

Expected:

```text id="lnkvgg"
Repository:
Capability:
Capability SDD:
SDD version:
Certification scope:
Expected implementation baseline:
Required certification scenarios:
Required regression scope:
```

When certification applies to the entire capability, state that explicitly.

When it applies only to an Implementation Unit or partial milestone, do NOT represent it as full capability certification.

---

# 6. PRECONDITIONS

Before certification verify:

```text id="14h3im"
[ ] Capability SDD exists
[ ] SDD is APPROVED / IMPLEMENTED as applicable
[ ] Certification scope is explicit
[ ] Implementation exists
[ ] Required authority is available
[ ] Required verification environment is available
```

If the target design itself remains materially unresolved:

```text id="1zgw8p"
BLOCKED
```

Certification cannot resolve design ambiguity.

---

# 7. READ-ONLY CONTRACT

Certification is read-only by default.

This Skill MUST NOT:

- modify product code;
- modify frontend code;
- create migrations;
- modify schema/data;
- change tests;
- update dependencies;
- refactor;
- fix defects;
- rewrite the SDD to match implementation;
- commit;
- push.

If certification finds a defect:

> RECORD THE FAILURE. DO NOT FIX IT.

---

# 8. REPOSITORY BASELINE

Capture current:

```text id="ftdxzh"
Repository:
Branch:
HEAD:
Working tree:
Migration head:
```

Compare against the implementation baseline expected by the SDD/implementation report.

Certification evidence MUST correspond to the exact repository state being certified.

---

# 9. WORKING-TREE RULE

A dirty working tree does not automatically invalidate certification.

However, determine whether uncommitted changes affect the certification surface.

Classify:

```text id="rm2yyb"
UNRELATED
IN_SCOPE
UNCERTAIN
```

If `UNCERTAIN` and correctness cannot be attributed to a stable implementation state:

```text id="amj3km"
BLOCKED
```

Never discard user changes.

---

# 10. CERTIFICATION SCOPE

Establish:

```text id="x1jch8"
Capability:
SDD version:
Implementation scope:
Included components:
Excluded components:
Regression boundary:
Known approved exceptions:
```

Certification MUST NOT imply coverage outside this boundary.

---

# 11. CERTIFICATION PROCEDURE

Perform the following sequence.

## Step 1 — Verify Authority

Confirm that certification is evaluating the implementation against the correct:

- Capability SDD;
- Global SDD;
- higher authority where materially required.

Do not certify against historical prompts.

## Step 2 — Verify Implementation Baseline

Confirm repository state corresponds to the intended implementation.

Identify baseline drift before executing certification.

## Step 3 — Verify SDD Coverage

Review the applicable SDD sections and identify all material requirements requiring evidence.

Focus especially on:

- critical invariants;
- lifecycle;
- ownership;
- persistence;
- transactions;
- concurrency;
- idempotency;
- API;
- authorization;
- audit;
- integrations;
- frontend behavior;
- security;
- failure/recovery;
- compatibility.

Use the Capability SDD as the detailed checklist.

Do not reproduce it.

## Step 4 — Verify Executable Contracts

Inspect applicable:

- migrations;
- database constraints;
- DTO/schema contracts;
- API contracts;
- Protocols;
- configuration.

Confirm they conform to the approved design.

## Step 5 — Execute Required Verification

Run the verification defined by the Capability SDD.

This may include:

- targeted backend tests;
- persistence tests;
- migration verification;
- API tests;
- authorization tests;
- concurrency tests;
- integration tests;
- frontend tests;
- E2E tests;
- type checking;
- build.

Do not invent unnecessary verification.

Do not omit required verification without explicitly reporting it.

## Step 6 — Execute Certification Scenarios

Execute every required applicable scenario:

```text id="7e5rba"
V1
V2
V3
...
```

Record actual evidence.

A scenario passes only when its defined expected result is observed.

## Step 7 — Execute Regression

Verify the SDD-defined:

```text id="37c0wp"
DIRECT
SECONDARY
COLLATERAL
```

regression scope.

## Step 8 — Verify Deviations

Identify differences between:

```text id="p8b4vi"
APPROVED DESIGN
        ↕
IMPLEMENTED REALITY
```

Classify every material deviation.

## Step 9 — Determine Result

Use the result rules defined below.

## Step 10 — Produce Certification Report

Report evidence, failures, deviations, and final result.

---

# 12. EVIDENCE STANDARD

Certification conclusions MUST be supported by:

```text id="cxceas"
EXECUTED
INSPECTED
VERIFIED
```

evidence.

Do not use:

```text id="54ce2h"
ASSUMED
PROBABLY
SHOULD WORK
IMPLEMENTATION AGENT SAID SO
```

as certification evidence.

---

# 13. EVIDENCE STATUS

For each required verification item use:

```text id="f7us8q"
PASS
FAIL
NOT_RUN
NOT_APPLICABLE
BLOCKED
```

`NOT_APPLICABLE` requires a valid reason.

`NOT_RUN` is not equivalent to `PASS`.

---

# 14. CRITICAL INVARIANTS

Every critical invariant defined by the Capability SDD MUST have sufficient certification evidence.

For each:

```text id="12ukg5"
Invariant:
Evidence:
Result:
```

A critical invariant failure normally results in:

```text id="g2xfo9"
FAIL
```

unless the scenario itself is blocked by environment limitations, in which case use `BLOCKED` appropriately.

---

# 15. OWNERSHIP AND TENANCY

Verify applicable:

- tenant isolation;
- organization/location ownership;
- membership scope;
- cross-tenant rejection;
- cross-location restrictions;
- mutation authority.

Do not certify a multi-tenant capability solely from happy-path same-tenant tests when cross-tenant integrity is material to the design.

---

# 16. PERSISTENCE AND MIGRATIONS

Where applicable verify:

- expected migration exists;
- migration ordering/head is correct;
- ORM/schema alignment;
- required foreign keys;
- unique constraints;
- check constraints;
- ownership constraints;
- relevant indexes;
- existing-data behavior where required.

Do not mutate authoritative databases merely to certify.

Use approved safe test environments.

---

# 17. TRANSACTIONS AND CONCURRENCY

Where required, verify:

- atomic success;
- rollback on failure;
- no partial business state;
- approved lock behavior;
- stale-state handling;
- conflict behavior;
- relevant race-condition protection.

A happy-path test alone is insufficient evidence for explicitly designed concurrency behavior.

---

# 18. IDEMPOTENCY

Where required verify:

```text id="xyn9s1"
First execution
Safe replay
Conflicting duplicate
External side-effect count
Persisted evidence
```

Duplicate irreversible effects are certification failures when prohibited by design.

---

# 19. API CONTRACTS

Verify applicable:

- routes;
- methods;
- request validation;
- response contracts;
- success statuses;
- error statuses;
- authorization;
- conflict behavior.

Do not certify undocumented API behavior as an approved contract.

---

# 20. AUTHORIZATION

Verify server-side enforcement for material operations.

Test applicable:

- allowed actor;
- unauthorized actor;
- wrong tenant;
- wrong location;
- missing capability;
- invalid membership;
- ownership restriction.

Frontend visibility is not authorization evidence.

---

# 21. AUDIT

Where required verify that audit evidence preserves:

- actor;
- operation;
- timestamp;
- affected entity;
- relevant before/after state;
- transition/version where applicable.

Historical evidence must remain consistent with the SDD.

---

# 22. INTEGRATIONS

For material integrations verify applicable:

- contract;
- adapter/port behavior;
- timeout/failure handling;
- retry;
- idempotency;
- evidence/reconciliation.

Do not invoke destructive real external side effects merely for certification unless explicitly authorized and safely controlled.

---

# 23. FRONTEND

Where frontend behavior is part of certification verify applicable:

- route/screen;
- required information;
- actions;
- authorization-dependent behavior;
- loading;
- empty;
- error;
- conflict recovery;
- state refresh/invalidation;
- validation;
- localization;
- accessibility requirements defined by the SDD.

Visual inspection alone is insufficient when executable frontend tests are required.

---

# 24. FAILURE AND RECOVERY

Execute required failure scenarios.

Verify that failures result in:

```text id="vfrbmj"
DETERMINATE BUSINESS STATE
        +
DEFINED NEXT ACTION
```

Certification fails when an expected failure can leave ambiguous authoritative state contrary to the SDD.

---

# 25. REGRESSION

Certification MUST distinguish:

## Direct

Behavior directly changed.

## Secondary

Behavior consuming or depending on the change.

## Collateral

Behavior potentially affected through shared components.

Report actual commands/scenarios and results.

Do not report "regression passed" without evidence.

---

# 26. DEVIATION CLASSIFICATION

For each material difference between design and implementation classify:

```text id="65nq2b"
IMPLEMENTATION_DEFECT
APPROVED_EXCEPTION
SDD_OUTDATED
EXECUTABLE_CONTRACT_CONFLICT
ENVIRONMENT_LIMITATION
UNKNOWN
```

Do not automatically rewrite the SDD to match code.

---

# 27. APPROVED EXCEPTIONS

`PASS_WITH_APPROVED_EXCEPTIONS` is allowed only when each exception:

1. is explicitly known;
2. has documented authority;
3. does not invalidate critical invariants;
4. has defined impact;
5. is represented in certification evidence.

An undocumented deviation is not an approved exception.

---

# 28. FAILURE RULE

Return `FAIL` when one or more required behaviors demonstrably violate approved design.

Examples:

- critical invariant failure;
- authorization bypass;
- tenant-isolation failure;
- incorrect monetary result;
- broken transaction atomicity;
- duplicate prohibited external effect;
- required certification scenario failure;
- required regression failure.

Do not downgrade a demonstrated defect to `BLOCKED`.

---

# 29. BLOCKED RULE

Return `BLOCKED` when correctness cannot be determined because required evidence cannot be obtained safely.

Examples:

- unavailable required dependency;
- unavailable test environment;
- ambiguous repository baseline;
- missing authoritative design;
- unavailable required credentials;
- unresolved authority conflict.

`BLOCKED` means:

> certification could not determine PASS or FAIL.

It does not mean the implementation passed.

---

# 30. NO REMEDIATION

When certification fails:

```text id="naw4px"
RECORD FAILURE
      ↓
IDENTIFY EVIDENCE
      ↓
CLASSIFY
      ↓
REPORT
      ↓
STOP
```

Do NOT:

```text id="g6p8ic"
FAIL
 ↓
EDIT CODE
 ↓
RETEST
 ↓
PASS
```

inside the same certification run.

Remediation belongs to `sdd-implementation` or another explicitly authorized remediation workflow.

This preserves certification independence.

---

# 31. RE-CERTIFICATION

After remediation:

```text id="q6dbvb"
FAILED CERTIFICATION
        ↓
AUTHORIZED REMEDIATION
        ↓
NEW IMPLEMENTATION BASELINE
        ↓
RE-CERTIFICATION
```

Re-certification MUST verify:

1. previously failed evidence;
2. affected behavior;
3. collateral regression from remediation;
4. remaining required certification scope.

Do not assume previous PASS evidence remains valid when remediation could affect it.

---

# 32. RESULT RULES

Use exactly one:

```text id="g6yja5"
PASS
PASS_WITH_APPROVED_EXCEPTIONS
FAIL
BLOCKED
```

## PASS

All required applicable evidence passes and no unapproved material deviation remains.

## PASS_WITH_APPROVED_EXCEPTIONS

Required evidence passes except for explicitly authorized non-critical deviations.

## FAIL

At least one required behavior demonstrably violates approved design.

## BLOCKED

Certification cannot safely establish conformity because required evidence or authority is unavailable.

---

# 33. CERTIFICATION REPORT

Return:

## A. Result

```text id="f7fgqu"
RESULT:
PASS | PASS_WITH_APPROVED_EXCEPTIONS | FAIL | BLOCKED

Capability:
SDD:
SDD version:
Certification scope:

Repository:
Branch:
HEAD:
Working tree:
Migration head:
```

## B. Executive Assessment

Briefly state whether implementation conforms and identify any material limitation.

## C. Certification Scenarios

| Scenario | Result | Evidence |
|---|---|---|
| V1 | | |
| V2 | | |

## D. Critical Invariants

| Invariant | Result | Evidence |
|---|---|---|
| | | |

## E. Verification

```text id="j7vvwq"
Targeted backend:
Persistence:
Migration:
API:
Authorization:
Concurrency:
Integration:
Frontend:
E2E:
Typecheck:
Build:
```

Use only applicable categories.

## F. Regression

```text id="tw7xkl"
Direct:
Secondary:
Collateral:
```

## G. Deviations

List:

- implementation defects;
- approved exceptions;
- design/executable-contract conflicts;
- none.

## H. Failures / Blockers

Provide exact evidence.

## I. Certification Boundary

```text id="pnbvvm"
Certified:
Excluded:
Regression boundary:
Known limitations:
```

## J. Recommended Next Step

Use one:

```text id="nxgrnx"
MARK CAPABILITY CERTIFIED
MARK CERTIFIED WITH APPROVED EXCEPTIONS
RETURN TO sdd-implementation FOR REMEDIATION
RESOLVE DESIGN / AUTHORITY CONFLICT
RESTORE REQUIRED CERTIFICATION ENVIRONMENT
RE-CERTIFY
```

---

# 34. SDD AS-BUILT RECONCILIATION

A successful certification requires the Capability SDD to accurately represent the approved implemented design.

If certification discovers that implementation contains an approved design change not reflected in the SDD:

```text id="hcmvhh"
DO NOT SILENTLY CERTIFY
```

Reconcile through the appropriate design-authoring/governance process, then certify against the updated approved SDD.

Certification itself does not edit the SDD.

---

# 35. CERTIFICATION STATUS

After successful governance action, the Capability SDD may move:

```text id="7ev1mp"
IMPLEMENTED
     ↓
CERTIFIED
```

or:

```text id="9ic23s"
IMPLEMENTED
     ↓
CERTIFIED_WITH_APPROVED_EXCEPTIONS
```

This Skill reports the certification result.

It does not automatically mutate document status unless a separate authorized workflow performs that documentation update.

---

# 36. EFFICIENCY RULE

Do not repeat the entire SDD in the certification report.

Do not rerun tests without reason.

Use:

- SDD-defined verification;
- dependency-based regression;
- exact evidence.

The objective is:

```text id="9qwt1q"
SUFFICIENT INDEPENDENT EVIDENCE
             ↓
       TRUSTWORTHY RESULT
```

not maximum command count.

---

# 37. STOP CONDITIONS

Stop and return `BLOCKED` when:

1. certification target cannot be identified;
2. applicable SDD is unavailable;
3. required authority materially conflicts;
4. repository baseline is ambiguous;
5. required safe environment is unavailable;
6. required evidence cannot be obtained without unauthorized mutation;
7. critical external dependency cannot be safely exercised or substituted according to approved design.

Do not guess certification results.

---

# 38. RELATIONSHIP WITH OTHER SKILLS

```text id="r7yqj7"
repository-discover
→ establishes reality

capability-sdd-authoring
→ creates design

sdd-gap-review
→ reviews design

sdd-implementation
→ implements design

capability-certification
→ independently proves implementation conformity
```

Certification is intentionally separated from implementation.

---

# 39. DEFINITION OF DONE

Certification is complete when:

```text id="fgbqje"
[ ] Certification scope established
[ ] Exact repository baseline captured
[ ] Applicable authority identified
[ ] Critical SDD requirements mapped to evidence
[ ] Required executable contracts inspected
[ ] Required certification scenarios executed
[ ] Critical invariants verified
[ ] Required targeted verification executed
[ ] Required regression executed
[ ] Material deviations classified
[ ] Failures/blockers documented
[ ] Final result assigned
[ ] Certification boundary documented
[ ] Recommended next step provided
[ ] No unauthorized remediation occurred

---

40. FINAL RULE
The contract of capability-certification is:
READ APPROVED DESIGN
        ↓
CAPTURE EXACT IMPLEMENTATION BASELINE
        ↓
MAP REQUIREMENTS TO EVIDENCE
        ↓
EXECUTE REQUIRED VERIFICATION
        ↓
EXECUTE CERTIFICATION SCENARIOS
        ↓
EXECUTE REQUIRED REGRESSION
        ↓
CLASSIFY DEVIATIONS
        ↓
PASS | PASS_WITH_APPROVED_EXCEPTIONS | FAIL | BLOCKED
        ↓
REPORT EVIDENCE
        ↓
STOP

Certification answers:
Does the implemented capability demonstrably conform to the approved design?

It does not design.
It does not implement.
It does not remediate.
It does not convert failures into success.
When implementation fails to conform:
REPORT THE FAILURE. DO NOT FIX IT DURING CERTIFICATION.

When required evidence cannot be obtained safely:
RETURN BLOCKED. DO NOT GUESS.


Con `# 40. FINAL RULE` termina `skills/capability-certification/SKILL.md`. No falta ninguna sección después.
