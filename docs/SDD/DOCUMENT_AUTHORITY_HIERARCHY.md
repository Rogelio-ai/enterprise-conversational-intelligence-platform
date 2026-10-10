RESTAURANT INTELLIGENCE PLATFORM
DOCUMENT AUTHORITY HIERARCHY
Document: DOCUMENT_AUTHORITY_HIERARCHY.md
Status: AUTHORITATIVE
Purpose: Define the official hierarchy of sources of truth for the Restaurant Intelligence Platform.

1. PURPOSE
This document defines:
    • which artifacts are authoritative;
    • their precedence;
    • the responsibility of each documentation layer;
    • how conflicts are resolved;
    • the role of Global and Capability SDDs;
    • the relationship between documentation, executable contracts, code, tests, certification, and Codex prompts.
The objective is to eliminate design authority distributed across historical prompts, conversations, implementation reports, and unrelated documents.

2. FUNDAMENTAL PRINCIPLE
The platform SHALL distinguish between:
    1. Product truth.
    2. Domain truth.
    3. Architectural truth.
    4. Technical design truth.
    5. Executable contract truth.
    6. Implementation state.
    7. Verification evidence.
    8. Execution instructions.
These responsibilities MUST NOT be silently mixed.

3. OFFICIAL AUTHORITY HIERARCHY
The authoritative hierarchy is:
LEVEL 0
PRODUCT CONSTITUTION / PRODUCT VISION
                │
                ▼
LEVEL 1
DOMAIN MODEL / DOMAIN RULES
                │
                ▼
LEVEL 2
GLOBAL ARCHITECTURAL POLICIES
ADR / SECURITY / REUSE / DEVELOPMENT PRINCIPLES
                │
                ▼
LEVEL 3
GLOBAL SDD
                │
                ▼
LEVEL 4
CAPABILITY SDD
                │
                ▼
LEVEL 5
EXECUTABLE CONTRACTS
OpenAPI / Schemas / Migrations / Protocols / Configuration
                │
                ▼
LEVEL 6
IMPLEMENTATION
Source Code
                │
                ▼
LEVEL 7
VERIFICATION / CERTIFICATION
Tests / Evidence / Certification Reports
Codex prompts, conversations, implementation notes, temporary plans, and agent reports are NOT part of the authority hierarchy.

4. LEVEL 0 — PRODUCT AUTHORITY
Examples:
    • PRODUCT_CONSTITUTION.md
    • PRODUCT_VISION.md
    • officially approved product requirements
Defines:
    • what product is being built;
    • strategic product boundaries;
    • fundamental product principles;
    • commercial/product objectives;
    • non-negotiable product behavior.
An SDD MUST NOT silently override product authority.

5. LEVEL 1 — DOMAIN AUTHORITY
Examples:
    • RESTAURANT_DOMAIN_MODEL.md
    • domain specifications;
    • formally approved business rules;
    • domain lifecycle definitions.
Defines:
    • business concepts;
    • business terminology;
    • business invariants;
    • domain relationships;
    • domain lifecycle;
    • rules that exist independently of technical implementation.
Example:
A restaurant table retains its individual identity when participating in a dynamic Table Group.
That is a domain rule, not merely an implementation decision.

6. LEVEL 2 — GLOBAL ARCHITECTURAL AUTHORITY
Examples:
    • ARCHITECTURE_DECISION_LOG.md
    • ADRs
    • approved standalone security or reuse policies, when present
    • platform-wide architectural policies
Defines decisions that apply across multiple capabilities.
Examples:
    • tenant isolation;
    • security architecture;
    • reusable-service boundaries;
    • database portability;
    • architectural ownership;
    • dependency direction.

Standalone Level 2 security and reuse documents are optional. When none exists, the
Global SDD MAY own the platform-wide technical Security Baseline and Reuse Policy at
Level 3. Those sections remain subordinate to any approved Level 0–2 authority and do
not promote the Global SDD above its defined level.

7. LEVEL 3 — GLOBAL SDD
The Global Software Design Document defines the authoritative technical design shared across the platform.
It answers:
How must capabilities be technically designed to coexist consistently within this platform?
Examples:
    • tenant context propagation;
    • authorization model;
    • API conventions;
    • transaction conventions;
    • audit conventions;
    • concurrency principles;
    • error contracts;
    • observability;
    • frontend/backend boundaries;
    • localization architecture;
    • integration principles.
The Global SDD MUST NOT duplicate detailed business behavior belonging to individual capabilities.

8. LEVEL 4 — CAPABILITY SDD
A Capability SDD defines the authoritative technical design for one bounded capability or closely related domain area.
Examples:
RECEPTION_SDD.md
WAITER_SDD.md
DINER_SDD.md
ORDERING_SDD.md
PREPARATION_SDD.md
CHECK_PAYMENT_SDD.md
CASH_MANAGEMENT_SDD.md
INVENTORY_SDD.md
PURCHASING_SDD.md
It answers:
How is this capability technically implemented while respecting product, domain, architectural, and Global SDD authority?
A Capability SDD inherits the Global SDD.
It MUST NOT redefine global rules unless explicitly referencing an approved exception represented by a higher-authority architectural decision.

