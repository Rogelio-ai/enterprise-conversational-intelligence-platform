# DOMAIN_APPLICATION_CAPABILITY_MAP.md

**Document Type:** Enterprise Architecture — Domain Application Capability Map
**Scope:** Domain Applications Only
**Status:** Proposed Master Document
**Architecture:** Enterprise Core + Domain Applications
**Applies To:** All vertical products built on the Enterprise Core

---

# 1. Purpose

This document formally defines the architectural role, responsibilities, capability boundaries and extension rules of **Domain Applications** built on the Enterprise Core.

A Domain Application represents the business-specific layer of a commercial product.

It owns:

* Vertical business concepts.
* Business terminology.
* Business entities.
* Business invariants.
* Business workflows.
* Business policies.
* Business state machines.
* Business analytics.
* Product-specific use cases.
* Product-specific integrations and mappings.
* Product-specific AI behavior.

The Enterprise Core provides reusable enterprise capabilities.

The Domain Application gives those capabilities **business meaning**.

---

# 2. Governing Architecture

The governing architectural model is:

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

Conceptually:

```text
┌────────────────────────────────────────────────────────────┐
│                    COMMERCIAL PRODUCT                      │
│                                                            │
│                  Product Experience                        │
│                         │                                  │
│                         ▼                                  │
│                  DOMAIN APPLICATION                        │
│                         │                                  │
│                         ▼                                  │
│                   ENTERPRISE CORE                          │
│                         │                                  │
│                         ▼                                  │
│                    INFRASTRUCTURE                           │
└────────────────────────────────────────────────────────────┘
```

---

# 3. Domain Application Definition

A Domain Application is:

> A product-specific business layer that defines the concepts, rules, processes, actions, intelligence and user-facing capabilities of a particular business domain while consuming reusable capabilities from the Enterprise Core.

Examples include:

```text
Restaurant Intelligence Platform

Laboratory / LIMS

Conversation Intelligence Platform

Future Vertical Applications
```

A Domain Application is **not** merely a UI placed on top of Enterprise Core.

It contains the actual business semantics of the product.

---

# 4. Governing Dependency Rule

The dependency direction is:

```text
DOMAIN APPLICATION
        │
        ▼
ENTERPRISE CORE
```

Allowed:

```text
domain → core
```

Forbidden:

```text
core → domain
```

Domain Applications may consume Enterprise Core.

Enterprise Core must never require a particular Domain Application.

---

# 5. Domain Application Capability Map

Every Domain Application may contain some or all of the following capability categories:

```text
DOMAIN APPLICATION
│
├── DA-01 Domain Identity & Terminology
├── DA-02 Domain Participants
├── DA-03 Domain Resources
├── DA-04 Domain Sessions & Context
├── DA-05 Domain Entities & Aggregates
├── DA-06 Domain Catalogs & Reference Data
├── DA-07 Domain Actions & Commands
├── DA-08 Domain State Machines
├── DA-09 Domain Business Events
├── DA-10 Domain Policies & Invariants
├── DA-11 Domain Workflows & Protocols
├── DA-12 Domain Tasks & Assignments
├── DA-13 Domain Communication Semantics
├── DA-14 Domain Files & Evidence
├── DA-15 Domain Integrations
├── DA-16 Domain Search
├── DA-17 Domain Analytics & KPIs
├── DA-18 Domain Reporting & Export
├── DA-19 Domain Intelligence
├── DA-20 Domain AI & Agent Behavior
├── DA-21 Domain UX / Application Experience
└── DA-22 Domain Administration & Configuration
```

Not every domain requires every capability.

This is a capability classification, not a mandatory implementation checklist.

---

# 6. DA-01 — Domain Identity & Terminology

**Owner:** Domain Application

Each Domain Application defines its own ubiquitous language.

Examples:

## Restaurant

```text
Guest
Table
Menu
Order
Order Item
Kitchen
Reservation
Dining Session
Bill
```

## Laboratory

```text
Customer
Sample
Analyte
Test Method
Result
Report
Technical Review
Authorization
```

## Conversation Intelligence

```text
Import
Import Source
Canonicalization
Conversation Finding
Knowledge Object
Conversation Dataset
Export Package
```

Domain terminology must remain outside Enterprise Core unless the underlying concept is independently justified as a reusable Core capability.

---

# 7. DA-02 — Domain Participants

Enterprise Core may provide:

```text
Participant
Identity
ExternalIdentity
IdentityResolution
```

The Domain Application defines what a participant means commercially.

Examples:

```text
Restaurant
Participant → Guest
```

```text
Laboratory
Participant → Customer
Participant → Analyst
Participant → Technical Reviewer
```

```text
Conversation Intelligence
Participant → Conversation Participant
```

The domain may associate additional domain-specific information with the Core participant without changing Core semantics.

---

# 8. DA-03 — Domain Resources

Enterprise Core may provide:

```text
Resource
Location
Ownership
Status Foundation
```

Domain Applications define concrete resources.

Examples:

## Restaurant

```text
Table
POS Terminal
Preparation Station
Service Station
```

## Laboratory

```text
Instrument
Sampling Equipment
Measurement Equipment
```

## Conversation Intelligence

