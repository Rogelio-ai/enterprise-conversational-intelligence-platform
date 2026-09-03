# WS-24_PAYMENT_EXECUTOR_FOUNDATION.md

## 1. DOCUMENT STATUS

**Workstream:** WS-24 — Payment Executor Foundation
**Status:** APPROVED FOR IMPLEMENTATION
**Discovery:** CODEX-WS-24-A completed
**Discovery decision:** PROCEED WITH MODIFICATION
**Human review:** APPROVED WITH MODIFICATION
**Certified predecessor:** WS-23-B — Canonical Payment & Settlement Foundation
**Certified predecessor commit:** `ca25651`
**Expected predecessor Alembic head:** `0023_restaurant_payment_settlement_foundation`

This document is the permanent implementation authority for WS-24.

Individual Codex implementation prompts such as:

* `CODEX-WS-24-B1`
* `CODEX-WS-24-B2`
* `CODEX-WS-24-B3`
* `CODEX-WS-24-B4`
* `CODEX-WS-24-B5`
* `CODEX-WS-24-B6`
* `CODEX-WS-24-B7`

MUST reference this document instead of repeating the entire architectural contract.

---

# 2. PURPOSE

WS-24 establishes the reusable, tenant-safe, location-aware and provider-neutral infrastructure required to connect real payment executors to the Restaurant Intelligence Platform.

WS-24 does **NOT** implement a real payment provider.

It creates the stable execution boundary through which future providers such as:

* Conekta
* Mercado Pago
* PayPal
* other future payment executors

may be connected without changing the canonical restaurant financial domain.

The target architecture is:

```text
RestaurantCheck
        ↓
RestaurantPayment
        ↓
PaymentExecutorResolver
        ↓
PaymentExecutorRegistry
        ↓
PaymentExecutionPort
        ↓
Provider Adapter
        ↓
Future Payment Provider
```

Merchant credentials are resolved through a separate infrastructure boundary:

```text
PaymentExecutorResolver
        ↓
MerchantCredentialResolver
        ↓
Secret Infrastructure
```

---

# 3. AUTHORITY ORDER

For WS-24 implementation, authority is:

```text
1. This document
2. Human review decisions
3. CODEX-WS-24-A Discovery findings
4. Certified WS-23-B behavior
5. Current repository evidence
```

If an individual Codex implementation prompt conflicts with this document, this document prevails unless the human reviewer explicitly changes the architectural decision.

If repository evidence proves an approved requirement unsafe or impossible, implementation must stop and report the blocker rather than silently redesigning the architecture.

---

# 4. FUNDAMENTAL FINANCIAL PRINCIPLE

The following distinction is immutable:

```text
PAYMENT != SETTLEMENT
```

`RestaurantPayment` represents money movement or attempted money movement.

`RestaurantCheckSettlement` represents the immutable application of confirmed money to RestaurantCheck liability.

A payment provider does not own restaurant financial truth.

Canonical success remains:

```text
Provider confirms financial success
        ↓
RestaurantPayment = SUCCEEDED
        ↓
RestaurantCheckSettlement created
        ↓
Liability extinguished
        ↓
RestaurantCheck may become SETTLED
```

A payment executor or provider adapter MUST NOT directly mutate:

* `RestaurantCheck`
* `RestaurantCheckSettlement`
* `RestaurantCheckAllocation`
* `RestaurantCheckMember`
* `RestaurantCheckTableScope`
* `DinerSession`
* `RestaurantServiceSession`
* ordering locks
* continuation state
* table balance

---

# 5. CERTIFIED LIABILITY INVARIANTS

WS-24 MUST preserve the financial invariants established by WS-23-B.

Canonical liability:

```text
liability_total =
    consumption_total
    + gratuity_total
```

Confirmed settlement:

```text
confirmed_settlement =
    SUM(RestaurantCheckSettlement.amount)
```

Reserved financial exposure:

```text
reserved_financial_exposure =
    SUM(
        RestaurantPayment.amount
        WHERE state IN (
            RESERVED,
            IN_PROGRESS,
            UNCERTAIN
        )
    )
```

Available capacity:

```text
available_to_initiate =
    liability_total
    - confirmed_settlement
    - reserved_financial_exposure
```

Mandatory invariant:

```text
confirmed_settlement
+ reserved_financial_exposure
<= liability_total
```

