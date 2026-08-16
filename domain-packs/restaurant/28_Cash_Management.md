# 28_Cash_Management.md

**Document ID:** RDM-028
**Document Name:** Cash Management
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Cash Management Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of physical cash handled by restaurant operations, from initial cash-float assignment through customer collection, cash movements, deposits, withdrawals, shift settlement, discrepancy detection, reconciliation and final custody transfer.

The Cash Management Model connects:

* Payments.
* Orders.
* Cash Registers.
* Employees.
* Shifts.
* Branches.
* Expenses.
* Refunds.
* Petty Cash.
* Deposits.
* Bank Transfers.
* Reconciliation.
* Operational Incidents.
* Audit.
* Financial Intelligence.
* Executive Intelligence.

Cash Management shall not be modeled merely as the `CASH` Payment Method.

A Cash Payment records that a financial obligation was settled in cash.

Cash Management records **where that physical cash went, who was responsible for it, how it moved and whether it reconciled correctly**.

---

# 2. OBJECTIVES

The Cash Management Model enables ECIP to:

* Manage Cash Registers.
* Manage Cash drawers.
* Manage opening cash float.
* Assign cash custody.
* Track Cash Payments.
* Track change given.
* Track cash inflows.
* Track cash outflows.
* Track petty-cash transactions.
* Track authorized withdrawals.
* Track cash deposits.
* Track register transfers.
* Track employee cash responsibility.
* Close shifts.
* Count physical cash.
* Reconcile expected and actual cash.
* Detect shortages and overages.
* Detect anomalous cash activity.
* Preserve audit evidence.
* Support multi-Branch operations.
* Support Financial Intelligence.
* Support Executive Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Asset
* Resource
* Employee
* Custody
* Action
* Action Authorization
* Financial Transaction
* Financial Event
* Evidence Record
* Workflow Instance
* Incident
* External Entity Reference
* Context Snapshot
* Audit Event

Restaurant-specific Cash Management entities remain within the Restaurant Domain Pack.

---

# 4. CASH MANAGEMENT PRINCIPLE

The platform shall distinguish between:

```text
CASH PAYMENT

CASH REGISTER

CASH DRAWER

CASH SESSION

CASH CUSTODY

CASH MOVEMENT

CASH COUNT

CASH RECONCILIATION

CASH DISCREPANCY

BANK DEPOSIT
```

These concepts shall remain independently traceable.

---

# 5. CASH REGISTER

A `CashRegister` represents an operational point where monetary transactions may be recorded and cash may be handled.

Typical attributes include:

* Cash Register ID
* Branch
* Register name
* Physical Location
* POS terminal reference
* Supported currencies
* Status
* Assigned drawer
* Current session
* External identifiers

---

# 6. CASH REGISTER STATUS

Suggested states:

```text
AVAILABLE

OPEN

CLOSED

SUSPENDED

OUT_OF_SERVICE

UNDER_RECONCILIATION
```

---

# 7. CASH DRAWER

A `CashDrawer` represents the physical or logical container that holds cash under controlled custody.

Typical attributes:

* Drawer ID
* Cash Register
* Branch
* Status
* Current custodian
* Currency
* Current session reference
* Seal or identifier where applicable

---

# 8. CASH DRAWER STATUS

Suggested states:

```text
AVAILABLE

ASSIGNED

OPEN

LOCKED

COUNTING

CLOSED

TRANSFERRED

OUT_OF_SERVICE
```

---

# 9. CASH SESSION

A `CashSession` represents a bounded period during which cash is handled under defined responsibility.

Typical attributes:

* Cash Session ID
* Cash Register
* Cash Drawer
* Branch
* Employee
* Opening time
* Closing time
* Opening float
* Expected closing balance
* Counted closing balance
* Difference
* Status
* Shift reference

---

# 10. CASH SESSION LIFECYCLE

Suggested lifecycle:

```text
CREATED
→ OPENING_COUNT
→ OPEN
→ CLOSING_REQUESTED
→ CLOSING_COUNT
→ RECONCILING
→ CLOSED
```

Alternative states:

```text
SUSPENDED
CANCELLED
UNDER_REVIEW
```

---

# 11. CASH CUSTODY

`CashCustody` represents responsibility for physical cash during a defined period.

Typical attributes:

* Custody ID
* Employee
* Cash Session
* Cash Drawer
* Start time
* End time
* Amount or scope
* Transfer evidence
* Status

Cash shall not become anonymously owned by "the register."

Responsibility shall remain attributable.

---

# 12. CUSTODY TRANSFER

A Cash Drawer or cash amount may transfer between authorized Employees.

Typical flow:

```text
Current Custodian
    ↓
Count / Verification
    ↓
Transfer Record
    ↓
New Custodian
```

