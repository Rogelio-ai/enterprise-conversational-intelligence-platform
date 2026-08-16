# 26_Payments.md

**Document ID:** RDM-026
**Document Name:** Payments
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Payments Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of financial settlement associated with Orders, Reservations, Events, Deposits, Refunds, Service Recovery and other restaurant commercial obligations.

The Payments Model connects:

* Orders.
* Customers.
* Checks.
* Reservations.
* Events.
* Deposits.
* Quotes.
* Discounts.
* Taxes.
* Service Charges.
* Tips.
* Cash Registers.
* Payment Gateways.
* Accounts Receivable.
* Billing.
* Refunds.
* Reconciliation.
* Fraud signals.
* Customer History.
* Operational Intelligence.
* Executive Intelligence.

Payment shall not be treated as a single Boolean field such as `paid=true`.

It is a governed financial lifecycle with independently traceable attempts, authorizations, settlements, failures, refunds and reconciliation.

---

# 2. OBJECTIVES

The Payments Model enables ECIP to:

* Create Payment requests.
* Support multiple Payment methods.
* Support partial Payments.
* Support split Payments.
* Support mixed Payment methods.
* Support prepayment.
* Support Payment at pickup.
* Support Payment on delivery.
* Support deposits.
* Support tips and gratuities.
* Support refunds.
* Support reversals.
* Support Payment retries.
* Support Payment failures.
* Support authorization and capture.
* Support reconciliation.
* Prevent duplicate Payments.
* Preserve historical Payment evidence.
* Support external Payment gateways.
* Support conversational Payment assistance.
* Support Accounts Receivable.
* Support Executive and Financial Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Commercial Obligation
* Action Request
* Action Authorization
* Action Execution
* Action Result
* Transaction
* Financial Event
* Commitment
* External System
* Connector
* External Entity Reference
* Evidence Record
* Audit Event
* Context Snapshot

Restaurant-specific Payment entities remain within the Restaurant Domain Pack.

---

# 4. PAYMENT PRINCIPLE

The platform shall distinguish between:

```text
COMMERCIAL OBLIGATION

PAYMENT REQUEST

PAYMENT ATTEMPT

PAYMENT AUTHORIZATION

PAYMENT CAPTURE

PAYMENT SETTLEMENT

PAYMENT FAILURE

REFUND

REVERSAL

RECONCILIATION
```

These concepts shall remain independently traceable.

---

# 5. PAYMENT

A `Payment` represents the governed financial settlement of all or part of a commercial obligation.

Typical attributes include:

* Payment ID
* Customer
* Related Order / Check / Reservation / Event
* Payment Method
* Amount
* Currency
* Status
* Requested amount
* Authorized amount
* Captured amount
* Settled amount
* Refunded amount
* Created time
* Authorized time
* Captured time
* Settled time
* Source channel
* Payment provider
* Cash Register reference
* External identifiers
* Idempotency key

---

# 6. PAYMENT STATUS

Suggested high-level lifecycle:

```text
CREATED
→ PENDING
→ AUTHORIZED
→ CAPTURED
→ SETTLED
```

Alternative states include:

```text
PARTIALLY_PAID
FAILED
DECLINED
CANCELLED
EXPIRED
PARTIALLY_REFUNDED
REFUNDED
REVERSED
DISPUTED
```

The exact lifecycle may vary by Payment Method.

---

# 7. PAYMENT OBLIGATION

A `PaymentObligation` represents an amount that must be financially settled.

Possible sources include:

* Order.
* Dining Check.
* Event.
* Reservation Deposit.
* Banquet Deposit.
* Delivery.
* Accounts Receivable.
* Service Charge.
* Other authorized commercial obligation.

Typical attributes:

* Obligation ID
* Source
* Customer
* Total amount
* Currency
* Due amount
* Settled amount
* Outstanding amount
* Due date
* Status

---

# 8. PAYMENT OBLIGATION STATUS

Suggested states:

```text
OPEN

PARTIALLY_SETTLED

SETTLED

OVERDUE

CANCELLED

WRITTEN_OFF
```

Write-off rules belong to financial governance.

---

# 9. PAYMENT REQUEST

A `PaymentRequest` represents a request for a Customer or authorized payer to settle an amount.

Typical attributes:

* Payment Request ID
* Obligation
* Amount
* Currency
* Supported methods
* Expiration
* Channel
* Status

---

# 10. PAYMENT ATTEMPT

A `PaymentAttempt` represents one concrete attempt to perform a Payment.

Typical attributes:

* Attempt ID
* Payment
* Method
* Provider
* Attempt number
* Requested amount
* Status
* Started at
* Completed at
* Provider result
* Failure reason
* External transaction reference

A Payment may have multiple Attempts.

---

# 11. PAYMENT ATTEMPT STATUS

