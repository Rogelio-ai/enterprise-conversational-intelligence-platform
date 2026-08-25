# ENTERPRISE_CORE_BOUNDARY_RULES.md

**Document Type:** Enterprise Architecture — Boundary Governance
**Scope:** Enterprise Core Boundary Rules
**Status:** Proposed Master Document
**Applies To:** Enterprise Core and all Domain Applications built on it

---

# 1. Purpose

This document defines the formal architectural rules that govern the boundary between the **Enterprise Core** and all **Domain Applications**.

Its purpose is to prevent:

* Domain-specific concepts from contaminating the Core.
* Premature abstraction.
* Duplicate reusable capabilities.
* Circular dependencies.
* Vendor lock-in.
* Inconsistent security boundaries.
* Cross-tenant leakage.
* Core growth without demonstrated value.
* Product delivery slowdown caused by overengineering.

This document complements:

```text
ENTERPRISE_CORE_CAPABILITY_MAP.md
```

The Capability Map defines **what capabilities belong to the Core**.

This document defines **how the boundary must be protected**.

---

# 2. Governing Principle

The fundamental architectural rule is:

> **The Enterprise Core owns reusable enterprise capabilities. Domain Applications own vertical business semantics.**

Dependency direction:

```text
Domain Application
        │
        ▼
Enterprise Core
        │
        ▼
Infrastructure
```

Allowed:

```text
domain → core
```

Forbidden:

```text
core → domain
```

The Enterprise Core must never depend on a Domain Application.

---

# 3. Core Independence Rule

The Enterprise Core must remain executable and conceptually valid without knowing which vertical applications consume it.

The Core must not require knowledge of concepts such as:

```text
Restaurant
Laboratory
Conversation Intelligence
Retail
Hotel
Clinic
Factory
```

A reusable Core capability must retain its meaning independently of every current product.

---

# 4. Domain Ownership Rule

A Domain Application owns all business concepts whose meaning depends on a particular industry or product.

Examples:

```text
Restaurant Domain

Table
Menu
Recipe
Order
Kitchen
Dining Session
Reservation
```

```text
Laboratory Domain

Sample
Analyte
Test Method
Measurement Result
Laboratory Report
Calibration
```

```text
Conversation Intelligence Domain

Import Session
Canonicalization
Conversation Finding
Knowledge Object
Source Importer
Conversation Intelligence Report
```

These concepts must not be promoted into Enterprise Core merely because the Core needs to reference them indirectly.

---

# 5. Dependency Direction Rule

Dependencies must flow inward toward generic abstractions.

Canonical direction:

```text
Domain
   │
   ▼
Core Contract
   │
   ▼
Infrastructure Adapter
```

Where applicable:

```text
Domain Service
      │
      ▼
Core Port
      │
      ▼
Vendor Adapter
```

Forbidden patterns include:

```text
Core → Restaurant

Core → Laboratory

Core → Conversation Intelligence
```

and:

```text
Core → Vendor-specific business implementation
```

---

# 6. No Reverse Domain Dependency Rule

The Core must not import:

```text
restaurant.*
laboratory.*
conversation_intelligence.*
```

or equivalent vertical modules.

This includes:

* ORM models.
* Services.
* Enums.
* DTOs.
* Policies.
* Events.
* Configuration structures.
* Domain-specific constants.

If the Core needs a domain concept to function, the abstraction is probably incorrectly located.

---

# 7. Domain Extension Rule

Domain Applications may specialize Core capabilities through composition.

Preferred:

```text
RestaurantTable
      │
      └── references Resource
```

Preferred:

```text
DiningSession
      │
      └── references InteractionSession
```

Preferred:

```text
LaboratoryInstrument
      │
      └── references Resource
```

Avoid modifying generic Core objects to include vertical fields.

Forbidden example:

```text
Resource
├── table_number
├── kitchen_station
├── analyte_code
└── whatsapp_chat_id
```

---

# 8. Composition Over Core Inheritance Rule

Domain-specific behavior should generally extend Core through:

* Composition.
* References.
* Domain services.
* Domain policies.
* Adapters.
* Event subscriptions.

Avoid creating deep inheritance hierarchies such as:

```text
Resource
  ↓
BusinessResource
  ↓
OperationalResource
  ↓
RestaurantResource
  ↓
DiningResource
  ↓
Table
```

Such hierarchies create unnecessary coupling.

Preferred:

```text
Table
  └── resource_id
```

when a Core resource identity is actually required.

---

# 9. Core Admission Rule

A new capability may enter Enterprise Core only when there is strong justification.