Possible domain resources should only be introduced when the business model actually requires them.

The existence of `Core.Resource` does not require every domain entity to become a Resource.

---

# 9. DA-04 — Domain Sessions & Context

Enterprise Core may provide:

```text
InteractionSession
```

The Domain Application owns the business interpretation.

Example:

```text
Restaurant

InteractionSession
       │
       ▼
DiningSession
```

A domain session may add:

```text
Domain participants
Domain resources
Business state
Business relationships
Domain-specific context
```

Domain context must not be pushed into generic Core session fields merely for convenience.

---

# 10. DA-05 — Domain Entities & Aggregates

Domain Applications own their business entities and aggregate boundaries.

Examples:

## Restaurant

```text
Menu
Product
Order
OrderItem
DiningSession
RestaurantAccount
Reservation
```

## Laboratory

```text
Sample
Test
Analyte
MeasurementResult
LaboratoryReport
```

## Conversation Intelligence

```text
ImportSession
ImportSource
CanonicalizationRecord
KnowledgeObject
ConversationFinding
ExportPackage
```

The Domain Application determines:

* Aggregate boundaries.
* Transactional invariants.
* Entity ownership.
* Lifecycle.
* Relationships.
* Consistency rules.

Enterprise Core must not impose a universal business aggregate model.

---

# 11. DA-06 — Domain Catalogs & Reference Data

Domain-specific catalogs remain domain-owned.

Examples:

## Restaurant

```text
Menu
Product Catalog
Ingredients
Modifiers
Promotions
Preparation Areas
```

## Laboratory

```text
Test Methods
Analytes
Units
Regulatory Methods
Sampling Types
```

## Conversation Intelligence

```text
Supported Source Types
Import Formats
Knowledge Categories
Finding Types
```

Generic metadata or classification capabilities may be reused from Enterprise Core where appropriate.

---

# 12. DA-07 — Domain Actions & Commands

Domain Applications define the actions meaningful to their business.

Examples:

## Restaurant

```text
CreateOrder
AddOrderItem
CancelOrderItem
SubmitOrder
ReplaceOrderItem
RequestBill
```

## Laboratory

```text
RegisterSample
EnterResult
ValidateResult
ReviewReport
AuthorizeReport
```

## Conversation Intelligence

```text
StartImport
NormalizeConversation
SearchConversations
CreateFinding
GenerateExport
```

Enterprise Core may provide authorization, auditing, correlation and event mechanisms around these actions.

It does not own their business meaning.

---

# 13. DA-08 — Domain State Machines

Domain Applications own their business lifecycles.

Example:

```text
Restaurant Order Item

PENDING
   ↓
SUBMITTED
   ↓
IN_PREPARATION
   ↓
READY
   ↓
DELIVERED
```

Laboratory:

```text
Laboratory Report

DRAFT
   ↓
UNDER_REVIEW
   ↓
VALIDATED
   ↓
AUTHORIZED
   ↓
ISSUED
```

Conversation Intelligence:

```text
Import

CREATED
   ↓
PROCESSING
   ↓
NORMALIZING
   ↓
COMPLETED
```

Enterprise Core may provide lifecycle infrastructure.

The domain defines the actual states and transitions.

---

# 14. DA-09 — Domain Business Events

Enterprise Core may provide:

```text
BusinessEvent
```

Domain Applications define event semantics.

Examples:

## Restaurant

```text
ORDER_SUBMITTED
ORDER_ITEM_READY
ORDER_ITEM_DELIVERED
TABLE_OCCUPIED
```

## Laboratory

```text
SAMPLE_REGISTERED
RESULT_VALIDATED
REPORT_AUTHORIZED
REPORT_ISSUED
```

## Conversation Intelligence

```text
IMPORT_STARTED
IMPORT_COMPLETED
CONVERSATION_NORMALIZED
KNOWLEDGE_EXTRACTED
EXPORT_COMPLETED
```

Domain events may trigger reusable Core capabilities such as notifications, audit, workflows or analytics.

---

# 15. DA-10 — Domain Policies & Invariants

Business rules remain owned by the domain.

Examples:

## Restaurant

```text
Can an order item be cancelled?

Can two tables be joined?

Can an account be split?

Can a product be replaced?
```

## Laboratory

```text
Can this result be validated?

Can this report be authorized?

Is the required review complete?
```

## Conversation Intelligence

```text
Can this source be imported?

Can imported evidence be deleted?

Can two identities be linked?

Can this export include restricted content?
```

Enterprise Core may provide policy evaluation infrastructure.

The Domain Application defines the rule.

---

# 16. DA-11 — Domain Workflows & Protocols

Domain Applications own business procedures.

Examples:

## Restaurant

```text
Customer Complaint Protocol
Product Return Protocol
Cancellation Protocol
Payment Failure Protocol
```

## Laboratory

```text
Technical Review Protocol
Report Authorization Protocol
Result Correction Protocol
Nonconformity Protocol
```

## Conversation Intelligence

```text
Import Failure Protocol
Identity Conflict Resolution
Evidence Validation Protocol
Export Approval Protocol
```

A reusable workflow capability may execute these protocols.

The workflow definition remains domain-owned.

---