Suggested states:

```text
CREATED

PROCESSING

AUTHORIZED

CAPTURED

SETTLED

DECLINED

FAILED

CANCELLED

TIMEOUT
```

---

# 12. PAYMENT METHODS

Initial Payment Methods may include:

```text
CASH

CREDIT_CARD

DEBIT_CARD

DIGITAL_WALLET

BANK_TRANSFER

SPEI_TRANSFER

PAYMENT_LINK

QR_PAYMENT

GIFT_CARD

LOYALTY_VALUE

CORPORATE_ACCOUNT

ACCOUNT_RECEIVABLE

THIRD_PARTY_PLATFORM_PAYMENT

OTHER
```

Supported methods remain deployment-specific.

---

# 13. CASH PAYMENT

Cash Payment may require:

* Cash Register.
* Cashier.
* Amount received.
* Change due.
* Currency.
* Receipt.

Detailed Cash custody belongs to `28_Cash_Management.md`.

---

# 14. CASH RECEIVED

Typical attributes:

* Payment
* Amount received
* Amount due
* Change
* Cash Register
* Employee
* Timestamp

The Payment domain records settlement.

Cash Management records custody and reconciliation.

---

# 15. CARD PAYMENT

Card Payment may use an external Payment Processor.

ECIP shall never store sensitive raw card information unless explicitly supported by compliant architecture and policy.

Tokenization and provider-hosted Payment mechanisms should be preferred.

---

# 16. CARD AUTHORIZATION

Some card flows separate:

```text
AUTHORIZATION
```

from:

```text
CAPTURE
```

An Authorization reserves Payment capacity.

It does not necessarily represent final settlement.

---

# 17. AUTHORIZATION

A `PaymentAuthorization` may preserve:

* Provider authorization ID
* Authorized amount
* Expiration
* Status
* Timestamp

Suggested states:

```text
PENDING

AUTHORIZED

DECLINED

EXPIRED

VOIDED
```

---

# 18. CAPTURE

A `PaymentCapture` represents collection of an authorized amount.

A Capture may be:

* Full.
* Partial.
* Multiple partial captures where supported.

---

# 19. IMMEDIATE CAPTURE

Some Payment methods perform Authorization and Capture as one logical flow.

The Domain Model shall support both combined and separate methods.

---

# 20. DIGITAL WALLET

Examples may include provider-supported wallets.

The platform shall normalize them as Payment Methods while provider-specific semantics remain behind connectors.

---

# 21. BANK TRANSFER

A bank transfer may remain pending until external settlement evidence is available.

ECIP shall not mark a transfer paid merely because the Customer says it was sent.

---

# 22. SPEI TRANSFER

In deployments supporting SPEI, a Payment may have:

* Payment reference.
* Bank transfer identifier.
* Settlement notification.
* Expiration.
* External evidence.

The exact implementation remains provider-specific.

---

# 23. PAYMENT LINK

A `PaymentLink` may enable a Customer to pay through a secure external flow.

Typical attributes:

* Link ID
* Payment Request
* Provider
* Expiration
* Status
* External URL reference or token

Sensitive URLs or tokens shall be handled securely.

---

# 24. QR PAYMENT

QR Payment may be:

* Static.
* Dynamic.
* Order-specific.

The platform shall wait for authoritative Payment confirmation before settlement.

---

# 25. GIFT CARD PAYMENT

Gift Card Payment may settle all or part of an Obligation.

Gift Card balance and lifecycle may exist in an external or loyalty-like value system.

---

# 26. LOYALTY VALUE AS PAYMENT

Where business rules permit, Loyalty value may be redeemed toward a Payment obligation.

Loyalty remains authoritative for points or reward balance.

Payment records the resulting financial effect.

---

# 27. CORPORATE ACCOUNT PAYMENT

Corporate customers may settle Orders through:

* Contract account.
* Invoice terms.
* Accounts Receivable.

This may create an Account Receivable rather than immediate cash settlement.

---

# 28. THIRD-PARTY PLATFORM PAYMENT

Delivery platforms or marketplaces may collect Payment externally.

The platform shall preserve:

* Platform
* External Payment reference
* Gross amount
* Fees where known
* Net receivable
* Settlement status

---

# 29. PAYMENT AMOUNT

Every Payment shall explicitly identify:

* Amount.
* Currency.

No Payment shall exist without an authoritative monetary amount.

---

# 30. CURRENCY

Payments may support multiple currencies where required.

The platform shall preserve:

* Transaction currency.
* Settlement currency if different.
* Exchange-rate source.
* Effective rate.

---

# 31. PAYMENT SPLIT

A commercial obligation may be settled through multiple Payments.

Example:

```text
Order Total:
$1,000

Payment 1:
$400 Cash

Payment 2:
$600 Card
```

