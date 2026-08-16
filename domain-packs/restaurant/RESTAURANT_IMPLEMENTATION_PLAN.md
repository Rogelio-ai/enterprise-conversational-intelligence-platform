# RESTAURANT_IMPLEMENTATION_PLAN.md

**Document ID:** RIP-IMPL-001  
**Document Name:** Restaurant Implementation Plan  
**Product:** Restaurant Intelligence Platform  
**Platform:** Enterprise Conversational Intelligence Platform (ECIP)  
**Repository:** pryecip  
**Version:** 1.0.0  
**Status:** ACTIVE  
**Document Type:** Implementation Plan  
**Authority:** PRODUCT_CONSTITUTION.md  
**Domain Authority:** RESTAURANT_DOMAIN_MODEL.md  
**MVP Scope Authority:** RESTAURANT_MVP_PRODUCTION_SCOPE.md  
**Governance Authority:** Enterprise Audit Framework  

---

# 1. PURPOSE

This document defines the implementation plan for the first production-capable version of the Restaurant Intelligence Platform.

Its purpose is to translate:

RESTAURANT_DOMAIN_MODEL.md

and:

RESTAURANT_MVP_PRODUCTION_SCOPE.md

into:

IMPLEMENTATION WORK

The plan defines:

WHAT SHALL BE IMPLEMENTED

IN WHAT ORDER

WITH WHICH DEPENDENCIES

USING WHICH REUSABLE CAPABILITIES

WITH WHICH TESTS

WITH WHICH RELEASE GATES

The objective is to move directly from domain design into controlled implementation without opening a new architecture-design phase.

---

# 2. PRIMARY IMPLEMENTATION OBJECTIVE

Implement the first production vertical slice:

CUSTOMER
    ↓
CONVERSATION
    ↓
CUSTOMER IDENTIFICATION
    ↓
INTENT
    ↓
MENU / PRODUCT
    ↓
AVAILABILITY
    ↓
PRICE
    ↓
RECOMMENDATION
    ↓
ORDER DRAFT
    ↓
CUSTOMER CONFIRMATION
    ↓
ORDER SUBMISSION
    ↓
EXISTING POS
    ↓
ORDER STATUS
    ↓
CUSTOMER HISTORY
    ↓
DOMAIN EVENTS
    ↓
INITIAL INTELLIGENCE

This flow is the primary implementation priority.

---

# 3. IMPLEMENTATION PRINCIPLE

From this point forward:

DOCUMENTATION SUPPORTS CODE.

CODE SUPPORTS CUSTOMER VALUE.

Do not introduce new architectural layers unless required by:

Production.

Security.

Integration.

Correctness.

Reliability.

A concrete implementation blocker.

---

# 4. GOVERNANCE

Implementation is governed by the existing Enterprise Audit Framework.

Priority order:

1. Runtime Preservation.
2. Ownership Preservation.
3. Context Preservation.
4. Certified Behavior Preservation.
5. Minimal Change.
6. Executable Fix.

No new governance framework shall be introduced.

---

# 5. PRODUCT PRIORITY

Implementation priority:

1. Customer Value.
2. Production Readiness.
3. Architecture Preservation.
4. Runtime Stability.
5. Security.
6. Performance.
7. Maintainability.
8. Innovation with measurable value.

---

# 6. IMPLEMENTATION STYLE

Use:

Small vertical increments.

Explicit module ownership.

Stable contracts.

Automated tests.

Incremental integration.

Production-capable code.

Avoid:

Large speculative refactors.

Premature microservices.

Premature event infrastructure.

Premature graph infrastructure.

Generic Rule Engines.

Universal plugin systems.

Unnecessary abstractions.

---

# 7. BASELINE ASSUMPTION

The implementation assumes:

Restaurant Domain Model v1.0 is frozen.

Restaurant MVP Production Scope v1.0 is approved.

Changes to these documents shall occur only if implementation reveals:

Contradiction.

Missing critical concept.

Security issue.

Integration incompatibility.

Production blocker.

---

# 8. REPOSITORY

Repository:

pryecip

The repository shall contain:

Reusable ECIP Core capabilities.

Restaurant Domain Pack.

Integration adapters.

Frontend.

Infrastructure.

Tests.

Operational documentation.

The exact physical layout may evolve while preserving logical boundaries.

---

# 9. TARGET LOGICAL ARCHITECTURE

Conceptually:

┌─────────────────────────────────────────────┐
│                  CHANNELS                   │
│                                             │
│ API │ Web Chat │ Voice │ Future Channels   │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│           CONVERSATIONAL RUNTIME            │
│                                             │
│ Conversation │ Intent │ Context │ AI        │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│           RESTAURANT DOMAIN PACK            │
│                                             │
│ Customer │ Menu │ Product │ Order │ Rules   │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│              INTEGRATION PORTS              │
│                                             │
│ POS │ Payment │ Voice │ Notifications       │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│             EXTERNAL SYSTEMS                │
└─────────────────────────────────────────────┘

Cross-cutting:

TENANCY

SECURITY

AUTHORIZATION

AUDIT

OBSERVABILITY

EVENTS

IDEMPOTENCY

---

# 10. IMPLEMENTATION WORKSTREAMS

The MVP shall be implemented through the following workstreams:

WS-00 — Repository and Runtime Baseline

WS-01 — Reuse Assessment

WS-02 — Multi-Tenant Core

WS-03 — Restaurant Foundation

WS-04 — POS Integration Contract

WS-05 — Mock POS Adapter

WS-06 — Real POS Adapter

WS-07 — Customer Foundation

WS-08 — Menu and Product Foundation

WS-09 — Pricing and Promotion Foundation

WS-10 — Conversation Foundation

WS-11 — Conversational Intelligence

WS-12 — Sales Recommendation Foundation

WS-13 — Order Draft

WS-14 — Order Submission

WS-15 — Order Status

WS-16 — Human Handoff

WS-17 — Domain Events

WS-18 — Relationships and History

WS-19 — Initial Intelligence

WS-20 — Frontend Workspace

WS-21 — Voice Integration

WS-22 — Security Hardening

WS-23 — Observability and Reliability

WS-24 — Production E2E Certification

WS-25 — Deployment and Release

---

# 11. WORKSTREAM ORDER

Recommended implementation order:

WS-00
    ↓
WS-01
    ↓
WS-02
    ↓
WS-03
    ↓
WS-04
    ↓
WS-05
    ↓
WS-07
    ↓
WS-08
    ↓
WS-09
    ↓
WS-10
    ↓
WS-11
    ↓
WS-12
    ↓
WS-13
    ↓
WS-14
    ↓
WS-15
    ↓
WS-16
    ↓
WS-17
    ↓
WS-18
    ↓
WS-19
    ↓
WS-20
    ↓
WS-06
    ↓
WS-21
    ↓
WS-22
    ↓
WS-23
    ↓
WS-24
    ↓
WS-25

