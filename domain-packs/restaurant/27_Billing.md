# 27_Billing.md

**Document ID:** RDM-027
**Document Name:** Billing
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Billing Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of billing documents and fiscal-commercial evidence associated with Orders, Payments, Events, Banquets, Corporate Customers, Accounts Receivable and other restaurant transactions.

The Billing Model connects:

* Orders.
* Customers.
* Payments.
* Reservations.
* Events.
* Banquets.
* Corporate Accounts.
* Taxes.
* Discounts.
* Charges.
* Accounts Receivable.
* Fiscal Documents.
* Credit Notes.
* Rebilling.
* Billing Corrections.
* Customer History.
* Financial Intelligence.
* Executive Intelligence.

Billing shall not be treated as equivalent to Payment.

A Customer may have:

* An Order without a fiscal Invoice.
* An Invoice that is not yet paid.
* A Payment made before an Invoice is issued.
* Multiple Payments applied to one Invoice.
* Multiple Invoices associated with one broader commercial relationship.

---

# 2. OBJECTIVES

The Billing Model enables ECIP to:

* Generate billing documents.
* Support fiscal invoices.
* Support receipts.
* Support corporate billing.
* Support Order billing.
* Support Event billing.
* Support Banquet billing.
* Support partial billing.
* Support consolidated billing.
* Support tax calculation references.
* Preserve billing data.
* Handle billing corrections.
* Handle cancellation.
* Handle Credit Notes.
* Track invoice status.
* Track payment application.
* Track outstanding balances.
* Support Accounts Receivable.
* Support Customer billing requests.
* Support external fiscal providers.
* Support reconciliation.
* Preserve complete billing history.
* Support Financial and Executive Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Organization
* Commercial Obligation
* Financial Document
* Transaction
* Action
* Action Authorization
* Evidence Record
* External System
* Connector
* External Entity Reference
* Audit Event
* Context Snapshot

Restaurant-specific Billing entities remain within the Restaurant Domain Pack.

---

# 4. BILLING PRINCIPLE

The platform shall distinguish between:

```text
ORDER

COMMERCIAL OBLIGATION

BILLING DOCUMENT

FISCAL DOCUMENT

PAYMENT

ACCOUNT RECEIVABLE

CREDIT NOTE

REFUND
```

These concepts are related but not equivalent.

---

# 5. BILLING DOCUMENT

A `BillingDocument` represents a commercial or fiscal document associated with a restaurant transaction.

Typical attributes include:

* Billing Document ID
* Document type
* Customer
* Billing entity
* Source transaction
* Issue date
* Currency
* Subtotal
* Discounts
* Taxes
* Charges
* Total
* Outstanding balance
* Payment status
* Fiscal status
* External identifiers
* Version
* Status

---

# 6. BILLING DOCUMENT TYPES

Initial types may include:

```text
RECEIPT

INVOICE

FISCAL_INVOICE

CORPORATE_INVOICE

EVENT_INVOICE

BANQUET_INVOICE

CREDIT_NOTE

DEBIT_NOTE

PRO_FORMA

ACCOUNT_STATEMENT
```

The catalog shall remain configurable.

---

# 7. BILLING DOCUMENT STATUS

Suggested lifecycle:

```text
DRAFT
→ PENDING_VALIDATION
→ ISSUED
→ DELIVERED
→ PARTIALLY_PAID
→ PAID
```

Alternative states:

```text
CANCELLED
VOIDED
CORRECTED
OVERDUE
DISPUTED
```

Fiscal lifecycle may differ according to jurisdiction and provider.

---

# 8. RECEIPT

A `Receipt` represents evidence of a commercial transaction or Payment.

Typical attributes:

* Receipt ID
* Order
* Payment
* Customer
* Amount
* Currency
* Issue time
* Payment method summary
* Tax summary
* External reference

Receipt semantics may differ from fiscal Invoice semantics.

---

# 9. INVOICE

An `Invoice` represents a formal billing document requesting or evidencing payment for goods or services.

Typical attributes:

* Invoice ID
* Customer
* Billing entity
* Invoice number
* Issue date
* Due date
* Currency
* Items
* Tax
* Total
* Outstanding balance
* Status

---

# 10. FISCAL INVOICE

A `FiscalInvoice` represents a tax-recognized billing document under applicable jurisdictional requirements.

The Billing Model shall support integration with external fiscal systems where those systems are authoritative.

---

# 11. BILLING ENTITY

A `BillingEntity` represents the legal or fiscal entity issuing the Invoice.

Typical attributes:

* Legal name.
* Tax identifier.
* Fiscal address.
* Branch or establishment.
* Tax regime reference.
* Fiscal configuration.

One restaurant group may have multiple Billing Entities.

---

# 12. CUSTOMER BILLING PROFILE

A `CustomerBillingProfile` represents billing information required to issue documents.

Typical attributes may include:

* Customer or Organization reference.
* Legal name.
* Tax identifier.
* Fiscal address.
* Email.
* Tax regime or classification where applicable.
* Preferred billing usage.
* Status.
* Verification state.

Billing information shall remain separate from the general Customer Profile where appropriate.

---

# 13. CORPORATE BILLING PROFILE

Corporate Customers may require:

* Legal entity.
* Tax information.
* Purchase Order number.
* Cost center.
* Billing contact.
* Payment terms.
* Invoice instructions.

---

# 14. BILLING PROFILE VERSION

Billing information may change.

Historical Invoices shall retain the billing data used when they were issued.

Current Customer billing changes shall not rewrite historical documents.

---

# 15. SOURCE TRANSACTION

A Billing Document may originate from:

```text
ORDER

DINING_CHECK

EVENT

BANQUET

RESERVATION_DEPOSIT

DELIVERY

CORPORATE_ACCOUNT

ACCOUNT_RECEIVABLE

MANUAL_AUTHORIZED_CHARGE
```

The source shall always remain explicit.

---

# 16. BILLABLE ITEM

A `BillableItem` represents one commercial line included in a Billing Document.

Typical attributes:

* Product or Service reference.
* Description.
* Quantity.
* Unit price.
* Discount.
* Tax.
* Line total.
* Source Order Item.

---

# 17. PRODUCT SNAPSHOT

Billing documents shall preserve enough historical data to reconstruct what was billed.

Examples:

* Product name.
* Quantity.
* Unit price.
* Tax.
* Discount.
* Description.

Current Product changes shall not alter issued documents.

---

# 18. BILLING SUMMARY

Conceptually:

```text
ITEM SUBTOTAL
+
SERVICE CHARGES
+
DELIVERY CHARGES
+
OTHER AUTHORIZED CHARGES
-
DISCOUNTS
-
PROMOTIONS
+
TAXES
=
DOCUMENT TOTAL
```

The calculation shall be deterministic.

---

# 19. BILLING CURRENCY

Every Billing Document shall explicitly identify currency.

Where source transactions occur in different currencies, conversion shall preserve:

* Original currency.
* Billing currency.
* Exchange rate.
* Exchange-rate source.
* Effective date.

---

# 20. TAX

Billing may consume tax calculation from:

* POS.
* ERP.
* Fiscal system.
* Tax engine.

The Billing Model shall preserve the authoritative result.

It shall not permit LLM-generated tax values.

---

# 21. TAX COMPONENT

A Billing Document may contain one or more tax components.

Typical attributes:

* Tax type.
* Tax rate.
* Tax base.
* Tax amount.
* Jurisdiction.
* Exemption reference where applicable.

---

# 22. TAX-INCLUSIVE PRICING

Where Prices include tax, Billing shall preserve the decomposition required by applicable fiscal logic.

---

# 23. TAX-EXCLUSIVE PRICING

Where tax is added separately, the final Billing total shall remain consistent with the underlying transaction.

---

# 24. TAX EXEMPTION

Tax exemptions shall require explicit evidence or configuration.

AI shall never invent tax exemption eligibility.

---

# 25. BILLING DISCOUNT

A Billing Document may reflect Discounts already determined by Pricing and Promotions.

Billing shall not independently create new promotional logic.

---

# 26. BILLING CHARGE

