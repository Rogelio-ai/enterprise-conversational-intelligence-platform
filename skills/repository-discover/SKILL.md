# SKILL — REPOSITORY DISCOVER

**Skill ID:** `repository-discover`
**Version:** 1.0.0
**Status:** ACTIVE
**Type:** Read-Only Engineering Discovery
**Mutation Permission:** NONE

---

# 1. PURPOSE

Perform focused, evidence-based discovery of the current repository state before designing or implementing a software capability or change.

This Skill answers:

> What actually exists in the repository today that is relevant to the requested capability or change?

Its purpose is to establish a trustworthy implementation baseline and identify:

- existing functionality;
- ownership;
- reusable components;
- persistence;
- APIs;
- services;
- frontend surfaces;
- authorization;
- integrations;
- tests;
- migrations;
- dependencies;
- relevant documentation;
- conflicts and gaps.

This Skill does NOT design or implement the requested capability.

---

# 2. CORE PRINCIPLE

Repository discovery is evidence gathering.

```text
OBSERVE
   ↓
TRACE
   ↓
VERIFY
   ↓
CLASSIFY
   ↓
REPORT
```

Do not modify.

Do not redesign.

Do not remediate.

Do not guess.

---

# 3. WHEN TO USE

Use this Skill before:

- creating a Capability SDD for an existing repository;
- materially extending an existing capability;
- integrating a new capability with existing functionality;
- deciding whether functionality should be reused;
- planning a migration;
- planning a cross-capability change;
- generating an implementation prompt when repository reality is uncertain;
- recovering development context after substantial prior work.

It is particularly important when documentation and implementation may have diverged.

---

# 4. INPUTS

The invoking instruction SHOULD provide:

```text
Repository:
Capability / subject:
Discovery objective:
Known authoritative documents:
Optional expected areas:
Optional known baseline:
```

Example:

```text
Repository: /home/rogelio/proyectos/pryecip
Capability: Expenses
Objective:
Discover all existing components relevant to implementing
the Expenses capability.

Authoritative documents:
- docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
- docs/SDD/GLOBAL_SDD.md
- applicable domain documents
```

If an input is not supplied, discover it only when it can be established safely from repository evidence.

---

# 5. AUTHORITY

When available, inspect applicable repository authority in this order:

```text
Product Authority
        ↓
Domain Authority
        ↓
Global Architectural Authority
        ↓
GLOBAL_SDD.md
        ↓
Existing Capability SDD
        ↓
Executable Contracts
        ↓
Implementation
        ↓
Tests / Certification
```

Follow:

`DOCUMENT_AUTHORITY_HIERARCHY.md`

Repository discovery MUST NOT redefine authority.

---

# 6. READ-ONLY CONTRACT

This Skill is strictly read-only.

It MUST NOT:

- edit files;
- create files;
- delete files;
- rename files;
- run migrations that modify a database;
- modify schema;
- install dependencies;
- update dependencies;
- format source files;
- generate code into the repository;
- commit;
- push;
- switch branches unless explicitly authorized;
- reset repository state;
- stash changes;
- clean untracked files;
- modify environment configuration;
- start destructive services;
- perform remediation.

If discovery identifies a defect:

> REPORT IT. DO NOT FIX IT.

---

# 7. REPOSITORY SAFETY

Before detailed discovery, inspect repository state.

At minimum determine where available:

```text
Repository root
Current branch
HEAD commit
Working-tree status
Relevant migration head(s)
```

Prefer read-only commands.

Examples:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
```

Migration inspection MUST use non-mutating mechanisms.

Do not assume a clean working tree.

Existing modifications or untracked files are evidence and MUST NOT be destroyed.

---

# 8. DISCOVERY SCOPE

Discovery SHALL be focused on the requested capability.

Do NOT recursively inspect the entire repository without reason.

Start with likely ownership boundaries, then expand only when evidence identifies dependencies.

Conceptually:

```text
REQUESTED CAPABILITY
        ↓
DIRECT IMPLEMENTATION
        ↓
OWNERSHIP
        ↓
DEPENDENCIES
        ↓
SHARED INFRASTRUCTURE
        ↓
