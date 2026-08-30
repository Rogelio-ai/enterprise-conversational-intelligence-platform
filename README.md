# README.md

# Enterprise Conversational Intelligence Platform (ECIP)

> **Building the conversational intelligence layer of the enterprise.**

---

# Overview

Enterprise Conversational Intelligence Platform (ECIP) is an enterprise-grade, AI-native and Agent-native software platform designed to understand, reason, decide and execute business actions through conversational interactions.

ECIP is the intelligence layer that connects:

* Customers
* Employees
* Enterprise Systems
* Enterprise Knowledge
* Artificial Intelligence
* Intelligent Agents

through a unified conversational runtime.

The platform is designed to operate across multiple communication channels while preserving a single enterprise context.

---

# First Commercial Product

The first commercial implementation of ECIP is:

**Restaurant Intelligence Platform**

Restaurant Intelligence Platform is implemented as the first Domain Pack of ECIP.

The enterprise platform remains domain-independent.

---

# Project Goals

The objectives of ECIP are to:

* Improve customer experience.
* Increase business value.
* Improve operational efficiency.
* Increase enterprise knowledge.
* Support intelligent business decisions.
* Execute authorized business actions.
* Enable intelligent human collaboration.
* Provide a reusable enterprise conversational platform.

---

# What ECIP Is

ECIP is:

* Enterprise-first
* AI-native
* Agent-native
* Multi-tenant
* Multi-channel
* Context-aware
* Knowledge-driven
* Action-oriented
* Secure
* Auditable
* Production-ready

---

# What ECIP Is Not

ECIP is not:

* A chatbot.
* An IVR.
* A CRM.
* A call center.
* A telephony platform.
* A messaging application.
* A replacement for ERP or POS systems.

Enterprise operational systems remain systems of record.

ECIP operates above them as the conversational intelligence layer.

---

# High-Level Architecture

```text
Communication Channels
        │
        ▼
Channel Adapters
        │
        ▼
Conversation Runtime
        │
        ▼
Enterprise Intelligence Core
        │
        ▼
Domain Packs
        │
        ▼
Enterprise Systems
```

---

# Initial Capabilities

The first implementation includes:

* Conversation Runtime
* Enterprise Context
* Enterprise Knowledge
* Enterprise Memory
* Decision Intelligence
* Action Runtime
* Human Escalation
* Multi-channel Architecture
* Restaurant Domain Pack

---

# Repository Structure

```text
pryecip/

apps/
services/
packages/
domain-packs/
connectors/
infrastructure/
docs/
projects/
tests/
scripts/
```

The repository is organized to separate reusable enterprise capabilities from domain-specific implementations.

---

# Repository Documentation

The most important project documents are:

| Document                                                                            | Purpose                                               |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `README.md`                                                                         | Repository overview                                   |
| `PRODUCT_CONSTITUTION.md`                                                           | Defines the permanent identity of ECIP                |
| `projects/Enterprise_Conversational_Intelligence_Platform/Project_Audit_Profile.md` | Project-specific governance                           |
| `docs/`                                                                             | Functional, technical and architectural documentation |

---

# Governance

This project is governed by:

## Enterprise Audit Framework

Defines:

* Architecture governance
* Runtime governance
* Ownership governance
* Risk classification
* Validation
* Certification
* Audit methodology

## Product Constitution

Defines:

* Product identity
* Product mission
* Product principles
* Product scope
* Long-term product direction

Project-specific adaptations are defined in:

```text
projects/Enterprise_Conversational_Intelligence_Platform/
Project_Audit_Profile.md
```

---

# Development Principles

Development follows the following priorities:

1. Customer Value
2. Production Readiness
3. Runtime Preservation
4. Ownership Preservation
5. Context Preservation
6. Certified Behavior Preservation
7. Security
8. Minimal Necessary Change

---

# Reuse Strategy

Reusable enterprise components from previously certified projects may be incorporated after evaluation.

Examples include:

* Infrastructure
* Authentication patterns
* Durable Job Runtime
* Observability
* Backend conventions
* Frontend shell
* Testing patterns

Business-specific implementations are not copied directly.

---

# Current Status

Project Status

**Active Development**

Repository

**pryecip**

Current Product

**Enterprise Conversational Intelligence Platform**

First Domain Pack

**Restaurant Intelligence Platform**

Commercial Status

**Pre-MVP**

## Restaurant Product Structure Foundation

Restaurant Products retain one canonical Organization-scoped identity. `ProductCategory` supports
cycle-safe parent/child classification and deterministic display ordering while remaining distinct
from customer-facing `MenuSection` placement.