The transfer shall preserve:

* Previous custodian.
* New custodian.
* Time.
* Amount.
* Verification.
* Acceptance.

---

# 13. OPENING CASH FLOAT

An `OpeningFloat` represents cash placed in a Cash Drawer at session start to support change.

Typical attributes:

* Cash Session
* Currency
* Amount
* Denomination breakdown where used
* Source
* Employee
* Approved by
* Timestamp

---

# 14. OPENING COUNT

The opening float should be physically confirmed where policy requires.

Conceptually:

```text
Authorized Opening Float

vs

Actual Counted Opening Cash
```

Any difference shall be resolved before normal operations.

---

# 15. CASH DENOMINATION

Where operationally useful, cash may be represented by denomination.

Example:

```text
$1,000 × 2

$500 × 5

$200 × 10

$100 × 15

$50 × 10
```

This can support:

* Accurate counts.
* Change management.
* Deposit preparation.

---

# 16. DENOMINATION COUNT

A `CashDenominationCount` may include:

* Currency.
* Denomination.
* Quantity.
* Subtotal.

The sum produces the physical cash count.

---

# 17. CASH PAYMENT

Cash Payments are defined commercially in `26_Payments.md`.

Cash Management consumes confirmed Cash Payment evidence.

Typical relationship:

```text
Order / Check
    ↓
Cash Payment
    ↓
Cash Session
    ↓
Physical Cash Balance
```

---

# 18. CASH RECEIPT

When a Customer pays cash, the register should record:

* Payment amount due.
* Cash amount received.
* Change given.
* Net cash retained.
* Employee.
* Session.
* Time.

---

# 19. CHANGE

Conceptually:

```text
Change Due
=
Cash Received
-
Amount Settled
```

Change shall be calculated deterministically.

AI shall not serve as the authoritative arithmetic engine for cash settlement.

---

# 20. CASH OVERPAYMENT FOR CHANGE

Example:

```text
Order:
$340

Cash received:
$500

Change:
$160
```

The Cash Drawer increases by the amount actually retained:

```text
$340
```

not by the full $500.

---

# 21. CASH MOVEMENT

A `CashMovement` represents any controlled increase, decrease or transfer of physical cash.

Typical attributes:

* Cash Movement ID
* Cash Session
* Movement type
* Amount
* Currency
* Source
* Destination
* Reason
* Related transaction
* Employee
* Authorized by
* Timestamp
* Status

---

# 22. CASH MOVEMENT TYPES

Initial types may include:

```text
OPENING_FLOAT

CUSTOMER_PAYMENT

REFUND

CASH_IN

CASH_OUT

PETTY_CASH_EXPENSE

SAFE_DROP

REGISTER_TRANSFER

BANK_DEPOSIT_PREPARATION

BANK_DEPOSIT

CHANGE_FUND_ADJUSTMENT

CASH_CORRECTION
```

---

# 23. CASH IN

A `CashIn` is an authorized addition to the Cash Drawer unrelated to a direct Customer Payment.

Examples:

* Additional change float.
* Transfer from another register.
* Return of unused petty cash.

Every Cash In shall preserve its source.

---

# 24. CASH OUT

A `CashOut` is an authorized removal of cash from the Drawer.

Examples:

* Safe drop.
* Petty Cash expense.
* Refund.
* Transfer.
* Bank deposit preparation.

Every Cash Out shall preserve its reason and destination.

---

# 25. SAFE DROP

A `SafeDrop` removes excess cash from an active drawer and transfers it into a secured cash location.

Typical attributes:

* Cash Session
* Amount
* Currency
* Employee
* Secure destination
* Verification
* Timestamp

This reduces theft and operational exposure.

---

# 26. CASH SAFE

A `CashSafe` represents a secure storage location for physical cash.

Typical attributes:

* Safe ID
* Branch
* Location
* Status
* Access policy
* Current custody
* Supported currencies

---

# 27. SAFE DEPOSIT

Cash transferred from a Register to a Safe shall create corresponding movements:

```text
Cash Drawer
    ↓
Safe Drop
    ↓
Cash Safe
```

The movement shall balance.

---

# 28. REGISTER TRANSFER

Cash may be transferred from one Register to another.

Example:

```text
Register A
needs small bills

Register B
transfers $1,000
```

This requires:

* Cash Out from source.
* Cash In to destination.
* Matching transfer reference.

---

# 29. CASH TRANSFER LIFECYCLE

Suggested states:

```text
REQUESTED
→ APPROVED
→ RELEASED
→ RECEIVED
→ COMPLETED
```

Alternative states:

```text
REJECTED
CANCELLED
DISPUTED
```

---

# 30. PETTY CASH