TEST / CONTRACT EVIDENCE
```

---

# 9. DISCOVERY PROCEDURE

Perform the following stages as applicable.

---

## 9.1 Establish Repository Baseline

Determine:

```text
Repository:
Branch:
HEAD:
Working tree:
Migration head:
Relevant runtime structure:
```

Record facts exactly.

Do not silently assume historical values remain current.

---

## 9.2 Locate Authoritative Documentation

Find documentation relevant to the capability.

Possible sources include:

- Product Constitution;
- Product Vision;
- Domain Model;
- domain specifications;
- Global SDD;
- existing Capability SDDs;
- ADRs;
- Security Baseline;
- Reuse Policy;
- development principles;
- certification documents.

Report the documents actually found.

Do not report an expected document as existing unless verified.

---

## 9.3 Locate Existing Domain/Application Implementation

Search for:

- domain models;
- application services;
- service-layer functions;
- protocols;
- repositories;
- adapters;
- business enums;
- lifecycle logic;
- validation;
- ownership checks.

Identify existing capability boundaries rather than relying solely on filenames.

---

## 9.4 Inspect Persistence

Identify relevant:

- ORM models;
- tables;
- migrations;
- foreign keys;
- composite foreign keys;
- unique constraints;
- check constraints;
- indexes;
- audit/history tables;
- lifecycle/status fields.

Determine ownership relationships.

Do NOT infer database behavior solely from ORM declarations when migration/schema evidence is available.

---

## 9.5 Inspect API Surface

Identify relevant:

- routes;
- methods;
- path structure;
- request DTOs;
- response DTOs;
- dependencies;
- authorization;
- error behavior.

Report actual endpoints.

Do not propose new endpoints during discovery.

---

## 9.6 Inspect Authentication and Authorization

Trace relevant:

- authentication dependencies;
- tenant context;
- membership;
- location grants;
- roles;
- capabilities;
- authorization checks;
- resource ownership validation.

Determine where authorization is actually enforced.

Do not infer authorization from frontend visibility.

---

## 9.7 Inspect Frontend

Where relevant, locate:

- routes;
- pages;
- components;
- API clients;
- hooks;
- state management;
- polling;
- invalidation;
- forms;
- validation;
- user actions;
- relevant tests.

Identify whether the capability already has partial or indirect UI support.

---

## 9.8 Inspect Integrations

Identify relevant:

- internal capability dependencies;
- external systems;
- ports/protocols;
- adapters;
- credential boundaries;
- retry behavior;
- idempotency;
- persisted integration evidence.

Do not assume an external integration exists merely because a domain concept references it.

---

## 9.9 Inspect Transactions and Concurrency

Where relevant, identify:

- transaction ownership;
- commit boundaries;
- rollback behavior;
- row locking;
- lock order;
- revalidation;
- conflict behavior;
- idempotency.

If behavior cannot be determined from evidence, classify it as `UNKNOWN`.

---

## 9.10 Inspect Tests

Locate relevant:

- unit tests;
- domain/service tests;
- persistence tests;
- API tests;
- authorization tests;
- integration tests;
- frontend tests;
- E2E tests;
- regression suites.

Tests are evidence of implemented expectations.

Tests are NOT automatically higher authority than approved design.

---

## 9.11 Inspect Certification Evidence

Where present, identify:

- certification reports;
- PASS/FAIL results;
- tested scenarios;
- certified commit;
- migration head;
- known exceptions.

Do not claim functionality is certified merely because tests exist.

---

## 9.12 Identify Reuse Candidates

For every component relevant to the requested capability, classify:

```text
REUSE AS-IS
REUSE WITH EXTENSION
REUSE WITH ADAPTER
NOT REUSABLE
UNCERTAIN
```

For each candidate record:

```text
Component:
Owner:
Current responsibility:
Relevant capability:
Reuse classification:
Evidence:
Risk:
```

Do not recommend duplication when an existing authoritative component already owns the responsibility.

---

## 9.13 Identify Cross-Capability Dependencies

Trace only dependencies materially relevant to the requested capability.

Examples:

```text
Identity
Tenant
Organization
Location
Staff
Authorization
Customer
Supplier
Catalog
Ordering
Preparation
Check
Payment
Cash
Inventory
Purchasing
Fiscal
```

Actual dependencies MUST come from repository evidence and domain authority.

---

# 10. EVIDENCE STANDARD

Every material discovery conclusion SHALL be classified as one of:

```text
VERIFIED
INFERRED
UNKNOWN
CONFLICTING
```

## VERIFIED

Directly supported by repository evidence.

## INFERRED

Strongly suggested by evidence but not conclusively established.

State the basis of inference.

## UNKNOWN

Cannot be established safely.

Do not fill the gap with assumptions.

## CONFLICTING

Two or more relevant sources disagree.

Report the conflict.

---

# 11. FACT VS RECOMMENDATION

Discovery reports MUST separate:

```text
FACT
```

from:

```text
OBSERVATION
```

from:

```text
POTENTIAL REUSE
```

from:

```text
GAP
```

from:

```text
CONFLICT
```

from:

```text
OPEN QUESTION
```

Do NOT present a proposed design as repository reality.

---

# 12. OWNERSHIP DISCOVERY

For relevant state determine, where possible:

```text
Entity / component:
Technical owner:
Tenant scope:
Organization scope:
Location scope:
Parent aggregate:
Mutation owner:
Read consumers:
```

Report ambiguous ownership as a gap.

Do not invent ownership to complete the report.

---

# 13. REUSE DISCOVERY

The primary reuse question is:

> Does the repository already contain an authoritative implementation or abstraction that should own this responsibility?

Check before recommending new:

- tables;
- services;
- DTOs;
- enums;
- authorization capabilities;
- integrations;
- frontend components;
- utilities;
- audit mechanisms.

Reuse analysis SHALL respect existing ownership.

---

# 14. DUPLICATION DETECTION

Report potential duplication when multiple components appear to implement the same responsibility.

For each:

```text
Responsibility:
Component A:
Component B:
Evidence:
Likely authority:
Classification:
```

Do NOT consolidate or refactor during discovery.

---

# 15. CONFLICT DETECTION

Look for material conflicts between:

```text
Documentation ↔ Documentation
Documentation ↔ Code
SDD ↔ Code
Migration ↔ ORM
API Contract ↔ Implementation
Authorization Design ↔ Enforcement
Tests ↔ Implementation
Tests ↔ Approved Design
Frontend Assumption ↔ Backend Contract
```

For each conflict:

```text
CONFLICT-ID:

Source A:
Source B:
Observed difference:
Potential impact:
Authority involved:
Blocking future design: YES / NO / UNKNOWN
```

Do not resolve the conflict unless resolution is directly established by higher authority.

---

# 16. GAP DETECTION

Identify missing elements relevant to the requested capability.

Possible gaps:

- missing ownership;
- missing persistence;
- missing authorization;
- missing API;
- missing lifecycle;
- missing audit evidence;
- missing integration contract;
- missing frontend support;
- missing tests;
- missing migration;
- missing domain authority;
- missing SDD;
- missing certification.

A gap is not automatically a defect.

It may simply represent functionality not yet implemented.

---

# 17. DOMAIN DECISION BOUNDARY

This Skill MUST NOT create domain rules.

If repository discovery reveals a question such as:

> Should an expense be allowed without a receipt?

the correct result is:

```text
DOMAIN DECISION REQUIRED
```

not an invented answer.

Similarly, this Skill MUST NOT decide:

- lifecycle semantics;
- business authorization policy;
- financial policy;
- operational workflow;
- UI behavior not already established;
- product behavior.

---

# 18. ARCHITECTURAL DECISION BOUNDARY

This Skill MAY identify an architectural problem.

It MUST NOT silently make a new permanent architectural decision.

Example:

```text
OBSERVED:
Two capabilities directly mutate the same state.

ARCHITECTURAL QUESTION:
Which capability should own mutation authority?