WS-24 MUST NOT weaken or bypass this invariant.

---

# 6. CANONICAL PAYMENT STATES

The canonical `RestaurantPayment` states remain:

```text
RESERVED
IN_PROGRESS
SUCCEEDED
FAILED
REJECTED
UNCERTAIN
CANCELLED
```

Provider-specific states MUST NOT become canonical restaurant payment states.

Forbidden examples:

```text
CONEKTA_PENDING
MERCADOPAGO_APPROVED
PAYPAL_CAPTURED
```

Provider-specific status may be preserved only as sanitized, noncanonical evidence.

---

# 7. THREE INDEPENDENT DIMENSIONS

The architecture MUST preserve:

```text
PAYMENT METHOD
    !=
PAYMENT PROVIDER / EXECUTOR
    !=
PAYMENT EXECUTION TOPOLOGY
```

Examples:

```text
method = CARD
executor = CONEKTA
topology = EXTERNAL
```

```text
method = TRANSFER
executor = MERCADO_PAGO
topology = EXTERNAL
```

Possible future configuration:

```text
method = CARD
executor = LOCAL_TERMINAL
topology = LOCAL
```

Never model:

```text
payment_method = CONEKTA
payment_method = PAYPAL
payment_method = MERCADO_PAGO
```

WS-24 topology values are initially:

```text
LOCAL
EXTERNAL
```

Topology does not imply payment method.

---

# 8. CASH

Cash remains on the certified WS-23-B local path.

WS-24 MUST NOT force CASH through the executor registry.

Canonical cash semantics remain:

```text
RestaurantPayment.amount
    = liability being settled
```

```text
tendered_amount
    = physical amount received
```

```text
change_due
    = tendered_amount - amount
```

With:

```text
tendered_amount >= amount
```

Cash requires no external provider and no merchant-provider credentials.

---

# 9. WS-23-B CAPABILITIES TO REUSE

WS-24 MUST reuse, not rebuild:

* `RestaurantPayment`
* `RestaurantPaymentAttempt`
* durable payment reservation
* payment initiation idempotency
* provider idempotency identity
* request fingerprinting
* leases
* claim tokens
* fencing
* `UNCERTAIN`
* recovery semantics
* settlement uniqueness
* `PaymentExecutionPort`
* `PaymentRecoveryPort`
* provider-neutral execution DTOs
* deterministic payment executor
* safe external evidence fields
* canonical settlement application

The default architectural rule is:

```text
REUSE FIRST
MINIMAL NECESSARY CHANGE
PRESERVE CERTIFIED BEHAVIOR
```

---

# 10. LOCATION PAYMENT EXECUTOR CONFIGURATION

WS-24 introduces the minimum persistent executor configuration required for safe multi-tenant execution.

Canonical concept:

```text
LocationPaymentExecutorConfiguration
```

Exact class/table naming may follow repository conventions.

The configuration belongs to:

```text
Tenant
    ↓
Organization
    ↓
Location
```

Minimum information:

```text
id
tenant_id
organization_id
location_id

executor_key
display_name

adapter_kind

topology
    LOCAL
    EXTERNAL

status
    ACTIVE
    INACTIVE

credential_binding
    optional nonsecret reference

selection_priority/default metadata
    only if required for deterministic AUTO
```

Rules:

* `executor_key` is stable.
* `executor_key` is safe to expose publicly.
* `executor_key` is unique within the appropriate location scope.
* `adapter_kind` identifies runtime implementation type.
* merchant credentials are never stored here.
* disabling a configuration prevents new selections.
* disabling a configuration MUST NOT prevent recovery of historical payments.
* historical configuration identity remains meaningful for the lifetime of a payment.

---

# 11. EXECUTOR CAPABILITIES

Canonical concept:

```text
LocationPaymentExecutorCapability
```

Capabilities represent which payment requests an executor configuration supports.

Minimum dimensions:

```text
executor_configuration
payment_method
currency
```

Examples:

```text
Executor X
CARD
MXN
```

```text
Executor Y
TRANSFER
MXN
```

Do NOT add:

* provider fee models
* risk policies
* promotions
* routing scores
* latency optimization
* health history
* AI routing
* economic optimization

---

# 12. RESTAURANT PAYMENT EXECUTOR IDENTITY

New configured non-cash payments MUST durably identify the executor configuration selected.