The following questions must be evaluated:

1. Does the capability have the same essential meaning across multiple domains?
2. Are its principal invariants domain-neutral?
3. Does centralization provide meaningful reuse?
4. Does centralization reduce duplication?
5. Does it improve security, auditability or consistency?
6. Can its contract remain stable independently of vertical evolution?
7. Does it avoid domain terminology?
8. Is there a current product need?
9. Does adding it improve delivery rather than delay it?
10. Is the abstraction supported by evidence rather than speculation?

If the answer is weak or uncertain, the capability should remain outside the Core.

---

# 10. Extraction Over Prediction Rule

The preferred evolution path is:

```text
Concrete Product Requirement
        │
        ▼
Domain Analysis
        │
        ▼
Working Implementation
        │
        ▼
Reusable Pattern Detected
        │
        ▼
Core Boundary Review
        │
        ▼
Generic Capability
```

Not:

```text
Possible Future Requirement
        │
        ▼
Generic Framework
        │
        ▼
Unused Complexity
```

Formal rule:

> **Prefer extracting proven reusable behavior over predicting hypothetical reuse.**

---

# 11. Two-Domain Evidence Rule

As a default guideline, a capability should not be generalized solely because one product needs it.

Strong evidence for Core admission exists when:

```text
Domain A
   +
Domain B
   ↓
Same semantic capability
```

However, this is not an absolute numeric requirement.

A capability may belong in Core immediately when its enterprise nature is already obvious, for example:

```text
Tenant isolation
Authentication
Audit
Configuration
Observability
```

The decision must be semantic, not mechanical.

---

# 12. Same Name ≠ Same Capability Rule

Two domains using the same word does not mean they share the same Core abstraction.

Example:

```text
Restaurant Order
Purchase Order
Laboratory Work Order
```

All contain the word:

```text
Order
```

but they may represent fundamentally different domain objects.

Do not create:

```text
CoreOrder
```

unless their true invariants and lifecycle justify it.

Similarity of naming is insufficient evidence for reuse.

---

# 13. Same Structure ≠ Same Domain Meaning Rule

Two entities having similar fields does not make them the same business concept.

Example:

```text
id
status
created_at
assigned_to
```

may appear in:

```text
Restaurant Order
Laboratory Test
Support Ticket
Maintenance Work Order
```

Their structural similarity does not justify a generic business entity.

The Core may reuse underlying capabilities such as:

```text
Lifecycle
Assignment
Audit
History
```

without owning the domain object itself.

---

# 14. Generic Mechanism vs Business Meaning Rule

The Enterprise Core may own generic mechanisms.

The Domain Application owns what those mechanisms mean.

Example:

```text
Core:
Task
```

```text
Restaurant:
Prepare Order Item
```

```text
Laboratory:
Review Test Result
```

The Core knows how to:

```text
create
assign
track
complete
audit
```

The domain knows why the task exists and what completion means.

---

# 15. State Ownership Rule

The Core may provide generic state-management infrastructure.

The Domain Application owns its actual business state machine.

Core may own:

```text
CurrentState
Transition
TransitionTime
TransitionActor
TransitionReason
TransitionHistory
```

Restaurant may define:

```text
PENDING
IN_PREPARATION
READY
DELIVERED
```

Laboratory may define:

```text
DRAFT
UNDER_REVIEW
VALIDATED
AUTHORIZED
```

Those states must not be added globally to Core.

---

# 16. Event Ownership Rule

Enterprise Core owns the generic event mechanism.

Domain Applications own domain event types.

Core:

```text
BusinessEvent
event_type
occurred_at
actor
subject
correlation_id
causation_id
```

Restaurant:

```text
ORDER_ITEM_READY
```

Laboratory:

```text
RESULT_VALIDATED
```

Conversation Intelligence:

```text
IMPORT_COMPLETED
```

The Core must not contain an ever-growing registry of vertical event semantics.

---

# 17. Policy Ownership Rule

The Enterprise Core may provide policy evaluation mechanisms.

Domain Applications own their policy definitions.

Core may answer:

```text
Can ACTOR perform ACTION on SUBJECT under CONTEXT?
```

Domain defines rules such as:

```text
Can this restaurant order item be cancelled?
```

or:

```text
Can this laboratory report be authorized?
```

The business policy must remain with the domain that owns the business invariant.

---

# 18. Workflow Ownership Rule

The Core may own reusable workflow/protocol execution infrastructure.

The domain owns:

* Workflow meaning.
* Workflow steps.
* Business conditions.
* Business escalation logic.
* Business completion criteria.

Example:

```text
Core:
Protocol execution
```

```text
Restaurant:
Customer Complaint Protocol
```

```text
Laboratory:
Technical Review Protocol
```

A generic workflow engine must not absorb domain semantics.

---

# 19. Participant Boundary Rule

The Core may own:

```text
Participant
ExternalIdentity
IdentityLink
IdentityResolution
```

Domains may specialize meaning through references.

Examples:

```text
Restaurant:
Guest
```

```text
Laboratory:
Customer
Analyst
```

```text
Conversation Intelligence:
Conversation Participant
```

Do not put all possible participant types into a global Core enum.

---

# 20. Resource Boundary Rule

The Core may own a generic Resource abstraction where reuse is useful.

Domains own the actual resource semantics.

Core:

```text
Resource
ResourceType
ResourceStatus
Location
Ownership
```

Possible domain-owned concepts:

```text
Table
Laboratory Instrument
Vehicle
Workstation
Production Station
```

Do not progressively transform `Resource` into a universal business object containing every domain attribute.

---

# 21. Conversation Boundary Rule

The Core may own canonical communication structures:

```text
Conversation
Message
Participant
AttachmentReference
Reaction
Thread
Channel
```

Source-specific behavior remains outside the Core.

Forbidden Core entities:

```text
WhatsAppMessage
TelegramChat
SlackThread
TeamsConversation
```

These belong in:

```text
Connector
Importer
Adapter
Source Mapping
```

---

# 22. Integration Boundary Rule

The Core owns vendor-neutral integration contracts.

Adapters own vendor-specific behavior.

Architecture:

```text
Core / Domain
      │
      ▼
     Port
      │
      ▼
    Adapter
      │
      ▼
External Provider
```

Examples:

```text
PaymentPort
   ↓
ConektaAdapter
```

```text
ConversationImportPort
   ↓
WhatsAppAdapter
```

```text
ObjectStoragePort
   ↓
MinIOAdapter
```

Vendor concepts must not leak upward into Core business models.

---

# 23. Vendor Neutrality Rule

A Core model must not expose vendor-specific identifiers as mandatory first-class business semantics.

Avoid:

```text
conekta_order_id
stripe_customer_id
whatsapp_message_id
openai_thread_id
```

inside generic Core entities.

Preferred:

```text
ExternalReference
provider
external_id
resource_type
metadata
```

where the external reference actually needs persistence.

---

# 24. Infrastructure Independence Rule

Core business semantics must not depend directly on infrastructure technology.

Forbidden business-level dependencies include direct assumptions about:

```text
MySQL
Redis
MinIO
Kafka
RabbitMQ
Elasticsearch
OpenAI
AWS
```

Infrastructure implements Core ports and persistence contracts.

Technology choices may influence implementation details but must not redefine Core business meaning.

---

# 25. Storage Boundary Rule

The Core may define persistence requirements and repository contracts.

It must not require domain code to know persistence details.

Preferred:

```text
Domain / Core Service
      │
      ▼
Repository / Port
      │
      ▼
SQLAlchemy Implementation
```

Avoid leaking ORM-specific behavior into domain contracts.

---

# 26. API Boundary Rule

External APIs must expose stable product semantics rather than internal implementation layout.

A module's physical location inside Core is not itself an API contract.

Do not expose internal abstractions merely because they exist.

Public APIs should be created only when required by actual consumers.

---

# 27. Security Boundary Rule

Security responsibilities that apply consistently across products should be centralized in Core.

Examples:

```text
Authentication
Tenant isolation
Authorization framework
Audit context
Secret handling
Security event recording
```

However, domain-level business authorization remains owned by the Domain Application.

Example:

```text
Core:
Does this actor hold required authority?
```

```text
Restaurant:
Does business policy permit cancellation at this stage?
```

Both may participate in a final decision.

---

# 28. Tenant Isolation Rule

All tenant-aware Core capabilities must enforce tenant boundaries structurally wherever practical.

Tenant isolation must not depend exclusively on frontend filtering or developer discipline.

Preferred protections include:

* Tenant-scoped queries.
* Composite ownership constraints where appropriate.
* Explicit tenant context.
* Authorization checks.
* Tenant-aware integration requests.
* Tenant-aware audit records.

Cross-tenant references must be rejected unless explicitly permitted by platform-level design.

---

# 29. Organizational Ownership Rule

Objects owned by an Organization or Location must preserve their higher-level tenant ownership.

Example:

```text
Tenant
  ↓
Organization
  ↓
Location
  ↓
Resource
```

A lower-level reference must not permit ownership relationships that contradict the hierarchy.