---

# 32. SPLIT PAYMENT BY PERSON

Dining parties may split settlement among multiple payers.

The Order or Check need not be duplicated.

---

# 33. SPLIT PAYMENT BY ITEM

Individual Check items may be allocated to separate Payments where supported.

Allocation shall remain traceable.

---

# 34. SPLIT PAYMENT BY AMOUNT

Customers may split equally or by custom amounts.

The total allocated amount shall reconcile to the intended obligation.

---

# 35. MIXED PAYMENT

A `MixedPayment` uses multiple Payment Methods.

Examples:

* Cash + Card.
* Gift Card + Card.
* Loyalty + Cash.

Each financial component shall remain individually traceable.

---

# 36. PARTIAL PAYMENT

A Payment may settle only part of the Obligation.

Example:

```text
Event Total:
$20,000

Deposit:
$5,000

Outstanding:
$15,000
```

---

# 37. DEPOSIT

A Deposit represents an advance Payment associated with a future obligation.

Examples:

* Banquet.
* Event.
* Large Reservation.
* Catering.

Deposit ownership may reference the Event or Reservation.

---

# 38. DEPOSIT APPLICATION

When the final Obligation is created, the Deposit may be applied toward it.

Example:

```text
Final Event Amount:
$30,000

Deposit Paid:
$10,000

Outstanding:
$20,000
```

Deposit application shall be explicit.

---

# 39. DEPOSIT REFUND

Cancellation or policy may require:

* Full Refund.
* Partial Refund.
* No Refund.
* Future Credit.

The applicable commercial policy shall govern the result.

---

# 40. PREPAYMENT

Some Orders may require complete Payment before:

* Production.
* Pickup.
* Delivery.
* Event confirmation.

Prepayment policy shall be explicit.

---

# 41. PAYMENT AT FULFILLMENT

Some Orders permit Payment at:

* Pickup.
* Table settlement.
* Delivery handoff.

The fulfillment domain shall verify the authoritative Payment state where required.

---

# 42. PAYMENT ON DELIVERY

Where allowed, Payment may occur during Delivery handoff.

Risks include:

* Customer unavailable.
* Cash custody.
* Network failure.
* Payment decline.

The Delivery may remain unresolved until Payment policy is satisfied.

---

# 43. TIP

A `Tip` represents a voluntary gratuity where applicable.

Typical attributes:

* Tip ID
* Payment or Check
* Amount
* Currency
* Recipient allocation reference
* Timestamp

Tip treatment may vary by jurisdiction.

---

# 44. SERVICE CHARGE

A Service Charge is not the same as a Tip.

It may be mandatory according to:

* Event.
* Party size.
* Contract.
* Restaurant policy.

Service Charge is part of the commercial obligation.

---

# 45. TIP VS SERVICE CHARGE

The model shall preserve:

```text
TIP
=
voluntary gratuity where applicable

SERVICE CHARGE
=
contractual or policy-based charge
```

They shall not be merged.

---

# 46. PAYMENT FEE

External Payment providers may charge:

* Transaction fee.
* Fixed fee.
* Percentage fee.

Payment Fee may support profitability and reconciliation analysis.

---

# 47. PAYMENT FAILURE

A `PaymentFailure` represents unsuccessful Payment execution.

Possible categories:

```text
INSUFFICIENT_FUNDS

DECLINED

INVALID_METHOD

AUTHORIZATION_FAILED

PROVIDER_UNAVAILABLE

NETWORK_ERROR

TIMEOUT

EXPIRED

CUSTOMER_CANCELLED

UNKNOWN
```

---

# 48. FAILURE REASON

Failure reason shall distinguish:

* Customer-facing explanation.
* Internal technical reason.
* Provider code.

Sensitive provider details should not necessarily be exposed to the Customer.

---

# 49. PAYMENT RETRY

A failed Payment may be retried.

Retries shall:

* Preserve prior Attempts.
* Avoid duplicate settlement.
* Use idempotency where supported.

---

# 50. PAYMENT FALLBACK

Where permitted, the Customer may choose another Payment Method after failure.

Example:

```text
Card declined
    ↓
Customer chooses cash
```

The failed card Attempt remains historical evidence.

---

# 51. PAYMENT TIMEOUT

A provider timeout means settlement may be uncertain.

The platform shall not automatically assume either success or failure without reconciliation or provider evidence.

---

# 52. UNCERTAIN PAYMENT STATE

Suggested status:

```text
PAYMENT_STATUS_UNKNOWN
```

or equivalent controlled state.

This may require:

* Provider lookup.
* Reconciliation.
* Human review.

---

# 53. PAYMENT IDEMPOTENCY

Payment creation and provider calls shall support idempotency where possible.

This is critical for preventing duplicate charges caused by:

* Network retries.
* Webhook retries.
* AI Action retries.
* Client retries.
* Provider timeouts.

---

# 54. DUPLICATE PAYMENT DETECTION

Potential signals:

* Same obligation.
* Same amount.
* Same method.
* Same Customer.
* Very short time interval.
* Same external provider reference.

Detection shall not automatically void a legitimate Payment.

---

# 55. DUPLICATE CHARGE

A confirmed duplicate charge is a critical financial defect.

The platform shall support:

* Identification.
* Refund or reversal.
* Customer communication.
* Incident tracking.
* Audit.

---

# 56. PAYMENT CANCELLATION

A Payment Request or pending Payment may be cancelled before irreversible settlement where the method permits.

Cancellation semantics depend on Payment state.

---

# 57. VOID

A `Void` usually cancels an Authorization or unsettled transaction before final settlement.

Void shall remain distinct from Refund.

---

# 58. REFUND

A `Refund` returns previously settled value to the payer.

Typical attributes:

* Refund ID
* Original Payment
* Amount
* Currency
* Reason
* Requested by
* Approved by
* Provider
* Status
* External reference
* Created time
* Completed time

---

# 59. FULL REFUND

A Full Refund returns the entire eligible settled amount.

---

# 60. PARTIAL REFUND

A Partial Refund returns only part of the settled amount.

Example:

```text
Payment:
$1,000

Refund:
$250

Remaining net settled:
$750
```

---

# 61. REFUND REASON

Possible reasons:

```text
ORDER_CANCELLED

ITEM_CANCELLED

MISSING_ITEM

QUALITY_ISSUE

DELIVERY_FAILURE

DUPLICATE_PAYMENT

OVERCHARGE

SERVICE_RECOVERY

EVENT_CANCELLATION

MANUAL_CORRECTION

OTHER
```

---

# 62. REFUND AUTHORIZATION

Refund thresholds may require different authority levels.

AI shall not issue Refunds beyond explicit delegated policy.

---

# 63. REFUND STATUS

Suggested lifecycle:

```text
REQUESTED
→ PENDING_APPROVAL
→ APPROVED
→ SUBMITTED
→ PROCESSING
→ COMPLETED
```

Alternative states:

```text
REJECTED
FAILED
CANCELLED
```

---

# 64. REFUND LIMIT

Refund amount shall not exceed the eligible net settled amount unless an explicit external credit mechanism exists.

---

# 65. REVERSAL

A `Reversal` negates a Payment transaction under provider or financial rules.

It is conceptually distinct from a normal Refund.

---

# 66. CHARGEBACK

A `Chargeback` or Payment dispute may originate externally.

Typical attributes:

* Dispute ID
* Payment
* Provider
* Amount
* Reason
* Evidence deadline
* Status

---

# 67. PAYMENT DISPUTE

Possible lifecycle:

```text
OPENED
→ EVIDENCE_REQUIRED
→ UNDER_REVIEW
→ WON / LOST
→ CLOSED
```

Payment disputes may require Human escalation.

---

# 68. FRAUD SIGNAL

Potential fraud signals may include:

* Repeated failed attempts.
* Unusual Payment velocity.
* Payment method mismatch.
* Repeated Refund behavior.
* Suspicious duplicate attempts.

These are risk indicators, not proof of fraud.

---

# 69. PAYMENT RISK ASSESSMENT

A `PaymentRiskAssessment` may produce:

```text
LOW

MEDIUM

HIGH

REVIEW_REQUIRED
```

Risk algorithms shall remain explainable enough for operational use.

---

# 70. PAYMENT AUTHORIZATION POLICY

Actions may require additional verification based on:

* Amount.
* Payment Method.
* Customer context.
* Risk.
* Refund type.

---

# 71. PAYMENT AND ORDER

Order defines the commercial obligation.

Payment settles that obligation.

Conceptually:

```text
Order
    ↓
Payment Obligation
    ↓
Payment
```

Order status and Payment status shall remain separate.

---

# 72. ORDER PAYMENT STATUS

Suggested derived states:

```text
UNPAID

PARTIALLY_PAID

PAID

PARTIALLY_REFUNDED

REFUNDED

PAYMENT_FAILED
```

These states shall derive from Payment evidence.

---

# 73. PAYMENT AND DINING CHECK

A Dining Check may be settled through one or more Payments.

The Check remains the billable grouping.

Payment remains the financial transaction.

---

# 74. PAYMENT AND RESERVATION

Reservations may require:

* Deposit.
* Guarantee.
* Cancellation fee.

The Reservation domain owns booking policy.

Payment executes financial settlement.

---

# 75. PAYMENT AND EVENT

Events may require:

* Deposit.
* Progress Payments.
* Final Settlement.
* Refund.

