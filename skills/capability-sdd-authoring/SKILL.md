# SKILL — CAPABILITY SDD AUTHORING

**Skill ID:** `capability-sdd-authoring`
**Version:** 1.0.0
**Status:** ACTIVE
**Type:** Technical Design Authoring
**Product Code Mutation:** PROHIBITED

---

# 1. PURPOSE

Create or update a Capability SDD using approved authority and verified repository evidence.

The Skill answers:

> What capability-specific technical design is required so an implementation agent can build and certify this capability without inventing permanent decisions?

The output MUST use:

`docs/SDD/CAPABILITY_SDD_TEMPLATE.md`

This Skill designs.

It does NOT implement.

It does NOT certify.

---

# 2. CORE CONTRACT

```text id="6j2e7u"
APPROVED REQUIREMENTS
        +
HIGHER AUTHORITY
        +
GLOBAL_SDD.md
        +
REPOSITORY DISCOVERY
        ↓
CAPABILITY SDD
```

The Capability SDD MUST contain or reference all authoritative information necessary for implementation and certification.

It MUST NOT depend on historical prompts or conversations as permanent sources of truth.

---

# 3. REQUIRED SOURCES

Read, when applicable:

```text id="mkh48g"
docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
docs/SDD/GLOBAL_SDD.md
docs/SDD/CAPABILITY_SDD_TEMPLATE.md
```

Then read only relevant:

- Product Authority;
- Domain Authority;
- ADRs;
- Security Baseline;
- Reuse Policy;
- existing Capability SDD;
- repository-discovery evidence.

Do NOT duplicate these sources inside the Capability SDD.

Reference them.

---

# 4. PRECONDITIONS

Before authoring an implementation-ready SDD, verify:

```text id="vpjtds"
[ ] Capability objective is known
[ ] Product/domain behavior is sufficiently defined
[ ] Applicable authority is identifiable
[ ] Global SDD is available
[ ] Repository reality is sufficiently known
[ ] Material domain decisions are resolved
```

If repository reality is insufficient:

```text id="dveutb"
RUN repository-discover
```

If a required permanent business/domain decision is missing:

```text id="eox6i2"
BLOCKED
```

Do not invent it.

---

# 5. AUTHORITY RULE

Follow `DOCUMENT_AUTHORITY_HIERARCHY.md`.

Conceptually:

```text id="p7ax8h"
PRODUCT
   ↓
DOMAIN
   ↓
GLOBAL ARCHITECTURE
   ↓
GLOBAL SDD
   ↓
CAPABILITY SDD
```

This Skill owns only the last layer.

A Capability SDD MUST NOT silently contradict higher authority.

---

# 6. ONE RULE / ONE HOME

Before adding a permanent rule, classify it:

```text id="4rzxk8"
Product behavior
→ Product Authority

Business/domain rule
→ Domain Authority

Platform-wide technical rule
→ Global SDD / ADR

Capability-specific technical design
→ Capability SDD
```

Reference higher authority instead of copying it.

The Capability SDD SHOULD contain only the capability-specific technical design necessary to apply those rules.

---

# 7. INPUTS

Expected inputs:

```text id="3m8k39"
Capability:
Objective:
Repository:
Applicable authority:
Approved domain decisions:
Repository discovery result:
Existing Capability SDD, if any:
```

Optional inputs:

- E2E walkthrough;
- approved UI/UX requirements;
- approved lifecycle;
- approved business rules;
- integration requirements;
- known implementation constraints.

User/domain knowledge that has not yet become authoritative MUST be classified before being treated as permanent design input.

---

# 8. AUTHORING MODES

## CREATE

Create:

```text id="0b4xql"
docs/SDD/capabilities/<CAPABILITY_NAME>_SDD.md
```

using the canonical template.

## UPDATE

Modify an existing Capability SDD only where approved requirements, repository evidence, or design decisions require change.

Preserve unaffected design.

Minimal Change applies.

---

# 9. PROCEDURE

Perform the following sequence.

## Step 1 — Establish Authority

Identify the exact governing Product, Domain, Global and architectural sources.