The Real POS Adapter may begin earlier once the required POS information is available.

---

# 12. WS-00 — REPOSITORY AND RUNTIME BASELINE

Objective:

Create a clean production-capable runtime baseline for `pryecip`.

Required capabilities:

Repository structure.

Environment configuration.

Docker configuration.

Database connectivity.

Redis connectivity if required.

Application startup.

Health checks.

Structured logging.

Correlation IDs.

Testing foundation.

Database migrations.

Configuration validation.

---

# 13. WS-00 DELIVERABLES

Deliver:

Backend starts successfully.

Frontend starts successfully.

Database migration works.

Health endpoint works.

Logging works.

Tests can run locally.

Dockerized environment works.

Configuration is environment-driven.

No production secrets are committed.

---

# 14. WS-00 EXIT CRITERIA

Pass when:

Application can be started from documented commands.

Database can be initialized from scratch.

Tests execute reproducibly.

Health checks return expected status.

No critical runtime errors exist.

---

# 15. WS-01 — REUSE ASSESSMENT

Objective:

Identify reusable capabilities from the Mineral Intelligence SaaS and existing enterprise infrastructure.

Every candidate component shall be classified as:

REUSE_AS_IS

REUSE_WITH_CONFIGURATION

ADAPT

EXTRACT_GENERIC_CAPABILITY

DO_NOT_REUSE

---

# 16. WS-01 REUSE CANDIDATES

Evaluate:

Authentication.

JWT/session handling.

Tenant middleware.

Role/permission patterns.

API Gateway patterns.

MySQL configuration.

SQLAlchemy patterns.

Alembic migrations.

Redis.

Background workers.

Durable jobs.

Retry handling.

Idempotency.

Correlation IDs.

Structured logging.

Prometheus.

Grafana.

Docker Compose.

Nginx.

Health endpoints.

Error handling.

Frontend shell.

Responsive layout.

Testing infrastructure.

CI/CD.

---

# 17. WS-01 PROHIBITED REUSE

Do not import domain concepts such as:

AOI.

GIS Workspace.

Datasets.

Mineral Analysis.

Remote sensing.

Satellite processing.

Map layers.

Mineral targets.

Only reusable infrastructure patterns may be extracted.

---

# 18. WS-01 OUTPUT

Create an implementation matrix:

| Component | Decision | Source | Target | Notes |
|---|---|---|---|---|
| Authentication | REUSE | existing SaaS | ECIP Core | configure |
| Tenant context | REUSE | existing SaaS | ECIP Core | preserve |
| AOI module | DO_NOT_REUSE | Mineral | — | domain-specific |
| Redis worker | REUSE | existing SaaS | ECIP Core | adapt config |

This matrix may be maintained inside implementation tracking rather than requiring another large design document.

---

# 19. WS-02 — MULTI-TENANT CORE

Objective:

Establish Tenant, Organization, Location and authorization context.

Minimum entities:

Tenant.

Organization.

Location.

User.

Role.

Permission.

UserRole.

---

# 20. WS-02 REQUIRED BEHAVIOR

Every protected request shall resolve:

tenant_id

user_id

roles

permissions

location context where required

Cross-Tenant access shall be rejected.

Tenant identity shall be server-enforced.

---

# 21. WS-02 APIs

Initial API candidates:

POST /auth/login

GET /auth/me

GET /organizations

POST /organizations

GET /locations

POST /locations

GET /users

GET /roles

Exact routes may vary.

---

# 22. WS-02 TESTS

Required:

Authentication test.

Invalid authentication test.

Tenant isolation test.

Role access test.

Unauthorized action test.

Location context test.

---

# 23. WS-03 — RESTAURANT FOUNDATION

Objective:

Create Restaurant Organization and Location domain structures.

Minimum entities:

RestaurantOrganization.

RestaurantLocation.

RestaurantSettings.

ServiceMode.

---

# 24. WS-03 SERVICE MODES

Initial values:

TAKE_AWAY

Future:

DINE_IN

DELIVERY

EVENT

Do not implement future flows yet.

---

# 25. WS-03 RESTAURANT SETTINGS

Initial settings:

timezone

currency

default_location

supported_service_modes

default_order_confirmation_policy

escalation_destination

AI behavior configuration

POS integration reference

---

# 26. WS-03 EXIT CRITERIA

A Tenant Administrator can configure:

Restaurant Organization.

Location.

Supported service mode.

Basic integration settings.

---

# 27. WS-04 — POS INTEGRATION CONTRACT

Objective:

Define the canonical boundary between Restaurant Domain and the existing POS.

Implement interfaces before vendor-specific code.

---

# 28. WS-04 POS PORTS

Minimum logical interfaces:

LocationPort

CustomerPort

CatalogPort

PricingPort

PromotionPort

OrderPort

OrderStatusPort

PaymentPort where necessary

---

# 29. WS-04 EXAMPLE CONTRACT

Conceptual:

interface OrderPort:

create_order(command)

get_order(order_id)

get_order_status(order_id)

cancel_order(order_id)

Exact programming language design may vary.

---

# 30. WS-04 CANONICAL DTOs

Define canonical DTOs for:

ExternalLocation.

ExternalCustomer.

ExternalProduct.

ExternalPrice.

ExternalPromotion.

ExternalOrder.

ExternalOrderItem.

ExternalOrderStatus.

---

# 31. WS-04 ANTI-CORRUPTION REQUIREMENT

No Restaurant Domain service shall depend on:

POS table names.

Vendor-specific status integers.

Vendor-specific field names.

Vendor-specific API payloads.

These belong inside the adapter.

---

# 32. WS-05 — MOCK POS ADAPTER

Objective:

Allow full MVP development without depending on live POS access.

The Mock POS shall implement the same interfaces as the Real POS Adapter.

---

# 33. WS-05 DATA

Mock POS seed:

1–2 Locations.

20–50 Products.

Categories.

Prices.

Promotions.

Customers.

Orders.

Order states.

---

# 34. WS-05 FAILURE MODES

Mock adapter must support simulated:

POS unavailable.

Product unavailable.

Order rejected.

Order timeout.

Duplicate submission.

Slow response.

Unknown Product.

This is essential for resilience testing.

---

# 35. WS-06 — REAL POS ADAPTER

Objective:

Integrate the actual Restaurant POS after technical discovery.

Required input:

Database schema or API specification.

Authentication.

Relevant tables.

Status catalogs.

Write-operation behavior.

Transaction behavior.

---

# 36. WS-06 MAPPING

Implement:

POS Customer
    ↔
Canonical Customer

POS Product
    ↔
Restaurant Product

POS Price
    ↔
Canonical Price

POS Ticket
    ↔
Restaurant Order

POS Order State
    ↔
Canonical Order State

---

# 37. WS-06 READ OPERATIONS

Prioritize:

Locations.

Products.

Prices.

Promotions.

Customers.

Order lookup.

Order status.

---

