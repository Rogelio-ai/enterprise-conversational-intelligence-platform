# RESTAURANT INTELLIGENCE PLATFORM
# AGENT INSTRUCTIONS

**File:** `AGENTS.md`
**Scope:** Entire repository
**Status:** ACTIVE

---

# 1. PURPOSE

This file defines the permanent working rules for AI development agents operating in this repository.

It answers:

> How must an agent behave while working in this repository?

It does NOT define:

- product requirements;
- domain behavior;
- capability design;
- implementation-specific requirements;
- temporary task instructions.

Those belong to their respective authoritative artifacts.

---

# 2. INSTRUCTION MODEL

Agents SHALL distinguish:

```text id="eg7y55"
AGENTS.md
How to behave in this repository
        ↓
SKILL.md
How to perform a specific class of work
        ↓
AUTHORITATIVE DESIGN
What the system must be
        ↓
TASK PROMPT
What to do now
```

These responsibilities MUST NOT be silently mixed.

---

# 3. DOCUMENT AUTHORITY

Before making a material design or implementation decision, follow:

`docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md`

The repository authority model includes, as applicable:

```text id="p5ev8x"
Product Authority
        ↓
Domain Authority
        ↓
Global Architectural Authority
        ↓
GLOBAL_SDD.md
        ↓
Capability SDD
        ↓
Executable Contracts
        ↓
Implementation
        ↓
Verification / Certification
```

Do not treat lower-level artifacts as permission to silently override higher authority.

---

# 4. PROMPTS ARE NOT SOURCES OF TRUTH

Task prompts and historical Codex prompts are execution artifacts.

They are NOT permanent sources of:

- product requirements;
- domain rules;
- architecture;
- security rules;
- API contracts;
- persistence design;
- authorization rules;
- concurrency rules;
- capability design.

A prompt MAY repeat an authoritative rule defensively.

Such repetition does not create new authority.

If a prompt materially conflicts with authoritative repository documentation:

```text id="zg5otx"
STOP
  ↓
REPORT CONFLICT
  ↓
DO NOT GUESS
```

---

# 5. REPOSITORY BASELINE

Before modifying repository state, establish the relevant baseline.

At minimum, inspect as applicable:

```text id="2ysqps"
Repository root
Current branch
HEAD commit
Working-tree status
Relevant migration head
```

Do not assume historical branch, commit, migration, or working-tree information remains current.

Use repository reality.

---

# 6. PRESERVE EXISTING WORK

Existing working-tree changes belong to the current development state.

Agents MUST:

- preserve unrelated modifications;
- preserve untracked files;
- avoid destructive cleanup;
- avoid resets;
- avoid overwriting unrelated work.

Never use destructive Git operations merely to obtain a clean workspace.

If existing changes materially overlap the requested work, inspect and report the overlap before proceeding.

---

# 7. MINIMAL CHANGE

Apply Minimal Change.

Modify only what is necessary to satisfy the authorized task.

Unless explicitly required, do NOT perform:

- unrelated refactoring;
- unrelated cleanup;
- broad renaming;
- formatting sweeps;
- dependency upgrades;
- architecture redesign;
- schema redesign;
- API redesign;
- unrelated frontend changes;
- opportunistic technical-debt work.

A nearby problem is not automatically part of the task.

---

# 8. INSPECT BEFORE CREATING

Before creating a new:

- module;
- service;
- table;
- DTO;
- endpoint;
- enum;
- utility;
- authorization capability;
- frontend component;
- integration abstraction;

inspect whether an existing authoritative component already owns or provides that responsibility.

Prefer reuse over duplication when ownership and design permit it.

---

# 9. OWNERSHIP FIRST

Every material state mutation must have explicit ownership.

Before modifying or introducing behavior, determine:

```text id="hsgw11"
Who owns this state?
What is its tenant scope?
What is its location scope?
Who may mutate it?
What capability exposes the contract?
```

Do not bypass another capability's ownership merely because direct access is easier.

Ambiguous ownership is a design issue, not an invitation to guess.

---

# 10. NO SILENT PERMANENT DECISIONS

Agents MUST NOT silently invent permanent:

- product behavior;
- domain rules;
- lifecycle rules;
- architectural decisions;
- security policy;
- persistence ownership;
- API semantics;
- authorization policy;
- concurrency behavior;
- integration behavior;
- UX business behavior.

If a permanent decision is required but missing:

```text id="htvlxg"
STOP
  ↓
CLASSIFY MISSING DECISION
  ↓
REPORT
  ↓
WAIT FOR / OBTAIN AUTHORITATIVE DECISION
  ↓
RESUME
```

---

# 11. SDD GOVERNANCE

For work governed by a Capability SDD:

1. read the applicable `GLOBAL_SDD.md`;
2. read the applicable Capability SDD;
3. read only necessary higher-authority references;
4. implement the approved design;
5. do not redesign the capability inside the implementation prompt.

If the SDD is incomplete or materially conflicts with repository reality, stop and report rather than silently diverging.

---

# 12. SKILLS

Repository Skills define reusable procedures.

Expected location:

```text id="05efui"
skills/<skill-name>/SKILL.md
```

Use an applicable Skill when the task invokes that workflow.

Skills define:

> how to perform the work.

Skills are NOT product or capability design authority.

If a Skill conflicts with authoritative design, authoritative design governs and the conflict MUST be reported where material.

---

# 13. DOMAIN BOUNDARY

Business/domain behavior must come from Domain Authority or an explicitly approved decision.

Code structure, existing tests, UI behavior, or implementation convenience MUST NOT independently create domain truth.

When repository behavior conflicts with approved domain behavior, classify and report the discrepancy.

---

# 14. FRONTEND / BACKEND AUTHORITY

Unless authoritative design explicitly states otherwise:

Backend owns:

- domain invariants;
- authorization;
- persistent business state;
- transactions;
- concurrency;
- monetary truth;
- auditable transitions.

Frontend owns:

- presentation;
- navigation;
- interaction;
- usability validation;
- loading/error/empty states;
- accessibility;
- visual state.

Frontend behavior MUST NOT substitute for backend enforcement.

---

# 15. TENANT AND LOCATION SAFETY

Tenant isolation is mandatory.

Agents MUST preserve applicable:

- tenant ownership;
- organization ownership;
- location ownership;
- membership scope;
- location grants;
- cross-tenant restrictions.

Never weaken ownership constraints for implementation convenience.

Cross-tenant behavior requires explicit authority.

---

# 16. SECURITY

Follow:

`docs/SDD/GLOBAL_SDD.md`, Section 18, and any approved standalone security
authority explicitly referenced by the applicable approved Global SDD version.

Do not:

- expose secrets;
- commit credentials;
- weaken authorization;
- log sensitive values unnecessarily;
- bypass tenant isolation;
- disable security controls merely to make tests pass.

Security remediation outside task scope requires explicit authorization unless necessary to prevent an immediate unsafe implementation.

---

# 17. DATABASE AND MIGRATIONS

Follow existing persistence and migration architecture.

Before schema changes:

- inspect current migration head;
- inspect existing models and migrations;
- identify ownership;
- evaluate existing data;
- verify whether reuse is possible.

Do not:

- create redundant tables;
- rewrite migration history casually;
- run destructive migrations without authority;
- destroy persisted business history;
- change database ownership semantics implicitly.

Schema changes require corresponding migration treatment according to repository conventions.

---

# 18. TRANSACTIONS AND CONCURRENCY

Preserve established transaction ownership and lock ordering.

Do not split an atomic business operation into partial commits without approved design.

For concurrency-sensitive mutations:

- inspect existing lock behavior;
- preserve deterministic ordering;
- revalidate required invariants;
- handle stale/conflicting state explicitly.

Do not introduce concurrency mechanisms speculatively.

---

# 19. EXTERNAL SIDE EFFECTS

External effects such as:

- payments;
- POS operations;
- messages;
- printing;
- external API calls;
- irreversible commands

require explicit ownership and failure behavior.

Do not create duplicate external side effects during retries.

Respect applicable idempotency contracts.

---

# 20. FRONTEND QUALITY

Frontend changes must preserve:

- correctness;
- clarity;
- responsiveness;
- accessibility;
- consistent platform behavior.

Use established frontend patterns before creating new ones.

Do not duplicate backend domain rules in client state.

After mutations, authoritative server state should be refreshed or invalidated according to established design.

---

# 21. VALIDATION

Client-side validation exists for usability.

Server-side validation remains authoritative where business correctness is involved.

Do not rely solely on browser-native validation when the approved platform UX requires platform-owned validation.

Validation errors SHOULD remain consistent with applicable localization and error contracts.

---

# 22. INTERNATIONALIZATION

Preserve established language/session rules.

Do not hard-code user-visible text where the affected surface is governed by localization.

Do not modify authoritative monetary values or identifiers as part of translation.

Capability-specific language behavior belongs in the applicable SDD.

---

# 23. TESTS

Tests are verification evidence.

They are NOT automatically product/domain authority.

When changing behavior:

- add or update targeted tests where required;
- verify critical invariants;
- run relevant regression;
- preserve unrelated tests.

Do not change tests merely to make an incorrect implementation pass.

If a test conflicts with approved authority, report and classify the conflict.

---

# 24. REGRESSION

Consider three regression categories:

```text id="rvzhzx"
DIRECT
SECONDARY
COLLATERAL
```