# 17. DA-12 — Domain Tasks & Assignments

Enterprise Core may provide generic:

```text
Task
Assignment
Assignee
Priority
Deadline
```

The Domain Application defines task semantics.

Examples:

```text
Restaurant:
Prepare product
Deliver product
Attend complaint
```

```text
Laboratory:
Perform analysis
Review result
Authorize report
```

```text
Conversation Intelligence:
Review import conflict
Review AI finding
Approve export
```

---

# 18. DA-13 — Domain Communication Semantics

Enterprise Core may provide:

```text
Conversation
Message
Notification
Acknowledgement
Response
```

The Domain Application determines why communication occurs.

Examples:

Restaurant:

```text
Product ready
Customer requires assistance
Complaint escalation
```

Laboratory:

```text
Result ready for review
Report ready for authorization
Customer notification
```

Conversation Intelligence:

```text
Import completed
Evidence issue detected
Export ready
AI finding requires review
```

Communication infrastructure remains generic.

Communication meaning remains domain-specific.

---

# 19. DA-14 — Domain Files & Evidence

Enterprise Core may provide:

```text
File
Evidence
Checksum
StorageReference
Provenance
```

Domain Applications define what the evidence represents.

Examples:

## Restaurant

```text
Receipt
Menu Image
Order Attachment
Complaint Evidence
```

## Laboratory

```text
Instrument Output
Result File
Report
Certificate
Supporting Evidence
```

## Conversation Intelligence

```text
Original Chat Export
ZIP Archive
Attachment
Original Database Export
Imported Media
```

Original evidence must remain distinguishable from normalized or derived information.

---

# 20. DA-15 — Domain Integrations

Domain Applications own product-specific integration contracts where the external system has domain meaning.

Examples:

## Restaurant

```text
POS Integration
Kitchen Display Integration
Reservation Integration
Delivery Integration
```

## Laboratory

```text
Instrument Integration
Regulatory System Integration
Customer Portal Integration
```

## Conversation Intelligence

```text
WhatsApp Import
Telegram Import
Slack Import
Teams Import
Email Import
```

Vendor implementations belong behind adapters.

Architecture:

```text
Domain Capability
       │
       ▼
Domain Port
       │
       ▼
Adapter
       │
       ▼
External System
```

---

# 21. DA-16 — Domain Search

Enterprise Core may provide search infrastructure.

Domain Applications define the search experience.

Examples:

## Restaurant

```text
Search orders
Search guests
Search reservations
Search incidents
```

## Laboratory

```text
Search samples
Search results
Search reports
Search customers
```

## Conversation Intelligence

```text
Search conversations
Search messages
Search participants
Search attachments
Search extracted knowledge
```

Domain search owns:

* Search semantics.
* Domain filters.
* Domain facets.
* Domain ranking.
* Result representation.
* Business permissions.

---

# 22. DA-17 — Domain Analytics & KPIs

Enterprise Core may provide generic operational measurements.

Domain Applications own business interpretation and KPIs.

## Restaurant

```text
Average preparation time
Average delivery time
Product return rate
Complaint rate
Sales per guest
Table turnover
```

## Laboratory

```text
Report TAT
Review time
Correction rate
Authorization time
Sample throughput
```

## Conversation Intelligence

```text
Conversation volume
Message volume
Participant activity
Source distribution
Topic frequency
Import success rate
Knowledge extraction coverage
```

Domain KPIs must not be promoted into Enterprise Core.

---

# 23. DA-18 — Domain Reporting & Export

Domain Applications define their deliverables.

Examples:

## Restaurant

```text
Operational Report
Sales Report
Service Report
Complaint Report
```

## Laboratory

```text
Test Report
Certificate
Operational Report
Quality Report
```

## Conversation Intelligence

```text
Conversation Export
Evidence Package
Search Export
Analytics Report
Knowledge Report
```

Enterprise Core may provide generic file, export or task infrastructure.

The product determines report meaning and content.

---

# 24. DA-19 — Domain Intelligence

Each Domain Application owns intelligence derived from its business information.

Generic transformation:

```text
DATA
  ↓
DOMAIN CONTEXT
  ↓
ANALYSIS
  ↓
FINDING
  ↓
INSIGHT
  ↓
RECOMMENDATION
```

Examples:

## Restaurant

```text
Service bottleneck detected
Repeated complaint pattern
Product profitability opportunity
Staff performance anomaly
```

## Laboratory

```text
Report bottleneck detected
Correction pattern
Instrument anomaly
Operational capacity issue
```

## Conversation Intelligence

```text
Recurring topic
Relationship pattern
Important historical event
Conversation anomaly
Emerging issue
Knowledge finding
```

These meanings remain domain-owned even when AI infrastructure is shared.

---

# 25. DA-20 — Domain AI & Agent Behavior

Enterprise Core may provide:

```text
Agent Identity
AI Execution Context
Tool Invocation
Policy Enforcement
Evidence Reference
Human Approval
Audit
```

The Domain Application defines what AI is allowed to understand and do.

Examples:

## Restaurant

```text
Recommend menu item
Create order request
Answer menu question
Detect complaint
Request waiter assistance
```

## Laboratory