Canonical field:

```text
executor_configuration_id
```

Rules:

* nullable where legitimate, including historical data and CASH.
* new configured non-cash payments use the selected executor configuration.
* full tenant/organization/location ownership must be enforced.
* recovery uses the original configuration.
* configuration changes do not move historical payments to another executor.
* AUTO does not reroute an existing payment.
* explicit selection replay does not reroute an existing payment.

---

# 13. EXTERNAL PROVIDER TRANSACTION IDENTITY

A provider transaction reference is not globally unique by itself.

Do NOT enforce:

```text
UNIQUE(external_reference)
```

Canonical external financial identity is:

```text
executor_configuration_id
+
external_reference
```

For non-null external references, the same provider transaction identity MUST NOT fund more than one logical `RestaurantPayment`.

Required semantics:

```text
same configuration
+ same external_reference
→ duplicate/rejected financial identity
```

```text
different configuration
+ same external_reference
→ allowed
```

A duplicate confirmed provider reference MUST NEVER create a second `RestaurantCheckSettlement`.

If canonical financial truth cannot safely determine whether money moved, preserve an unresolved/UNCERTAIN-safe state rather than fabricating failure.

MySQL and MariaDB nullable uniqueness behavior must be explicitly certified.

---

# 14. PAYMENT EXECUTOR REGISTRY

WS-24 introduces a runtime:

```text
PaymentExecutorRegistry
```

Its responsibility is runtime implementation resolution.

It may know:

* `adapter_kind`
* runtime executor implementation
* intrinsic topology support
* intrinsic recovery support
* intrinsic execution capabilities where appropriate

It MUST NOT:

* own tenant authorization
* own restaurant financial state
* store merchant secrets
* determine canonical settlement
* directly mutate restaurant models

Persistent configuration answers:

```text
May this tenant/location use this executor?
```

Runtime registry answers:

```text
Does an implementation for this adapter exist?
```

These responsibilities remain separate.

---

# 15. PAYMENT EXECUTOR RESOLVER

Canonical service concept:

```text
PaymentExecutorResolver
```

The resolver is tenant/location aware.

Trusted inputs include:

```text
tenant
organization
location
payment_method
currency
selection_intent
```

Selection intent may be:

```text
EXPLICIT
```

or:

```text
AUTO
```

Resolver responsibilities:

1. establish trusted tenant/location scope;
2. load eligible persistent configurations;
3. require ACTIVE status for new selection;
4. validate payment method;
5. validate currency;
6. verify runtime adapter availability;
7. select deterministically;
8. return selected configuration/runtime executor;
9. prevent cross-tenant resolution;
10. prevent cross-location resolution.

Historical recovery uses:

```text
RestaurantPayment.executor_configuration_id
```

and does not reroute.

---

# 16. EXPLICIT EXECUTOR SELECTION

Clients may select an executor through a public-safe:

```text
executor_key
```

The server MUST NOT translate this directly into an object from a global runtime dictionary.

Resolution must pass through:

```text
authenticated scope
        ↓
tenant
        ↓
organization
        ↓
location
        ↓
persistent executor configuration
        ↓
method/currency capability
        ↓
runtime registry
```

A client cannot select another tenant/location's executor.

---

# 17. MINIMAL AUTO SELECTION

WS-24 supports only deterministic minimal AUTO selection.

Canonical flow:

```text
AUTO
    ↓
find current location configurations
    ↓
ACTIVE only
    ↓
filter payment method
    ↓
filter currency
    ↓
apply deterministic priority/default
    ↓
select exactly one
    ↓
persist selected configuration
```

AUTO MUST NOT consider:

* transaction fees
* commissions
* latency optimization
* provider promotions
* customer promotions
* risk scoring
* provider health scores
* AI
* machine learning
* dynamic fallback
* autonomous economic optimization

If resolution is ambiguous, fail deterministically.

Never choose randomly.

---

# 18. AUTO IDEMPOTENCY

Selection intent and resolved executor identity are different concepts.

For example:

```text
selection_intent = AUTO
```

while:

```text
executor_configuration_id = X
```

The logical request fingerprint must preserve the original request intent.

Once AUTO creates a payment using configuration `X`, replay of that same logical payment MUST reuse `X`.

It MUST NOT recalculate AUTO and choose `Y` because configuration priorities or runtime state changed.