Do not include irrelevant documents.

## Step 2 — Establish Repository Baseline

Consume `repository-discover` evidence.

Confirm relevant:

- existing implementation;
- ownership;
- persistence;
- APIs;
- frontend;
- authorization;
- integrations;
- tests;
- migrations;
- reusable components.

Do not convert inference into fact.

## Step 3 — Define Capability Boundary

State explicitly:

```text id="zk4d2b"
OWNS
DOES NOT OWN
```

Ambiguous ownership is blocking when it affects safe implementation.

## Step 4 — Define Scope

Establish:

```text id="hl0c7c"
IN SCOPE
OUT OF SCOPE
DEFERRED
NON-GOALS
```

Prevent opportunistic scope expansion.

## Step 5 — Determine Reuse

For each required responsibility classify:

```text id="t0qvlm"
REUSE AS-IS
REUSE WITH EXTENSION
REUSE WITH ADAPTER
NEW COMPONENT REQUIRED
UNRESOLVED
```

Prefer existing authoritative ownership over duplication.

Follow `GLOBAL_SDD.md` Section 32 and any approved standalone reuse authority it
explicitly references.

## Step 6 — Populate Technical Design

Complete every applicable section of `CAPABILITY_SDD_TEMPLATE.md`.

Use:

- approved domain requirements;
- higher authority;
- verified repository evidence;
- capability-specific technical decisions.

Do not duplicate Global SDD rules.

Use `N/A — <reason>` for genuinely non-applicable sections.

## Step 7 — Define Implementation Boundary

Explicitly establish:

```text id="0vmv3j"
ALLOWED
CONDITIONALLY ALLOWED
PROHIBITED
```

Apply Minimal Change.

## Step 8 — Define Verification

Ensure the SDD specifies enough to determine objectively whether implementation conforms.

Include as applicable:

- required tests;
- direct regression;
- secondary regression;
- collateral regression;
- certification scenarios;
- acceptance criteria.

## Step 9 — Evaluate Completeness

Apply the canonical Definition of Ready in `CAPABILITY_SDD_TEMPLATE.md`.

## Step 10 — Return Status

Return:

```text id="b2ugfa"
READY_FOR_REVIEW
BLOCKED
```

Do NOT declare the SDD `CERTIFIED`.

---

# 10. TECHNICAL DECISION RULE

This Skill MAY define capability-specific technical decisions when:

1. higher authority leaves the technical choice open;
2. repository reality is known;
3. the decision does not change business meaning;
4. the decision conforms to Global SDD;
5. existing ownership is respected.

Examples:

- reuse of an existing service;
- capability-owned persistence structure;
- DTO structure;
- endpoint organization consistent with repository conventions;
- locking mechanism consistent with global concurrency rules.

Material decisions SHOULD include concise rationale.

---

# 11. MISSING DECISION RULE

When authoring exposes a missing permanent decision, classify it:

```text id="fgyrm9"
PRODUCT
DOMAIN
GLOBAL ARCHITECTURE
CAPABILITY TECHNICAL
```

If it belongs above the Capability SDD:

```text id="tctt0z"
STOP
  ↓
REPORT QUESTION
  ↓
UPDATE CORRECT AUTHORITY
  ↓
RESUME
```

Do not hide the missing decision as an assumption.

---

# 12. DOMAIN BOUNDARY

This Skill MUST NOT invent:

- business lifecycle;
- financial policy;
- operational rules;
- actor responsibilities;
- business authorization policy;
- business exceptions;
- product behavior.

When these are missing, return a blocking domain question.

Technical design implements domain truth.

It does not create domain truth.

---

# 13. REPOSITORY BOUNDARY

Repository reality constrains implementation but does not automatically define desired behavior.

If repository evidence conflicts with approved design, classify the discrepancy.

Possible classifications:

```text id="d5w3dm"
IMPLEMENTATION DEFECT
LEGACY BEHAVIOR
OUTDATED DOCUMENTATION
MISSING MIGRATION
DESIGN / REPOSITORY CONFLICT
UNKNOWN
```

Do not silently rewrite the SDD to match existing code.

