# SKILL — SDD GAP REVIEW

**Skill ID:** `sdd-gap-review`
**Version:** 1.0.0
**Status:** ACTIVE
**Type:** Read-Only Technical Design Review
**Repository Mutation:** PROHIBITED
**SDD Mutation:** PROHIBITED

---

# 1. PURPOSE

Independently review a Capability SDD before implementation approval.

Answer:

> Can this SDD be implemented and objectively certified without inventing permanent decisions, violating higher authority, duplicating existing ownership, or relying on undocumented assumptions?

This Skill identifies gaps.

It does NOT:

- redesign;
- remediate;
- edit the SDD;
- implement;
- approve the SDD.

---

# 2. CORE CONTRACT

```text id="i0jx0x"
HIGHER AUTHORITY
       +
GLOBAL_SDD.md
       +
CAPABILITY_SDD.md
       +
VERIFIED REPOSITORY REALITY
       ↓
   GAP REVIEW
       ↓
PASS | PASS_WITH_NON_BLOCKING_GAPS | FAIL | BLOCKED
```

Review the design independently.

Do not assume it is correct because another Skill authored it.

---

# 3. REQUIRED SOURCES

Read:

```text id="n9v2cr"
AGENTS.md
docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
docs/SDD/GLOBAL_SDD.md
docs/SDD/CAPABILITY_SDD_TEMPLATE.md
<APPLICABLE_CAPABILITY_SDD>
```

Read additionally only when relevant:

- Product Authority;
- Domain Authority;
- ADRs;
- the approved security authority identified by `GLOBAL_SDD.md` Section 18;
- the approved reuse authority identified by `GLOBAL_SDD.md` Section 32;
- `repository-discover` result;
- relevant executable contracts;
- relevant Capability SDDs;
- certification evidence.

Do not load unrelated documentation by default.

---

# 4. REQUIRED INPUTS

Expected:

```text id="g5h3l8"
Capability:
Capability SDD:
Repository:
Repository baseline:
Repository Discovery result:
Applicable authority:
```

If repository reality required for the review is insufficient:

```text id="cmjuh6"
BLOCKED
→ RUN repository-discover
```

Do not guess.

---

# 5. READ-ONLY CONTRACT

This Skill MUST NOT:

- modify the SDD;
- modify product code;
- modify frontend code;
- create migrations;
- modify databases;
- change tests;
- remediate defects;
- refactor;
- commit;
- push.

If a problem is found:

> REPORT IT. DO NOT FIX IT.

---

# 6. REVIEW DIMENSIONS

Review the SDD across five dimensions.

## 6.1 Authority

Ask:

> Is the design authorized?

Verify that it:

- follows `DOCUMENT_AUTHORITY_HIERARCHY.md`;
- references applicable higher authority;
- does not invent Product or Domain truth;
- does not silently contradict `GLOBAL_SDD.md`;
- has authority for any explicit exception.

## 6.2 Completeness

Ask:

> Does the SDD contain or reference enough design to implement safely?

Review every applicable section of:

`CAPABILITY_SDD_TEMPLATE.md`

Do not reproduce the template inside the review.

A valid `N/A — <reason>` is acceptable.

## 6.3 Repository Compatibility

Ask:

> Is the proposed design compatible with verified repository reality?

Compare against `repository-discover` evidence and relevant executable contracts.

Check especially:

- existing ownership;
- existing persistence;
- existing APIs;
- authorization;
- integrations;
- frontend;
- migrations;
- certified behavior.

## 6.4 Reuse and Ownership

Ask:

> Is the design respecting existing authoritative ownership and reuse opportunities?

Flag:

- duplicated responsibility;
- competing ownership;
- unnecessary new components;
- direct bypass of another capability;
- missed reuse that materially affects design.

Do not require reuse when it creates inappropriate coupling.

## 6.5 Verifiability

Ask:

> Can an independent agent objectively prove the implementation conforms to this SDD?