---

# 19. CREDENTIAL MODEL

The platform formally distinguishes three credential concepts:

```text
CUSTOMER PAYMENT SOURCE
        !=
MERCHANT PROVIDER CREDENTIAL
        !=
CREDENTIAL BINDING
```

---

## 19.1 CUSTOMER PAYMENT SOURCE

Ephemeral customer authorization/payment-source material.

Future examples:

* provider token
* payment-source token
* hosted-fields token
* checkout token

Rules:

* ephemeral only;
* never persisted;
* never fingerprinted;
* never logged;
* never returned;
* never confused with merchant credentials;
* raw PAN/CVV must not enter the platform's canonical payment storage.

---

## 19.2 MERCHANT PROVIDER CREDENTIAL

Secret used to authenticate the merchant/platform against a provider.

Future examples:

* API secret
* access token
* private credential

Rules:

* resolved server-side;
* never supplied as an executor selector;
* never persisted in `RestaurantPayment`;
* never stored plaintext in executor configuration;
* never fingerprinted;
* never logged;
* never exposed by API;
* never included in exception text.

---

## 19.3 CREDENTIAL BINDING

A nonsecret durable reference that allows infrastructure to find the correct merchant credential.

It may exist in executor configuration when necessary.

It MUST NOT itself contain secret material.

---

# 20. MERCHANT CREDENTIAL RESOLVER

Canonical infrastructure concept:

```text
MerchantCredentialResolver
```

This is a provider-neutral secret-resolution boundary.

Its trusted context may include:

```text
tenant
organization
location
executor_configuration_id
credential_binding
```

It returns ephemeral merchant authentication material.

It does not persist the returned secret.

It does not log it.

WS-24 does not require a real external secret manager.

A deterministic/test implementation may be used for certification.

`.env` and `.env.example` MUST NOT be modified for WS-24.

---

# 21. PAYMENT EXECUTION PORT

Reuse:

```text
PaymentExecutionPort
```

Do NOT create a competing payment execution interface.

The provider-neutral execution contract MUST remain free of restaurant ORM/domain objects.

The following MUST NOT cross the provider boundary:

* `RestaurantCheck`
* `RestaurantOrder`
* ORM `RestaurantPayment`
* `RestaurantCheckSettlement`
* `DinerSession`
* `RestaurantServiceSession`
* `CheckMember`
* `CheckAllocation`
* table balance

The existing execution DTO remains sufficient for direct tokenized execution unless concrete future provider evidence proves otherwise.

Do NOT add speculative:

* hosted checkout abstractions
* redirects
* payment links
* authorization/capture lifecycle
* provider-specific DTOs

---

# 22. PAYMENT RECOVERY PORT

Reuse:

```text
PaymentRecoveryPort
```

Recovery may minimally add an optional safe:

```text
external_reference
```

if required.

Recovery MUST use:

* original logical payment
* original executor configuration
* original provider idempotency identity
* original request fingerprint
* known safe provider reference when available

Recovery MUST NOT:

* create another logical payment;
* change provider;
* generate another provider idempotency key;
* blindly re-charge an `UNCERTAIN` payment.

If authoritative resolution is impossible:

```text
STILL_UNCERTAIN
```

and canonical payment remains:

```text
UNCERTAIN
```

---

# 23. UNCERTAIN

`UNCERTAIN` remains a first-class financial state.

Examples that may lead to UNCERTAIN:

```text
timeout after possible submission
connection loss after possible submission
provider pending/nonfinal
unknown execution result
```

UNCERTAIN:

* creates no settlement;
* reserves the complete payment amount;
* prevents reuse of that financial capacity;
* preserves check protection;
* blocks affected closure;
* prohibits blind retry;
* requires recovery/reconciliation.

A generic timeout MUST NOT automatically become `FAILED`.

`FAILED` requires authoritative evidence that no financial effect occurred or can occur.

---

# 24. DURABLE RESERVATION BEFORE EXTERNAL EXECUTION

Absolute invariant:

```text
NO EXTERNAL PAYMENT CALL
BEFORE DURABLE PAYMENT RESERVATION COMMIT
```

Canonical sequence:

```text
BEGIN
    ↓
lock RestaurantCheck
    ↓
validate liability
    ↓
validate financial capacity
    ↓
resolve/validate executor
    ↓
create RestaurantPayment RESERVED
    ↓
persist executor configuration identity
    ↓
persist idempotency/fingerprint
    ↓
COMMIT
    ↓
claim execution
    ↓
RestaurantPayment IN_PROGRESS
    ↓
RestaurantPaymentAttempt
    ↓
COMMIT
    ↓
resolve ephemeral merchant credential
    ↓
external provider call
```

Never move external execution into the liability transaction.

---

# 25. EXECUTION REVALIDATION

Before a new external execution call, revalidate the originally selected configuration.

At minimum:

* correct tenant;
* correct organization;
* correct location;
* selected configuration identity;
* runtime adapter exists;
* new-execution eligibility;
* method compatibility;
* currency compatibility.

Do not reroute if revalidation fails.

If no external request could have occurred, use safe definite failure semantics where appropriate.

If provider execution may already have occurred, preserve UNCERTAIN.

---

# 26. CONFIGURATION DISABLEMENT

Distinguish:

```text
NEW EXECUTION
```

from:

```text
HISTORICAL RECOVERY
```

When configuration becomes `INACTIVE`:

New selection:

```text
FORBIDDEN
```

Historical recovery for an already bound payment:

```text
ALLOWED
```

An `UNCERTAIN` payment MUST NOT become unrecoverable merely because new transactions were disabled.

---

# 27. CREDENTIAL ROTATION

WS-24 does not implement full secret rotation management.

The executor configuration and credential resolver boundary must nevertheless avoid making future rotation architecturally impossible.

Historical/in-flight recovery must remain associated with the correct merchant/provider account.

Do not introduce speculative credential-version infrastructure unless repository evidence proves it necessary.

---

# 28. PROVIDER RESULT SANITIZATION

Provider adapters must normalize external results into provider-neutral safe evidence.

Safe examples:

* `external_reference`
* sanitized external status
* normalized error classification
* safe provider error code
* brand
* last4
* masked display
* canonical outcome

Forbidden durable/public evidence:

* raw provider response body
* raw provider exception object
* Authorization header
* merchant secret
* payment source token
* PAN
* CVV/CVC
* magnetic-stripe data
* unfiltered provider diagnostic messages

---

# 29. EXACTLY-ONCE FINANCIAL EFFECT

Required architecture:

```text
one logical RestaurantPayment
        ↓
one stable provider idempotency identity
        ↓
at most one provider financial effect
        ↓
at most one RestaurantCheckSettlement
```

Retries and recovery MUST reuse the same provider idempotency identity.

Never generate a new provider idempotency identity merely because a payment became `UNCERTAIN`.

---

# 30. ATTEMPTS, LEASES AND FENCING

Reuse existing:

* `RestaurantPaymentAttempt`
* attempt sequence
* claim token
* lease expiry
* worker ownership
* fencing
* recovery semantics

Do not create another worker-coordination subsystem.

A stale worker cannot overwrite the canonical result chosen by a later valid owner.

If a lease expires while a provider request may still be in flight, use recovery semantics rather than issuing another blind charge.

---

# 31. PROVIDER AVAILABILITY

WS-24 only requires minimal availability semantics.

Persistent configuration:

```text
ACTIVE
INACTIVE
```

Runtime:

```text
adapter implementation available
adapter implementation unavailable
```

Do NOT build:

* health dashboards
* provider health history
* health scoring
* failover engine
* circuit-breaker platform
* dynamic routing optimization

An already-created payment is never automatically moved to a different provider merely because its adapter becomes unavailable.

---

# 32. AVAILABLE EXECUTORS API

The backend may expose the safe executors available for a payment context.

Diner context derives location from authenticated diner/service-session context.

Staff context requires authorized tenant/location scope.

Filtering dimensions:

```text
payment_method
currency
```

Safe public information may include:

* `executor_key`
* `display_name`
* method
* currency
* possibly safe topology where useful

Never expose:

* merchant credentials
* credential bindings
* raw runtime adapter identity
* secret-store references
* provider diagnostic data

No frontend implementation belongs to WS-24.

---

# 33. CONFIGURATION MANAGEMENT SCOPE

Persistent executor configuration is required.

A complete administrative CRUD product is NOT required.

WS-24 may use controlled deterministic/bootstrap/test provisioning where sufficient.

A minimal administrative API is permitted only when technically required for safe runtime operation or certification.