# 38. WS-06 WRITE OPERATIONS

Prioritize only required writes:

Customer creation if necessary.

Order creation.

Order cancellation if supported.

Do not enable broad POS write access.

---

# 39. WS-06 EXIT CRITERIA

The primary E2E flow must execute against the real POS.

No mock-only MVP release.

---

# 40. WS-07 — CUSTOMER FOUNDATION

Objective:

Create canonical Customer capability independent from POS-specific identity.

Minimum entities:

Customer.

CustomerExternalIdentity.

CustomerContact.

CustomerPreference.

CustomerHistoryEntry.

---

# 41. WS-07 CUSTOMER IDENTITY

Support identifiers:

Phone.

Email.

External POS ID.

Conversation Channel ID.

---

# 42. WS-07 MATCHING

Initial matching may use deterministic rules.

Example:

Verified external ID.

Exact normalized phone.

Exact known email.

Do not implement advanced probabilistic identity matching unless required.

---

# 43. WS-07 CUSTOMER APIs

Candidates:

GET /customers

GET /customers/{id}

POST /customers

PATCH /customers/{id}

GET /customers/{id}/history

GET /customers/{id}/preferences

---

# 44. WS-07 TESTS

Required:

Create Customer.

Find by phone.

External ID mapping.

Duplicate prevention.

Ambiguous identity handling.

Tenant isolation.

---

# 45. WS-08 — MENU AND PRODUCT FOUNDATION

Objective:

Allow Restaurant Intelligence to retrieve valid Menu and Product information.

Minimum entities:

Menu.

MenuSection.

Product.

ProductCategory.

ProductExternalMapping.

ProductAvailability.

---

# 46. WS-08 DATA AUTHORITY

For MVP, the POS may remain authoritative for:

Product existence.

Product status.

Product Price.

Basic Product availability.

ECIP may cache/normalize this information as permitted.

---

# 47. WS-08 APIs

Candidates:

GET /menus

GET /menus/{id}

GET /products

GET /products/{id}

GET /products/search

GET /products/{id}/availability

---

# 48. WS-08 SEARCH

Initial search should support:

Product name.

Category.

Keywords.

Simple fuzzy matching if needed.

Do not require vector search for MVP.

---

# 49. WS-09 — PRICING AND PROMOTIONS

Objective:

Resolve the authoritative commercial offer.

Minimum capabilities:

Current Price.

Currency.

Applicable Location.

Applicable service mode.

Basic Promotion.

---

# 50. WS-09 PRICE RULE

Never calculate or invent a commercial Price outside approved pricing logic.

If POS is authoritative:

Use POS Price.

If ECIP stores normalized Price:

Preserve source and synchronization state.

---

# 51. WS-09 PROMOTIONS

Initial Promotion support:

Percentage.

Fixed amount.

Simple bundle.

Promotion metadata.

If the POS calculates Promotions authoritatively, ECIP should not duplicate calculation unnecessarily.

---

# 52. WS-10 — CONVERSATION FOUNDATION

Objective:

Create a Channel-independent Conversation domain.

Minimum entities:

Conversation.

ConversationSession.

Participant.

Message.

ConversationContext.

ConversationReference.

---

# 53. WS-10 CONVERSATION STATES

Initial:

ACTIVE

WAITING

ESCALATED

RESOLVED

CLOSED

ABANDONED

---

# 54. WS-10 PARTICIPANTS

Initial actor types:

CUSTOMER

AI

EMPLOYEE

SYSTEM

---

# 55. WS-10 MESSAGE TYPES

Initial:

TEXT

SYSTEM_EVENT

Future:

VOICE_TRANSCRIPT

AUDIO

IMAGE

DOCUMENT

---

# 56. WS-10 APIs

Candidates:

POST /conversations

GET /conversations/{id}

POST /conversations/{id}/messages

GET /conversations/{id}/messages

POST /conversations/{id}/close

---

# 57. WS-10 CONTEXT

Conversation Context should preserve references such as:

customer_id

location_id

current_intent

current_product_id

current_order_id

pending_question

last_action

Do not persist opaque unlimited AI context as domain truth.

---

# 58. WS-11 — CONVERSATIONAL INTELLIGENCE

Objective:

Interpret Customer language and determine the next valid business action.

Logical responsibilities:

Intent Detection.

Entity Resolution.

Context Assembly.

Clarification.

Tool Selection.

Response Composition.

---

# 59. WS-11 INITIAL INTENTS

Implement:

GREETING

MENU_QUERY

PRODUCT_QUERY

PRODUCT_AVAILABILITY

PRICE_QUERY

PROMOTION_QUERY

PRODUCT_RECOMMENDATION

CREATE_ORDER

MODIFY_ORDER

CONFIRM_ORDER

ORDER_STATUS

CANCEL_ORDER

COMPLAINT

HUMAN_ASSISTANCE

UNKNOWN

---

# 60. WS-11 ENTITY TYPES

Initial:

PRODUCT

QUANTITY

MODIFIER

LOCATION

TIME

CUSTOMER

ORDER

PROMOTION

---

# 61. WS-11 AI ORCHESTRATION

AI shall interact with Restaurant domains through tools/services.

Logical flow:

MESSAGE
    ↓
INTENT / ENTITIES
    ↓
CONTEXT
    ↓
TOOL CALL
    ↓
DOMAIN RESULT
    ↓
RESPONSE

---

# 62. WS-11 DETERMINISTIC VALIDATION

AI output shall be validated before material business actions.

Example:

AI extracts:

quantity = 2

product = Burger

Domain validates:

Product exists.

Quantity valid.

Product sellable.

---

# 63. WS-11 UNKNOWN HANDLING

If intent remains unclear:

ASK CLARIFICATION.

Do not invent.

---

# 64. WS-11 TESTS

Required:

Intent recognition.

Multi-turn context.

Ambiguous Product.

Missing quantity.

Product not found.

Product unavailable.

Price unknown.

Human escalation.

AI provider failure.

---

# 65. WS-12 — SALES RECOMMENDATION FOUNDATION

Objective:

Provide useful cross-sell and upsell without building a complex recommendation engine.

Initial inputs:

Current Order.

Product category.

Known Preferences.

Simple Product affinity configuration.

Active Promotions.

Availability.

---

# 66. WS-12 RECOMMENDATION STRATEGY

Initial strategy may use deterministic rules.

Example:

Burger
    → Fries
    → Beverage

Pizza
    → Beverage
    → Dessert

Do not require machine learning for MVP.

---

# 67. WS-12 RECOMMENDATION RECORD

Capture:

recommendation_id

conversation_id

customer_id

product_id

reason

presented_at

accepted

resulting_order_item_id

This enables future Sales Intelligence.

---

# 68. WS-13 — ORDER DRAFT

Objective:

Create a canonical Order Draft before authoritative POS submission.

Minimum entities:

OrderDraft.

OrderDraftItem.

OrderDraftModifier.