Do not silently rewrite code to match the SDD.

Report the conflict.

---

# 14. UI BOUNDARY

Approved UI/UX requirements are valid design inputs.

However:

```text id="ph8jpw"
UI
≠
DOMAIN MODEL
≠
DATABASE MODEL
```

Do not derive tables directly from form fields.

When UI design reveals a missing business rule, promote the question to Domain Authority before depending on it.

The Capability SDD SHOULD specify functional UI behavior sufficiently for implementation, without unnecessary pixel-level design unless explicitly required.

---

# 15. PERSISTENCE BOUNDARY

Before defining new persistence ask:

```text id="xfep2n"
Does this state already have an owner?
Is durable persistence required?
What is its ownership scope?
What integrity must be enforced?
What history must survive?
Can existing persistence be reused?
```

Do not create new tables merely because a new screen requires data.

---

# 16. API BOUNDARY

Before defining a new API operation determine:

```text id="25j8db"
Use case
Owner
Actor
Authorization
Invariant
Transaction
Failure behavior
Existing contract reuse
```

Avoid CRUD symmetry for its own sake.

The API should expose capability behavior, not accidental persistence structure.

---

# 17. FRONTEND / BACKEND BOUNDARY

Inherit the boundary from `GLOBAL_SDD.md`.

Capability SDDs define only capability-specific application.

Backend remains authoritative for:

- domain invariants;
- authorization;
- persistent state;
- transactions;
- monetary truth.

Frontend owns user interaction and presentation.

Do not create competing business authority in frontend state.

---

# 18. IMPLEMENTATION UNIT RULE

A Capability SDD MAY define multiple implementation units.

Units exist only to divide execution safely.

Example:

```text id="4ttwtp"
UNIT 1 — Persistence
UNIT 2 — Application / Domain Integration
UNIT 3 — API
UNIT 4 — Frontend
UNIT 5 — Certification
```

Do not force this structure when technical coupling suggests another sequence.

Implementation units are NOT independent specifications.

All inherit the same Capability SDD.

---

# 19. DETAIL RULE

The SDD must contain enough detail to:

```text id="mnx9mr"
IMPLEMENT WITHOUT INVENTING
          +
CERTIFY OBJECTIVELY
```

but should avoid:

- copying source code;
- repository dumps;
- repeating Global SDD;
- repeating Domain Authority;
- implementation-agent instructions;
- speculative architecture;
- unnecessary future design.

The target is **minimum sufficient authoritative design**.

---

# 20. SIZE DISCIPLINE

Do not optimize for document length.

Optimize for completeness without duplication.

When information already exists authoritatively:

```text id="l5h9dd"
REFERENCE IT
```

Do not reproduce it.

Every substantial section should help answer at least one question:

1. What must exist?
2. Who owns it?
3. What must always be true?
4. How does it integrate?
5. How will correctness be proven?

Otherwise consider removing it.

---

# 21. CONFLICT RULE

When authoritative sources materially conflict:

```text id="zhdzum"
STOP
  ↓
IDENTIFY CONFLICT
  ↓
IDENTIFY AUTHORITY LEVEL
  ↓
REPORT
```

Do not choose the easiest interpretation.

Conflict resolution follows `DOCUMENT_AUTHORITY_HIERARCHY.md`.

---

# 22. ASSUMPTIONS

Avoid assumptions.

A non-blocking assumption MAY be recorded only when it does not create permanent product/domain behavior.

Format:

```text id="phb3e8"
ASSUMPTION:
Evidence:
Why non-blocking:
How it will be validated:
```

A blocking assumption becomes an open question.

---

# 23. NO IMPLEMENTATION

This Skill MUST NOT:

- modify backend code;
- modify frontend code;
- create migrations;
- modify database schema;
- remediate defects;
- refactor product code;
- install/update dependencies;
- commit;
- push.

Its responsibility ends with technical design.

---

# 24. DOCUMENT MUTATION

When explicitly authorized to create/update the Capability SDD, modify only:

```text id="08e6ya"
docs/SDD/capabilities/<CAPABILITY_NAME>_SDD.md
```