```text
Assist report preparation
Detect inconsistencies
Summarize results
Suggest review priorities
```

## Conversation Intelligence

```text
Summarize conversation
Extract knowledge
Detect topics
Identify relationships
Answer questions over evidence
Generate findings
```

AI must invoke governed domain capabilities.

Forbidden:

```text
AI
 ↓
direct domain database mutation
```

Required:

```text
AI / Agent
     │
     ▼
Structured Domain Tool
     │
     ▼
Authorization / Policy
     │
     ▼
Domain Service
     │
     ▼
Business Action
     │
     ▼
Event + Audit
```

---

# 26. DA-21 — Domain UX / Application Experience

The Domain Application owns the user experience of the commercial product.

This includes:

```text
Navigation
Dashboards
Workspaces
Domain terminology
Domain forms
Domain actions
Domain-specific alerts
Domain workflows
Domain visualizations
```

Enterprise Core may expose reusable APIs and UI-neutral contracts.

The Core must not dictate the final product UX.

---

# 27. DA-22 — Domain Administration & Configuration

Domain Applications own business-specific configuration.

Examples:

## Restaurant

```text
Menu configuration
Preparation areas
Cancellation rules
Service policies
```

## Laboratory

```text
Test methods
Report rules
Authorization workflows
Laboratory-specific parameters
```

## Conversation Intelligence

```text
Import policies
Source configuration
Retention behavior
Knowledge extraction configuration
Export policies
```

Enterprise Core owns generic configuration mechanisms.

The domain owns configuration semantics.

---

# 28. Formal Core-to-Domain Mapping

The generic relationship is:

| Enterprise Core     | Domain Application Responsibility |
| ------------------- | --------------------------------- |
| Identity            | Domain roles and business meaning |
| Tenant              | Tenant-specific domain ownership  |
| Organization        | Business organizational meaning   |
| Location            | Domain operating location         |
| Resource            | Concrete domain resource          |
| Participant         | Domain participant role           |
| Interaction Session | Domain session                    |
| Conversation        | Domain communication semantics    |
| Message             | Domain interpretation             |
| Notification        | Domain notification reason        |
| Business Event      | Domain event type                 |
| Workflow            | Domain workflow definition        |
| Task                | Domain task meaning               |
| Lifecycle           | Domain states and transitions     |
| Policy              | Domain business rule              |
| History             | Domain historical interpretation  |
| Audit               | Domain audit context              |
| File/Evidence       | Domain evidence meaning           |
| Search              | Domain search experience          |
| Metadata            | Domain classification             |
| Payment             | Domain financial reason           |
| Integration         | Domain external system            |
| Analytics           | Domain KPI                        |
| AI Enablement       | Domain AI capability              |

---

# 29. Restaurant Intelligence Platform Capability Map

The Restaurant Domain may contain:

```text
RESTAURANT INTELLIGENCE PLATFORM
│
├── Guest Management
├── Dining Sessions
├── Table Management
├── Menu Management
├── Product Availability
├── Modifiers & Preparation Instructions
├── Buffets
├── Combos / Packages
├── Promotions
├── Orders
├── Order Items
├── Production Routing
├── Preparation
├── Product Delivery
├── Returns
├── Replacements / Remakes
├── Restaurant Accounts
├── Consumption Assignment
├── Bill Splitting
├── Reservations
├── Customer Service Requests
├── Complaints
├── Compliments / Feedback
├── Restaurant Payments
├── Restaurant Protocols
├── Restaurant Analytics
├── Restaurant Intelligence
└── Digital Waiter
```

These capabilities belong to the Restaurant Domain, not Enterprise Core.

---

# 30. Restaurant Operational Flow

A representative flow is:

```text
Guest
  │
  ▼
Dining Session
  │
  ▼
Conversation
  │
  ▼
Menu Interaction
  │
  ▼
Order
  │
  ▼
Order Item
  │
  ▼
Production
  │
  ▼
Ready Event
  │
  ▼
Waiter Notification
  │
  ▼
Acknowledgement
  │
  ▼
Delivery
  │
  ▼
Account
  │
  ▼
Payment
```

Some mechanisms are supplied by Enterprise Core.

The business flow remains Restaurant-owned.

---

# 31. Laboratory / LIMS Capability Map

The Laboratory Domain may contain:

```text
LABORATORY / LIMS
│
├── Customer Management
├── Service Requests
├── Quotations
├── Laboratory Orders
├── Sampling
├── Sample Management
├── Chain of Custody
├── Test Methods
├── Analytes
├── Analysis Execution
├── Instrument Interaction
├── Result Management
├── Quality Control
├── Result Validation
├── Technical Review
├── Report Preparation
├── Report Authorization
├── Report Issuance
├── Corrections / Amendments
├── Regulatory Requirements
├── Laboratory Analytics
└── Laboratory Intelligence
```

These remain Laboratory-owned even when they reuse Core capabilities.

---

# 32. Laboratory Operational Flow

Representative flow:

```text
Customer
   │
   ▼
Service Request
   │
   ▼
Quotation
   │
   ▼
Order
   │
   ▼
Sample
   │
   ▼
Analysis
   │
   ▼
Result
   │
   ▼
Validation
   │
   ▼
Technical Review
   │
   ▼
Report
   │
   ▼
Authorization
   │
   ▼
Issuance
```