A Product may own one current commercial composition containing:

* Fixed canonical Product components with exact included quantities.
* Choice groups with explicit minimum and maximum selections.
* Canonical Product options with exact included quantities.
* Deterministic, read-only selection validation for future Order Draft consumption.

Commercial composition is intentionally single-level. Nested compositions, Buffet entitlement,
daily availability, price deltas, Recipe, Ingredient and Inventory remain deferred.

## Product and Choice Resolution Foundation

Restaurant catalog data may include curated, Organization-scoped Product aliases. The internal
resolver uses deterministic Unicode normalization and exact canonical-name or active-alias matching,
then evaluates Product orderability through the active Location, Menu assignment, Menu, section,
item, and Product chain. Multiple canonical matches produce a typed ambiguity result; Choice
resolution remains inside the resolved parent Product's active WS-12 composition and returns
canonical group and option identities for WS-12 selection validation.

This capability does not provide fuzzy or vector matching, automatic translation, real-time
availability, final Order, pricing calculation, or POS submission.

## Order Draft Foundation

The Restaurant Domain owns one canonical mutable Order Draft per Conversation. A Draft copies its
trusted Tenant, Organization, and mandatory Location scope from the active Conversation and stores
ordered canonical Product items, exact `DECIMAL(19,4)` quantities, and explicit WS-12 ChoiceOption
selections. Fixed components remain derived. Draft reads deterministically derive `EMPTY`,
`INCOMPLETE`, `INVALID`, or `READY` by reusing WS-12 selection validation and WS-13 canonical-ID
Location/Menu orderability rules.

Every item or selection mutation requires the current Draft version and executes under a row lock;
one successful command increments the version exactly once. Conversation closure makes the Draft
immutable but leaves it readable. Access uses `order_draft.read` and `order_draft.manage` and is
available to authenticated staff, trusted orchestration, and the owning WS-16 DinerSession.
Final Order, commercial acceptance, POS submission, Recipe and
Ingredient semantics, free-form modifiers, and Buffet entitlement remain deferred.

## Commercial Resolution and Checkout Preview Foundation

A read-only Restaurant commercial resolver revalidates a currently `READY` Order Draft and derives
its Checkout Preview from the authoritative parent Product Price at the Draft Location. Fixed
components and selected options remain included and never add their standalone prices. Product-scoped
percentage and fixed-amount Promotions resolve by ascending numeric priority, then Promotion ID;
non-combinable Promotions do not stack, while eligible combinable Promotions apply in that stable
order. Prices are tax-inclusive (`tax_mode = INCLUDED`), all arithmetic remains exact `Decimal`, and
whole-unit `HALF_DOWN` rounding occurs once at the final payable boundary with its adjustment exposed.

`GET /order-drafts/{draft_id}/checkout-preview` uses `order_draft.read` and returns a transient
preview—not an Order, quote, receipt, payment, or POS submission. Diner access is limited to the
Preview derived from the diner's own Conversation and Draft. Commercial acceptance,
order-wide Promotions, tax engines, FX conversion, final Order, and POS
submission remain deferred.

## Restaurant Service Session and Diner Access Foundation

Restaurant table occupancy is derived from an `OPEN` Restaurant-owned Service Session; the Core
`Resource` remains administratively `ACTIVE` or `INACTIVE`. A TABLE has at most one open session,
with a party size from 1 to 999 and transactionally serialized capacity. Staff use
`restaurant_service.read` and `restaurant_service.manage` to open, read, resize, regenerate the
temporary credential, and close service.

Each open session exposes a high-entropy join context and a server-generated four-digit access code.
Only a keyed HMAC digest is stored; five invalid attempts within five minutes lock joining for five
minutes. External per-IP throttling remains a deployment responsibility. Production customer-device
traffic requires HTTPS, and discarding or expiring a bearer token does not end a DinerSession.

A successful join atomically creates one ACTIVE DinerSession, one personal `IN_PERSON_DIGITAL`
Conversation, a CUSTOMER participant, and a DIGITAL_WAITER participant. The dedicated
`diner_access` JWT is database-lifecycle validated and grants ownership only of that diner's
Conversation, lazily created OrderDraft, transient Checkout Preview, and explicit commercial
acceptance into immutable RestaurantOrder snapshots. Diner authority does not
create a User, TenantMembership, Role, or Permission grant, and multiple diners at one table never
share or merge Drafts.