Charges may include:

* Delivery.
* Service.
* Packaging.
* Event.
* Overtime.
* Other authorized charges.

Each shall remain traceable to the commercial source.

---

# 27. TIP ON BILLING DOCUMENT

Tip representation may depend on jurisdiction and billing policy.

Tip remains semantically distinct from mandatory Service Charges.

---

# 28. INVOICE CREATION

Typical flow:

```text
Billable Transaction
    ↓
Billing Data Validation
    ↓
Tax / Commercial Validation
    ↓
Invoice Draft
    ↓
Fiscal Processing if required
    ↓
Issued Invoice
```

---

# 29. BILLING DATA VALIDATION

Before issuing an Invoice, ECIP should validate:

* Customer billing information.
* Billing Entity.
* Source transaction.
* Amount.
* Currency.
* Tax data.
* Required legal fields.
* Existing Invoice state.

---

# 30. BILLING REQUEST

A `BillingRequest` represents a Customer or Employee request to issue a Billing Document.

Typical attributes:

* Request ID.
* Customer.
* Source transaction.
* Requested document type.
* Billing profile.
* Requested delivery channel.
* Status.

---

# 31. CUSTOMER BILLING REQUEST

Example:

```text
Customer:
"Can you invoice order 4421?"
```

ECIP should:

1. Resolve Customer.
2. Resolve Order.
3. Verify authorization.
4. Identify required billing data.
5. Validate whether Invoice already exists.
6. Create authorized Billing Request.
7. Route through fiscal process.
8. Return authoritative result.

---

# 32. BILLING REQUEST STATUS

Suggested lifecycle:

```text
CREATED
→ VALIDATING
→ READY
→ PROCESSING
→ COMPLETED
```

Alternative states:

```text
MISSING_INFORMATION
REJECTED
FAILED
CANCELLED
```

---

# 33. MISSING BILLING DATA

Missing information may include:

* Tax identifier.
* Fiscal name.
* Email.
* Fiscal address.
* Tax classification.

The system should request only the required missing information.

---

# 34. BILLING DUPLICATE DETECTION

Before issuing a new Invoice, ECIP should determine whether the same commercial transaction has already been billed.

Duplicate issuance may create fiscal and accounting problems.

---

# 35. BILLING IDEMPOTENCY

Invoice creation and external fiscal requests shall use idempotency where supported.

This reduces duplicate fiscal documents caused by retries.

---

# 36. INVOICE NUMBER

Invoice numbering may be controlled by:

* Fiscal authority.
* ERP.
* POS.
* External fiscal provider.
* Internal billing system.

ECIP shall not independently fabricate authoritative fiscal numbering.

---

# 37. DOCUMENT ISSUE DATE

Issue date shall reflect the authoritative time established by the billing or fiscal system.

---

# 38. DUE DATE

Invoices with credit terms may define:

* Due date.
* Payment terms.
* Grace period.

Immediate restaurant transactions may have no meaningful future due date.

---

# 39. PAYMENT TERMS

Examples:

```text
DUE_IMMEDIATELY

NET_7

NET_15

NET_30

NET_60

CUSTOM_CONTRACT_TERMS
```

Terms may derive from Corporate Account or Event agreement.

---

# 40. INVOICE PAYMENT STATUS

Suggested derived states:

```text
UNPAID

PARTIALLY_PAID

PAID

OVERPAID

REFUNDED

PARTIALLY_REFUNDED
```

These shall derive from Payment allocations.

---

# 41. PAYMENT APPLICATION

A `PaymentApplication` links a Payment to a Billing Document or Account Receivable.

Typical attributes:

* Payment.
* Invoice.
* Amount applied.
* Application date.
* Currency.
* Status.

---

# 42. MULTIPLE PAYMENTS PER INVOICE

Example:

```text
Invoice:
$20,000

Deposit:
$5,000

Second Payment:
$10,000

Final Payment:
$5,000
```

All allocations shall remain traceable.

---

# 43. ONE PAYMENT ACROSS MULTIPLE INVOICES

Corporate Customers may submit one Payment covering several Invoices.