9. LEVEL 5 — EXECUTABLE CONTRACTS
Examples:
    • OpenAPI specifications;
    • database migrations;
    • schemas;
    • DTO contracts;
    • Protocol definitions;
    • machine-readable configuration;
    • database constraints.
These represent executable or mechanically verifiable technical contracts.
They MUST conform to the applicable SDD.
If an executable contract contradicts an approved SDD, the contradiction MUST be investigated rather than silently treating either side as correct.

10. LEVEL 6 — IMPLEMENTATION
Source code represents the currently implemented system.
Code is authoritative regarding:
What the software currently does.
Code is NOT automatically authoritative regarding:
What the software is supposed to do.
Therefore:
CODE != DESIGN AUTHORITY
A difference between code and approved design is a discrepancy requiring classification.
It may represent:
    • implementation defect;
    • outdated SDD;
    • undocumented approved change;
    • incomplete implementation;
    • legacy behavior requiring migration.

11. LEVEL 7 — VERIFICATION AND CERTIFICATION
Examples:
    • automated tests;
    • integration tests;
    • E2E tests;
    • regression suites;
    • certification reports;
    • verification evidence.
Tests provide evidence that implementation satisfies defined contracts.
Tests MUST NOT silently become the source of new business or architectural rules.
A test that contradicts authoritative design requires investigation.

12. CODEX PROMPTS
Codex prompts are:
EPHEMERAL EXECUTION ARTIFACTS.
They are NOT sources of truth.
A Codex prompt MAY:
    • identify the applicable SDD;
    • select an implementation scope;
    • establish execution boundaries;
    • request repository inspection;
    • request implementation;
    • request tests;
    • request verification;
    • establish stop conditions;
    • request an implementation report.
A Codex prompt MUST NOT be the sole location of:
    • product requirements;
    • domain rules;
    • architectural decisions;
    • permanent invariants;
    • API contracts;
    • security requirements;
    • persistent design decisions.
Fundamental rule:
CODEX PROMPTS ARE EXECUTION INSTRUCTIONS, NOT SOURCES OF TRUTH.

13. CONVERSATIONS
ChatGPT conversations, Codex conversations, development discussions, and human discussions MAY produce decisions.
However, a decision does not become authoritative merely because it appeared in a conversation.
Before implementation, a permanent decision MUST be promoted to the appropriate authoritative artifact.
DISCUSSION
    ↓
DECISION
    ↓
AUTHORITATIVE DOCUMENT
    ↓
IMPLEMENTATION

14. CONFLICT RESOLUTION
When two artifacts conflict, implementation MUST NOT automatically choose the most convenient interpretation.
The conflict must be classified.
General precedence:
Product Authority
      >
Domain Authority
      >
Global Architecture
      >
Global SDD
      >
Capability SDD
      >
Executable Contract
      >
Implementation
      >
Verification Evidence
However, precedence does NOT authorize blindly changing lower layers.
A conflict may indicate that the higher-level artifact is outdated.
Therefore:
CONFLICT
   ↓
STOP
   ↓
CLASSIFY
   ↓
IDENTIFY INTENDED AUTHORITY
   ↓
UPDATE AUTHORITATIVE ARTIFACT IF REQUIRED
   ↓
IMPLEMENT
   ↓
VERIFY

15. NO SILENT DESIGN DECISIONS
During implementation, Codex or another implementation agent MUST NOT silently invent a permanent design rule when the authoritative design is insufficient.
Required behavior:
Missing design decision
        ↓
       STOP
        ↓
Report:
- missing decision
- affected components
- alternatives
- consequences
        ↓
Human/design decision
        ↓
Update authoritative artifact
        ↓
Resume implementation

16. SDD LIFECYCLE
An SDD may have the following states:
DRAFT
  ↓
REVIEWED
  ↓
APPROVED
  ↓
IMPLEMENTED
  ↓
CERTIFIED
Additional state:
SUPERSEDED

Lifecycle meanings:
    • DRAFT: being authored; not eligible to govern implementation.
    • REVIEWED: required review has passed and the document is READY_FOR_APPROVAL;
      it is not approved and cannot govern implementation.
    • APPROVED: the identified approval authority made an explicit approval
      decision and the approval record is complete.
    • IMPLEMENTED: the approved design has been implemented, but certification is
      not implied.
    • CERTIFIED: independent evidence demonstrates conformity to the approved
      design for the recorded implementation baseline.
    • SUPERSEDED: replaced by a later approved version; historical approval and
      certification evidence remains preserved.

Only an approved SDD may govern new implementation.
CERTIFIED means implementation and required verification evidence have demonstrated conformity with the approved design.

16.1 APPROVAL ROLES

Status: ACCEPTED — 2026-10-08

The approved governance roles are:
    • Product Owner: approves product/domain decisions and business requirements.
    • Architecture Authority: approves cross-capability architecture, security
      boundaries, reuse decisions, global technical invariants, and technical
      Capability SDDs when no product/domain decision changes.
    • Capability Owner: prepares and maintains a Capability SDD and its traceability.
    • Certification Authority: independently evaluates implementation evidence
      against approved contracts and reports certification status.