Each Conversation may retain many terminal ACCEPTED/ABANDONED Drafts while a portable nullable-slot
unique constraint permits at most one current OPEN Draft. Confirmation requires the reviewed Draft
version, a versioned commercial/configuration fingerprint, and a case-sensitive idempotency key.
Pure presentation-name edits are excluded from commercial freshness but are captured from server
state in the accepted historical snapshot. Combined or split table billing, payment, POS submission,
POS recovery, and external POS lifecycle synchronization remain deferred to later workstreams.

---

# Development Runtime

The executable baseline contains the FastAPI service and an isolated local MySQL service. Copy the
example environment and replace both `AUTH_JWT_SECRET` and `RESTAURANT_ACCESS_CODE_SECRET` with
independent random values of at least 32 characters.

```bash
cp .env.example .env
docker compose up --build
```

Compose applies the Alembic migration before starting the API. To apply it explicitly or inspect the migration state:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

The current application migration head is `0018_preparation_routing_foundation`.

Restaurant operations are native-first and integration-optional. Every Location explicitly chooses
`PLATFORM` or `EXTERNAL_POS` preparation ownership; the first post-acceptance dispatch freezes that
choice for the immutable Restaurant Order. Platform-owned orders route accepted item/component
snapshots through explicit `AREA`, `COMPONENTS`, or `NO_PREPARATION` policies into one durable work
aggregate per Preparation Area. This native path requires no POS connection.

The POS connection capability `external_preparation_behavior` enforces one preparation authority.
Platform preparation can coexist with POS sales/accounting submission only when the connection is
explicitly `NO_PREPARATION_OUTPUT`; the conservative `MAY_PRODUCE_PREPARATION_OUTPUT` value blocks
native materialization. External-POS ownership creates no native Preparation Work and never falls
back silently when the integration is unavailable.

Restaurant commercial acceptance exposes:

```text
POST /diner/order/confirm
GET  /diner/orders
GET  /diner/orders/{order_id}
GET  /restaurant-orders
GET  /restaurant-orders/{order_id}
```

The diner confirmation endpoint derives all ownership scope from the diner token and accepts only
`expected_draft_version`, `expected_commercial_fingerprint`, and the `Idempotency-Key` header.
Staff reads require `restaurant_order.read`; staff POS materialization exposes separately authorized
submit, read, retry, and recover endpoints under
`/restaurant-orders/{order_id}/pos-submission`. Restaurant Order mutation/deletion, payment,
cancellation, Preparation, and POS status synchronization remain outside this scope.

The bounded Restaurant conversational-intelligence foundation records provider-neutral,
append-only derivation provenance and versioned Restaurant message intents without changing the
canonical Conversation evidence. An internal Restaurant-owned understanding port accepts trusted
Conversation scope and bounded ordered history; only a deterministic test fake is provided. Typed
read-only knowledge capabilities reuse canonical Menu, Product, current Price, and Promotion
candidate rules. There is no public intelligence endpoint, AI provider, response generator,
business mutation, Product Composition, RAG, translation, or voice processing.

The Restaurant domain now includes an Organization-owned canonical Menu and Product foundation.
Product categories classify reusable Products, while one-level Menu sections control presentation;
Menu-to-Location assignments determine where a Menu applies. POS product observations resolve through
the vendor-neutral `CatalogPort` into canonical Products using case-sensitive external mappings.
Access is governed by `product.read`, `product.manage`, `menu.read`, and `menu.manage`.

The Conversation foundation stores tenant-owned, Organization-scoped conversations, explicit
participants, and append-only semantic messages. Supported channels are `IN_PERSON_DIGITAL`,
`PHONE`, `WHATSAPP`, `WEB_CHAT`, and `MOBILE_APP`; message modalities are `TEXT`, `VOICE`, and
`TOUCH`. CUSTOMER, DIGITAL_WAITER, HUMAN_STAFF, and SYSTEM participants support anonymous and
multi-customer interactions. Nullable BCP-47-style defaults, participant preferences, and
per-message language observations preserve multilingual Unicode content without changing the
original evidence. AI behavior, translation/localization, media, connectors, and provider mappings
remain explicitly deferred. Access uses `conversation.read` and `conversation.manage`.

The commercial-offer foundation stores one current Product-and-Location Price using exact
`DECIMAL(19,4)` money and an explicit currency, with immutable PLATFORM/POS provenance. An explicit
`PricingPort` resolver can project a mapped POS Price; reads never trigger POS access. Promotions
support only percentage and fixed-amount benefits, Product targets, all-or-selected Location scope,
a UTC half-open validity interval, explicit combinability, and ascending numeric priority with
Promotion ID as the stable tie-breaker. Candidate lookup continues to return every matching
Promotion without calculating an effective Price; the Restaurant commercial resolver owns
selection, stacking, and calculation. PromotionPort canonicalization remains deferred. Access uses
`pricing.read`, `pricing.manage`, `promotion.read`, and `promotion.manage`.