Allocation shall remain explicit.

---

# 44. OVERPAYMENT

If Payment exceeds an Invoice balance, the excess shall not be silently lost.

Possible outcomes:

* Customer credit.
* Apply to another Invoice.
* Refund.
* Manual review.

---

# 45. UNDERPAYMENT

Partial settlement shall leave an explicit outstanding balance.

---

# 46. OUTSTANDING BALANCE

Conceptually:

```text
Outstanding Balance
=
Invoice Total
-
Applied Settled Payments
-
Authorized Credits
```

---

# 47. ACCOUNTS RECEIVABLE

An issued Invoice with unpaid future obligation may generate or update Accounts Receivable.

Accounts Receivable remains financially authoritative for collections state.

---

# 48. ACCOUNT RECEIVABLE RELATIONSHIP

Conceptually:

```text
Invoice
    ↓
Account Receivable
    ↓
Payment Application
    ↓
Settlement
```

---

# 49. CORPORATE ACCOUNT

A Corporate Customer may maintain:

* Credit limit.
* Payment terms.
* Outstanding balance.
* Past-due balance.

Billing consumes these policies but does not redefine Corporate Customer identity.

---

# 50. CREDIT LIMIT

Credit-limit decisions belong to financial policy.

AI shall not independently extend credit beyond authorized thresholds.

---

# 51. CONSOLIDATED BILLING

Multiple transactions may be combined into one Invoice where business and fiscal policy allow.

Examples:

* Weekly corporate lunches.
* Monthly corporate account.
* Event plus additional consumption.

---

# 52. CONSOLIDATED BILLING PERIOD

Possible periods:

* Daily.
* Weekly.
* Monthly.
* Contract-defined.

---

# 53. PARTIAL BILLING

A large Event or Contract may be billed in stages.

Example:

```text
Stage 1:
Deposit

Stage 2:
Pre-event installment

Stage 3:
Final settlement
```

Each Billing Document shall reference its commercial basis.

---

# 54. EVENT BILLING

Event Billing may include:

* Package.
* Guest count.
* Additional consumption.
* Overtime.
* Equipment.
* Service.
* Taxes.
* Deposit application.

---

# 55. BANQUET BILLING

Banquet Billing may require detailed reconciliation between:

* Contracted amount.
* Actual attendance.
* Additional Products.
* Event changes.
* Deposits.

---

# 56. RESERVATION BILLING

Reservations may create Billing for:

* Deposit.
* Cancellation fee.
* No-show charge where legally and contractually permitted.

---

# 57. DELIVERY BILLING

Delivery Billing may include:

* Products.
* Delivery fee.
* Packaging.
* Discounts.
* Tax.

---

# 58. THIRD-PARTY PLATFORM BILLING

Orders originating from Delivery Platforms may have:

* Customer-facing platform document.
* Restaurant internal sale record.
* Platform commission.
* Net receivable.

The Billing Model shall distinguish these financial relationships.

---

# 59. BILLING DOCUMENT DELIVERY

Billing documents may be delivered through:

* Email.
* Customer portal.
* Download.
* Print.
* Messaging channel where authorized.

Document transmission shall preserve security and privacy.

---

# 60. BILLING EMAIL

An Invoice may be sent to the Customer's verified billing email.

The system shall avoid exposing billing documents to unauthorized recipients.

---

# 61. BILLING DOCUMENT ACCESS

Access may require:

* Authenticated Customer.
* Secure token.
* Employee permission.

Billing Documents contain sensitive financial and personal information.

---

# 62. BILLING CORRECTION

A `BillingCorrection` represents a governed change required after document creation.

Possible reasons:

* Incorrect billing data.
* Wrong Product description.
* Incorrect amount.
* Incorrect tax information.
* Wrong Customer.
* Duplicate Invoice.

---

# 63. IMMUTABILITY PRINCIPLE

Issued fiscal documents should not simply be edited in place when legal or fiscal rules require cancellation and replacement.

The platform shall preserve historical evidence.

---

# 64. INVOICE CANCELLATION

An Invoice may require cancellation.

Typical attributes:

* Invoice.
* Cancellation reason.
* Requested by.
* Approval.
* External fiscal result.
* Cancellation date.
* Status.

---

# 65. CANCELLATION STATUS

Suggested lifecycle:

```text
REQUESTED
→ PROCESSING
→ CANCELLED
```

Alternative states:

```text
REJECTED
FAILED
PENDING_CUSTOMER_ACCEPTANCE
```

where applicable.

---

# 66. REBILLING

A corrected commercial transaction may require:

```text
Original Invoice
    ↓
Cancel / Credit
    ↓
Corrected Billing Data
    ↓
New Invoice
```

All documents shall remain linked.

---

# 67. CREDIT NOTE

A `CreditNote` reduces a previously billed amount or recognizes a credit.

Typical reasons:

* Product return.
* Refund.
* Billing correction.
* Price adjustment.
* Event cancellation.
* Service Recovery.

---

# 68. CREDIT NOTE ATTRIBUTES

Typical attributes:

* Credit Note ID.
* Original Invoice.
* Amount.
* Currency.
* Reason.
* Issue date.
* Fiscal status.
* External identifier.

---

# 69. PARTIAL CREDIT NOTE

A Credit Note may affect only part of the original Invoice.

The remaining Invoice balance shall remain explicit.

---

# 70. DEBIT NOTE

Where applicable, a Debit Note may increase a commercial billing obligation.

Use shall follow financial and jurisdictional policy.

---

# 71. REFUND VS CREDIT NOTE

The model shall distinguish:

```text
REFUND
=
movement of financial value back to payer

CREDIT NOTE
=
billing/accounting document reducing billed value
```

A transaction may require both.

---

# 72. BILLING DISPUTE

A `BillingDispute` represents Customer disagreement with an Invoice.

Possible reasons:

* Incorrect amount.
* Duplicate charge.
* Wrong Product.
* Tax problem.
* Missing discount.
* Contract mismatch.

---

# 73. BILLING DISPUTE STATUS

Suggested lifecycle:

```text
OPEN
→ UNDER_REVIEW
→ RESOLUTION_PROPOSED
→ RESOLVED
→ CLOSED
```

---

# 74. BILLING DISPUTE EVIDENCE

Relevant evidence may include:

* Order.
* Quote.
* Contract.
* Price.
* Promotion.
* Event changes.
* Payment.
* Invoice.

---

# 75. BILLING ADJUSTMENT AUTHORIZATION

Billing corrections with financial impact may require approval.

AI shall not arbitrarily alter issued billing documents.

---

# 76. TAX AUTHORITY INTEGRATION

Where required, fiscal documents may be processed through:

* Government-authorized system.
* Certified fiscal provider.
* ERP fiscal module.

ECIP shall preserve external result and identifiers.

---

# 77. FISCAL PROVIDER

A `FiscalProvider` represents an external system responsible for fiscal document generation or validation.

Typical attributes:

* Provider ID.
* Connector.
* Supported document types.
* Service status.
* Capabilities.

---

# 78. FISCAL PROVIDER STATUS

Suggested values:

```text
OPERATIONAL

DEGRADED

UNAVAILABLE
```

---

# 79. FISCAL PROVIDER FAILURE

A provider outage may prevent fiscal document issuance while the commercial transaction itself remains valid.

These states shall remain distinct.

---

# 80. PENDING FISCALIZATION

A Billing Document may temporarily exist in a state such as:

```text
PENDING_FISCALIZATION
```

until authoritative fiscal processing completes.

---

# 81. FISCAL IDENTIFIER

External fiscal identifiers may include:

* UUID.
* Folio.
* Series.
* Tax authority reference.
* Certification reference.

These shall never be fabricated by AI.

---

# 82. BILLING SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Commercial transaction

ERP:
Accounts Receivable

Fiscal Provider:
Fiscal Invoice authority

Payment Provider:
Payment authority

ECIP:
Billing orchestration and intelligence
```

Ownership shall be explicitly configured.

---

# 83. EXTERNAL BILLING MAPPING

Example:

```text
ECIP Invoice:
INV-1025