and any other documentation artifact explicitly requested.

Preserve unrelated working-tree changes.

Do not perform broad documentation reformatting.

---

# 25. OUTPUT

Return:

## Result

```text id="0odw0v"
RESULT:
READY_FOR_REVIEW | BLOCKED

Capability:
SDD:
Version:
Repository baseline:
```

## Capability SDD

Produce/update the canonical Capability SDD.

## Blocking Questions

For each:

```text id="cf21ns"
Question:
Required authority:
Why blocking:
Affected SDD section:
```

## Non-Blocking Questions

List unresolved items that do not prevent safe review.

## Authority Updates Required

Identify higher-authority artifacts requiring changes.

Do not modify them unless separately authorized.

## Reuse Summary

Summarize material reuse decisions.

## Recommended Next Step

Normally:

```text id="rtj7ve"
RESOLVE DOMAIN DECISIONS
RESOLVE ARCHITECTURAL CONFLICT
RUN repository-discover
RUN sdd-gap-review
```

---

# 26. READY-FOR-REVIEW CRITERIA

Return `READY_FOR_REVIEW` only when:

```text id="k3g93s"
[ ] Applicable authority is identified
[ ] Capability boundary is explicit
[ ] Scope is bounded
[ ] Repository baseline is sufficient
[ ] Reuse has been evaluated
[ ] Critical domain concepts are resolved
[ ] Critical invariants are represented
[ ] Lifecycle is represented where applicable
[ ] Ownership is unambiguous
[ ] Persistence is sufficiently designed
[ ] Transactions/concurrency are addressed where relevant
[ ] API contracts are sufficiently designed
[ ] Authorization is explicit
[ ] Audit/integrations are addressed
[ ] Frontend behavior is defined where applicable
[ ] Security implications are addressed
[ ] Failure/recovery is addressed
[ ] Implementation boundaries are explicit
[ ] Verification/regression is defined
[ ] Certification scenarios are defined
[ ] No blocking question remains
[ ] No permanent rule depends solely on a historical prompt
```

`READY_FOR_REVIEW` does NOT mean `APPROVED`.

The next independent step is `sdd-gap-review`.

---

# 27. BLOCKED CRITERIA

Return `BLOCKED` when safe technical design requires an unresolved:

- product decision;
- domain decision;
- global architectural decision;
- ownership decision;
- repository fact;
- security requirement;
- cross-capability contract;
- destructive-change approval.

Prefer `BLOCKED` over invented design.

---

# 28. RELATIONSHIP WITH OTHER SKILLS

Normal workflow:

```text id="ymx47p"
DOMAIN KNOWLEDGE
      ↓
APPROVED DOMAIN AUTHORITY
      ↓
repository-discover
      ↓
capability-sdd-authoring
      ↓
sdd-gap-review
      ↓
SDD APPROVAL
      ↓
sdd-implementation
      ↓
capability-certification
```

Do not absorb another Skill's responsibility.

---

# 29. DEFINITION OF DONE

This Skill is done when:

```text id="96wtuc"
[ ] Canonical template used
[ ] Applicable authority referenced
[ ] Repository evidence incorporated
[ ] Reuse decisions documented
[ ] Capability-specific design completed
[ ] Missing decisions exposed
[ ] Implementation boundaries defined
[ ] Verification/certification requirements defined
[ ] Ready-for-review status determined
[ ] No higher-authority rule invented
[ ] No product code modified
```

---

# 30. FINAL RULE

The contract of `capability-sdd-authoring` is:

```text id="5g7otn"
READ AUTHORITY
      ↓
READ VERIFIED DISCOVERY
      ↓
USE CANONICAL TEMPLATE
      ↓
DESIGN ONLY WHAT THIS CAPABILITY OWNS
      ↓
REFERENCE — DO NOT DUPLICATE
      ↓
EXPOSE MISSING DECISIONS
      ↓
READY_FOR_REVIEW OR BLOCKED
      ↓
STOP
```

The Capability SDD defines **what must be built**.

This Skill defines **how to author that design**.

The implementation prompt will later define only **what to execute now**.