OrderDraftPricing.

---

# 69. WS-13 ORDER DRAFT STATES

DRAFT

PENDING_CONFIRMATION

CONFIRMED

SUBMITTING

SUBMITTED

FAILED

CANCELLED

---

# 70. WS-13 ORDER DRAFT OPERATIONS

Create draft.

Add Item.

Remove Item.

Change quantity.

Apply Modifier.

Apply Promotion reference.

Calculate expected total.

Confirm draft.

---

# 71. WS-13 ORDER DRAFT RULES

Require:

Valid Product.

Valid quantity.

Valid Price.

Sellable Product.

Valid Location.

Supported fulfillment mode.

---

# 72. WS-14 — ORDER SUBMISSION

Objective:

Submit confirmed Order to the authoritative POS safely.

Flow:

Confirmed Order Draft
    ↓
Idempotency Key
    ↓
Canonical Order Command
    ↓
POS Adapter
    ↓
POS
    ↓
External Order ID
    ↓
Canonical Order
    ↓
OrderSubmitted / OrderAccepted

---

# 73. WS-14 IDEMPOTENCY

Mandatory.

Use:

idempotency_key

submission state

external_order_id

deduplication logic

Retries shall not create duplicate Orders.

---

# 74. WS-14 FAILURE STATES

Handle:

POS timeout.

POS unavailable.

Validation error.

Rejected Product.

Price mismatch.

Order rejected.

Unknown response.

---

# 75. WS-14 UNCERTAIN RESULT

If POS request times out after submission and success is unknown:

DO NOT immediately retry blindly.

Perform reconciliation/lookup where possible.

Prevent duplicate Orders.

---

# 76. WS-15 — ORDER STATUS

Objective:

Allow Customers and Employees to retrieve current Order state.

Canonical states:

SUBMITTED

ACCEPTED

IN_PREPARATION

READY

COMPLETED

CANCELLED

FAILED

UNKNOWN

---

# 77. WS-15 STATUS MAPPING

Vendor-specific POS states shall map inside adapter.

Example:

POS status 7
    ↓
READY

The domain shall never depend directly on `7`.

---

# 78. WS-15 STATUS FRESHNESS

Status responses shall include sufficient freshness information where needed.

If live state is unavailable:

Return UNKNOWN or degraded result.

Do not fabricate.

---

# 79. WS-16 — HUMAN HANDOFF

Objective:

Allow AI-to-human transfer without context loss.

Minimum entities:

Escalation.

EscalationReason.

EscalationTarget.

EscalationBriefing.

EscalationStatus.

---

# 80. WS-16 ESCALATION REASONS

CUSTOMER_REQUEST

LOW_CONFIDENCE

UNRESOLVED_INTENT

BUSINESS_RULE

COMPLAINT

AUTHORIZATION_REQUIRED

INTEGRATION_FAILURE

AI_FAILURE

---

# 81. WS-16 BRIEFING

Include:

Customer.

Conversation summary.

Current Intent.

Current Order Draft.

Relevant history.

Actions attempted.

Reason for escalation.

Recommended next action.

---

# 82. WS-16 HUMAN TAKEOVER

Human operator must be able to:

View Conversation.

View Customer context.

View Order context.

Continue conversation.

Perform authorized Actions.

Resolve escalation.

---

# 83. WS-17 — DOMAIN EVENTS

Objective:

Emit the minimum meaningful Domain Events required by MVP.

Initial events:

CustomerIdentified

CustomerCreated

ConversationStarted

ConversationalIntentDetected

ProductQueried

ProductAvailabilityChecked

ProductRecommended

RecommendationAccepted

OrderDraftCreated

OrderConfirmed

OrderSubmitted

OrderAccepted

OrderPreparationStarted

OrderReady

OrderCompleted

OrderCancelled

OrderFailed

HumanEscalationRequested

HumanEscalationCompleted

ConversationResolved

---

# 84. WS-17 EVENT ENVELOPE

Minimum fields:

event_id

event_type

event_version

tenant_id

organization_id

location_id

aggregate_type

aggregate_id

occurred_at

recorded_at

correlation_id

causation_id

source_system

payload

---

# 85. WS-17 EVENT TRANSPORT

Prefer simple reliable architecture.

Candidate:

Transactional Outbox
    ↓
Background Publisher
    ↓
Redis queue / internal consumer mechanism

Do not introduce Kafka unless actual requirements justify it.

---

# 86. WS-18 — RELATIONSHIPS AND HISTORY

Objective:

Preserve enough connectivity to support Customer continuity and Intelligence.

Minimum relationships:

Customer
    PARTICIPATES_IN
Conversation

Customer
    PLACES
Order

Conversation
    REFERENCES
Order

Order
    CONTAINS
Product

Recommendation
    SUGGESTS
Product

Customer
    HAS_PREFERENCE
Preference

---

# 87. WS-18 CUSTOMER HISTORY

Generate Customer History from authoritative records.

Do not create an uncontrolled duplicated Customer timeline.

Initial history:

Orders.

Conversations.

Recommendations.

Preferences.

Escalations.

---

# 88. WS-19 — INITIAL INTELLIGENCE

Objective:

Provide useful business metrics without building advanced AI analytics.

Initial domains:

Sales Intelligence.

Customer Intelligence.

Operational Intelligence.

Executive Intelligence.

---

# 89. WS-19 SALES METRICS

Implement:

Conversation-to-Order conversion.

Recommendation acceptance.

Average Order value.

Top requested Products.

Unavailable Product requests.

Failed Order submissions.

---

# 90. WS-19 CUSTOMER METRICS

Implement:

New Customers.

Returning Customers.

Order frequency.

Top Products by Customer.

Preference usage.

---

# 91. WS-19 OPERATIONAL METRICS

Implement:

POS failures.

AI failures.

Order submission failures.

Product unavailability.

Escalations.

Latency.

---

# 92. WS-19 EXECUTIVE SUMMARY

Provide initial answer to:

"How is the Restaurant Intelligence Platform performing today?"

Possible summary:

Conversations.

Orders.

Sales.

Conversion.

Average Order.

Recommendations.

Escalations.

Failures.

Top Products.

Unavailable requests.

---

# 93. WS-20 — FRONTEND WORKSPACE

Objective:

Provide an operational interface for Restaurant staff.

Core views:

Login.

Dashboard.

Conversation Workspace.

Customer Context.

Menu/Product Search.

Order Draft.

Human Escalations.

Configuration.

---

# 94. WS-20 CONVERSATION WORKSPACE

Suggested layout:

LEFT:
Conversation List.

CENTER:
Active Conversation.

RIGHT:
Customer + Restaurant Context.

BOTTOM / SIDE:
Order Draft + Actions.

The exact UI shall remain responsive and operationally clear.

---

# 95. WS-20 CUSTOMER CONTEXT

Display only relevant information:

Customer identity.

Recent Orders.

Preferences.