ERP:
AR-88442

Fiscal Provider:
UUID-...

POS:
DOC-544
```

Canonical ECIP identity remains separate from external IDs.

---

# 84. BILLING SYNCHRONIZATION

Synchronization may include:

* Invoice creation.
* Fiscal result.
* Payment status.
* Cancellation.
* Credit Note.
* Accounts Receivable state.

It shall be idempotent and observable.

---

# 85. BILLING CONFLICT

Possible conflicts include:

```text
ECIP:
Invoice issued

Fiscal Provider:
Issuance failed
```

or:

```text
ERP:
Invoice unpaid

Payment System:
Payment settled
```

Conflicts shall remain explicit until authoritative reconciliation.

---

# 86. BILLING RECONCILIATION

A `BillingReconciliation` may compare:

* Order totals.
* Invoice totals.
* Payment applications.
* Accounts Receivable.
* Fiscal provider records.

---

# 87. ORDER-TO-INVOICE RECONCILIATION

Conceptually:

```text
Order Commercial Total

vs

Invoice Total
```

Differences shall be explainable.

---

# 88. INVOICE-TO-PAYMENT RECONCILIATION

Conceptually:

```text
Invoice Balance

vs

Applied Payments
```

---

# 89. FISCAL RECONCILIATION

Internal billing records may be compared with external fiscal records to detect:

* Missing documents.
* Duplicate documents.
* Cancelled documents.
* Amount mismatches.

---

# 90. BILLING ANOMALY

Potential anomaly signals include:

* Duplicate Invoice.
* Unusual cancellation.
* Repeated Credit Notes.
* Invoice total mismatch.
* Billing after unusual delay.
* Customer billing profile changed immediately before issuance.

These are risk signals, not proof of misconduct.

---

# 91. BILLING METRICS

Potential metrics include:

* Total billed revenue.
* Number of Invoices.
* Average Invoice amount.
* Unpaid Invoice value.
* Overdue value.
* Cancellation rate.
* Credit Note rate.
* Billing error rate.
* Average issuance time.

---

# 92. BILLING CONVERSION

Potential flow:

```text
Billing Requested
→ Billing Data Complete
→ Document Issued
→ Document Delivered
```

Failures may reveal UX or process friction.

---

# 93. BILLING DELAY

Billing delay may be measured between:

```text
Commercial Transaction Completion

and

Billing Document Issuance
```

where relevant.

---

# 94. ACCOUNTS RECEIVABLE INTELLIGENCE

Billing may contribute to:

* Outstanding balance.
* Aging.
* Customer payment behavior.
* Corporate account risk.

Detailed Receivable management may be extended in a dedicated financial domain if needed.

---

# 95. AGING

Potential Accounts Receivable aging categories:

```text
CURRENT

1–30 DAYS

31–60 DAYS

61–90 DAYS

90+ DAYS
```

The exact bands remain configurable.

---

# 96. OVERDUE INVOICE

An Invoice becomes overdue according to its due date and Payment state.

The platform should preserve:

* Days overdue.
* Outstanding amount.
* Customer.
* Responsible account.

---

# 97. COLLECTION FOLLOW-UP

Where authorized, ECIP may support:

* Payment reminder.
* Statement delivery.
* Human escalation.

Collection activity shall respect business and legal policy.

---

# 98. CUSTOMER BILLING HISTORY

Customer History may reference significant billing events such as:

* Invoice issuance.
* Billing dispute.
* Correction.
* Corporate payment behavior.

Sensitive fiscal data shall not be unnecessarily exposed in general Customer contexts.

---

# 99. BILLING PRIVACY

Billing data may contain:

* Tax identifiers.
* Addresses.
* Financial amounts.
* Corporate information.

Access shall follow:

* Least privilege.
* Purpose limitation.
* Tenant isolation.
* Audit logging.
* Retention policy.

---

# 100. BILLING RETENTION

Billing records may require long-term retention according to:

* Tax law.
* Accounting requirements.
* Tenant policy.
* Contractual requirements.

Retention shall be configurable and jurisdiction-aware.

---

# 101. CONVERSATIONAL BILLING

ECIP should support requests such as:

```text
"Can you send me my invoice?"