A `PettyCashFund` represents controlled cash reserved for small operational expenses.

Typical attributes:

* Fund ID
* Branch
* Authorized amount
* Custodian
* Currency
* Current balance
* Maximum transaction
* Status

---

# 31. PETTY CASH EXPENSE

A `PettyCashExpense` represents an authorized small operational expense.

Typical attributes:

* Expense ID
* Petty Cash Fund
* Amount
* Currency
* Expense category
* Reason
* Employee
* Receipt or evidence
* Approval
* Timestamp

Detailed Expense semantics may be extended in a financial expense domain.

---

# 32. PETTY CASH LIMIT

Petty Cash policy may define:

* Maximum amount per transaction.
* Allowed categories.
* Required evidence.
* Approval thresholds.

AI shall not bypass these limits.

---

# 33. PETTY CASH REPLENISHMENT

A Petty Cash Fund may be replenished after expenses are validated.

Replenishment shall preserve:

* Previous balance.
* Approved expenses.
* Added amount.
* New balance.

---

# 34. CASH REFUND

A Refund approved in `26_Payments.md` may be physically executed in cash.

Cash Management records:

* Cash outflow.
* Register.
* Employee.
* Customer Payment reference.
* Refund reference.

---

# 35. CASH REFUND RULE

A Cash Refund shall not be performed merely because a Customer requests it.

The Refund must first be authorized through Payment and commercial policy.

---

# 36. CASH EXPENSE

Cash may be used for operational expenses such as:

* Emergency purchase.
* Local transportation.
* Minor supplies.

These shall remain traceable to an Expense or Purchase reference where applicable.

---

# 37. CASH COUNT

A `CashCount` represents an observed physical quantity of cash.

Typical attributes:

* Count ID
* Cash Session
* Employee
* Currency
* Denomination breakdown
* Counted amount
* Timestamp
* Count type
* Status

---

# 38. CASH COUNT TYPES

Possible types:

```text
OPENING

INTERMEDIATE

CUSTODY_TRANSFER

SAFE_DROP

CLOSING

AUDIT

SURPRISE_COUNT
```

---

# 39. BLIND COUNT

A restaurant may use `BlindCount`, where the Employee counts cash without seeing the expected system balance.

This may reduce bias.

The model supports both blind and informed count procedures.

---

# 40. DUAL COUNT

Higher-risk operations may require two Employees to verify a Count.

Typical evidence:

* Primary counter.
* Secondary verifier.
* Both timestamps.
* Confirmation.

---

# 41. EXPECTED CASH BALANCE

Conceptually:

```text
Expected Cash
=
Opening Float
+
Cash Payments
+
Authorized Cash Ins
-
Cash Refunds
-
Authorized Cash Outs
-
Safe Drops
-
Transfers Out
```

plus applicable incoming transfers and corrections.

The exact formula shall be deterministic.

---

# 42. ACTUAL CASH BALANCE

Actual Cash Balance is the amount physically counted.

---

# 43. CASH RECONCILIATION

A `CashReconciliation` compares expected cash with physically counted cash.

Conceptually:

```text
Cash Difference
=
Actual Cash
-
Expected Cash
```

---

# 44. RECONCILIATION STATUS

Suggested states:

```text
MATCHED

OVERAGE

SHORTAGE

UNDER_REVIEW

ADJUSTED

RESOLVED
```

---

# 45. CASH SHORTAGE

A `CashShortage` occurs when:

```text
Actual Cash < Expected Cash
```

Example:

```text
Expected:
$12,500

Counted:
$12,300

Shortage:
$200
```

---

# 46. CASH OVERAGE

A `CashOverage` occurs when:

```text
Actual Cash > Expected Cash
```

An overage is also a discrepancy requiring explanation.

It is not automatically positive business performance.

---

# 47. CASH DISCREPANCY

A `CashDiscrepancy` represents an unexplained or partially explained difference.

Typical attributes:

* Discrepancy ID
* Cash Session
* Expected amount
* Counted amount
* Difference
* Currency
* Severity
* Status
* Possible reason
* Final reason
* Resolution

---

# 48. DISCREPANCY REASONS

Potential categories:

```text
CHANGE_ERROR

PAYMENT_ENTRY_ERROR

REFUND_ERROR

UNRECORDED_CASH_OUT

UNRECORDED_CASH_IN

REGISTER_TRANSFER_ERROR

COUNTING_ERROR

SYSTEM_ERROR

UNKNOWN
```

The system shall not automatically classify theft without evidence.

---

# 49. CASH DISCREPANCY SEVERITY

Suggested levels:

```text
MINOR

MODERATE

MAJOR

CRITICAL
```

Thresholds shall be tenant-configurable.

---

# 50. CASH DISCREPANCY INVESTIGATION