Core may support identity, events, tasks, workflow, notifications, evidence, audit and analytics.

The laboratory semantics remain entirely Domain-owned.

---

# 33. Conversation Intelligence Platform Capability Map

The Conversation Intelligence Domain is defined at the highest level as:

```text
CONVERSATION INTELLIGENCE PLATFORM
│
├── Source Management
├── Import Management
├── Import Validation
├── Evidence Preservation
├── Source Parsing
├── Canonicalization
├── Conversation Reconstruction
├── Participant Resolution
├── Conversation Explorer
├── Conversation Search
├── Conversation Classification
├── Conversation Analytics
├── Knowledge Extraction
├── Knowledge Objects
├── Findings
├── Relationship Intelligence
├── Temporal Intelligence
├── AI-assisted Analysis
├── Evidence-backed Q&A
├── Export Management
└── Conversation Intelligence Reporting
```

This is the Domain Application currently governed by this project.

---

# 34. Conversation Intelligence Data Flow

The canonical product flow is:

```text
SOURCE
   │
   ▼
IMPORT
   │
   ▼
ORIGINAL EVIDENCE
   │
   ▼
PARSING
   │
   ▼
NORMALIZATION
   │
   ▼
CANONICAL CONVERSATION
   │
   ▼
INDEXING
   │
   ├─────────────┐
   ▼             ▼
SEARCH        ANALYTICS
   │             │
   └──────┬──────┘
          ▼
    KNOWLEDGE EXTRACTION
          │
          ▼
       FINDINGS
          │
          ▼
      INTELLIGENCE
          │
          ▼
       EXPORT / AI
```

This flow is Domain-owned.

Enterprise Core supplies reusable capabilities underneath it.

---

# 35. Source Management

**Conversation Intelligence Domain**

Represents the origin from which conversational information is acquired.

Possible concepts:

```text
ImportSource
SourceType
SourceAccount
SourceConfiguration
SourceCapability
```

Examples of source types:

```text
WhatsApp Export
Telegram Export
Slack Export
Teams Export
Email
Future Sources
```

The Domain owns source semantics.

Enterprise Core Integration Foundation may provide generic connector infrastructure.

---

# 36. Import Management

**Conversation Intelligence Domain**

Responsible for controlled ingestion.

Potential concepts:

```text
ImportSession
ImportJob
ImportBatch
ImportStatus
ImportError
ImportStatistics
```

Responsibilities:

* Initiate imports.
* Validate input.
* Track progress.
* Preserve provenance.
* Handle failures.
* Support idempotency.
* Produce import evidence.
* Record import statistics.

Import is a Conversation Intelligence business capability, not a generic Enterprise Core entity.

---

# 37. Evidence Preservation

Conversation Intelligence consumes the Core File & Evidence Foundation but defines product-specific evidence requirements.

The relationship is:

```text
Original Export
      │
      ▼
Core Evidence
      │
      +
Conversation Intelligence Provenance
```

The original source must remain distinguishable from all transformations.

---

# 38. Source Parsing

Each supported source may require a specialized parser.

Examples:

```text
WhatsApp TXT Parser
WhatsApp ZIP Parser
Telegram Parser
Slack Parser
Teams Parser
```

These belong to the Conversation Intelligence Domain/integration layer.

They must never enter Enterprise Core.

---

# 39. Canonicalization

Canonicalization transforms source-specific representations into the canonical conversational representation.

Architecture:

```text
Source Record
      │
      ▼
Source Parser
      │
      ▼
Intermediate Representation
      │
      ▼
Canonicalization
      │
      ▼
Canonical Conversation Model
```

Canonicalization must preserve:

```text
Source identity
Original timestamps
Participants
Message ordering
Attachments
Source references
Transformation provenance
```

where available.

---

# 40. Conversation Reconstruction

Some imported sources may not explicitly provide complete conversation boundaries.

The domain may therefore need to reconstruct:

```text
Conversation
Participants
Message sequence
Threads
Replies
Temporal relationships
```

Any inferred reconstruction must remain distinguishable from explicit source facts when materially relevant.

---

# 41. Participant Resolution

Conversation Intelligence may consume the Core Participant & Identity Resolution capability.

The Domain Application determines when source identities may represent the same participant.

Conceptually:

```text
WhatsApp Identity ─┐
Email Identity ────┼──► Participant
Slack Identity ────┘
```

Automatic merging must be conservative.

Evidence and confidence should be retained for inferred matches where applicable.

---

# 42. Conversation Explorer

The Conversation Explorer is a product capability for navigating canonical conversational information.

It may provide:

```text
Conversation list
Conversation timeline
Participants
Messages
Attachments
Threads
Source provenance
Filters
Context navigation
Evidence inspection
```

This belongs to the Conversation Intelligence Domain UX.

---

# 43. Conversation Search

Search is a primary differentiator of the product.

The Domain Application may expose:

```text
Full-text search
Participant search
Date/time search
Source search
Attachment search
Conversation search
Metadata search
Advanced filters
Combined filters
Saved searches
```

Later capabilities may include semantic search where product value justifies it.