---

# 30. Audit Boundary Rule

Core owns the generic audit mechanism.

Domain Applications determine which business operations require domain-specific audit semantics.

Core audit should be able to record:

```text
actor
action
subject
before
after
timestamp
origin
correlation
```

Domains may add contextual meaning without modifying the Core audit schema unnecessarily.

---

# 31. History Boundary Rule

Business history and technical audit are different concerns.

Do not use a single audit table as the only representation of business lifecycle.

Business history answers:

```text
What happened to this business object?
```

Audit answers:

```text
Who changed what in the system?
```

Both may reference the same correlation context.

---

# 32. Metadata Boundary Rule

Metadata must not become an escape hatch for poor domain modeling.

Use metadata when information is:

* Optional.
* Source-specific.
* Variable.
* Extensible.
* Not part of stable invariants.

Do not use generic JSON metadata for important stable concepts simply to avoid schema design.

Bad:

```text
metadata = {
  "order_total": ...,
  "table_number": ...,
  "customer_balance": ...
}
```

when these values are core business semantics of a domain.

---

# 33. Shared Utility Rule

Not every reusable utility belongs to Enterprise Core.

Examples:

```text
String helper
Date helper
CSV helper
JSON helper
```

may belong to technical shared libraries rather than the Enterprise Core domain layer.

Enterprise Core is a capability boundary, not a dumping ground for shared code.

---

# 34. Shared Library vs Enterprise Core Rule

Three different concepts must remain distinct:

```text
Enterprise Core
Technical Shared Library
Domain Application
```

Example:

```text
enterprise_core/
shared/
domains/
```

The Core owns reusable enterprise semantics.

`shared/` may own low-level technical utilities with no enterprise meaning.

Domains own vertical semantics.

---

# 35. Core Data Ownership Rule

Each Core capability must clearly own its data.

Examples:

```text
Identity owns authentication identities.

Tenant owns tenant lifecycle.

Participant owns participant identity resolution.

Conversation owns canonical conversational structures.

Audit owns audit records.
```

Domains must not bypass Core invariants by writing directly into Core persistence tables.

Interactions must occur through approved services/contracts.

---

# 36. Domain Data Ownership Rule

Enterprise Core must not directly manipulate domain-owned persistence.

Forbidden:

```text
Core Service
   ↓
updates restaurant_orders table
```

Preferred:

```text
Core capability
   ↓
Domain contract / event
   ↓
Restaurant domain service
```

Ownership boundaries must remain explicit.

---

# 37. Transaction Boundary Rule

A transaction should be owned by the capability that owns the business invariant.

Avoid Core transactions that manipulate unrelated domain state.

Where a workflow spans capabilities, coordinate through:

* Application services.
* Domain services.
* Explicit transactions.
* Events.
* Idempotent reactions.

Do not introduce distributed architecture merely to preserve conceptual separation inside a modular monolith.

---

# 38. Modular Monolith Rule

Logical boundaries do not require microservices.

Core and Domain Applications may coexist within one deployable application while preserving strict module boundaries.

Conceptually:

```text
Application
│
├── enterprise_core/
│
├── conversation_intelligence/
│
├── restaurant/
│
└── infrastructure/
```

Modularity is architectural.

Deployment topology is operational.

Do not create network boundaries where in-process boundaries are sufficient.

---

# 39. No Premature Microservices Rule

A Core capability must not become a separate service solely because it is reusable.

Service extraction requires concrete operational justification such as:

* Independent scaling.
* Independent deployment.
* Security isolation.
* Team ownership.
* Reliability requirements.
* Technology requirements.

Until then, prefer a modular monolith.

---

# 40. Configuration Boundary Rule

Configuration may control:

```text
Enabled capability
Deployment mode
Limits
Entitlements
Provider choice
Feature availability
Operational settings
```

Configuration must not redefine fundamental domain meaning.

Avoid:

```text
if deployment_mode == "restaurant":
    core behaves differently
```

Prefer:

```text
Domain Application
    +
Core Configuration
```

The Core should not contain vertical-mode switches.

---

# 41. Deployment Mode Rule

The same Core must support:

```text
Cloud SaaS
Enterprise Self-Hosted
Personal / Local
```

Deployment differences may affect:

* Infrastructure.
* Licensing.
* Tenant provisioning.
* Operational limits.
* Provider configuration.

They must not create duplicate business implementations.

Forbidden:

```text
saas_core/
enterprise_core/
personal_core/
```

Preferred:

```text
enterprise_core/
+
deployment configuration
```

---

# 42. Edition Boundary Rule