Each Payment shall reference the appropriate Event obligation.

---

# 76. PAYMENT AND TAKE AWAY

Take Away may require:

* Prepayment.
* Payment at Pickup.

Handoff shall respect applicable Payment policy.

---

# 77. PAYMENT AND DELIVERY

Delivery may require:

* Prepayment.
* Payment on Delivery.
* Platform-paid settlement.

Delivery completion and Payment completion are related but distinct.

---

# 78. PAYMENT AND LOYALTY

Loyalty may:

* Redeem rewards.
* Apply monetary value.
* Earn points after eligible settlement.

Payment shall not directly mutate Loyalty state without governed Loyalty actions.

---

# 79. PAYMENT AND PROMOTIONS

Pricing and Promotions determine the final commercial obligation before Payment.

Payment shall not recalculate Promotion eligibility.

---

# 80. PAYMENT AND BILLING

Billing may generate:

* Invoice.
* Receipt.
* Fiscal document.

Payment records settlement.

`27_Billing.md` defines the billing/document lifecycle.

---

# 81. PAYMENT AND ACCOUNTS RECEIVABLE

If immediate Payment is not required, a commercial obligation may become Account Receivable.

Payment later settles that receivable.

---

# 82. PAYMENT AND CASH MANAGEMENT

Cash Payments create physical cash custody obligations.

Cash Management owns:

* Drawer.
* Cashier custody.
* Shift settlement.
* Cash reconciliation.

---

# 83. PAYMENT RECEIPT

A Payment may generate or reference a receipt.

The receipt may include:

* Payment ID.
* Amount.
* Method.
* Timestamp.
* Order reference.

Fiscal receipt semantics belong to Billing.

---

# 84. PAYMENT CONFIRMATION

Customer-facing confirmation shall occur only after authoritative Payment state supports it.

Example:

```text
"Your payment of $540 MXN has been confirmed."
```

ECIP shall not claim success while the provider remains uncertain.

---

# 85. PAYMENT STATUS INQUIRY

ECIP should support questions such as:

```text
"Did my payment go through?"

"Why was my card declined?"

"Has my refund been processed?"

"How much do I still owe?"

"Can I pay half in cash and half by card?"
```

Responses shall use authoritative Payment evidence.

---

# 86. CONVERSATIONAL PAYMENT

Example:

```text
Customer:
"I'll pay with card."

ECIP:
1. Resolve outstanding obligation.
2. Identify supported Payment flow.
3. Initiate secure Payment action.
4. Await authoritative result.
5. Confirm success or explain failure.
```

The LLM shall not handle card credentials directly unless explicitly governed by compliant architecture.

---

# 87. PAYMENT LINK CONVERSATION

Example:

```text
Customer:
"Send me a link to pay."

ECIP:
Generate authorized Payment Request
    ↓
Payment Provider
    ↓
Secure Payment Link
    ↓
Customer completes external Payment
    ↓
Provider confirmation
    ↓
Payment status updated
```

---

# 88. PAYMENT SECURITY

Payment handling shall follow:

* Least privilege.
* Tokenization where applicable.
* Encryption.
* Secret management.
* Audit logging.
* Provider isolation.
* PCI-related requirements where applicable.

---

# 89. CARD DATA PRINCIPLE

ECIP should minimize exposure to:

* PAN.
* CVV.
* Sensitive authentication data.

Where possible, these shall remain entirely within compliant Payment-provider flows.

---

# 90. PAYMENT TOKEN

A provider token may reference a Payment Method without exposing underlying sensitive credentials.

Tokens shall be treated as sensitive security artifacts.

---

# 91. STORED PAYMENT METHOD

Where supported and legally permitted, Customers may retain reusable Payment Method references.

Typical attributes:

* Provider.
* Token reference.
* Type.
* Last four digits when permitted.
* Brand.
* Expiration metadata.
* Status.

ECIP shall not store underlying card secrets.

---

# 92. PAYMENT CONSENT

A Customer shall understand when a Payment is being initiated.

AI shall not create unintended charges based merely on inferred Customer intent.

---

# 93. CUSTOMER CONFIRMATION

Material Payment actions should have explicit confirmation where appropriate.

Example:

```text
"Charge $1,250 MXN to the card ending in 4821?"
```

---

# 94. RECURRING PAYMENT

Future commercial models may include:

* Membership.
* Subscription.
* Meal plan.

Recurring Payment authorization shall be explicit and separately governed.

---

# 95. PAYMENT PROVIDER

A `PaymentProvider` represents an external financial processor.

Typical attributes:

* Provider ID
* Name
* Connector
* Supported methods
* Supported currencies
* Service status
* Capabilities

---

# 96. PAYMENT PROVIDER CAPABILITIES

Capabilities may include:

* Create charge.
* Authorize.
* Capture.
* Refund.
* Void.
* Payment Link.
* Webhook notifications.
* Settlement reports.

Provider capabilities shall be normalized behind connectors.

---

# 97. PROVIDER HEALTH

Suggested status:

```text
OPERATIONAL

DEGRADED

UNAVAILABLE
```

A degraded provider may affect available Payment Methods.

---

# 98. PAYMENT FALLBACK PROVIDER

Where configured, the platform may use another authorized provider.

Fallback shall consider:

* Method.
* Currency.
* Cost.
* Health.
* Policy.

It shall not create duplicate charges.

---

# 99. PROVIDER WEBHOOK

External Payment providers may send status events asynchronously.

Webhook processing shall be:

* Authenticated.
* Idempotent.
* Auditable.
* Replay-safe where applicable.

---

# 100. OUT-OF-ORDER PAYMENT EVENTS

Example:

```text
SETTLED event
arrives before
CAPTURED event
```

Runtime logic shall preserve valid business state.

---

# 101. PAYMENT SYNCHRONIZATION

Synchronization may include:

* Payment status.
* Refund status.
* Settlement status.
* Dispute status.

Synchronization shall be idempotent and observable.

---

# 102. PAYMENT SOURCE OF TRUTH

Authority may vary by state.

Example:

```text
Order:
Commercial obligation authority

Payment Provider:
External transaction authority

Cash Register:
Cash settlement evidence

ECIP:
Payment orchestration and intelligence
```

Ownership shall be explicit.

---

# 103. EXTERNAL PAYMENT MAPPING

Example:

```text
ECIP Payment:
PAY-10552

Provider:
CHG-882201

POS:
PAYMENT-5442
```

Canonical Payment identity shall remain internal.

---

# 104. PAYMENT RECONCILIATION

A `PaymentReconciliation` compares internal Payment records with external settlement evidence.

Potential sources:

* Payment Provider report.
* Bank settlement.
* POS.
* Cash Register.

---

# 105. RECONCILIATION STATUS

Suggested values:

```text
MATCHED

PARTIAL_MATCH

UNMATCHED

MISMATCH

UNDER_REVIEW

RESOLVED
```

---

# 106. RECONCILIATION DISCREPANCY

Examples:

* Internal Payment says settled, provider does not.
* Provider reports Payment not known internally.
* Amount differs.
* Refund exists externally but not internally.
* Duplicate settlement.

---

# 107. SETTLEMENT

Provider Settlement represents transfer of funds to the restaurant or merchant account.

A Payment may be customer-paid before merchant settlement completes.

These states shall remain distinct.

---

# 108. PROVIDER SETTLEMENT BATCH

Providers may group Payments into settlement batches.

Typical attributes:

* Settlement Batch ID
* Provider
* Settlement date
* Gross amount
* Fees
* Refunds
* Net amount
* Payments included
* Status

---

# 109. PAYMENT FEES

Provider fees should remain traceable for:

* Profitability.
* Channel cost analysis.
* Reconciliation.

---

# 110. NET PAYMENT VALUE

Conceptually:

```text
Gross Settled Amount
-
Provider Fees
-
Refunds
-
Chargebacks
=
Net Payment Value
```

Exact accounting belongs to financial systems.

---

# 111. CASH RECONCILIATION

Cash Payments may be reconciled against:

* POS Payments.
* Cash Register balance.
* Shift settlement.

Detailed process belongs to `28_Cash_Management.md`.

---

# 112. PAYMENT ANOMALY

Possible anomaly signals include:

* Repeated failed attempts.
* Duplicate Payments.
* Unusually high Refund rate.
* Payment outside normal business flow.
* Repeated manual Payment adjustments.
* Unexpected provider mismatch.

Anomaly is not proof of fraud.

---

# 113. PAYMENT METRICS

Potential metrics include:

* Payment success rate.
* Payment failure rate.
* Payment method mix.
* Average Payment value.
* Refund rate.
* Chargeback rate.
* Provider failure rate.
* Payment processing latency.
* Reconciliation discrepancy rate.

---

# 114. PAYMENT SUCCESS RATE

Conceptually:

```text
Successful Payments
/
Valid Payment Attempts
```

The exact denominator shall be defined consistently.

---

# 115. PAYMENT CONVERSION

Conversational Payment flows may track:

```text
Payment Requested
→ Payment Initiated
→ Payment Completed
```

Drop-off may indicate UX or provider issues.

---

# 116. PAYMENT METHOD MIX

Analysis may reveal:

* Cash share.
* Card share.
* Digital wallet share.
* Corporate account share.

This supports operational and financial planning.

---

# 117. PROVIDER PERFORMANCE

Potential measures:

* Authorization success.
* Processing latency.
* Outage frequency.
* Refund processing.
* Settlement delay.
* Cost.

---

# 118. PAYMENT COST INTELLIGENCE

Payment method profitability may consider:

* Provider fee.
* Cash handling cost.
* Refund rate.
* Chargeback risk.

This is analytical.

---

# 119. EXECUTIVE PAYMENT INTELLIGENCE

Potential KPIs include:

* Gross Payments.
* Net Payments.
* Cash vs digital mix.
* Refund rate.
* Chargeback value.
* Failed Payment value.
* Reconciliation variance.
* Provider fees.
* Outstanding obligations.

---

# 120. AI PAYMENT ASSISTANCE

AI may assist with:

* Explaining Payment status.
* Identifying failed Attempts.
* Summarizing reconciliation discrepancies.
* Recommending another supported Payment Method.
* Preparing Refund requests.
* Detecting anomalous patterns.

---

# 121. AI AUTHORITY LIMIT

AI shall not:

* Invent Payment success.
* Handle sensitive card credentials outside approved flows.
* Create unauthorized charges.
* Issue unauthorized Refunds.
* Alter settled amounts.
* Ignore Payment disputes.
* Mark cash as received without authoritative evidence.
* Reconcile financial discrepancies by guesswork.

---

# 122. PAYMENT ACTION AUTHORIZATION

Sensitive actions may include:

* Charge Customer.
* Capture Authorization.
* Refund.
* Void.
* Reverse.
* Write off.
* Manual adjustment.

Each shall use explicit Action Authorization appropriate to risk.

---

# 123. MANUAL PAYMENT ADJUSTMENT

A `PaymentAdjustment` may be required for controlled exceptions.

Typical attributes:

* Payment
* Previous state
* New state
* Amount impact
* Reason
* Actor
* Approval
* Evidence

Manual adjustments shall be rare and auditable.

---

# 124. PAYMENT INCIDENT

Examples:

* Provider outage.
* Duplicate charging.
* Widespread failures.
* Cash discrepancy.
* Refund processing failure.
* Incorrect settlement.

Material issues may create an Operational Incident.

---

# 125. CUSTOMER SERVICE RECOVERY

Payment issues may require:

* Explanation.
* Refund.
* Reversal.
* Alternative Payment flow.
* Manager escalation.
* Follow-up.

Service Recovery shall not conceal financial discrepancies.

---

# 126. PAYMENT CUSTOMER HISTORY

Customer History may record significant facts such as:

* Payment failure associated with an Order.
* Refund.
* Payment dispute.

It should not expose sensitive Payment details unnecessarily.

---

# 127. PRIVACY

Payment information is sensitive.

Access shall follow:

* Least privilege.
* Purpose limitation.
* Security classification.
* Data minimization.
* Audit logging.
* Retention requirements.

---

# 128. PAYMENT DATA RETENTION

Different Payment records may have different retention requirements.

Examples:

* Transaction evidence.
* Refund records.
* Reconciliation.
* Provider references.
* Disputes.

Retention shall follow applicable legal, financial and security requirements.

---

# 129. PAYMENT EVENTS

Initial domain events include:

```text
PaymentObligationCreated
PaymentObligationUpdated
PaymentObligationSettled

PaymentRequestCreated
PaymentRequestExpired
PaymentRequestCancelled

PaymentCreated

PaymentAttemptCreated
PaymentAttemptStarted
PaymentAttemptSucceeded
PaymentAttemptFailed
PaymentAttemptDeclined
PaymentAttemptTimedOut

PaymentAuthorizationRequested
PaymentAuthorized
PaymentAuthorizationDeclined
PaymentAuthorizationExpired
PaymentAuthorizationVoided

PaymentCaptureRequested
PaymentCaptured
PaymentCaptureFailed

PaymentSettled
PaymentPartiallySettled

PaymentFailed
PaymentCancelled

PartialPaymentRecorded
SplitPaymentCreated

DepositPaymentReceived
DepositApplied

TipRecorded

RefundRequested
RefundApproved
RefundRejected
RefundSubmitted
RefundCompleted
RefundFailed

PaymentVoidRequested
PaymentVoided

PaymentReversalRecorded

PaymentDisputeOpened
PaymentDisputeUpdated
PaymentDisputeClosed

DuplicatePaymentDetected

PaymentProviderDegraded
PaymentProviderRecovered

PaymentReconciliationStarted
PaymentReconciliationMatched
PaymentReconciliationMismatchDetected
PaymentReconciliationResolved

PaymentSynchronizationStarted
PaymentSynchronizationCompleted
PaymentSynchronizationFailed

PaymentConflictDetected
PaymentConflictResolved
```

---

# 130. RELATIONSHIPS