The repository/platform owner MAY hold multiple roles when explicitly authorized.
Role combination does not collapse the lifecycle: preparation, approval, implementation,
and certification decisions must remain separately recorded. Codex and other AI agents
may prepare or review documents but cannot supply the required human/operator approval.

16.2 EXPLICIT APPROVAL MECHANISM

Status: ACCEPTED — 2026-10-08

Approval requires an auditable record containing:
    • document path;
    • document version;
    • approving authority or role;
    • explicit APPROVED or REJECTED decision;
    • decision date;
    • approval evidence/reference;
    • open conditions, if any.

The record MAY live in the SDD itself or in an approved repository governance record
referenced by the SDD. A Git commit, test result, Codex report, or REVIEWED status is not
an approval decision. Missing approval fields remain PENDING and prohibit APPROVED status.

16.3 APPROVAL RESPONSIBILITY

Status: ACCEPTED — 2026-10-08

The Product Owner approves Product or Domain Authority changes. The Architecture
Authority approves the Global SDD and capability technical designs. A Capability SDD
that changes product/domain truth also requires the applicable Product Owner decision.
The Certification Authority does not approve design; it certifies an implemented,
approved version.

16.4 GOVERNANCE MODEL ACCEPTANCE RECORD

```text
Document path: docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
Approved scope: Sections 16.1–16.3, role-based SDD governance model
Document version: N/A — authority document is unversioned; approved scope is dated 2026-10-08
Approving authority/role: Project operator
Explicit decision: ACCEPTED
Decision date: 2026-10-08
Approval evidence/reference: Explicit operator authorization in “SDD FORMAL APPROVAL REGISTRATION — GLOBAL SDD + MYSQL BACKUP RECOVERY — FINAL”, received 2026-10-08
Open conditions: NONE
```

17. AS-DESIGNED VS AS-BUILT
After certification, the SDD must accurately describe the certified implementation.
Therefore:
APPROVED SDD
     ↓
IMPLEMENTATION
     ↓
DISCOVERED NECESSARY CHANGE?
     ├── NO → verify
     │
     └── YES
           ↓
       update SDD
           ↓
       approve change
           ↓
       implementation
     ↓
CERTIFICATION
     ↓
CERTIFIED AS-BUILT SDD
No permanent design decision should exist only in the implementation report.

18. LEGACY TRANSITION POLICY
Existing certified functionality SHALL NOT be rewritten or redocumented solely to adopt SDD.
Existing artifacts remain valid historical evidence.
When an existing capability is materially modified:
    1. inspect existing documentation;
    2. inspect current implementation;
    3. inspect executable contracts;
    4. inspect relevant tests;
    5. recover relevant historical decisions when necessary;
    6. reconcile discrepancies;
    7. establish or update its Capability SDD;
    8. only then perform material redesign.
This is the progressive SDD adoption strategy.

19. MINIMAL DOCUMENTATION PRINCIPLE
SDD adoption MUST reduce fragmentation rather than increase it.
Do NOT create:
one SDD per endpoint
one SDD per bug
one SDD per migration
one SDD per prompt
one SDD per minor UI change
Prefer one durable SDD per coherent capability.

20. DOCUMENT OWNERSHIP RULE
Every permanent rule must have exactly one authoritative home.
Other documents MAY reference it.
They SHOULD NOT maintain independent competing copies.
ONE RULE
   ↓
ONE AUTHORITATIVE HOME
   ↓
MANY REFERENCES ALLOWED

21. TRACEABILITY
Important implementation work should permit tracing:
Product Requirement
       ↓
Domain Rule
       ↓
Architectural Constraint
       ↓
SDD Design
       ↓
Executable Contract
       ↓
Implementation
       ↓
Test
       ↓
Certification Evidence
Not every trivial line of code requires formal traceability.
Traceability SHALL be proportional to architectural and business risk.

22. CHANGE CLASSIFICATION
Before changing the system, classify the change.
Product change
Update appropriate Product Authority.
Domain change
Update Domain Authority.
Global architectural change
Update ADR/global architectural authority and, when affected, Global SDD.
Capability design change
Update Capability SDD.
Implementation-only correction
No SDD modification is required if the approved design remains unchanged.
Temporary execution decision
May remain only in the implementation prompt/report if it has no permanent architectural or behavioral effect.

23. OFFICIAL RULE
From adoption of this hierarchy forward:
No new permanent product, domain, architectural, security, API, persistence, lifecycle, authorization, concurrency, integration, or capability-design rule shall exist exclusively in a Codex prompt.
If implementation requires such a rule, it must first be represented in its proper authoritative artifact.

24. PRIMARY OBJECTIVE
This hierarchy exists to achieve:
    • one coherent source-of-truth model;
    • smaller Codex prompts;
    • less repeated context;
    • lower implementation ambiguity;
    • less design drift;
    • easier recovery between development sessions;
    • safer changes;
    • stronger certification;
    • faster path to production.
Documentation exists to accelerate correct implementation, not to become an independent deliverable that delays the product.
Clarify authority versus current-state evidence