Verify sufficient:

- invariants;
- contracts;
- failure behavior;
- test strategy;
- regression scope;
- certification scenarios;
- acceptance criteria.

---

# 7. REVIEW PROCEDURE

Perform this sequence.

## Step 1 — Establish Baseline

Record:

```text id="amylf3"
Capability:
SDD:
SDD version:
Repository:
Branch:
HEAD:
Migration head:
```

Use verified current evidence.

## Step 2 — Review Authority

Identify:

- missing authority;
- authority conflicts;
- undocumented permanent rules;
- rules located at the wrong authority level.

## Step 3 — Review Canonical Template

Review every applicable section of `CAPABILITY_SDD_TEMPLATE.md`.

For each material concern ask:

```text id="q7ej9d"
Present?
Unambiguous?
Authorized?
Compatible?
Verifiable?
```

Do not demand capability-local duplication of rules already clearly inherited from higher authority.

## Step 4 — Review Repository Compatibility

Compare material design assumptions against verified repository evidence.

Identify:

```text id="m34b19"
SUPPORTED
CONFLICTING
UNKNOWN
```

Do not treat inferred repository behavior as verified fact.

## Step 5 — Review Reuse and Ownership

For proposed new components determine whether existing authoritative components already own the responsibility.

Flag only material duplication or ownership conflicts.

## Step 6 — Review Implementation Boundaries

Confirm the SDD sufficiently constrains:

```text id="v67h2b"
ALLOWED
CONDITIONALLY ALLOWED
PROHIBITED
```

Check that Minimal Change can be applied without ambiguity.

## Step 7 — Test Implementability

Ask:

> Could an implementation agent with no historical chat/prompt context implement this capability using repository instructions, applicable Skills, authoritative sources, this SDD, and repository reality without inventing a permanent decision?

If not, identify the missing design.

## Step 8 — Test Certifiability

Ask:

> Could an independent certification agent objectively determine whether implementation conforms?

If not, identify the missing verification contract.

## Step 9 — Apply Definition of Ready

Evaluate the canonical Definition of Ready in:

`CAPABILITY_SDD_TEMPLATE.md`

Do not create a competing readiness checklist.

## Step 10 — Assign Result

Return one canonical review result.

---

# 8. WHAT TO LOOK FOR

Prioritize material gaps involving:

- Product/Domain authority;
- capability boundary;
- scope;
- ownership;
- tenancy/location scope;
- reuse;
- critical invariants;
- lifecycle;
- persistence/integrity;
- transactions;
- concurrency;
- idempotency;
- API/DTO contracts;
- authorization;
- audit;
- integrations;
- frontend/backend boundary;
- security/privacy;
- failure/recovery;
- compatibility;
- implementation boundaries;
- testing;
- regression;
- certification.

Do not expand these into a second SDD.

Use the canonical template for detailed expectations.

---

# 9. OVERDESIGN REVIEW

The review MUST also identify material unnecessary complexity.

Examples:

- speculative microservices;
- unnecessary events;
- duplicate persistence;
- redundant abstractions;
- duplicated audit mechanisms;
- unnecessary DTO layers;
- premature scalability mechanisms.

The review asks both:

```text id="gwd9s8"
WHAT IS MISSING?
```

and:

```text id="v3aw45"
WHAT SHOULD NOT BE HERE?
```

Do not reject a valid design merely because another implementation is personally preferable.

---

# 10. FINDING SEVERITY

Use:

```text id="tvx2km"
BLOCKER
MAJOR
MINOR
INFORMATIONAL
```

## BLOCKER

Safe implementation cannot proceed without resolution.

Examples:

- missing permanent domain decision;
- material authority conflict;
- ambiguous ownership;
- undefined critical security requirement;
- critical repository/design contradiction.

## MAJOR

Implementation could proceed only with substantial risk of incorrect behavior or significant rework.

## MINOR