Commercial editions may expose different entitlements.

Example:

```text
Feature A:
Cloud SaaS → enabled

Enterprise → enabled

Personal → limited
```

The feature implementation remains singular.

Commercial packaging must not produce source-code forks.

---

# 43. Localization Boundary Rule

Canonical Core values must remain language-neutral.

Store:

```text
ACKNOWLEDGED
```

Display:

```text
Enterado
Acknowledged
Confirmado
```

according to locale.

Do not make localized labels part of Core invariants.

---

# 44. Timezone Boundary Rule

Stored event timestamps should follow a consistent canonical representation.

Display conversion belongs to localization/context.

The Core must preserve the distinction between:

```text
occurred_at
received_at
created_at
processed_at
```

when relevant.

Do not infer event time solely from database creation time.

---

# 45. Original Evidence Boundary Rule

Original evidence and normalized information must remain distinct.

Architecture:

```text
Original Evidence
       │
       ▼
Transformation
       │
       ▼
Canonical Representation
       │
       ▼
Derived Intelligence
```

The Core may provide evidence infrastructure.

The Domain Application owns source interpretation and canonicalization rules where those rules are product-specific.

---

# 46. Derived Intelligence Boundary Rule

AI-generated or analytically derived information must not overwrite source facts.

Maintain distinction:

```text
Observed Fact
Derived Fact
Inference
Recommendation
Prediction
```

where relevant.

Derived information should preserve provenance and evidence references.

---

# 47. AI Boundary Rule

AI models may consume Core and Domain information but must not become the source of authorization.

AI must pass through:

```text
Identity
Policy
Domain Validation
Service Boundary
Audit
```

Forbidden:

```text
LLM
 ↓
direct database mutation
```

Preferred:

```text
LLM / Agent
     │
     ▼
Structured Tool Request
     │
     ▼
Policy Evaluation
     │
     ▼
Domain/Core Service
     │
     ▼
Validated Mutation
     │
     ▼
Audit/Event
```

---

# 48. Agent Identity Rule

An intelligent agent performing actions must have explicit identity.

The system must be able to determine:

```text
Which agent acted?
On whose behalf?
Under which authorization?
Using which tool?
With which input?
What result occurred?
```

Agent actions must be auditable at least as strongly as human actions.

---

# 49. Human Approval Boundary Rule

When business or security policy requires human authorization, AI must not bypass it.

Generic outcome:

```text
REQUIRE_APPROVAL
```

must result in an explicit approval workflow.

Approval ownership belongs to the relevant policy/domain.

---

# 50. Payment Boundary Rule

The Core may own generic payment mechanics.

The Domain Application owns why money is owed.

Core may know:

```text
Payment
PaymentAttempt
Refund
Allocation
Payment Status
```

Restaurant may own:

```text
Dining Account
```

Laboratory may own:

```text
Invoice / service charge semantics
```

Do not create generic Core billing objects solely because payments exist.

---

# 51. Search Boundary Rule

Core may provide common search infrastructure and contracts.

Domain Applications own:

* Search semantics.
* Domain-specific filters.
* Domain-specific ranking.
* Domain-specific result presentation.

Search infrastructure may evolve without changing domain meaning.

---

# 52. Analytics Boundary Rule

Core analytics may expose generic operational facts.

Examples:

```text
event counts
durations
transition times
failure rates
response times
```

Domains own business interpretation.

Core:

```text
average duration from EVENT_A to EVENT_B
```

Restaurant:

```text
average preparation time
```

Laboratory:

```text
average technical review time
```

Do not move business KPIs into Core merely because they use generic measurements.

---

# 53. Observability Boundary Rule

Observability belongs to Core/shared infrastructure when it provides consistent cross-product operational context.

Standard context may include:

```text
tenant_id
request_id
correlation_id
actor_id
service/module
```

Domain-specific business information should only be logged when operationally justified and safe.

---

# 54. Correlation Boundary Rule

Core may provide correlation mechanisms.

Domains determine which objects participate in a business correlation.

Generic fields:

```text
correlation_id
causation_id
request_id
```

The Core must not require every entity to share one global transaction identifier unnecessarily.

---

# 55. Idempotency Boundary Rule

Core may provide reusable idempotency infrastructure.

The owner of the operation defines the idempotency scope.

Examples:

```text
Payment creation
Import execution
Webhook handling
External command
Agent action
```

The idempotency key must be scoped sufficiently to prevent cross-tenant or cross-operation collisions.

---

# 56. Versioning Boundary Rule

Core mechanisms may support versioned definitions.