Do not create speculative provider-management screens or broad CRUD.

---

# 34. TENANT ISOLATION

Tenant isolation is mandatory.

A tenant MUST NOT:

* select another tenant's executor;
* inspect another tenant's executor configuration;
* resolve another tenant's merchant credential;
* recover using another tenant's configuration.

Location isolation is also mandatory.

Where possible, use database-enforced composite ownership FKs instead of relying solely on application filters.

---

# 35. OBSERVABILITY

Minimum safe executor lifecycle observability should cover:

* executor resolution
* payment reservation
* execution claim
* external call start
* external call completion
* canonical execution outcome
* UNCERTAIN transition
* fencing
* recovery
* duplicate external-reference conflict
* settlement application

Safe context may include:

* correlation ID
* tenant ID
* organization ID
* location ID
* payment ID
* attempt ID
* executor configuration ID
* executor key
* topology
* canonical outcome
* safe external reference
* sanitized external status/error code
* timing

Secrets MUST NEVER be logged.

Metrics must use bounded-cardinality labels.

Do not place payment IDs, check IDs, external references, tenant IDs or similar high-cardinality identifiers into metric labels.

---

# 36. MIGRATION

WS-24 implementation is expected to introduce:

```text
0024_payment_executor_foundation
```

Parent:

```text
0023_restaurant_payment_settlement_foundation
```

There must remain exactly one Alembic head.

Expected conceptual schema:

```text
location_payment_executor_configurations
location_payment_executor_capabilities
restaurant_payments.executor_configuration_id
configuration-scoped external-reference uniqueness
```

Use repository naming conventions for exact names.

Portability requirements:

```text
MySQL 8.4.x
MariaDB 10.6.x
InnoDB
utf8mb4
utf8mb4_unicode_ci
```

Do not use PostgreSQL-only mechanisms.

Existing WS-23-B data must remain valid.

Do not fabricate real provider configuration for historical data.

Nullable historical configuration identity is preferable to invented provider history.

---

# 37. REQUIRED CONCURRENCY / FAILURE BEHAVIOR

Implementation and certification must cover at least:

1. duplicate provider execution;
2. concurrent claims on the same payment;
3. expired lease while request may be in flight;
4. stale worker success after recovery winner;
5. timeout after possible charge;
6. network disconnect after possible charge;
7. duplicate provider success;
8. recovery/original worker race;
9. duplicate external reference across logical payments;
10. provider pending remains UNCERTAIN;
11. delayed success produces exactly one settlement;
12. delayed failure releases exposure only after authoritative proof;
13. provider unavailable before call;
14. executor disabled after reservation;
15. configuration changes while payment is IN_PROGRESS;
16. historical recovery after configuration disablement;
17. merchant credential resolution failure before call;
18. cross-tenant executor selection;
19. cross-location executor selection;
20. cross-tenant credential resolution;
21. UNCERTAIN payment plus another payer;
22. final success racing another partial payment;
23. settlement racing continuation/order lifecycle;
24. AUTO replay after priorities change;
25. explicit-selection replay after configuration changes;
26. concurrent AUTO under the same logical idempotency request;
27. duplicate provider financial reference never creating duplicate settlement.

---

# 38. SECURITY REQUIREMENTS

Tests must prove at minimum:

```text
customer payment source is not persisted
merchant credential is not persisted
customer payment source is not fingerprinted
merchant credential is not fingerprinted
merchant secret is not returned by APIs
merchant secret is not logged
credential binding is not exposed to diner APIs
raw provider errors are not blindly persisted
cross-tenant resolution fails
cross-location resolution fails
PAN/CVV are not canonical stored payment data
```

---

# 39. PORTABILITY CERTIFICATION

WS-24 must be certified on both:

```text
MySQL 8.4.x
MariaDB 10.6.x
```

Migration certification must include:

```text
fresh database -> head
```

and:

```text
0023 -> 0024
0024 -> 0023
0023 -> 0024
```

Actual schema must be inspected.

Do not certify solely from Alembic exit status.

Verify:

* engine
* charset
* collation
* FKs
* composite ownership FKs
* UNIQUE constraints
* CHECK constraints
* indexes
* nullable uniqueness semantics
* ORM/migration parity
* exactly one Alembic head

---

# 40. FULL REGRESSION

After focused WS-24 tests and migration certification:

Run full regression against:

```text
MySQL 8.4.x
MariaDB 10.6.x
```

Requirements:

```text
0 failures
no hidden skips
no disabled tests
no weakening previous certified behavior
```

WS-23-B financial behavior must remain intact.

---

# 41. OUT OF SCOPE

WS-24 MUST NOT implement:

* Conekta real adapter
* Mercado Pago real adapter
* PayPal real adapter
* Stripe real adapter
* any other real payment provider
* provider webhooks
* hosted checkout
* hosted fields implementation
* redirect payment flow
* payment links
* authorization/capture lifecycle
* card vault
* stored cards
* PAN/CVV handling
* refunds
* reversals
* chargebacks
* disputes
* accounts receivable
* courtesy settlements
* gift cards
* loyalty
* cash drawer
* cashier shifts
* bank reconciliation
* accounting/GL
* CFDI
* fiscal invoice
* billing
* parent RestaurantOrder ticket to CAJA
* paid RestaurantCheck ticket
* preparation printing modifications
* frontend payment screens
* sophisticated AUTO routing
* fee optimization
* latency optimization
* risk optimization
* promotion-based routing
* health-score routing
* automatic provider fallback
* payment microservice extraction
* post-settlement experience

---

# 42. FUTURE REAL PROVIDER WORKSTREAM

After WS-24 is certified, the first real provider MUST be implemented in a separate documentation-driven workstream.

Before selecting that provider, research official provider documentation.

The provider workstream will determine:

* authentication
* tokenization
* customer payment-source mechanism
* supported methods
* supported currencies
* idempotency guarantees
* synchronous result semantics
* pending semantics
* authoritative recovery lookup
* provider references
* webhook requirements
* webhook authentication
* hosted/redirect flows if applicable
* error normalization
* provider-specific security requirements

The reusable restaurant payment domain must not change merely because a particular provider requires a different transport mechanism.

---

# 43. FUTURE POST-SETTLEMENT FLOW

WS-24 does not implement this flow, but MUST preserve compatibility with it.

Canonical future sequence:

```text
FULL SETTLEMENT
        ↓
RestaurantCheck = SETTLED
        ↓
¿Desea factura?
        ├── YES → Billing/Fiscal flow
        └── NO
        ↓
¿Necesita la cuenta impresa?
        ├── YES
        │      ↓
        │ paid RestaurantCheck ticket
        │      ↓
        │ PAGADA
        │      ↓
        │ Print Dispatch
        │      ↓
        │ CAJA
        └── NO
        ↓
SERVICE_CONTINUATION_DECISION_REQUIRED
        ↓
¿Desean algo más?
```

There is NO automatic paid-check printing.

---

# 44. FUTURE ORDER COMMERCIAL DISPATCH

WS-24 does not implement this flow.

Future architecture remains:

```text
RestaurantOrder
    ├── Parent Order Ticket → CAJA
    ├── Preparation child → COCINA
    ├── Preparation child → BARRA
    └── ...
```

Architectural distinction:

```text
ORDER COMMERCIAL DISPATCH
    !=
PREPARATION DISPATCH
```

CAJA must not be modeled as a preparation area merely to reuse routing.

---

# 45. WS-24 IMPLEMENTATION PARTITION

To reduce Codex context size and execution cost, WS-24 implementation is divided into smaller implementation stages.

The planned sequence is:

```text
WS-24-A
Discovery
DONE
        ↓
WS-24-B1
Executor Configuration + Migration
        ↓
WS-24-B2
Runtime Registry + Resolver
        ↓
WS-24-B3
Credential Boundary + Payment Integration
        ↓
WS-24-B4
API + Security + Observability
        ↓
WS-24-B5
Concurrency + Focused Certification
        ↓
WS-24-B6
MySQL/MariaDB Migration Certification + Full Regression
        ↓
WS-24-B7
Final Human Review / Implementation Report
        ↓
COMMIT
```

Each B-stage is a subdivision of WS-24 implementation.

They are not independent architectural workstreams.

---

# 46. B1 — EXECUTOR CONFIGURATION + MIGRATION

Primary responsibility:

```text
durable configuration
capabilities
payment executor configuration identity
external-reference structural protection
migration 0024
```

B1 must not implement registry, credentials, frontend or real providers.

---

# 47. B2 — REGISTRY + RESOLVER