Authentication uses an Argon2 password hash and a signed access token. The relevant settings are
`AUTH_JWT_SECRET`, `AUTH_JWT_ALGORITHM`, `AUTH_ACCESS_TOKEN_TTL_MINUTES`, and
`PASSWORD_MIN_LENGTH`. Restaurant joining additionally requires an independent
`RESTAURANT_ACCESS_CODE_SECRET`; diner token lifetime is bounded by
`DINER_ACCESS_TOKEN_TTL_MINUTES` (maximum 12 hours).

Bootstrap the first development or staging Tenant administrator with explicit environment values:

```bash
docker compose exec \
  -e BOOTSTRAP_TENANT_NAME='Development Tenant' \
  -e BOOTSTRAP_TENANT_SLUG='development' \
  -e BOOTSTRAP_ADMIN_EMAIL='admin@example.invalid' \
  -e BOOTSTRAP_ADMIN_PASSWORD \
  -e BOOTSTRAP_ADMIN_DISPLAY_NAME='Development Admin' \
  api python -m app.bootstrap_admin
```

Set `BOOTSTRAP_ADMIN_PASSWORD` in the invoking shell; the command does not print it. Re-running the
same bootstrap is safe and reports `already_configured`.

Log in (include `tenant_id` when the User has more than one active Tenant membership):

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.invalid","password":"<password>"}'
```

Use the returned access token for the authenticated context and permission-protected Tenant:

```bash
curl http://localhost:8000/auth/me -H 'Authorization: Bearer <access-token>'
curl http://localhost:8000/tenants/current \
  -H 'Authorization: Bearer <access-token>' \
  -H 'X-Tenant-ID: <signed-tenant-id>'
```

The Organization, Location, and Resource foundations expose these tenant-scoped endpoints:

```text
GET|POST   /organizations
GET|PATCH  /organizations/{organization_id}
GET|POST   /locations
GET|PATCH  /locations/{location_id}
GET|POST   /resources
GET|PATCH  /resources/{resource_id}
GET|POST   /customers
GET|PATCH  /customers/{customer_id}
```

They use the corresponding `organization.read|manage`, `location.read|manage`, and
`resource.read|manage` permissions. Resource is a bounded, Location-owned physical operational
identity; hierarchy, capacity, availability, and other real-time operational state are deferred.
Tenant ownership is always taken from the signed authentication context, never from request data.

Customer is a canonical, Tenant-owned Restaurant identity with one optional normalized email and
phone. Its endpoints use `customer.read|manage`. POS Customer identifiers are preserved separately
through Tenant- and connector-scoped external mappings. The internal resolver depends on the
vendor-neutral `CustomerPort`; CRM, preferences, history, addresses, loyalty, automatic contact
merging, and POS synchronization remain deferred.

The Restaurant Domain Pack includes a vendor-neutral POS contract and a deterministic in-memory
Mock POS Adapter. Accepted Restaurant Orders can be durably materialized through a location POS
connection with frozen mappings, stable idempotency, retry evidence, claim fencing, and uncertain
create recovery. No real vendor adapter or credentials are stored by this implementation.

A single active membership is inferred during login. Multiple active memberships require an
explicit `tenant_id` at login. `X-Tenant-ID` may only confirm the Tenant bound into the signed token;
it cannot switch or grant Tenant access.

Run backend tests in an isolated container:

```bash
docker compose run --rm api pytest
```

The WS-17 pre-implementation certified regression baseline was `251 passed, 0 failed, 0 skipped,
0 xfailed` on MySQL 8.4.8 and MariaDB 10.6.28.

Run the same migration and integration suite against an isolated MariaDB 10.6 service with:

```bash
docker compose -p pryecip-mariadb -f compose.yaml -f compose.mariadb.yaml \
  run --build --rm api pytest
docker compose -p pryecip-mariadb -f compose.yaml -f compose.mariadb.yaml down -v
```

Runtime endpoints are available at:

* `http://localhost:8000/health`
* `http://localhost:8000/ready`
* `http://localhost:8000/metrics`

Stop the runtime without deleting the MySQL volume:

```bash
docker compose down
```

---

# Long-Term Vision

Build a reusable enterprise platform capable of supporting multiple industries through Domain Packs while preserving a common conversational intelligence core.

Restaurant Intelligence Platform is the first commercial realization of that vision.

---

# License

License information will be defined before the first commercial release.