Does not prevent safe implementation but should be corrected for clarity, maintainability, or certification quality.

## INFORMATIONAL

Useful observation requiring no mandatory design change.

Use the lowest severity that accurately represents risk.

---

# 11. FINDING FORMAT

For every material finding:

```text id="ek1wbj"
GAP-<NNN>

Severity:
Type:
SDD section:
Evidence:
Problem:
Why it matters:
Required authority:
Required resolution:
Blocking implementation: YES / NO
```

Useful finding types include:

```text id="dbomz4"
AUTHORITY
DOMAIN
BOUNDARY
SCOPE
REPOSITORY
REUSE
OWNERSHIP
DATA
TRANSACTION
CONCURRENCY
IDEMPOTENCY
API
AUTHORIZATION
AUDIT
INTEGRATION
FRONTEND
SECURITY
FAILURE_RECOVERY
COMPATIBILITY
TESTING
REGRESSION
CERTIFICATION
```

Do not prescribe implementation code as the resolution unless specifically required.

---

# 12. EVIDENCE RULE

Classify supporting evidence as:

```text id="9vkm47"
VERIFIED
INFERRED
UNKNOWN
CONFLICTING
```

Do not present inference as fact.

If a material conclusion requires missing repository evidence:

```text id="ggt97m"
BLOCKED
or
ADDITIONAL DISCOVERY REQUIRED
```

as appropriate.

---

# 13. MISSING DECISIONS

When a required permanent decision is missing, classify it:

```text id="jjnb56"
PRODUCT
DOMAIN
GLOBAL ARCHITECTURE
CAPABILITY TECHNICAL
```

Do not answer Product, Domain, or Global Architecture questions from implementation convenience.

Report:

```text id="wy8iz5"
Question:
Authority required:
Why required:
Affected SDD section:
Blocking: YES / NO
```

---

# 14. CONFLICT RULE

When material sources disagree:

```text id="47p38u"
STOP ON THE AFFECTED DECISION
        ↓
IDENTIFY SOURCES
        ↓
CLASSIFY AUTHORITY
        ↓
REPORT
```

Follow `DOCUMENT_AUTHORITY_HIERARCHY.md`.

Do not automatically assume:

```text id="wrqy08"
SDD > Code
```

or:

```text id="vzrqgj"
Code > SDD
```

The discrepancy may represent:

- implementation defect;
- legacy behavior;
- outdated SDD;
- missing migration;
- undocumented approved change;
- unsupported design assumption.

Report what evidence supports.

---

# 15. FALSE-POSITIVE CONTROL

Before reporting a gap, verify whether it is already governed by:

- higher authority;
- `GLOBAL_SDD.md`;
- an applicable referenced Capability SDD;
- established repository contract.

Do not require duplicated text merely for local completeness.

A clear authoritative reference is sufficient.

---

# 16. REVIEW RESULT

Use exactly one:

```text id="38xz1m"
PASS
PASS_WITH_NON_BLOCKING_GAPS
FAIL
BLOCKED
```

## PASS

No material gaps remain and Definition of Ready passes.

## PASS_WITH_NON_BLOCKING_GAPS

No `BLOCKER` or `MAJOR` findings remain, but minor/informational findings exist.

## FAIL

The SDD contains resolvable `BLOCKER` or `MAJOR` design gaps.

## BLOCKED

The review cannot be completed safely because required authority or repository evidence is unavailable or materially unresolved.

---

# 17. APPROVAL BOUNDARY

This Skill does NOT approve an SDD.

Expected workflow:

```text id="a4ux55"
capability-sdd-authoring
        ↓
sdd-gap-review
        ↓
PASS
        ↓
HUMAN / GOVERNANCE APPROVAL
        ↓
SDD = APPROVED
```

Do not change SDD status automatically.

---

# 18. OUTPUT CONTRACT

Return:

## A. Review Result