```text
Customer
    MAY_MAKE Payment

Order
    CREATES PaymentObligation

DiningCheck
    MAY_CREATE PaymentObligation

Reservation
    MAY_CREATE DepositObligation

Event
    MAY_CREATE DepositObligation

Event
    MAY_CREATE FinalPaymentObligation

PaymentObligation
    MAY_BE_SETTLED_BY Payment

Payment
    HAS PaymentAttempt

PaymentAttempt
    MAY_USE PaymentProvider

Payment
    MAY_HAVE PaymentAuthorization

PaymentAuthorization
    MAY_BE_CAPTURED_BY PaymentCapture

Payment
    MAY_HAVE Refund

Payment
    MAY_HAVE PaymentDispute

Payment
    MAY_HAVE Tip

Payment
    MAY_MAP_TO ExternalEntityReference

CashPayment
    MAY_REFERENCE CashRegister

Payment
    MAY_GENERATE ReconciliationRecord

PaymentState
    CONTRIBUTES_TO OrderPaymentStatus

PaymentHistory
    CONTRIBUTES_TO FinancialIntelligence
```

---

# 131. BUSINESS RULES

The following rules apply:

1. Payment shall remain distinct from the commercial Obligation it settles.

2. A Payment may have multiple Payment Attempts.

3. Payment Attempt failure shall not erase previous or subsequent Attempts.

4. Payment success shall only be represented from authoritative evidence.

5. Payment amount and currency shall always be explicit.

6. Order Payment Status shall derive from Payment evidence rather than manual inference.

7. Partial and Split Payments shall preserve allocation.

8. Authorization, Capture and Settlement shall remain distinct where the provider supports them separately.

9. Deposit shall remain traceable to the future obligation it secures.

10. Refund shall preserve the original Payment reference.

11. Refund amount shall not exceed eligible settled value without an explicit authorized financial mechanism.

12. Void and Refund shall remain distinct.

13. AI shall not invent charges, Payment status or Refund results.

14. Sensitive Payment credentials shall not be stored as ordinary domain data.

15. Provider integrations shall use idempotency where available.

16. Duplicate Payment detection shall not automatically reverse transactions without evidence.

17. Provider Webhooks shall be authenticated and processed idempotently.

18. Uncertain Payment state shall remain explicit until resolved.

19. Customer-facing Payment confirmation shall use authoritative state.

20. Manual financial adjustments shall require explicit reason and authority.

21. Reconciliation discrepancies shall remain visible until resolved.

22. External Payment IDs shall remain integration mappings.

23. Payment security and Customer protection override convenience and sales optimization.

---

# 132. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
PaymentObligation

Payment

PaymentStatus

PaymentMethod

PaymentRequest

PaymentAttempt

PaymentAttemptStatus

CashPaymentReference

CardPaymentReference

BankTransferReference

PaymentProvider

PaymentAuthorization

PaymentCapture

PartialPayment

SplitPayment

DepositPayment

TipReference

Refund

RefundStatus

PaymentFailure

PaymentIdempotency

ExternalPaymentMapping

PaymentReconciliation

PaymentAuditHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Payment Routing Optimization

Autonomous Provider Selection

Advanced Fraud Prediction

Payment Cost Optimization

Dynamic Payment Method Incentives

Complex Recurring Billing

Advanced Chargeback Automation

Multi-Currency Treasury Optimization

Autonomous Financial Reconciliation
```

---

# 133. IMPLEMENTATION PRINCIPLE

This document defines the logical Payments Model.

It does not prescribe:

* Payment Gateway vendor.
* POS Payment implementation.
* PCI architecture.
* Database schema.
* Cash Register implementation.
* Bank integration.
* Accounting implementation.
* Fraud engine.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
PAYMENT OBLIGATION

PAYMENT REQUEST

PAYMENT

PAYMENT ATTEMPT

AUTHORIZATION

CAPTURE

SETTLEMENT

FAILURE

REFUND

VOID

REVERSAL

DISPUTE

RECONCILIATION
```

---

# 134. FINAL RULE

Before ECIP represents a financial obligation as paid, unpaid, refunded, failed or settled, it shall be able to determine:

> What commercial obligation is being settled?

> Who is the payer?

> What exact amount and currency are involved?

> Which Payment Method was selected?

> Which Payment Attempt is currently relevant?

> What authoritative provider, Cash Register or financial evidence exists?

> Was the Payment merely authorized, actually captured or finally settled?

> Is the obligation fully paid or only partially settled?

> Were multiple Payment Methods used?

> Is any Deposit already applied?

> Has any Refund, Void, Reversal or dispute affected the net financial result?

> Is the Payment status certain or still unresolved?

> Has reconciliation confirmed the internal and external records?

> Does the requested financial action require additional authorization?

> Can every material Payment event be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably communicate, execute or reason about restaurant Payments.