---

# 44. Conversation Classification

The domain may classify conversational information using:

```text
Tags
Topics
Categories
Entities
Relationship types
Importance
Custom classifications
```

Core metadata infrastructure may be reused.

Classification meaning remains Conversation Intelligence-owned.

---

# 45. Conversation Analytics

Domain analytics may include:

```text
Conversation volume
Message volume
Activity over time
Participant activity
Source distribution
Conversation duration
Temporal patterns
Topic frequency
Attachment distribution
Import quality
```

Analytics must be designed to answer useful product questions rather than merely display available data.

---

# 46. Knowledge Extraction

A central Conversation Intelligence capability.

Conceptually:

```text
Conversation Evidence
        │
        ▼
Interpretation
        │
        ▼
Knowledge Extraction
        │
        ▼
Knowledge Object
```

Potential extracted knowledge may include:

```text
Fact
Decision
Commitment
Preference
Event
Relationship
Topic
Issue
Action Item
Agreement
Disagreement
Question
Answer
```

The exact knowledge model requires dedicated domain design.

---

# 47. Knowledge Objects

A Knowledge Object represents structured knowledge derived from conversational evidence.

Conceptually:

```text
KnowledgeObject
│
├── type
├── statement
├── participants
├── temporal context
├── evidence references
├── provenance
├── confidence
└── status
```

A Knowledge Object must remain distinguishable from the original message or source evidence.

---

# 48. Findings

A Finding represents an analytically significant conclusion or observation.

Potential examples:

```text
Recurring issue
Important historical event
Relationship pattern
Contradiction
Emerging topic
Unresolved commitment
Anomaly
```

A Finding should reference supporting evidence.

---

# 49. Relationship Intelligence

The platform may derive relationships between:

```text
Participants
Conversations
Topics
Events
Knowledge Objects
Organizations
```

Potential representations:

```text
Participant A
    │
    ├── communicates with
    ├── mentions
    ├── agrees with
    └── participates with
          │
          ▼
Participant B
```

Not all relationships should be inferred automatically.

Confidence and evidence are required where interpretation is probabilistic.

---

# 50. Temporal Intelligence

Conversation Intelligence should preserve and analyze time as a first-class dimension.

Potential capabilities:

```text
Conversation timelines
Event timelines
Participant activity timelines
Topic evolution
Relationship evolution
Historical reconstruction
```

This supports questions such as:

```text
What happened first?

When did this topic begin?

How did this decision evolve?

When did a participant become involved?
```

---

# 51. Evidence-Backed Intelligence

A fundamental product rule should be:

> **Derived intelligence must remain traceable to supporting conversational evidence whenever practical.**

Architecture:

```text
Insight
   │
   ▼
Finding
   │
   ▼
Knowledge Object
   │
   ▼
Message / File
   │
   ▼
Original Evidence
```

This traceability significantly increases trust in AI-generated results.

---

# 52. Evidence-Backed Q&A

Future AI capabilities should support questions over conversational knowledge.

Architecture:

```text
User Question
      │
      ▼
Authorized Retrieval
      │
      ▼
Relevant Evidence
      │
      ▼
AI Reasoning
      │
      ▼
Answer
      │
      ▼
Evidence References
```

Answers should distinguish:

```text
Explicit source fact

Derived conclusion

Uncertain inference
```

where relevant.

---

# 53. Export Management

Conversation Intelligence owns export semantics.

Possible export targets:

```text
Conversation
Search Results
Selected Messages
Analytics
Knowledge Objects
Findings
Evidence Package
```

Potential formats may include:

```text
PDF
CSV
XLSX
JSON
HTML
```

depending on product requirements.

Export authorization must respect tenant and data-access boundaries.

---

# 54. Domain AI Safety Boundary

AI may interpret domain information but may not redefine historical evidence.

Forbidden:

```text
AI-generated summary
      ↓
replaces original conversation
```

Required:

```text
Original Conversation
      │
      ├── preserved
      │
      └── supports
             │
             ▼
        AI Summary
```

The same applies to:

```text
Findings
Knowledge Objects
Classifications
Recommendations
```

---

# 55. Domain Data Ownership

Each Domain Application owns its domain persistence.

Conceptually:

```text
Enterprise Core Tables
        │
        │ referenced by
        ▼
Domain Tables
```

Core must not directly manipulate domain-owned tables.

Domains must not bypass Core services when modifying Core-owned state.

---

# 56. Cross-Domain Isolation

Domain Applications must not directly depend on each other's internal models.

Forbidden:

```text
Restaurant → Laboratory

Laboratory → Conversation Intelligence

Conversation Intelligence → Restaurant
```

If capabilities need to be shared, evaluate whether:

```text
A. Enterprise Core already owns the abstraction.

B. A reusable optional capability should be extracted.

C. An explicit integration contract is required.
```

Do not create hidden cross-domain coupling.

---

# 57. Domain Integration Rule

A Domain Application may integrate with another product through explicit contracts.

Example:

```text
Domain A
   │
   ▼
Integration Contract
   │
   ▼
Domain B
```

This does not make Domain B's internal entities part of Domain A.

---

# 58. Domain Configuration Rule