Domains own the content of domain definitions.

Examples:

```text
Core:
PolicyVersion mechanism
```

```text
Restaurant:
Cancellation Policy v3
```

```text
Laboratory:
Technical Review Protocol v5
```

Historical records must remain interpretable under the version applicable at execution time.

---

# 57. Migration Boundary Rule

Core schema migrations must not silently mutate domain-owned data.

Domain migrations must not redefine Core invariants.

Cross-boundary schema changes require explicit architectural review.

Migration order should preserve dependency direction:

```text
Core foundation
   ↓
Domain dependencies
```

where practical.

---

# 58. API Compatibility Rule

Once multiple Domain Applications consume a Core contract, breaking changes require deliberate compatibility management.

Before modifying a shared Core contract evaluate:

```text
Existing consumers
Database migrations
Historical compatibility
API compatibility
Deployment compatibility
Security
Tenant isolation
```

Do not optimize one vertical by breaking shared Core semantics.

---

# 59. Core Stability Rule

Core APIs and invariants should become progressively more stable as reuse grows.

Early Core capabilities may evolve rapidly.

Once multiple products depend on them, changes must become more conservative.

Conceptually:

```text
Experimental
   ↓
Used by one domain
   ↓
Used by multiple domains
   ↓
Stable Core Contract
```

---

# 60. No Domain Enum Leakage Rule

Do not place vertical enums into Core modules.

Forbidden:

```text
RestaurantOrderStatus
LaboratoryReportStatus
WhatsAppMessageType
```

Core may provide mechanisms for validating generic state definitions, but domain values remain domain-owned.

---

# 61. No Domain Foreign-Key Leakage Rule

Core tables must not contain mandatory foreign keys to domain tables.

Forbidden:

```text
core_notifications.restaurant_order_id
```

Better:

```text
subject_type
subject_reference
```

or an explicit generic reference abstraction when justified.

Domain tables may reference Core identities.

---

# 62. Generic Reference Caution Rule

Generic references such as:

```text
entity_type
entity_id
```

must not be used indiscriminately.

They reduce database referential integrity.

Prefer explicit foreign keys when relationships are stable and belong within the same ownership boundary.

Use generic references only when true polymorphism across independent domains is required.

---

# 63. Domain Event Reaction Rule

Core capabilities may react to domain events through contracts without owning the domain.

Example:

```text
Restaurant:
ORDER_ITEM_READY
       │
       ▼
Core Notification Capability
       │
       ▼
Notify assigned recipient
```

The notification module does not need to understand restaurant preparation semantics.

It only consumes a validated event/request.

---

# 64. Core Event Reaction Rule

Domains may react to Core events.

Example:

```text
Core:
PARTICIPANT_IDENTIFIED
       │
       ▼
Domain Application:
Load domain-specific context
```

Events must not create hidden circular dependencies.

---

# 65. Synchronous vs Asynchronous Boundary Rule

Module boundaries do not automatically imply asynchronous communication.

Use synchronous in-process calls when:

* Immediate consistency is required.
* Operation is local.
* Complexity would otherwise increase unnecessarily.

Use asynchronous processing when justified by:

* Long-running work.
* External systems.
* Retry requirements.
* Failure isolation.
* Eventual consistency.
* Independent processing.

Avoid queues solely for architectural aesthetics.

---

# 66. Core Error Boundary Rule

Core capabilities should expose stable, semantic error types.

Examples:

```text
NotFound
Conflict
Forbidden
InvalidTransition
PolicyDenied
ExternalDependencyUnavailable
```

Domains may translate them into business-specific responses.

Vendor exceptions must not leak through Core boundaries.

---

# 67. External Failure Boundary Rule

External integration failures must be mapped into domain-neutral integration semantics.

Examples:

```text
TemporaryExternalFailure
DefiniteExternalRejection
UncertainExternalResult
UnsupportedCapability
ExternalMappingFailure
```

This allows domains to react without knowing provider implementation details.

---

# 68. Validation Boundary Rule

Core validates Core invariants.

Domain validates Domain invariants.

Example:

Core can validate:

```text
tenant consistency
required identity
valid lifecycle transition
```

Restaurant validates:

```text
product may be cancelled before preparation
```

Laboratory validates:

```text
report cannot be authorized before technical review
```

Never relocate a domain invariant into Core simply to reuse validation code.

---

# 69. Security Validation Rule

Boundary crossings must not weaken security.

Whenever a Domain Application invokes a Core capability, the system must preserve appropriate:

```text
tenant context
actor identity
authorization context
correlation context
```