An investigation may review:

* Payment records.
* Refunds.
* Cash movements.
* Drawer openings.
* Shift handoffs.
* POS events.
* Employee activity.
* Count history.

The objective is evidence-based resolution.

---

# 51. CASH ADJUSTMENT

A `CashAdjustment` may be required after discrepancy review.

Typical attributes:

* Adjustment ID
* Cash Session
* Amount
* Direction
* Reason
* Evidence
* Approved by
* Timestamp

Adjustments shall not erase the original discrepancy.

---

# 52. CASH CORRECTION VS CASH MOVEMENT

A Correction changes the accounting representation of cash state.

A Movement represents actual physical movement.

These concepts shall remain separate.

---

# 53. CASH SESSION CLOSE

Before closing a Cash Session, the system should verify:

* Active Payments resolved.
* Required Cash movements posted.
* Closing Count completed.
* Difference calculated.
* Required approvals completed.

---

# 54. CLOSING COUNT

The Closing Count represents physical cash present at the end of the session before or during custody transfer.

---

# 55. CLOSING BALANCE

The session should preserve:

* Expected balance.
* Counted balance.
* Difference.
* Amount retained as next float if policy allows.
* Amount transferred to Safe or Deposit.

---

# 56. SHIFT SETTLEMENT

A `CashShiftSettlement` may consolidate one or more Cash Sessions associated with an Employee or shift.

Typical attributes:

* Shift.
* Sessions.
* Expected cash.
* Actual cash.
* Payments.
* Refunds.
* Deposits.
* Difference.
* Approval.

---

# 57. CASH REGISTER SHARING

Where multiple Employees use the same Register, custody controls become more important.

Possible policies include:

* Shared drawer.
* Employee-specific session.
* Employee-specific drawer.

The Domain Model supports these without prescribing one method.

---

# 58. EMPLOYEE-SPECIFIC DRAWER

A Drawer may remain assigned to one Employee for an entire Session.

This improves accountability.

---

# 59. SHARED DRAWER

A shared Drawer reduces direct Employee attribution.

The platform should preserve which Employees performed material cash actions.

---

# 60. DRAWER OPEN EVENT

A `CashDrawerOpened` event may be recorded when:

* Customer transaction occurs.
* Authorized Cash In/Out occurs.
* Manager override occurs.

Unexpected drawer openings may become anomaly signals.

---

# 61. MANUAL DRAWER OPEN

Manual opening without a commercial transaction may require:

* Reason.
* Employee.
* Authorization.

---

# 62. CHANGE FUND

A `ChangeFund` represents cash maintained specifically to provide denominations needed for transactions.

It may exist:

* At Branch level.
* In Safe.
* Per Register.

---

# 63. CHANGE SHORTAGE

A restaurant may have sufficient total cash but insufficient small denominations.

Example:

```text
Drawer Total:
$8,000

Available change:
No $20 or $50 bills
```

This is an operational cash condition distinct from total balance.

---

# 64. CHANGE AVAILABILITY

The platform may detect risk of insufficient change based on denomination counts.

This can generate an operational alert.

---

# 65. CASH COLLECTION POINTS

Cash may originate from:

* Front Register.
* Bar.
* Delivery Driver.
* Event.
* Banquet.
* Temporary sales station.
* Kiosk with cash capability.

Each collection point should map into governed Cash custody.

---

# 66. DELIVERY DRIVER CASH

Drivers collecting Payment may temporarily hold restaurant cash.

A `DriverCashCustody` may preserve:

* Driver.
* Delivery Orders.
* Cash collected.
* Change fund.
* Amount returned.
* Difference.

---

# 67. DRIVER CASH SETTLEMENT

At shift or route end:

```text
Cash Collected
+
Initial Driver Change Fund
-
Authorized Customer Change
=
Expected Driver Cash
```

This shall be reconciled against returned cash.

---

# 68. EVENT CASH

Banquets or Events may have dedicated Cash Registers or temporary Cash Sessions.

These should link to:

* Event.
* Location.
* Employee.
* Settlement.

---

# 69. TEMPORARY CASH REGISTER

A temporary Register may be created for:

* Event.
* Festival.
* Outdoor service.
* Banquet station.

The same Cash Management controls apply.

---

# 70. SAFE MANAGEMENT

Cash accumulated from Safe Drops may later be:

* Counted.
* Bundled.
* Prepared for bank deposit.
* Transferred to authorized custody.

---

# 71. SAFE COUNT

A `SafeCashCount` should reconcile:

* Prior Safe balance.
* Safe Drops.
* Cash removals.
* Deposit preparation.
* Current count.

---

# 72. BANK DEPOSIT

A `BankDeposit` represents physical or authorized transfer of restaurant cash into a bank account.