Domain Applications own business configuration.

Enterprise Core owns generic configuration mechanics.

Correct:

```text
Core:
Configuration resolution
```

```text
Restaurant:
Cancellation policy configuration
```

Incorrect:

```text
Core:
restaurant_cancellation_minutes
```

---

# 59. Domain Security Rule

Every Domain Application must consume the Core security context.

At minimum, relevant business actions should preserve:

```text
tenant
actor
authorization
correlation
audit
```

The Domain Application may impose stricter business restrictions.

It may never weaken Core tenant or security boundaries.

---

# 60. Domain Audit Rule

Domain operations requiring traceability should use Core audit mechanisms where appropriate.

The domain provides business context.

Core provides consistent audit infrastructure.

Example:

```text
Domain:

CancelOrderItem
      │
      ▼
Business Event
      +
Audit Record
```

---

# 61. Domain Event Rule

A Domain Application may publish domain events.

Core capabilities may react to them without understanding their full business meaning.

Example:

```text
DOMAIN EVENT
     │
     ├── Notification
     ├── Analytics
     ├── Audit
     └── Workflow
```

Events must not become a mechanism for bypassing domain invariants.

Only validated domain actions should produce authoritative domain events.

---

# 62. Domain Transaction Rule

Business invariants should be enforced inside the transaction boundary of the owning domain where practical.

Do not split transactions merely because multiple logical modules participate.

The modular monolith remains the default architecture.

---

# 63. Domain Modular Monolith Rule

Domain boundaries are logical module boundaries.

They do not imply separate deployments.

Preferred initial architecture:

```text
application/
│
├── enterprise_core/
│
├── domains/
│   │
│   ├── conversation_intelligence/
│   ├── restaurant/
│   └── laboratory/
│
└── infrastructure/
```

A commercial product does not necessarily deploy all domains.

The structure represents architectural capability ownership, not mandatory runtime composition.

---

# 64. Domain Extraction Rule

A capability initially implemented in a Domain Application may later become Enterprise Core.

The extraction path is:

```text
Domain Requirement
      │
      ▼
Domain Implementation
      │
      ▼
Reusable Pattern Proven
      │
      ▼
Boundary Review
      │
      ▼
Generic Contract
      │
      ▼
Enterprise Core
```

The original domain must then consume the extracted Core capability rather than maintain duplicate logic.

---

# 65. No Premature Generalization Rule

Do not generalize a domain capability because another future product might theoretically need it.

Example:

```text
Restaurant Order
```

must not become:

```text
EnterpriseOrder
```

merely because another industry may also use the word "order".

Reuse must be semantic.

---

# 66. Domain Product Value Rule

Domain development exists to deliver customer value.

Architecture should therefore prioritize:

```text
Customer Value
      ↓
Production Readiness
      ↓
Commercial Viability
      ↓
Clean Architecture
      ↓
Security
      ↓
Scalability
      ↓
Performance
      ↓
Maintainability
      ↓
Future Intelligence
```

Clean architecture must support delivery, not prevent it.

---

# 67. Domain Capability Admission Rule

A capability belongs in a Domain Application when one or more of the following are true:

1. Its meaning depends on the vertical.
2. Its invariants depend on vertical business rules.
3. Its lifecycle is domain-specific.
4. Its terminology is domain-specific.
5. Its value proposition belongs to the commercial product.
6. Its analytics require domain interpretation.
7. Its AI behavior requires domain knowledge.
8. Generalizing it would create artificial abstractions.

---

# 68. Domain Capability Success Criteria

A well-designed Domain Application should:

1. Express business concepts clearly.
2. Use the language of its users.
3. Protect its own invariants.
4. Reuse Enterprise Core without contaminating it.
5. Avoid duplicating Core capabilities.
6. Remain independently evolvable.
7. Hide vendor-specific implementation.
8. Preserve tenant and security boundaries.
9. Generate meaningful business events.
10. Produce useful operational data.
11. Support future intelligence.
12. Remain simple enough to deliver quickly.

---

# 69. Enterprise Core vs Domain Application Decision Test

For every proposed capability ask:

```text
Does it describe WHAT THE BUSINESS IS OR DOES?
                 │
                 ├── YES
                 │
                 ▼
          DOMAIN APPLICATION

                 OR

Does it provide a reusable mechanism used
across different businesses?
                 │
                 ├── YES
                 │
                 ▼
           ENTERPRISE CORE
```

When uncertain:

> **Keep the concept in the Domain Application until reuse is demonstrated.**

---

# 70. Three-Layer Ownership Model

The architecture must distinguish:

```text
BUSINESS MEANING
      │
      ▼
DOMAIN APPLICATION

REUSABLE ENTERPRISE CAPABILITY
      │
      ▼
ENTERPRISE CORE

TECHNICAL IMPLEMENTATION
      │
      ▼
INFRASTRUCTURE / ADAPTER
```

Example:

```text
Restaurant Payment
        │
        │ business meaning
        ▼
Payment
        │
        │ reusable capability
        ▼
PaymentGatewayPort
        │
        │ technical integration
        ▼
ConektaAdapter
```

Another example:

```text
WhatsApp Conversation Import
        │
        │ product meaning
        ▼
Conversation Import
        │
        │ domain capability
        ▼
Integration / Evidence Core
        │
        │ reusable foundation
        ▼
WhatsApp Parser / Adapter
```

---

# 71. Domain Application Boundary

The formal boundary is:

```text
┌──────────────────────────────────────────────────────────────┐
│                     DOMAIN APPLICATION                       │
│                                                              │
│ Business Entities                                            │
│ Business Aggregates                                          │
│ Business Rules                                               │
│ Business Policies                                            │
│ Business Workflows                                           │
│ Business State Machines                                      │
│ Business Events                                              │
│ Business Analytics                                           │
│ Product Intelligence                                         │
│ Domain AI Behavior                                           │
│ Product UX                                                   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            │ consumes
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                       ENTERPRISE CORE                        │
│                                                              │
│ Identity │ Tenant │ Participant │ Conversation │ Events       │
│ Tasks │ Messaging │ Policies │ Evidence │ Audit │ Search      │
│ Integration │ Security │ Analytics Foundation │ AI Governance │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            │ implemented through
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                       INFRASTRUCTURE                          │
│                                                              │
│ MySQL │ S3/MinIO │ External Systems │ Providers │ Monitoring │
└──────────────────────────────────────────────────────────────┘
```

---

# 72. Relationship With Enterprise Core Documents

This document must be interpreted together with:

```text
ENTERPRISE_CORE_CAPABILITY_MAP.md
```

and:

```text
ENTERPRISE_CORE_BOUNDARY_RULES.md
```

Their responsibilities are intentionally different.

```text
ENTERPRISE_CORE_CAPABILITY_MAP.md
        │
        └── Defines WHAT the Core owns.


ENTERPRISE_CORE_BOUNDARY_RULES.md
        │
        └── Defines HOW the Core boundary is protected.


DOMAIN_APPLICATION_CAPABILITY_MAP.md
        │
        └── Defines WHAT Domain Applications own
            and HOW they consume the Core.
```

Together they establish:

```text
CORE OWNERSHIP
      +
BOUNDARY GOVERNANCE
      +
DOMAIN OWNERSHIP
```

---

# 73. Architectural Authority

When deciding where a new capability belongs, the decision order is:

```text
1. Determine its business meaning.

2. Determine who owns its invariants.

3. Apply ENTERPRISE_CORE_BOUNDARY_RULES.md.

4. Compare against ENTERPRISE_CORE_CAPABILITY_MAP.md.

5. Classify as:

   CORE
   OPTIONAL REUSABLE CORE
   DOMAIN APPLICATION
   TECHNICAL SHARED LIBRARY

6. Implement only the minimum capability required
   by the active product.
```

---

# 74. Current Project Application

For the current **Conversation Intelligence Platform**, the governing architecture is:

```text
CONVERSATION INTELLIGENCE PLATFORM
                │
                │ Domain Application
                ▼
         ENTERPRISE CORE
                │
                ▼
          INFRASTRUCTURE
```

Therefore, implementation should not begin by building every capability listed in Enterprise Core.

Instead:

```text
Conversation Intelligence requirement
                │
                ▼
Does existing Core support it?
        │
        ├── YES
        │     ↓
        │   REUSE
        │
        └── NO
              ↓
        Is missing capability
        genuinely Core?
              │
          ┌───┴────┐
          │        │
         YES       NO
          │        │
          ▼        ▼
      Minimal    Implement in
      Core       Conversation
      Extension  Intelligence Domain
```

This preserves both development speed and long-term architectural integrity.

---

# 75. Final Architectural Definition

A Domain Application is formally defined as:

> **The business-semantic layer of a commercial product that owns vertical entities, aggregates, rules, policies, workflows, state machines, events, analytics, intelligence, AI behavior and user experience while consuming reusable enterprise capabilities from the Enterprise Core through governed architectural boundaries.**

The fundamental relationship remains:

```text
ENTERPRISE CORE
        +
DOMAIN APPLICATION
        =
BUSINESS CAPABILITY
```

while:

```text
BUSINESS CAPABILITY
        +
INFRASTRUCTURE
        +
PRODUCT EXPERIENCE
        +
DEPLOYMENT CONFIGURATION
        =
COMMERCIAL PRODUCT
```

---

# 76. Governing Decision

`DOMAIN_APPLICATION_CAPABILITY_MAP.md` is the authoritative document for defining the architectural ownership of Domain Applications built on the Enterprise Core.

It establishes:

```text
WHAT belongs to Domain Applications.

WHAT remains Enterprise Core.

HOW domains consume Core.

HOW domains specialize reusable capabilities.

HOW domain invariants remain protected.

HOW domain events interact with Core.

HOW product-specific AI remains governed.

HOW capabilities may later be extracted into Core.

HOW vertical products remain independent.
```

The permanent governing dependency remains:

```text
DOMAIN → CORE        ALLOWED

CORE → DOMAIN        FORBIDDEN

DOMAIN A → DOMAIN B  FORBIDDEN BY DEFAULT
```

The permanent implementation principle is:

> **Build business semantics in the Domain. Extract reusable mechanisms into the Core only when reuse is justified.**

---

**END OF DOCUMENT**