Run regression proportional to actual dependency and risk.

Do not mechanically run the entire test universe when targeted verification is sufficient.

Do not avoid broader regression when shared architecture or contracts justify it.

---

# 25. VERIFICATION BEFORE COMPLETION

Do not report a task as complete merely because code was written.

Verify the applicable combination of:

- targeted tests;
- regression tests;
- API contracts;
- migrations;
- authorization;
- frontend tests;
- type checking;
- build;
- E2E scenarios;
- certification requirements.

Use the applicable SDD/Skill/task contract to determine required verification.

---

# 26. EVIDENCE

Completion reports SHOULD identify actual evidence.

As applicable:

```text id="yr3l1a"
Branch:
HEAD:
Working tree:
Migration head:
Files changed:
Tests:
Regression:
Typecheck:
Build:
Certification scenarios:
Known deviations:
```

Do not claim a command passed if it was not executed successfully.

Distinguish:

```text id="pmny3r"
VERIFIED
NOT RUN
BLOCKED
FAILED
```

---

# 27. STOP CONDITIONS

Stop and report instead of guessing when:

1. Product Authority is materially ambiguous.
2. Domain Authority is missing for required behavior.
3. Higher-authority documents conflict.
4. Global SDD and Capability SDD materially conflict.
5. Capability SDD and repository reality materially conflict.
6. Ownership cannot be determined.
7. Required scope exceeds authorization.
8. A destructive data/schema operation lacks authority.
9. Required credentials or external contracts are unavailable.
10. Security requirements cannot be satisfied.
11. A permanent new decision is required.
12. Safe verification cannot be performed.

A stop condition is preferable to unauthorized design.

---

# 28. FAILURE HANDLING

If implementation or verification fails:

- preserve evidence;
- identify the failing layer;
- distinguish implementation failure from environment failure;
- do not expand scope automatically;
- do not perform broad remediation without authorization.

If a minimal, directly related correction is clearly within the approved design and task scope, apply it and reverify.

Otherwise stop and report.

---

# 29. GIT SAFETY

Do not:

- reset unrelated work;
- force checkout over user changes;
- force push;
- rewrite history;
- delete branches/tags;
- create commits unless requested or authorized by the workflow.

When commits are authorized, include only intended changes.

Always preserve user work.

---

# 30. COMMAND SAFETY

Prefer the least destructive command capable of accomplishing the task.

Before running commands with potentially irreversible effects, determine whether the task explicitly requires them.

Do not run destructive commands merely for convenience.

---

# 31. DOCUMENTATION

Update authoritative documentation when the approved permanent design changes.

Do NOT update SDDs for implementation-only fixes when design remains unchanged.

Do NOT use documentation changes to retroactively legitimize unauthorized implementation behavior.

Documentation must reflect approved design and, after certification, approved as-built reality.

---

# 32. WORKFLOW SEPARATION

Keep workflows distinct:

```text id="f3t10n"
DISCOVERY
≠
DESIGN
≠
IMPLEMENTATION
≠
CERTIFICATION
```

A read-only Discovery task must not become remediation.

An SDD-authoring task must not become implementation.

An implementation task must not silently redesign the capability.

A certification task must not silently fix failures unless its workflow explicitly authorizes bounded remediation.

---

# 33. REPORTING

Reports should be concise, evidence-based, and structured around the requested task.

Clearly identify:

- result;
- changes;
- evidence;
- unresolved issues;
- deviations;
- next required action.

Do not hide failures inside verbose output.

Do not present inference as verified fact.

---

# 34. EFFICIENCY

Optimize for:

```text id="jy8ufq"
CORRECTNESS
     +
MINIMAL CHANGE
     +
REUSE
     +
SUFFICIENT VERIFICATION
     +
LOW CONTEXT WASTE
```

Avoid unnecessary:

- repository scans;
- repeated tests;
- duplicated documentation;
- giant prompts;
- speculative work.

Use existing authoritative artifacts and Skills instead of restating them.

---

# 35. DEFAULT DEVELOPMENT FLOW

For a new material capability:

```text id="p4igda"
DOMAIN KNOWLEDGE / E2E WALKTHROUGH
             ↓
DOMAIN DECISIONS
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
             ↓
CERTIFIED AS-BUILT SDD
```

Existing capabilities may enter the flow at the appropriate stage.

---

# 36. FINAL RULE

The agent's responsibility is not merely to produce code.

The agent must preserve:

```text id="ol7fs1"
AUTHORITY
   +
OWNERSHIP
   +
MINIMAL CHANGE
   +
REUSE
   +
CORRECTNESS
   +
EVIDENCE
```

When correct implementation requires a decision the agent is not authorized to make:

> **STOP AND REPORT. DO NOT GUESS.**