Typical attributes:

* Deposit ID
* Branch
* Bank account reference
* Amount
* Currency
* Source Safe or cash batches
* Prepared by
* Delivered by
* Deposit date
* Bank confirmation
* Status

---

# 73. BANK DEPOSIT STATUS

Suggested lifecycle:

```text
PREPARING
→ READY
→ IN_TRANSIT
→ DEPOSITED
→ BANK_CONFIRMED
→ RECONCILED
```

Alternative states:

```text
CANCELLED
DISCREPANCY
FAILED
```

---

# 74. DEPOSIT PREPARATION

A `DepositPreparation` may include:

* Cash amount.
* Denominations.
* Source Sessions.
* Source Safe Drops.
* Deposit bag.
* Seal.
* Employee.

---

# 75. DEPOSIT BAG

Where used, a deposit bag or sealed container may have:

* Bag ID.
* Seal number.
* Amount.
* Prepared by.
* Custodian.

This strengthens chain of custody.

---

# 76. CASH IN TRANSIT

Cash moving from Branch to Bank remains a controlled asset.

Custody may belong to:

* Employee.
* Manager.
* Cash logistics provider.

---

# 77. BANK CONFIRMATION

A Bank Deposit shall not be considered fully reconciled solely because it left the restaurant.

External bank confirmation may be required.

---

# 78. BANK DEPOSIT RECONCILIATION

Conceptually:

```text
Deposit Prepared

vs

Deposit Delivered

vs

Bank Credited Amount
```

Differences shall create explicit discrepancies.

---

# 79. CASH MANAGEMENT AND PAYMENTS

Payment answers:

> Did the Customer satisfy the financial obligation?

Cash Management answers:

> Where is the physical money representing that settlement?

This separation is mandatory.

---

# 80. CASH MANAGEMENT AND BILLING

Billing documents the commercial/fiscal transaction.

Cash Management records physical cash custody.

An Invoice does not imply cash exists in a Drawer.

---

# 81. CASH MANAGEMENT AND ORDERS

Orders generate Payment obligations.

Cash Management shall not modify Order commercial values.

---

# 82. CASH MANAGEMENT AND REFUNDS

Refund authorization comes from Payment/Commercial policy.

Cash Management records physical execution when Refund is paid in cash.

---

# 83. CASH MANAGEMENT AND EXPENSES

Cash expenses shall reference the appropriate Expense or Purchase transaction.

Cash should not leave a Drawer under an unstructured "expense" label when a more specific business reason exists.

---

# 84. CASH MANAGEMENT AND PURCHASING

Emergency Purchases may use Cash.

The Purchase remains a procurement transaction.

Cash Management records how it was funded physically.

---

# 85. CASH MANAGEMENT AND ACCOUNTS RECEIVABLE

Accounts Receivable settlement may be paid in cash.

The received amount shall generate:

* Payment.
* Cash Movement.
* Receivable application.

---

# 86. CASH MANAGEMENT AND BRANCH

All physical cash should be attributable to an operational Branch or authorized centralized location.

---

# 87. MULTI-CURRENCY CASH

Some restaurants may accept multiple currencies.

Cash Management shall preserve separate balances by Currency.

Currencies shall not be merged without explicit conversion.

---

# 88. CURRENCY EXCHANGE

Where foreign currency is accepted, the platform should preserve:

* Currency received.
* Exchange rate.
* Source.
* Local-value equivalent.
* Change policy.

Exchange-rate ownership remains a financial configuration concern.

---

# 89. CASH ROUNDING

Cash transactions in some currencies may require rounding due to available denominations.

Rounding rules shall be explicit.

---

# 90. CASH SECURITY

Cash Management shall support controls such as:

* Least-privilege access.
* Employee custody.
* Approval thresholds.
* Safe Drops.
* Session closure.
* Audit logging.
* Segregation of duties.

---

# 91. SEGREGATION OF DUTIES

Higher-risk processes may separate responsibilities.

Example:

```text
Cashier:
Handles customer cash

Supervisor:
Approves large Cash Outs

Manager:
Verifies closing discrepancy
```

The model supports configurable separation.

---

# 92. CASH AUTHORIZATION

Actions potentially requiring authorization include:

* Manual Cash In.
* Manual Cash Out.
* Cash Refund.
* Large Safe Drop.
* Cash Adjustment.
* Drawer opening.
* Discrepancy resolution.

---

# 93. CASH LIMIT

Operational policy may define:

* Maximum Drawer balance.
* Safe Drop threshold.
* Petty Cash limit.
* Employee Cash Out limit.

---

# 94. DRAWER CASH LIMIT

Example:

```text
Maximum recommended drawer balance:
$10,000

Current:
$14,500
```