Recent Conversation summary.

Active Order.

No unnecessary information overload.

---

# 96. WS-20 ORDER DRAFT UI

Required:

Products.

Quantities.

Modifiers.

Price.

Promotion.

Subtotal.

Total.

Confirmation state.

Submission state.

---

# 97. WS-20 ESCALATION UI

Show:

Reason.

Customer.

Conversation summary.

Current Order.

AI actions attempted.

Recommended next step.

---

# 98. WS-21 — VOICE INTEGRATION

Objective:

Connect Telephone to the same Conversation architecture.

Do not create a separate Voice business logic stack.

Flow:

Phone Call
    ↓
Voice Adapter
    ↓
Speech-to-Text
    ↓
Conversation Message
    ↓
Existing Conversational Intelligence
    ↓
Semantic Response
    ↓
Text-to-Speech

---

# 99. WS-21 VOICE CAPABILITIES

Initial:

Inbound call.

Caller ID.

Conversation creation/resumption.

Streaming or turn-based speech recognition.

AI response.

Speech generation.

Human transfer.

Call end.

---

# 100. WS-21 VOICE DATA

Preserve as allowed:

call_id

channel identity

caller number

conversation_id

timestamps

transcript references

transfer result

Recording policy shall be legally and operationally controlled.

---

# 101. WS-21 FAILURE HANDLING

Voice failure shall not destroy Conversation state.

If speech service fails:

Allow transfer.

Preserve available context.

Record failure.

---

# 102. WS-22 — SECURITY HARDENING

Review:

Authentication.

Authorization.

Tenant isolation.

Secrets.

Transport encryption.

Input validation.

Rate limiting.

API exposure.

Prompt/tool safety.

Sensitive logging.

Customer privacy.

POS credentials.

---

# 103. WS-22 AI SECURITY

Validate:

AI cannot access unauthorized Tenant.

AI cannot invoke unauthorized tools.

AI cannot directly modify database.

Tool arguments validated.

Sensitive data minimized.

Prompt injection cannot bypass domain authorization.

---

# 104. WS-22 POS SECURITY

Use:

Least-privilege DB/API credentials.

Encrypted transport where available.

Restricted write permissions.

Secret rotation strategy.

Audit.

---

# 105. WS-23 — OBSERVABILITY AND RELIABILITY

Technical metrics:

API latency.

API errors.

AI latency.

AI failures.

POS latency.

POS failures.

DB health.

Redis health.

Queue backlog.

Worker failures.

---

# 106. WS-23 BUSINESS METRICS

Business metrics:

Conversations.

Customer recognition.

Intent success.

Order creation.

Order completion.

Recommendations.

Escalations.

Unavailable Products.

Conversion.

---

# 107. WS-23 TRACING

Correlation should connect:

Conversation

AI call

Tool call

Domain operation

POS request

Order

Domain Event

This is essential for production diagnosis.

---

# 108. WS-23 ALERTS

Initial production alerts:

API unavailable.

DB unavailable.

POS integration degraded.

AI integration degraded.

High Order failure rate.

High escalation failure rate.

Queue backlog.

Cross-Tenant security violation attempt.

---

# 109. WS-24 — PRODUCTION E2E CERTIFICATION

Objective:

Prove the complete commercial flow against real infrastructure.

---

# 110. E2E-001 — CUSTOMER ORDER SUCCESS

Customer recognized
    ↓
Conversation started
    ↓
Product requested
    ↓
Product resolved
    ↓
Availability checked
    ↓
Price resolved
    ↓
Recommendation presented
    ↓
Recommendation accepted
    ↓
Order Draft created
    ↓
Customer confirms
    ↓
Order submitted
    ↓
POS confirms
    ↓
Order status retrieved
    ↓
Conversation resolved
    ↓
History verified
    ↓
Events verified
    ↓
Metrics verified

PASS required.

---

# 111. E2E-002 — UNKNOWN CUSTOMER

Unknown caller/User
    ↓
Conversation created
    ↓
Customer context established
    ↓
Order completed
    ↓
Customer identity/history preserved appropriately

PASS required.

---

# 112. E2E-003 — AMBIGUOUS PRODUCT

Customer:

"Give me two of those."

without resolvable context.

Expected:

Clarification.

No unsupported Order Item.

PASS required.

---

# 113. E2E-004 — PRODUCT UNAVAILABLE

Customer requests unavailable Product.

Expected:

Do not add invalid Item.

Provide accurate status.

Offer valid alternative if available.

PASS required.

---

# 114. E2E-005 — POS FAILURE

POS unavailable.

Expected:

No fabricated Order confirmation.

Conversation preserved.

Failure recorded.

Human escalation available.

PASS required.

---

# 115. E2E-006 — DUPLICATE SUBMISSION

Same submission retried.

Expected:

One POS Order.

One canonical Order.

PASS required.

---

# 116. E2E-007 — TENANT ISOLATION

Tenant A attempts access to Tenant B:

Customer.

Conversation.

Order.

Expected:

Rejected.

PASS required.

---

# 117. E2E-008 — AUTHORIZATION

Unauthorized Employee attempts protected Action.

Expected:

Rejected.

PASS required.

---

# 118. E2E-009 — AI FAILURE

AI provider unavailable.

Expected:

Platform records failure.

Conversation preserved.

Human takeover works.

No business corruption.

PASS required.

---

# 119. E2E-010 — HUMAN HANDOFF

Conversation escalated.

Human receives:

Customer.

Summary.

Intent.

Order.

History.

Expected:

Human continues without Customer restarting.

PASS required.

---

# 120. E2E-011 — EVENT TRACEABILITY

Complete Order flow.

Verify:

Events generated.

Correlation preserved.

No duplicate Event side effects.

PASS required.

---

# 121. E2E-012 — BUSINESS METRICS

Complete several Conversations.

Verify dashboard metrics reflect actual:

Conversations.

Orders.

Recommendations.

Escalations.

PASS required.

---

# 122. WS-25 — DEPLOYMENT AND RELEASE

Objective:

Deploy MVP as a reproducible production service.

Required:

Production configuration.

Secrets.

TLS.

Database migration.

Backup.

Restore procedure.

Health checks.

Metrics.

Logs.

Alerting.

Deployment runbook.

Rollback procedure.

---

# 123. ENVIRONMENTS

Recommended:

development

test

staging

production

At minimum:

development

staging

production

Production credentials shall never be used casually in development.

---

# 124. DATABASE MIGRATION STRATEGY

All schema changes shall use controlled migrations.

Required:

Migration history.

Forward migration.

Rollback or safe remediation plan.

Testing against staging.

---

# 125. BACKUP

Minimum:

Database backup.

Configuration backup.

Critical object/file backup if used.

Restore verification.

A backup that has never been tested is not sufficient production readiness.

---

# 126. DEPLOYMENT GATE

Before production:

Tests pass.

E2E passes.

Tenant isolation passes.