```text id="83phqf"
RESULT:
PASS | PASS_WITH_NON_BLOCKING_GAPS | FAIL | BLOCKED

Capability:
SDD:
SDD version:
Repository:
Branch:
HEAD:
Migration head:
```

## B. Executive Assessment

Briefly answer:

> Is this SDD sufficiently complete, authorized, compatible, and verifiable to proceed toward approval?

## C. Findings Summary

| Severity | Count |
|---|---:|
| BLOCKER | |
| MAJOR | |
| MINOR | |
| INFORMATIONAL | |

## D. Findings

List only actual findings using the canonical finding format.

## E. Missing Decisions

Group by:

```text id="vfb6pm"
Product
Domain
Global Architecture
Capability Technical
```

## F. Authority / Repository Conflicts

List material conflicts.

## G. Reuse / Ownership Findings

List only material findings.

## H. Definition of Ready

Return:

```text id="y1pgf2"
PASS
FAIL
NOT_EVALUABLE
```

Identify failed items by reference to the canonical template.

## I. Recommended Next Step

Use one of:

```text id="njipyg"
APPROVE SDD
CORRECT CAPABILITY SDD
RESOLVE PRODUCT/DOMAIN DECISION
RESOLVE ARCHITECTURAL CONFLICT
RUN ADDITIONAL REPOSITORY DISCOVERY
REVIEW AGAIN
```

---

# 19. EFFICIENCY RULE

Do not turn the review into:

- another Capability SDD;
- another repository-discovery report;
- an implementation plan;
- a remediation prompt.

Report only what is necessary to determine readiness and what must change before approval.

Reference existing authority instead of reproducing it.

---

# 20. RE-REVIEW

After findings are corrected, review:

1. previously reported material findings;
2. affected SDD sections;
3. collateral effects of corrections;
4. Definition of Ready.

Do not repeat full repository discovery unless the relevant baseline materially changed.

---

# 21. STOP CONDITIONS

Return `BLOCKED` when review requires unavailable or unresolved:

- Product Authority;
- Domain Authority;
- Global SDD;
- repository evidence;
- ownership evidence;
- security authority;
- cross-capability contract.

Also stop if continuing safely would require repository mutation.

Do not compensate with assumptions.

---

# 22. RELATIONSHIP WITH OTHER SKILLS

```text id="klr6e8"
repository-discover
→ establishes repository reality

capability-sdd-authoring
→ creates the technical design

sdd-gap-review
→ challenges the design

sdd-implementation
→ implements the approved design

capability-certification
→ proves conformity
```

Normal flow:

```text id="0j13yj"
repository-discover
        ↓
capability-sdd-authoring
        ↓
sdd-gap-review
        ↓
human/governance approval
        ↓
sdd-implementation
        ↓
capability-certification
```

Do not absorb another Skill's responsibility.

---

# 23. DEFINITION OF DONE

The review is complete when:

```text id="wjhbh7"
[ ] Required authority reviewed
[ ] Capability SDD reviewed against canonical template
[ ] Global SDD compatibility evaluated
[ ] Repository compatibility evaluated
[ ] Reuse/ownership evaluated
[ ] Implementability tested
[ ] Certifiability tested
[ ] Definition of Ready evaluated
[ ] Material findings classified
[ ] Overall result assigned
[ ] Recommended next step provided
[ ] No SDD or repository mutation occurred
```

---

# 24. FINAL RULE

The contract of `sdd-gap-review` is:

```text id="0s4yt3"
READ
  ↓
COMPARE
  ↓
CHALLENGE
  ↓
FIND GAPS
  ↓
TEST IMPLEMENTABILITY
  ↓
TEST CERTIFIABILITY
  ↓
PASS | PASS_WITH_NON_BLOCKING_GAPS | FAIL | BLOCKED
  ↓
STOP
```

The Skill does not make the SDD correct.

It determines whether the SDD is sufficiently correct to deserve approval.

When required information is missing:

> **REPORT THE GAP. DO NOT INVENT THE ANSWER.**