This may generate a Safe Drop recommendation.

---

# 95. CASH EXPOSURE

A `CashExposure` metric may represent physical cash currently outside secure bank custody.

Potential scope:

* Drawers.
* Drivers.
* Temporary registers.
* Safe.
* Cash in transit.

---

# 96. CASH ANOMALY

Potential anomaly signals include:

* Frequent manual drawer openings.
* Repeated shortages.
* Repeated overages.
* Large Cash Outs.
* Late safe deposits.
* Unusual refund frequency.
* Cash Payments removed from POS after entry.
* Repeated adjustments.

These are investigation signals, not proof of misconduct.

---

# 97. REPEATED CASH SHORTAGE

Repeated shortage associated with:

* Register.
* Shift.
* Process.
* Employee.

may require investigation.

The system shall consider context before attribution.

---

# 98. EMPLOYEE ATTRIBUTION CAUTION

A shortage during an Employee's Session does not automatically prove wrongdoing.

Potential causes include:

* Counting error.
* Shared drawer.
* POS failure.
* Incorrect change.
* Refund error.
* Transfer error.

Evidence is required.

---

# 99. CASH FRAUD SIGNAL

Potential fraud-related signals may include:

* Suspicious void/refund patterns.
* Repeated manual corrections.
* Split Cash Outs below approval threshold.
* Missing deposit evidence.

These shall be classified as risk indicators.

---

# 100. CASH INCIDENT

Material issues may create an Operational Incident.

Examples:

* Large shortage.
* Cash theft allegation.
* Register failure during peak service.
* Bank deposit loss.
* Safe access issue.
* System-wide cash reconciliation failure.

---

# 101. CASH ALERT

Possible alerts:

* Drawer exceeds cash limit.
* Closing shortage exceeds threshold.
* Deposit overdue.
* Driver has unsettled cash.
* Petty Cash below threshold.
* Safe discrepancy.
* Unreconciled session.

Alerts shall be actionable.

---

# 102. CASH METRICS

Potential metrics include:

* Cash sales value.
* Cash Payment share.
* Drawer overage.
* Drawer shortage.
* Cash discrepancy rate.
* Safe Drop frequency.
* Average Drawer balance.
* Unreconciled Cash value.
* Deposit cycle time.
* Petty Cash spending.
* Cash Refund rate.

---

# 103. CASH PAYMENT MIX

The platform may analyze Cash versus digital Payment share.

This can influence:

* Register staffing.
* Change requirements.
* Security planning.
* Bank deposit frequency.

---

# 104. CASH RECONCILIATION RATE

Potential metric:

```text
Sessions Reconciled Without Difference
/
Total Closed Cash Sessions
```

---

# 105. CASH LOSS

Confirmed unrecovered Cash shortages may contribute to financial loss.

The accounting treatment belongs to Finance.

---

# 106. CASH FLOW INTELLIGENCE

Operational Cash data may contribute to near-term liquidity visibility.

However, physical Cash Management shall remain distinct from complete financial Cash Flow accounting.

---

# 107. CASH EXECUTIVE INTELLIGENCE

Potential executive indicators include:

* Total Cash collected.
* Total Cash deposited.
* Open cash exposure.
* Unreconciled amount.
* Shortage trend.
* Cash by Branch.
* Deposit latency.
* Manual adjustment frequency.

---

# 108. CASH MANAGEMENT SOURCE OF TRUTH

Authority may vary by state.

Example:

```text
POS:
Cash Payment transaction

Cash Register:
Physical custody session

Bank:
Deposit confirmation

ECIP:
Cash orchestration and intelligence
```

Ownership shall remain explicit.

---

# 109. EXTERNAL CASH MAPPING

External systems may use:

* Register ID.
* Drawer ID.
* Shift ID.
* Cash movement ID.
* Deposit ID.

These shall map to canonical Cash Management entities.

---

# 110. CASH SYNCHRONIZATION

Synchronization may include:

* Cash Payments.
* Register state.
* Session state.
* Refunds.
* Drawer movements.
* Deposit confirmations.

Synchronization shall be idempotent and observable.

---

# 111. CASH CONFLICT

Example:

```text
POS:
Cash sale = $1,000

Cash Session:
No corresponding Cash Payment movement
```

or:

```text
Cash Management:
Deposit = $20,000

Bank:
Confirmed = $19,500
```

Conflicts shall remain explicit until reconciled.

---

# 112. OFFLINE CASH OPERATIONS

If POS or network connectivity is unavailable, restaurants may continue accepting Cash according to controlled offline policy.

Offline transactions shall later reconcile with:

* Orders.
* Payments.
* Cash Session.

Duplicate financial recording shall be prevented.

---