RESULT:
REQUIRES DESIGN DECISION.
```

---

# 19. MINIMAL SEARCH PRINCIPLE

Use the smallest repository inspection scope that can establish reliable evidence.

Expand scope when:

- ownership crosses modules;
- shared infrastructure is involved;
- a dependency is discovered;
- certification requires broader evidence;
- conflicting implementations exist.

Do not perform exhaustive searches merely because they are possible.

---

# 20. COMMAND SAFETY

Commands SHOULD be observational.

Generally acceptable categories:

```text
git status
git log
git diff
git show
git grep
find
rg
grep
cat
sed
head
tail
read-only test collection
read-only schema/migration inspection
```

Tests MAY be executed only when they are known not to mutate authoritative data or repository state.

When uncertain whether a command is destructive:

> DO NOT RUN IT.

Report the limitation instead.

---

# 21. DATABASE SAFETY

Do NOT:

- run upgrade/downgrade migrations;
- modify production/staging data;
- truncate tables;
- insert test data into authoritative databases;
- change schema;
- reset databases.

Database discovery is read-only.

If live database inspection is required but safe access is not established:

```text
DATABASE INSPECTION NOT PERFORMED
Reason:
Required evidence:
```

---

# 22. DIRTY WORKING TREE

A dirty working tree is NOT automatically a stop condition.

If unrelated changes exist:

- preserve them;
- do not modify them;
- report them;
- continue read-only discovery when safe.

If current uncommitted changes materially affect the requested discovery, distinguish:

```text
HEAD BASELINE
```

from:

```text
WORKING-TREE REALITY
```

Do not confuse the two.

---

# 23. STOP CONDITIONS

Stop discovery when continuing would require:

1. modifying repository state;
2. destructive database activity;
3. guessing a required domain decision;
4. guessing architectural authority;
5. accessing unavailable credentials;
6. crossing an explicitly prohibited scope;
7. resolving a material conflict without authority;
8. treating uncertain evidence as fact.

Report:

```text
STOP CONDITION:
Observed:
Why discovery cannot safely continue:
Missing evidence:
Recommended next action:
```

---

# 24. OUTPUT CONTRACT

The final report MUST use the following structure.

## A. Discovery Result

```text
RESULT:
COMPLETE | PARTIAL | BLOCKED

Repository:
Branch:
HEAD:
Working tree:
Migration head:
Capability:
```

## B. Executive Finding

Briefly state what already exists and the principal discovery conclusion.

## C. Authoritative Sources Found

List only verified sources.

## D. Existing Implementation

Organize by:

```text
Domain/Application
Persistence
API
Authorization
Frontend
Integrations
Audit
```

## E. Reuse Map

| Component | Owner | Classification | Evidence |
|---|---|---|---|
| | | | |

## F. Dependency Map

List material capability dependencies and direction.

## G. Tests and Certification

Report relevant verified test/certification evidence.

## H. Gaps

List discovered gaps.

## I. Conflicts

List authority/implementation conflicts.

## J. Unknowns

List facts that could not be safely established.

## K. Required Domain Decisions

List only decisions that must come from domain/product authority.

## L. Required Architectural Decisions

List only decisions requiring architectural authority.

## M. Recommended Next Step

Recommend the next process step, NOT an implementation solution unless specifically requested by the governing workflow.

---

# 25. OUTPUT QUALITY RULES

The report MUST:

- distinguish fact from inference;
- identify evidence;
- remain concise enough to be usable;
- avoid repository dumps;
- avoid speculative redesign;
- avoid implementation instructions unless required by the next workflow stage;
- explicitly identify blockers;
- explicitly identify reusable components.

The report SHOULD answer:

> What do we know with evidence?

> What already exists?

> What should probably be reused?

> What is missing?

> What remains undecided?

---

# 26. SUCCESS CRITERIA

Repository discovery is `COMPLETE` when sufficient evidence exists to support the requested next design step without requiring the designer to guess repository reality.

It does NOT require knowing every detail in the repository.

Success means:

```text
Relevant reality known
        +
Ownership understood
        +
Reuse identified
        +
Dependencies identified
        +
Material conflicts exposed
        +
Material unknowns exposed
```

---

# 27. DEFINITION OF DONE

This Skill is done when:

```text
[ ] Repository baseline captured
[ ] Relevant authority inspected
[ ] Relevant implementation located
[ ] Persistence inspected where applicable
[ ] API inspected where applicable
[ ] Authorization inspected where applicable
[ ] Frontend inspected where applicable
[ ] Integrations inspected where applicable
[ ] Relevant tests identified
[ ] Certification evidence checked where applicable
[ ] Reuse candidates classified
[ ] Cross-capability dependencies identified
[ ] Material conflicts reported
[ ] Material gaps reported
[ ] Unknowns explicitly reported
[ ] Domain decisions were not invented
[ ] Architectural decisions were not invented
[ ] No repository mutation occurred
[ ] Recommended next process step provided
```

---

# 28. FINAL RULE

`repository-discover` establishes repository reality.

It does not decide what the product should become.

It does not implement.

It does not remediate.

It does not redesign.

Its contract is:

```text
DISCOVER
   ↓
PROVE
   ↓
CLASSIFY
   ↓
REPORT
   ↓
STOP
```

The resulting evidence may then be consumed by:

```text
Domain Analysis
        ↓
Capability SDD Authoring
        ↓
SDD Gap Review
        ↓
Implementation
        ↓
Certification
```