Anonymous or system-generated operations must be explicitly represented rather than inferred.

---

# 70. Boundary Review Trigger

A formal boundary review should occur when any of the following happens:

* A second domain needs similar functionality.
* Core gains a domain-specific field.
* A domain imports another domain.
* A vendor concept appears in a Core model.
* A Core API requires vertical terminology.
* A generic abstraction becomes difficult to explain.
* Metadata begins carrying important stable business semantics.
* Core complexity increases significantly.
* A new cross-domain capability is proposed.
* A shared contract needs a breaking change.

---

# 71. Boundary Smell Indicators

The following are warning signs of an incorrect boundary:

```text
"Just add this restaurant field to Core."

"We may need this someday."

"All objects can inherit from BaseBusinessObject."

"Everything should be an Event."

"Everything should be a Resource."

"Everything should be configurable."

"Let's create a generic Order."

"Let's put it in metadata for now."

"The Core can inspect the domain table."

"We need a microservice because this is a separate module."
```

Each of these statements requires architectural scrutiny.

---

# 72. Core Candidate Decision Matrix

A proposed capability should be evaluated using:

| Criterion             | Low             | Medium            | High                  |
| --------------------- | --------------- | ----------------- | --------------------- |
| Cross-domain reuse    | One product     | Possible reuse    | Proven/common reuse   |
| Semantic neutrality   | Domain-specific | Partially generic | Fully domain-neutral  |
| Stable invariants     | Highly vertical | Mixed             | Stable across domains |
| Security benefit      | None            | Moderate          | Strong                |
| Duplication avoided   | Little          | Some              | Significant           |
| Complexity introduced | High            | Moderate          | Low                   |
| Current need          | Hypothetical    | Near-term         | Immediate             |
| Contract stability    | Unclear         | Possible          | Strong                |

Core admission is favored when reuse, neutrality and value are high while introduced complexity remains controlled.

---

# 73. Boundary Decision Outcomes

Every boundary review should conclude with one of four outcomes:

```text
CORE

OPTIONAL REUSABLE CORE

DOMAIN APPLICATION

TECHNICAL SHARED LIBRARY
```

These classifications must not be conflated.

---

# 74. CORE Classification

Use when the capability is:

* Foundational.
* Domain-neutral.
* Broadly reusable.
* Security/tenant/audit critical.
* Required by multiple product areas.

Examples:

```text
Tenant
Identity
Audit
Conversation
Business Event mechanism
Configuration
Integration contracts
```

---

# 75. OPTIONAL REUSABLE CORE Classification

Use when the capability is generic and reusable but not universally required.

Examples may include:

```text
Workflow engine
Payments
Contextual memory
Advanced licensing
```

These capabilities may remain disabled or unimplemented until a product requires them.

---

# 76. DOMAIN APPLICATION Classification

Use when business meaning depends materially on the vertical.

Examples:

```text
Restaurant Order
Laboratory Sample
Conversation Import Session
```

Domain ownership remains even if another product has a structurally similar concept.

---

# 77. TECHNICAL SHARED LIBRARY Classification

Use for implementation utilities without enterprise-domain semantics.

Examples:

```text
datetime utilities
serialization utilities
retry helper
HTTP helper
testing utilities
```

These do not belong in the Enterprise Core capability model.

---

# 78. Boundary Decision Documentation Rule

Significant boundary decisions should record:

```text
Capability
Requested owner
Final owner
Reason
Alternatives considered
Reuse evidence
Security implications
Migration implications
Decision date
```

For major architectural decisions, use an ADR where appropriate.

Do not create ADRs for trivial placement decisions.

---

# 79. Domain Independence Test

Before accepting a capability into Core, ask:

> Could this capability be explained completely without using the name of any current Domain Application?

If not, it is probably still domain-specific.

Example:

Bad Core description:

```text
Handles tables that restaurant customers occupy.
```

Clearly domain-specific.

Better generic capability:

```text
Represents location-bound resources managed by a tenant.
```

Only valid if the abstraction genuinely has reusable semantics.

---

# 80. Replacement Test

Ask:

> Could we remove the Restaurant application tomorrow and the Core concept would still make complete sense?

If the answer is no, reconsider the boundary.

The same test applies independently to every vertical.

---

# 81. New Domain Adoption Test

A new Domain Application should be able to consume Enterprise Core without needing changes to existing Core semantics.

Some Core extensions may legitimately be required, but adopting a new domain should not require rewriting the foundation.

If every new domain causes broad Core modifications, the Core boundary is too coupled.

---

# 82. Core Value Test

The Core must measurably provide at least one of:

```text
Faster product delivery
Reduced duplicated implementation
Consistent security
Consistent tenant isolation
Consistent auditability
Stable integration boundaries
Shared operational intelligence
Commercial deployment reuse
AI/agent governance reuse
```

If a proposed abstraction delivers none of these, it probably does not belong in Core.

---

# 83. Core Complexity Budget Rule

Every Core abstraction creates long-term maintenance cost.

Therefore, any proposed capability must justify:

```text
complexity added
<
reuse + consistency + security + delivery value
```

This principle must be treated as a permanent architectural constraint.

---

# 84. No Framework-for-Framework's-Sake Rule

The Enterprise Core exists to accelerate production-grade products.

It is not an independent academic framework project.

Therefore:

> **Do not expand the Core unless the expansion directly supports product value, production readiness, commercial viability, security or demonstrated reuse.**

Core work that does not serve active or strongly justified product requirements should be deferred.

---

# 85. Product Priority Rule

When there is tension between creating a theoretically perfect reusable abstraction and delivering a clean product implementation:

1. Preserve critical security and architectural boundaries.
2. Prefer the simplest correct product implementation.
3. Gather evidence.
4. Extract the reusable pattern later.

Do not block product delivery waiting for speculative Core perfection.

---

# 86. Formal Boundary Model

The final architectural boundary is:

```text
┌───────────────────────────────────────────────────────┐
│                  DOMAIN APPLICATIONS                  │
│                                                       │
│ Restaurant │ Laboratory │ Conversation Intelligence   │
│ Future Domains                                        │
└───────────────────────┬───────────────────────────────┘
                        │
                        │ depends on
                        ▼
┌───────────────────────────────────────────────────────┐
│                    ENTERPRISE CORE                    │
│                                                       │
│ Identity │ Tenant │ Participant │ Conversation         │
│ Events │ Tasks │ Policies │ Audit │ Integration       │
│ Security │ Configuration │ Analytics │ AI Enablement  │
└───────────────────────┬───────────────────────────────┘
                        │
                        │ implemented through
                        ▼
┌───────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE                     │
│                                                       │
│ MySQL │ S3/MinIO │ External APIs │ Payment Providers │
│ Messaging Providers │ AI Providers │ Monitoring      │
└───────────────────────────────────────────────────────┘
```

The Domain Application supplies business meaning.

The Enterprise Core supplies reusable enterprise capability.

Infrastructure supplies technical implementation.

---

# 87. Governing Formula

The architectural model is:

```text
ENTERPRISE CORE
        +
DOMAIN APPLICATION
        +
INFRASTRUCTURE ADAPTERS
        +
DEPLOYMENT CONFIGURATION
        =
COMMERCIAL PRODUCT
```

No layer should assume ownership of semantics belonging to another layer.

---

# 88. Final Boundary Rules

The following rules are authoritative:

```text
1. DOMAIN → CORE is allowed.

2. CORE → DOMAIN is forbidden.

3. Core owns reusable capability, not vertical semantics.

4. Domains own business invariants.

5. Vendors remain behind adapters.

6. Infrastructure must not define business meaning.

7. Reuse must be demonstrated or strongly justified.

8. Prefer extraction over speculative abstraction.

9. Same name does not imply same domain concept.

10. Same structure does not imply same domain concept.

11. Generic mechanisms may be Core; business meaning remains Domain.

12. Security, tenant isolation and audit boundaries must survive every integration.

13. AI and agents must use the same governed service boundaries as humans and systems.

14. Deployment models must not create business-code forks.

15. Metadata must not replace proper domain modeling.

16. Core changes must become more conservative as reuse increases.

17. Modular boundaries do not require microservices.

18. Core complexity must remain proportional to demonstrated value.

19. The Core exists to accelerate products, not to become an end in itself.

20. When uncertain, keep the concept in the Domain until reuse is proven.
```

---

# 89. Final Architectural Decision

`ENTERPRISE_CORE_BOUNDARY_RULES.md` is the authoritative governance document for protecting the separation between the Enterprise Core, Domain Applications and Infrastructure.

It answers:

```text
Where should a capability live?

Who owns its semantics?

Which dependencies are permitted?

When should something become reusable Core?

How should domains extend Core?

How should vendors and infrastructure remain isolated?

How do we prevent overengineering and Core contamination?
```

Together:

```text
ENTERPRISE_CORE_CAPABILITY_MAP.md
        +
ENTERPRISE_CORE_BOUNDARY_RULES.md
```

define the formal architectural constitution of the reusable Enterprise Core.

---

**END OF DOCUMENT**