Security review passes.

POS integration verified.

Observability verified.

Backup verified.

Rollback path defined.

---

# 127. INITIAL MODULE BOUNDARIES

Recommended logical backend modules:

core/
    tenancy/
    auth/
    authorization/
    organizations/
    locations/
    audit/
    observability/
    events/

restaurant/
    customers/
    menu/
    products/
    pricing/
    promotions/
    orders/
    conversations/
    recommendations/
    intelligence/
    integrations/

This is logical guidance, not mandatory folder syntax.

---

# 128. INITIAL DATA MODEL

Minimum tables/entities may include:

tenants

organizations

locations

users

roles

permissions

user_roles

customers

customer_external_identities

customer_preferences

customer_history_entries

menus

menu_sections

products

product_external_mappings

product_availability

prices

promotions

conversations

conversation_participants

messages

conversation_context

order_drafts

order_draft_items

orders

order_external_mappings

recommendations

escalations

domain_events

outbox_events

audit_events

Exact physical schema shall be defined during implementation.

---

# 129. DATABASE OWNERSHIP PRINCIPLE

A table existing in one database does not remove logical ownership.

Example:

products
    OWNER = Product Domain

conversations
    OWNER = Conversation Domain

orders
    OWNER = Order Domain

---

# 130. API ERROR MODEL

Use consistent error contracts.

Example logical fields:

error_code

message

correlation_id

details where safe

Avoid returning internal stack traces to clients.

---

# 131. DOMAIN ERROR EXAMPLES

PRODUCT_NOT_FOUND

PRODUCT_UNAVAILABLE

PRICE_NOT_AVAILABLE

ORDER_INVALID

ORDER_DUPLICATE

ORDER_SUBMISSION_FAILED

POS_UNAVAILABLE

UNAUTHORIZED

TENANT_ACCESS_DENIED

AMBIGUOUS_REQUEST

HUMAN_ESCALATION_REQUIRED

---

# 132. IDEMPOTENCY MODEL

Critical commands should support:

idempotency_key

tenant_id

operation_type

request_hash

status

result_reference

created_at

expires_at where applicable

---

# 133. CORRELATION MODEL

Each incoming interaction should establish:

correlation_id

This should propagate through:

API

Conversation

AI

Tool calls

Domain command

POS Adapter

Events

Logs

---

# 134. BACKGROUND JOBS

Use background jobs only where asynchronous work is actually required.

Potential uses:

Event publication.

Delayed synchronization.

Follow-up.

Metrics aggregation.

POS reconciliation.

Do not move simple synchronous logic into workers unnecessarily.

---

# 135. RETRY POLICY

Retries shall depend on operation semantics.

Safe retry examples:

Read Product.

Read Order status.

Publish Event.

Potentially unsafe:

Create Order.

Process Payment.

Cancel Order.

Unsafe retries require idempotency/reconciliation.

---

# 136. CACHING

Caching may be used for:

Menu.

Product Catalog.

Slow-changing configuration.

Do not cache time-sensitive data beyond safe freshness limits.

Examples requiring caution:

Product availability.

Order status.

Price.

Promotion validity.

---

# 137. CACHE SOURCE OF TRUTH

Cache is never authoritative.

It is a performance optimization over an authoritative source.

---

# 138. TEST PYRAMID

Use:

UNIT TESTS

for Domain logic.

INTEGRATION TESTS

for DB/adapters.

CONTRACT TESTS

for POS ports.

E2E TESTS

for commercial flows.

SECURITY TESTS

for Tenant/authorization.

---

# 139. DOMAIN RULE TESTS

Priority tests:

Product sellability.

Price resolution.

Order state transitions.

Order confirmation.

Order idempotency.

Tenant isolation.

Authorization.

Ambiguity handling.

Escalation conditions.

---

# 140. POS CONTRACT TESTS

Both:

Mock POS Adapter

and:

Real POS Adapter

shall pass the same contract test suite where possible.

This ensures consistent behavior.

---

# 141. AI TESTING

Test behavior, not model wording.

Validate:

Correct Intent class.

Correct tool selected.

Correct Product entity.

Correct refusal to guess.

Correct clarification.

Correct escalation.

Correct Business Action.

Avoid brittle tests based on exact natural-language phrasing.

---

# 142. PROMPT MANAGEMENT

AI prompts/configuration should be version-controlled.

Prompt changes affecting production behavior should be reviewable.

Do not hide critical Business Rules solely inside prompts.

---

# 143. TOOL CONTRACTS

AI tools shall have explicit input/output schemas.

Example:

check_product_availability

Input:

tenant_id

location_id

product_id

service_mode

Output:

availability

reason

source

timestamp

---

# 144. TOOL SECURITY

Never trust AI-generated tool arguments directly.

Validate:

Tenant.

Entity existence.

Authorization.

Allowed values.

Business Rules.

---

# 145. HUMAN-IN-THE-LOOP BOUNDARY

Require human approval for Actions beyond AI authority.

Examples may include:

Exceptional Refund.

Unusual Discount.

Critical complaint compensation.

Business policy exception.

High-value Event negotiation.

These are primarily post-MVP except where the first Restaurant requires them.

---

# 146. IMPLEMENTATION PROMPT STRATEGY FOR CODEX

Each Codex prompt shall include:

OBJECTIVE

CURRENT BASELINE

AUTHORIZED FILES / MODULES

REQUIRED BEHAVIOR

PROHIBITED CHANGES

DOMAIN OWNERSHIP

TEST REQUIREMENTS

ACCEPTANCE CRITERIA

REQUIRED OUTPUT / EVIDENCE

---

# 147. CODEX CHANGE SIZE

Prefer one coherent work package per prompt.

Examples:

"Implement Tenant context middleware."

"Implement Customer canonical entity."

"Implement POS ProductPort."

"Implement MockCatalogAdapter."

"Implement Conversation entity + migration."

Avoid:

"Build the whole Restaurant Intelligence Platform."

---

# 148. CODEX PROHIBITIONS

Every implementation prompt should reinforce:

Do not refactor unrelated modules.

Do not change certified runtime behavior without need.

Do not introduce new libraries unnecessarily.

Do not change public contracts outside scope.

Do not remove tests.

Do not weaken security.

Do not invent domain semantics.

Do not create speculative infrastructure.

---

# 149. IMPLEMENTATION EVIDENCE

Codex should report:

Files changed.

Tests added.

Tests executed.

Commands executed.

Observed results.

Known limitations.

No unsupported claim of success.

---

# 150. IMPLEMENTATION COMMIT STRATEGY

Recommended commits:

Small.

Single-purpose.

Tested.

Reversible.

Examples:

feat(core): add tenant context

feat(restaurant): add customer domain

feat(pos): add canonical product port

feat(conversation): persist conversation messages

feat(order): add idempotent order submission

---

# 151. BRANCH STRATEGY

Use implementation branches aligned to bounded work.

Examples:

feat/ecip-core-tenancy

feat/restaurant-customer

feat/restaurant-menu

feat/conversation-runtime

feat/order-pos-integration

Avoid long-lived branches containing unrelated changes.

---

# 152. RELEASE INCREMENTS

Recommended milestones:

M0 — Runtime Baseline

M1 — Tenant + Restaurant Foundation

M2 — Customer + Menu

M3 — Conversation

M4 — Conversational Menu Intelligence

M5 — Recommendations

M6 — Order Draft

M7 — Real POS Order

M8 — Human Handoff

M9 — Metrics/Dashboard

M10 — Voice

M11 — Hardening

M12 — MVP Production

---

# 153. M0 ACCEPTANCE

Runtime baseline works.

No Restaurant functionality required.

---

# 154. M1 ACCEPTANCE

Tenant.

Organization.

Location.

Authorization.

Configuration.

All working.

---

# 155. M2 ACCEPTANCE

Customer lookup.

Menu retrieval.

Product search.

Price retrieval.

Working using Mock POS.

---

# 156. M3 ACCEPTANCE

Conversation persists.

Multi-turn context works.

Customer associated.

---

# 157. M4 ACCEPTANCE

Customer can ask:

"What hamburgers do you have?"

"How much is this?"

"Is it available?"

Answers use canonical Restaurant data.

---

# 158. M5 ACCEPTANCE

System can suggest valid complementary Product.

Recommendation is recorded.

---

# 159. M6 ACCEPTANCE

Customer can construct a Take-Away Order Draft conversationally.

---

# 160. M7 ACCEPTANCE

Confirmed Order reaches real POS exactly once.

Canonical Order mapping stored.

Status can be retrieved.

This is a major commercial milestone.

---

# 161. M8 ACCEPTANCE

AI can hand off to human with full context.

---

# 162. M9 ACCEPTANCE

Basic operational/business metrics visible.

---

# 163. M10 ACCEPTANCE

Telephone Channel uses the same Conversation and Restaurant domain pipeline.

---

# 164. M11 ACCEPTANCE

Security.

Reliability.

Failure handling.

Observability.

All meet production requirements.

---

# 165. M12 ACCEPTANCE

All MVP Exit Criteria in `RESTAURANT_MVP_PRODUCTION_SCOPE.md` pass.

---

# 166. FIRST DEVELOPMENT TARGET

The first coding target after baseline/reuse assessment should be:

TENANT
+
ORGANIZATION
+
LOCATION
+
CUSTOMER
+
POS PORT

This establishes the minimal domain/context foundation required by every later flow.

---

# 167. SECOND DEVELOPMENT TARGET

Then:

MENU
+
PRODUCT
+
PRICE
+
MOCK POS

This gives the first meaningful Restaurant query capability.

---

# 168. THIRD DEVELOPMENT TARGET

Then:

CONVERSATION
+
MESSAGES
+
CUSTOMER CONTEXT
+
INTENT

This creates the conversational foundation.

---

# 169. FOURTH DEVELOPMENT TARGET

Then:

AI TOOLS
+
MENU QUERY
+
PRODUCT AVAILABILITY
+
PRICE

This creates the first product demonstration.

---

# 170. FIFTH DEVELOPMENT TARGET

Then:

RECOMMENDATION
+
ORDER DRAFT

This introduces commercial intelligence.

---

# 171. SIXTH DEVELOPMENT TARGET

Then:

ORDER CONFIRMATION
+
POS SUBMISSION
+
IDEMPOTENCY

This creates real transactional value.

---

# 172. SEVENTH DEVELOPMENT TARGET

Then:

HUMAN ESCALATION
+
EVENTS
+
METRICS

This makes the system operationally usable.

---

# 173. EIGHTH DEVELOPMENT TARGET

Then:

REAL POS HARDENING
+
VOICE

This completes the first intended Customer Channel.

---

# 174. BLOCKER POLICY

When a blocker is discovered:

Classify:

DOMAIN_BLOCKER

INTEGRATION_BLOCKER

SECURITY_BLOCKER

RUNTIME_BLOCKER

DATA_BLOCKER

EXTERNAL_DEPENDENCY_BLOCKER

Then resolve only the minimum required blocker.

Do not use blockers as justification for broad architectural redesign.

---

# 175. POS DATA BLOCKER

If POS documentation is incomplete:

Use:

Schema inspection.

Sample data.

Read-only discovery.

Adapter tests.

Mock Adapter.

Do not stop all development while waiting for complete POS knowledge.

---

# 176. AI PROVIDER BLOCKER

If preferred AI provider is unavailable:

Keep AI provider behind minimal adapter.

Development may continue using another compatible provider or deterministic test implementation.

Do not couple Restaurant domain semantics to provider-specific behavior.

---

# 177. FRONTEND BLOCKER

Backend/domain implementation should not be blocked by complete UI design.

Use APIs and minimal developer interfaces first.

Frontend should follow stable contracts.

---

# 178. VOICE BLOCKER

Voice shall not block Conversation/domain implementation.

Text pipeline remains authoritative foundation.

---

# 179. IMPLEMENTATION CHANGE CONTROL

A proposed change outside current workstream requires evidence that it:

Blocks current scope.

Fixes critical correctness.

Fixes security.

Fixes production reliability.

Otherwise:

Defer.

---

# 180. DEFINITION OF DONE — WORK ITEM

A work item is complete when:

Code implemented.

Tests implemented.

Tests pass.

No unrelated regression.

Relevant documentation updated if necessary.

Observability added where required.

Security considered.

Acceptance criteria demonstrated.

---

# 181. DEFINITION OF DONE — MODULE

A module is complete when:

Canonical model implemented.

API/service contracts implemented.

Business Rules implemented.

Persistence implemented.

Authorization implemented.

Tests pass.

Error handling implemented.

Observability exists.

Integration boundaries are clear.

---

# 182. DEFINITION OF DONE — INTEGRATION

An integration is complete when:

Canonical adapter exists.

External IDs mapped.

Errors normalized.

Timeouts handled.

Retries controlled.

Idempotency handled where required.

Credentials secured.

Contract tests pass.

Observability exists.

---

# 183. DEFINITION OF DONE — AI CAPABILITY

An AI capability is complete when:

Intent/use case defined.

Required context bounded.

Tools explicit.

Tool inputs validated.

Tool outputs authoritative.

Low-confidence behavior exists.

Failure behavior exists.

Escalation exists.

Tests validate business behavior.

---

# 184. DEFINITION OF DONE — MVP

MVP is complete only when:

The complete real Customer-to-POS vertical slice passes in staging against the real POS.

Not when:

Individual modules compile.

Not when:

Mock tests pass only.

Not when:

A chatbot demo works.

---

# 185. IMPLEMENTATION RISKS

Primary risks:

POS schema complexity.

Unknown POS write behavior.

AI response reliability.

Voice latency.

Identity ambiguity.