# 113. CASH IDEMPOTENCY

Cash events imported from POS or external systems shall support idempotent processing.

A repeated synchronization event shall not increase the physical expected balance twice.

---

# 114. CASH HISTORY

Historical cash state should support reconstruction of:

```text
Opening Balance
    ↓
Every Cash Movement
    ↓
Intermediate Counts
    ↓
Closing Count
    ↓
Discrepancy
    ↓
Transfer / Deposit
    ↓
Final Reconciliation
```

---

# 115. CASH AUDIT

Material Cash actions shall preserve:

* Actor.
* Role.
* Branch.
* Register.
* Drawer.
* Session.
* Amount.
* Currency.
* Reason.
* Authorization.
* Previous state.
* New state.
* Timestamp.
* Related Payment / Expense / Transfer / Deposit.

---

# 116. CASH PRIVACY AND SECURITY

Cash records may contain:

* Employee responsibility.
* Financial amounts.
* Customer Payment references.
* Security-related operations.

Access shall follow:

* Least privilege.
* Tenant isolation.
* Role-based access.
* Audit logging.
* Retention policy.

---

# 117. CONVERSATIONAL CASH INTELLIGENCE

Authorized Employees may ask:

```text
"How much cash should be in register 3?"

"Why is yesterday's closing not reconciled?"

"Which registers have not been closed?"

"How much cash is waiting to be deposited?"

"Which branch had the largest cash difference this week?"
```

Responses shall use authoritative financial evidence.

---

# 118. CUSTOMER-FACING CASH INTERACTION

Customers may ask:

```text
"Can I pay cash?"

"Do you have change for $1,000?"

"Can I pay part in cash and part by card?"
```

ECIP may answer based on:

* Accepted Payment Methods.
* Current policy.
* Relevant change availability where operationally exposed.

Internal Cash balances shall not be unnecessarily disclosed.

---

# 119. AI CASH ASSISTANCE

AI may assist with:

* Summarizing discrepancies.
* Identifying missing Cash movements.
* Detecting anomalies.
* Recommending Safe Drops.
* Explaining expected balance calculations.
* Preparing reconciliation investigations.

---

# 120. AI AUTHORITY LIMIT

AI shall not:

* Invent physical cash balances.
* Mark a Drawer reconciled without Count evidence.
* Approve unexplained shortages.
* Create unapproved Cash Outs.
* Alter historical Counts.
* Fabricate Bank Deposit confirmation.
* Accuse Employees of theft without evidence.
* Resolve financial discrepancies by guesswork.

---

# 121. AUTOMATED CASH ACTIONS

Future controlled automation may support low-risk actions such as:

* Safe Drop alert.
* Session-close reminder.
* Deposit reminder.
* Change-fund alert.

High-risk actions such as:

* Cash adjustment.
* Discrepancy write-off.
* Refund execution.
* Custody override.

shall require authorized controls.

---

# 122. CASH EVENTS

Initial domain events include:

```text
CashRegisterCreated
CashRegisterOpened
CashRegisterClosed
CashRegisterSuspended

CashDrawerCreated
CashDrawerAssigned
CashDrawerOpened
CashDrawerLocked

CashSessionCreated
CashSessionOpeningStarted
CashSessionOpened
CashSessionClosingRequested
CashSessionClosingStarted
CashSessionClosed

CashCustodyAssigned
CashCustodyTransferred
CashCustodyReleased

OpeningFloatAssigned
OpeningCashCountRecorded

CashPaymentRecorded
CashChangeGiven

CashInRecorded
CashOutRecorded

SafeDropRequested
SafeDropCompleted

CashTransferRequested
CashTransferApproved
CashTransferReleased
CashTransferReceived
CashTransferCompleted

PettyCashFundCreated
PettyCashExpenseRecorded
PettyCashReplenished

CashRefundRecorded

CashCountStarted
CashCountCompleted

CashShortageDetected
CashOverageDetected
CashDiscrepancyDetected

CashDiscrepancyInvestigationStarted
CashDiscrepancyResolved

CashAdjustmentRequested
CashAdjustmentApproved
CashAdjustmentRecorded

CashShiftSettlementCreated
CashShiftSettlementCompleted

CashSafeCountRecorded

BankDepositPrepared
BankDepositDispatched
BankDepositRecorded
BankDepositConfirmed
BankDepositReconciled

CashAnomalyDetected
CashIncidentDetected

CashSynchronizationStarted
CashSynchronizationCompleted
CashSynchronizationFailed

CashConflictDetected
CashConflictResolved
```

---

# 123. RELATIONSHIPS