"I gave you the wrong tax information."

"Has my invoice been cancelled?"

"Why does the invoice show a different amount?"

"Can you invoice the company instead of me?"

"Which invoices are still unpaid?"
```

Responses shall use authoritative billing state.

---

# 102. BILLING DATA CLARIFICATION

ECIP may ask for missing information required to complete a Billing Request.

It shall not ask again for valid information already available and authorized for reuse.

---

# 103. BILLING ASSISTANCE

AI may assist with:

* Summarizing billing requirements.
* Identifying missing fields.
* Explaining Invoice status.
* Detecting likely duplicates.
* Summarizing disputes.
* Preparing correction requests.

---

# 104. AI AUTHORITY LIMIT

AI shall not:

* Invent fiscal identifiers.
* Invent tax values.
* Alter issued fiscal documents directly.
* Cancel fiscal documents without authorization.
* Generate unsupported Credits.
* Mark an Invoice paid without Payment evidence.
* Change Customer tax identity silently.
* Resolve fiscal conflicts by guesswork.

---

# 105. BILLING ACTION AUTHORIZATION

Sensitive actions may include:

* Issue Invoice.
* Cancel Invoice.
* Create Credit Note.
* Correct Billing Profile.
* Rebill.
* Write off receivable.
* Override billing exception.

Each shall use appropriate Action Authorization.

---

# 106. BILLING INCIDENT

Examples:

* Fiscal provider outage.
* Mass duplicate Invoice generation.
* Tax-calculation defect.
* Incorrect Customer billing mapping.
* Invoice/Payment reconciliation failure.

Material issues may create Operational Incidents.

---

# 107. BILLING SERVICE RECOVERY

Billing errors may require:

* Correction.
* Cancellation and rebilling.
* Credit Note.
* Refund coordination.
* Human follow-up.

The financial and fiscal state shall remain transparent.

---

# 108. BILLING EVENTS

Initial domain events include:

```text
BillingRequestCreated
BillingRequestValidated
BillingRequestMissingInformation
BillingRequestRejected
BillingRequestCompleted

BillingDocumentCreated
BillingDocumentValidated
BillingDocumentIssued
BillingDocumentDelivered

InvoiceCreated
InvoiceIssued
InvoicePartiallyPaid
InvoicePaid
InvoiceOverdue
InvoiceDisputed

FiscalizationRequested
FiscalizationCompleted
FiscalizationFailed

BillingProfileCreated
BillingProfileUpdated
BillingProfileVerified

BillingDuplicateDetected

PaymentAppliedToInvoice
PaymentApplicationAdjusted

CreditNoteRequested
CreditNoteApproved
CreditNoteIssued
CreditNoteFailed

DebitNoteIssued

InvoiceCancellationRequested
InvoiceCancellationApproved
InvoiceCancelled
InvoiceCancellationFailed

BillingCorrectionRequested
BillingCorrectionApproved
BillingCorrectionCompleted

InvoiceRebillingStarted
InvoiceRebillingCompleted

BillingDisputeOpened
BillingDisputeResolved

BillingReconciliationStarted
BillingReconciliationMatched
BillingReconciliationMismatchDetected
BillingReconciliationResolved

BillingSynchronizationStarted
BillingSynchronizationCompleted
BillingSynchronizationFailed

BillingConflictDetected
BillingConflictResolved
```

---

# 109. RELATIONSHIPS

```text
Customer
    MAY_HAVE CustomerBillingProfile

Organization
    MAY_HAVE CorporateBillingProfile

BillingEntity
    ISSUES BillingDocument

Order
    MAY_GENERATE BillingDocument

DiningCheck
    MAY_GENERATE BillingDocument

Reservation
    MAY_GENERATE BillingDocument

Event
    MAY_GENERATE BillingDocument

BillingDocument
    CONTAINS BillableItem

BillingDocument
    MAY_REFERENCE PaymentObligation

Invoice
    MAY_CREATE AccountReceivable

Payment
    MAY_BE_APPLIED_TO Invoice