Duplicate Order creation.

Tenant leakage.

Stale Product data.

Stale Price data.

Integration outages.

Over-engineering.

Scope expansion.

---

# 186. RISK MITIGATION — POS

Mitigate with:

Adapter boundary.

Read-only discovery.

Mock contract.

Staging tests.

Idempotency.

Reconciliation.

Observability.

---

# 187. RISK MITIGATION — AI

Mitigate with:

Tool-based architecture.

Domain validation.

Explicit Business Rules.

Confidence handling.

Clarification.

Human escalation.

No direct DB writes.

---

# 188. RISK MITIGATION — SCOPE

Apply:

RESTAURANT_MVP_PRODUCTION_SCOPE.md

Feature addition rule.

Vertical-slice priority.

Defer nonblocking domains.

---

# 189. RISK MITIGATION — OVER-ENGINEERING

Do not build:

Graph platform.

Kafka platform.

Rule engine.

Universal plugin architecture.

Multi-agent runtime.

Complex workflow engine.

unless proven necessary.

---

# 190. RISK MITIGATION — SECURITY

Mandatory:

Tenant isolation tests.

Server-side auth.

Tool authorization.

Secret management.

Audit.

Data minimization.

---

# 191. PRODUCTION READINESS CHECKLIST

Before release:

[ ] Tenant isolation verified.

[ ] Authentication verified.

[ ] Authorization verified.

[ ] POS credentials secured.

[ ] Real POS integration verified.

[ ] Order idempotency verified.

[ ] AI failure path verified.

[ ] POS failure path verified.

[ ] Human handoff verified.

[ ] Logs verified.

[ ] Metrics verified.

[ ] Alerts verified.

[ ] Database backups verified.

[ ] Restore tested.

[ ] TLS configured.

[ ] Secrets removed from repository.

[ ] Staging deployment verified.

[ ] Rollback documented.

[ ] E2E suite passes.

[ ] Enterprise Audit Framework Gate passes.

---

# 192. POST-MVP IMPLEMENTATION ORDER

After MVP production:

1. Reservations.

2. Delivery.

3. Complaint / Service Recovery.

4. Customer Intelligence expansion.

5. Sales Intelligence expansion.

6. Kitchen Intelligence.

7. Inventory Intelligence.

8. Operational Intelligence.

9. Executive Intelligence.

10. Intelligent Business Advisor.

11. Intelligent Agents.

This order may change based on Customer value discovered in production.

---

# 193. POST-MVP RESERVATION SLICE

Implement:

Availability.

Capacity.

Reservation creation.

Modification.

Cancellation.

Reminder.

Arrival.

No-show.

Customer History.

Conversation integration.

---

# 194. POST-MVP DELIVERY SLICE

Implement:

Address.

Delivery zone.

Fee.

Capacity.

Dispatch.

Tracking.

ETA.

Delivery outcome.

Operational Intelligence.

---

# 195. POST-MVP SERVICE RECOVERY SLICE

Implement:

Complaint.

Classification.

Severity.

Customer context.

Order context.

Recovery policy.

Approval.

Action.

Outcome.

Customer Intelligence.

---

# 196. POST-MVP OPERATIONS SLICE

Connect:

Kitchen.

Inventory.

Maintenance.

Incidents.

Orders.

Customer commitments.

Build:

Bottleneck detection.

Operational risk.

Capacity.

Alerts.

---

# 197. POST-MVP EXECUTIVE SLICE

Build:

Business Health.

Executive Attention Queue.

Risks.

Opportunities.

Recommendations.

Decision tracking.

Outcome learning.

This becomes the foundation for the future Intelligent Business Advisor.

---

# 198. IMPLEMENTATION PHILOSOPHY

The platform shall grow by:

VERTICAL VALUE SLICES

not:

HORIZONTAL INFRASTRUCTURE PERFECTION.

Preferred:

Customer can complete one real Order end-to-end.

Before:

Building 30 incomplete domain services.

---

# 199. PRODUCTION-FIRST DECISION

If choosing between:

A beautifully generalized infrastructure capability.

and:

A safe, maintainable implementation that completes the primary Customer flow.

Prefer:

THE IMPLEMENTATION THAT COMPLETES CUSTOMER VALUE

unless it creates unacceptable architectural or security debt.

---

# 200. FINAL EXECUTION SEQUENCE

The official execution sequence is:

1. Freeze Restaurant Domain Model v1.0.

2. Freeze Restaurant MVP Production Scope v1.0.

3. Baseline `pryecip`.

4. Perform Reuse Assessment.

5. Implement Tenant / Auth foundation.

6. Implement Restaurant Organization / Location.

7. Define POS canonical ports.

8. Implement Mock POS Adapter.

9. Implement Customer foundation.

10. Implement Menu / Product / Price.

11. Implement Conversation foundation.

12. Implement Conversational Intelligence.

13. Implement Restaurant query tools.

14. Implement Recommendations.

15. Implement Order Draft.

16. Implement Order Confirmation.

17. Implement idempotent POS submission.

18. Implement Order status.

19. Implement Human Handoff.

20. Implement MVP Domain Events.

21. Implement Customer History / Relationships.

22. Implement initial Intelligence and metrics.

23. Implement operational frontend.

24. Implement Real POS Adapter.

25. Pass real POS E2E.

26. Integrate Telephone/Voice.

27. Perform Security Hardening.

28. Perform Reliability Hardening.

29. Execute Enterprise Audit Framework production certification.

30. Deploy MVP to production.

---

# 201. IMMEDIATE NEXT ACTION

The immediate implementation action after approval of this plan is:

WS-00
+
WS-01

Specifically:

1. Inspect the current `pryecip` repository.

2. Inventory what already exists.

3. Compare it with reusable components from the Mineral Intelligence SaaS.

4. Establish the smallest production runtime baseline.

5. Produce the first bounded Codex implementation prompt.

The first Codex prompt should NOT build Restaurant functionality yet if the repository baseline is unknown.

It should first establish:

WHAT EXISTS NOW

WHAT CAN BE REUSED

WHAT IS MISSING

WHAT IS THE MINIMUM SAFE CHANGE REQUIRED TO BEGIN IMPLEMENTATION.

---

# 202. FINAL RULE

From this point forward, every implementation task shall answer:

DOES THIS ADVANCE THE PRIMARY CUSTOMER-TO-POS VERTICAL SLICE?

DOES IT PROTECT PRODUCTION?

DOES IT PROTECT SECURITY?

DOES IT PRESERVE DOMAIN OWNERSHIP?

DOES IT USE EXISTING PROVEN CAPABILITIES WHERE APPROPRIATE?

IS THE CHANGE SMALL ENOUGH TO VERIFY?

IS IT TESTABLE?

IS IT NECESSARY NOW?

If not:

DEFER.

The objective is no longer to further describe the Restaurant Intelligence Platform.

The objective is to build it.

---

# END OF DOCUMENT