```text
Branch
    HAS CashRegister

CashRegister
    MAY_HAVE CashDrawer

CashDrawer
    HAS CashSession

Employee
    HAS CashCustody

CashSession
    HAS OpeningFloat

CashSession
    RECEIVES CashPayment

CashSession
    HAS CashMovement

CashMovement
    MAY_REFERENCE Payment

CashMovement
    MAY_REFERENCE Refund

CashMovement
    MAY_REFERENCE Expense

CashMovement
    MAY_REFERENCE CashTransfer

CashSession
    HAS CashCount

CashCount
    CONTRIBUTES_TO CashReconciliation

CashReconciliation
    MAY_CREATE CashDiscrepancy

CashDiscrepancy
    MAY_CREATE OperationalIncident

CashSession
    MAY_CREATE SafeDrop

CashSafe
    RECEIVES SafeDrop

CashSafe
    MAY_CREATE BankDeposit

BankDeposit
    MAY_HAVE BankConfirmation

CashState
    CONTRIBUTES_TO FinancialIntelligence
```

---

# 124. BUSINESS RULES

The following rules apply:

1. Cash Payment and physical Cash custody shall remain separate concepts.

2. Every Cash Session shall belong to a defined Branch and Register.

3. Cash custody shall identify the responsible Employee or governed shared-custody model.

4. Opening Float shall be explicit.

5. Every Cash Movement shall have an amount, currency, source and reason.

6. Cash In and Cash Out shall not be used to hide business transactions that belong to Payment, Expense, Purchase or Refund domains.

7. Transfers shall create matching source and destination evidence.

8. Physical Cash Counts shall remain distinct from expected system balances.

9. Cash discrepancies shall remain visible until investigated and resolved.

10. Cash Adjustments shall not erase original Count or discrepancy evidence.

11. A shortage shall not automatically imply Employee misconduct.

12. Cash Refunds require valid Refund authorization.

13. Safe Drops and Bank Deposits shall preserve chain of custody.

14. Cash deposited at a Bank shall not be considered fully reconciled until authoritative confirmation exists where required.

15. Multi-currency balances shall remain separated.

16. AI shall not invent or alter physical cash evidence.

17. External identifiers shall remain integration mappings.

18. High-risk Cash actions shall require appropriate authorization.

19. Offline Cash transactions shall be reconciled without duplication when systems recover.

20. Every material Cash lifecycle event shall be reconstructable and auditable.

---

# 125. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
CashRegister

CashRegisterStatus

CashDrawer

CashSession

CashSessionStatus

CashCustody

OpeningFloat

CashPaymentReference

CashMovement

CashMovementType

CashIn

CashOut

SafeDrop

CashTransfer

CashCount

CashDenominationCount

ExpectedCashBalance

CashReconciliation

CashShortage

CashOverage

CashDiscrepancy

CashAdjustment

CashShiftSettlement

CashSafeReference

BankDeposit

ExternalCashMapping

CashAuditHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Denomination Forecasting

Automated Safe Hardware Integration

Cash Logistics Provider Integration

Predictive Cash Shortage Detection

Advanced Fraud Detection

Autonomous Change-Fund Rebalancing

Computer-Vision Cash Counting

Smart Cash Drawer IoT

Autonomous Bank Deposit Scheduling
```

---

# 126. IMPLEMENTATION PRINCIPLE

This document defines the logical Cash Management Model.

It does not prescribe:

* POS implementation.
* Cash drawer hardware.
* Safe hardware.
* Bank integration.
* Accounting implementation.
* Expense system.
* Fraud engine.
* Computer vision.
* Database schema.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
CASH PAYMENT

CASH REGISTER

CASH DRAWER

CASH SESSION

CASH CUSTODY

CASH MOVEMENT

CASH COUNT

CASH RECONCILIATION

CASH DISCREPANCY

SAFE DROP

BANK DEPOSIT
```

---

# 127. FINAL RULE

Before ECIP concludes that a Cash Register, Cash Session, Employee custody or Bank Deposit is balanced, closed or reconciled, it shall be able to determine:

> Which Branch, Register and Drawer are involved?

> Which Employee or custody model is responsible?

> What Opening Float was assigned?

> What Cash Payments were actually recorded?

> What Cash Ins, Cash Outs, Refunds, Transfers and Safe Drops occurred?

> What physical amount was actually counted?

> How was the expected Cash balance calculated?

> Is there a shortage or overage?

> Has the discrepancy been investigated?

> Were any adjustments authorized?

> Where did the physical Cash move after session close?

> Was it transferred to a Safe or prepared for Bank Deposit?

> Did the Bank confirm the deposited amount?

> Are there any unresolved Cash conflicts, anomalies or custody gaps?

> Can every material physical Cash movement from Customer receipt through final custody be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably represent restaurant Cash as collected, held, transferred, deposited, reconciled or financially accounted for.