Primary responsibility:

```text
PaymentExecutorRegistry
PaymentExecutorResolver
explicit selection
minimal AUTO
tenant/location resolution
historical configuration resolution
```

B2 reuses B1 persistence.

---

# 48. B3 — CREDENTIAL BOUNDARY + PAYMENT INTEGRATION

Primary responsibility:

```text
Customer Payment Source semantics
MerchantCredentialResolver
executor binding to payment execution
recovery configuration binding
provider-safe result normalization
```

No real provider.

Use deterministic executors.

---

# 49. B4 — API + SECURITY + OBSERVABILITY

Primary responsibility:

```text
available executors API
validated selection API behavior
security boundary tests
safe logs/events
minimal metrics
permissions if actually needed
```

No frontend UI.

---

# 50. B5 — CONCURRENCY + FOCUSED CERTIFICATION

Primary responsibility:

```text
race conditions
UNCERTAIN behavior
fencing
duplicate external reference
AUTO replay
configuration disablement
historical recovery
tenant/location isolation
focused payment regression
```

---

# 51. B6 — DATABASE + FULL REGRESSION CERTIFICATION

Primary responsibility:

```text
MySQL certification
MariaDB certification
migration round-trip
schema inspection
ORM/migration parity
full regression
```

B6 must not expand implementation scope except to correct discovered WS-24 defects.

---

# 52. B7 — FINAL REVIEW

Primary responsibility:

```text
final diff review
contract verification
certification evidence
deviation report
remaining risks
human-review report
```

No commit or push occurs until B7 is approved by the human reviewer.

---

# 53. GIT SAFETY

During WS-24 implementation, Codex MUST NOT autonomously:

```text
git add .
git add -A
git commit
git push
git reset --hard
git restore .
git clean -fd
git stash
```

Changes remain unstaged until human review.

Before every implementation stage, verify:

```text
git status
git branch --show-current
git log --oneline --decorate -5
git diff --check
```

If the working tree contains partial WS-24 changes from a previous stage, inspect and preserve them.

Do not discard legitimate partial work.

---

# 54. INTERRUPTION / RECOVERY RULE

If VS Code, Codex or the development machine terminates unexpectedly:

Do not restart WS-24 from scratch.

Inspect:

```text
git status
git diff --check
git diff --stat
git diff --name-status
```

Determine which approved WS-24 changes already exist.

Preserve legitimate work and continue from the last safe point.

Never erase partial work without explicit human authorization.

---

# 55. DEFINITION OF DONE

WS-24 is complete only when:

```text
provider-neutral executor configuration exists
tenant/location isolation is enforced
runtime registry exists
resolver exists
explicit selection is safe
minimal AUTO is deterministic
historical recovery preserves original configuration
credential concepts are separated
merchant credential resolver boundary exists
customer payment sources remain ephemeral
external provider reference identity is protected
UNCERTAIN semantics remain intact
exactly-once settlement protection remains intact
PaymentExecutionPort remains provider-neutral
PaymentRecoveryPort remains provider-neutral
focused tests pass
security tests pass
concurrency tests pass
MySQL certification passes
MariaDB certification passes
migration certification passes
full regression passes on both engines
exactly one Alembic head exists
WS-23-B behavior remains certified
no real provider was implemented
no unrelated domain expansion occurred
```

---

# 56. FINAL ARCHITECTURAL RESULT

At WS-24 completion, the platform should have:

```text
Restaurant Financial Domain
        │
        │ canonical
        ▼
RestaurantPayment
        │
        ▼
Payment Executor Foundation
        │
        ├── Location Configuration
        ├── Capabilities
        ├── Executor Registry
        ├── Executor Resolver
        ├── Credential Resolver
        ├── Execution Port
        └── Recovery Port
        │
        ▼
Provider Adapter Boundary
        │
        ├── Conekta       FUTURE
        ├── Mercado Pago  FUTURE
        ├── PayPal        FUTURE
        └── others        FUTURE
```

A future provider must be replaceable without changing:

* RestaurantCheck liability
* RestaurantPayment canonical states
* RestaurantCheckSettlement
* payment capacity calculation
* table balance
* ordering locks
* continuation semantics
* diner/session semantics

This is the architectural contract of WS-24.

---

# END — WS-24_PAYMENT_EXECUTOR_FOUNDATION.md