Invoice
    MAY_HAVE CreditNote

Invoice
    MAY_BE_CANCELLED_BY BillingCancellation

Invoice
    MAY_BE_REPLACED_BY CorrectedInvoice

BillingDocument
    MAY_MAP_TO ExternalEntityReference

FiscalProvider
    MAY_PROCESS BillingDocument

BillingHistory
    CONTRIBUTES_TO FinancialIntelligence
```

---

# 110. BUSINESS RULES

The following rules apply:

1. Billing shall remain distinct from Payment.

2. An Order may exist without an Invoice.

3. An Invoice may exist without full Payment.

4. Payment status shall derive from authoritative Payment applications.

5. Billing Documents shall preserve historical Product, Price and tax information.

6. Current Customer billing profile changes shall not rewrite issued documents.

7. Fiscal identifiers shall only come from authoritative systems.

8. Issued fiscal documents shall not be silently edited where cancellation/replacement is required.

9. Credit Note and Refund shall remain separate concepts.

10. Duplicate Invoice prevention shall use idempotency where possible.

11. Invoice totals shall reconcile with their source commercial transaction or preserve explainable differences.

12. Customer billing data shall be validated before fiscal issuance.

13. Sensitive billing data shall follow least-privilege access.

14. AI shall not fabricate tax, fiscal or Payment evidence.

15. Cancellation, Credit and correction actions shall require appropriate authority.

16. External Billing identifiers shall remain integration mappings.

17. Billing conflicts and reconciliation differences shall remain explicit until resolved.

18. Accounts Receivable remains authoritative for unpaid credit obligations.

19. Fiscal and accounting requirements override conversational convenience.

20. Every material Billing mutation shall be auditable.

---

# 111. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
BillingDocument

BillingDocumentType

BillingDocumentStatus

BillingEntity

CustomerBillingProfile

CorporateBillingProfile

BillingRequest

BillableItem

Invoice

InvoiceStatus

TaxReference

PaymentApplication

OutstandingBalance

CreditNote

InvoiceCancellation

BillingCorrection

RebillingReference

BillingDispute

FiscalProviderReference

ExternalBillingMapping

BillingReconciliation

BillingAuditHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Multi-Jurisdiction Billing

Autonomous Fiscal Exception Resolution

Advanced Accounts Receivable Collections

Dynamic Credit-Risk Billing Policies

AI-Based Billing Fraud Detection

Autonomous Corporate Consolidated Billing

Advanced Revenue Recognition

Multi-Currency Fiscal Optimization
```

---

# 112. IMPLEMENTATION PRINCIPLE

This document defines the logical Billing Model.

It does not prescribe:

* Fiscal provider.
* ERP.
* Accounting system.
* Tax engine.
* Database schema.
* Accounts Receivable implementation.
* Document rendering system.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
COMMERCIAL TRANSACTION

BILLING REQUEST

BILLING DOCUMENT

INVOICE

FISCAL DOCUMENT

PAYMENT OBLIGATION

PAYMENT

ACCOUNT RECEIVABLE

CREDIT NOTE

REFUND

CANCELLATION

RECONCILIATION
```

---

# 113. FINAL RULE

Before ECIP represents a transaction as correctly billed, invoiced, paid, cancelled, corrected or outstanding, it shall be able to determine:

> What commercial transaction is being billed?

> Who is the Customer and which Billing Entity is issuing the document?

> Which billing profile and tax information apply?

> What Products, Services, quantities, Prices, Discounts, Charges and Taxes compose the document?

> What total and currency are authoritative?

> Has this transaction already been billed?

> Is a fiscal document required?

> Which external fiscal identifiers or validations exist?

> What Payments have actually been applied?

> What amount remains outstanding?

> Has any Credit Note, Refund, cancellation or correction changed the financial result?

> Is the Invoice linked to Accounts Receivable?

> Is there any unresolved billing dispute, synchronization conflict or reconciliation difference?

> Does the requested Billing action require additional authority?

> Can every material Billing document, state transition and financial relationship be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably communicate, generate, modify or reason about restaurant Billing.

