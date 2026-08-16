# 24_Purchasing.md

**Document ID:** RDM-024
**Document Name:** Purchasing
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Purchasing Model for the Restaurant Intelligence Platform.

Its purpose is to represent how the restaurant plans, requests, approves, orders, receives and evaluates the acquisition of Ingredients, Beverages, Packaging, Supplies, Equipment-related consumables and other operational goods.

The Purchasing Model connects:

* Inventory.
* Ingredients.
* Suppliers.
* Purchase Requirements.
* Purchase Requisitions.
* Purchase Orders.
* Receiving.
* Quality Control.
* Costs.
* Accounts Payable.
* Events.
* Production Forecast.
* Branches.
* Warehouses.
* Contracts.
* Operational Intelligence.
* Executive Intelligence.

Purchasing shall not be modeled merely as creation of Purchase Orders.

It represents the complete governed replenishment and procurement lifecycle.

---

# 2. OBJECTIVES

The Purchasing Model enables ECIP to:

* Detect purchasing requirements.
* Generate replenishment needs.
* Create Purchase Requisitions.
* Compare Suppliers.
* Create Purchase Orders.
* Track approvals.
* Track Order status.
* Track expected delivery.
* Receive goods.
* Detect short deliveries.
* Detect over-deliveries.
* Detect price discrepancies.
* Perform receiving Quality Control.
* Handle rejected goods.
* Handle Supplier returns.
* Track lead times.
* Track Supplier performance.
* Support multi-Branch procurement.
* Support central purchasing.
* Support Event-specific purchasing.
* Support emergency purchasing.
* Support Accounts Payable.
* Preserve complete purchasing history.
* Support Purchasing Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Organization
* Party
* Supplier
* Contract
* Resource
* Requirement
* Request
* Approval
* Action
* Commitment
* Workflow Instance
* Document
* Evidence Record
* Context Snapshot
* External Entity Reference

Restaurant-specific Purchasing entities remain within the Restaurant Domain Pack.

---

# 4. PURCHASING PRINCIPLE

The platform shall distinguish between:

```text
PURCHASE REQUIREMENT

PURCHASE REQUISITION

SUPPLIER QUOTATION

PURCHASE ORDER

SUPPLIER COMMITMENT

GOODS RECEIPT

QUALITY ACCEPTANCE

INVENTORY RECEIPT

SUPPLIER INVOICE

ACCOUNT PAYABLE
```

These are related but separate business concepts.

---

# 5. SUPPLIER

A `Supplier` represents an external organization or person authorized to provide goods or services to the restaurant.

Typical attributes include:

* Supplier ID
* Legal name
* Commercial name
* Tax identifiers
* Contact information
* Payment terms
* Delivery terms
* Supported Products or Categories
* Service regions
* Lead time
* Currency
* Status
* Quality status
* Contract references
* External identifiers

---

# 6. SUPPLIER STATUS

Suggested states:

```text
PROSPECT

UNDER_EVALUATION

APPROVED

ACTIVE

SUSPENDED

BLOCKED

INACTIVE
```

Only Suppliers valid under purchasing policy should receive new Purchase Orders.

---

# 7. SUPPLIER TYPE

Examples:

```text
FOOD_SUPPLIER

BEVERAGE_SUPPLIER

PRODUCE_SUPPLIER

MEAT_SUPPLIER

SEAFOOD_SUPPLIER

BAKERY_SUPPLIER

PACKAGING_SUPPLIER

CLEANING_SUPPLIER

EQUIPMENT_SUPPLIER

MAINTENANCE_SUPPLIER

GENERAL_SUPPLIER
```

A Supplier may belong to multiple categories.

---

# 8. SUPPLIER CONTACT

A Supplier may have contacts for:

* Sales.
* Orders.
* Logistics.
* Accounting.
* Quality.
* Emergency service.

Contact role shall be explicit.

---

# 9. SUPPLIER PRODUCT

A `SupplierProduct` represents a Supplier's commercial offering mapped to a canonical Inventory Item.

Typical attributes:

* Supplier Product ID
* Supplier
* Inventory Item
* Supplier SKU
* Description
* Purchase unit
* Conversion to Inventory unit
* Minimum order
* Price reference
* Lead time
* Availability
* Status

---

# 10. SUPPLIER PRODUCT MAPPING

Example:

```text
Inventory Item:
Fresh Salmon Fillet

Supplier A:
SAL-220-A

Supplier B:
FISH-88
```

External Supplier identifiers shall not replace canonical Inventory Item identity.

---

# 11. PURCHASE REQUIREMENT

A `PurchaseRequirement` represents the detected need to acquire additional stock.

Possible sources include:

* Low Stock.
* Reorder Point.
* Forecast.
* Production Plan.
* Event.
* Reservation demand.
* Manual request.
* Quality rejection.
* Emergency.
* New Product launch.

---

# 12. PURCHASE REQUIREMENT ATTRIBUTES

Typical attributes include:

* Requirement ID
* Inventory Item
* Required quantity
* Required date
* Branch or Warehouse
* Source
* Priority
* Suggested Supplier
* Current stock
* Committed stock
* Forecast consumption
* Status

---

# 13. PURCHASE REQUIREMENT STATUS

Suggested lifecycle:

```text
DETECTED
→ REVIEWED
→ APPROVED
→ SOURCING
→ ORDERED
→ SATISFIED
```

Alternative states:

```text
REJECTED
CANCELLED
EXPIRED
```

---

# 14. AUTOMATIC REQUIREMENT DETECTION

Purchase Requirements may be generated from governed rules.

Conceptually:

```text
Available Stock
+
Confirmed Demand
+
Forecast Demand
+
Safety Stock
+
Supplier Lead Time
=
Potential Replenishment Requirement
```

The result may require review before procurement.

---

# 15. REORDER-POINT REQUIREMENT

Example:

```text
Current stock:
8 kg

Reorder point:
10 kg

Target stock:
25 kg

Potential Purchase Requirement:
17 kg
```

The actual purchase quantity may still require optimization or approval.

---

# 16. EVENT PURCHASE REQUIREMENT

A confirmed Event may generate future demand.

Example:

```text
Wedding:
150 guests

Required wine:
75 bottles

Current available:
30

Reserved for other demand:
10

Potential requirement:
55 bottles
```

---

# 17. EMERGENCY PURCHASE REQUIREMENT

Emergency purchasing may be triggered by:

* Unexpected Stockout.
* Supplier failure.
* Quality rejection.
* Demand surge.
* Equipment-related consumable failure.

Emergency status shall not bypass all controls automatically.

---

# 18. PURCHASE REQUISITION

A `PurchaseRequisition` represents an internal request for approval to purchase one or more items.

Typical attributes:

* Requisition ID
* Requesting Branch
* Requesting department
* Requested by
* Items
* Quantities
* Required date
* Business reason
* Priority
* Estimated value
* Status

---

# 19. REQUISITION STATUS

Suggested lifecycle:

```text
DRAFT
→ SUBMITTED
→ UNDER_REVIEW
→ APPROVED
→ SOURCING
→ CONVERTED_TO_PURCHASE_ORDER
```

Alternative states:

```text
REJECTED
CANCELLED
```

---

# 20. REQUISITION ITEM

A `PurchaseRequisitionItem` represents one requested procurement line.

Typical attributes:

* Inventory Item
* Quantity
* Unit
* Required date
* Preferred Supplier
* Estimated cost
* Reason
* Source Purchase Requirement

---

# 21. PURCHASE APPROVAL

Approval may depend on:

* Amount.
* Item category.
* Branch.
* Supplier.
* Urgency.
* Contract status.

Example:

```text
≤ $5,000
Branch Manager

$5,001–$25,000
Regional Manager

> $25,000
Corporate Approval
```

Actual thresholds remain tenant-configurable.

---

# 22. APPROVAL CHAIN

A Purchase may require one or more sequential or parallel approvals.

Approval evidence shall preserve:

* Approver.
* Decision.
* Timestamp.
* Conditions.
* Comments.

---

# 23. AI AUTHORIZATION LIMIT

AI may prepare or recommend a Purchase Requisition.

AI shall not bypass required approval thresholds.

---

# 24. SOURCING

`Sourcing` represents the process of identifying the appropriate Supplier and commercial conditions.

Potential criteria:

* Price.
* Quality.
* Lead time.
* Availability.
* Contract.
* Reliability.
* Minimum order.
* Delivery capacity.

---

# 25. REQUEST FOR QUOTATION

A `SupplierQuotationRequest` may be sent to one or more Suppliers.

Typical attributes:

* Requested items.
* Quantities.
* Delivery location.
* Required date.
* Quote deadline.
* Commercial requirements.

---

# 26. SUPPLIER QUOTATION

A `SupplierQuotation` represents a Supplier's commercial offer.

Typical attributes:

* Supplier
* Items
* Quantity
* Price
* Currency
* Tax
* Delivery cost
* Lead time
* Validity
* Minimum order
* Payment terms
* Availability
* Status

---

# 27. QUOTATION COMPARISON

A Comparison may evaluate:

```text
PRICE

QUALITY

LEAD TIME

AVAILABILITY

DELIVERY TERMS

PAYMENT TERMS

SUPPLIER PERFORMANCE
```

Lowest price shall not automatically mean best procurement decision.

---

# 28. SUPPLIER SELECTION

Supplier selection shall be explainable.

Potential decision factors:

* Total landed cost.
* Required delivery date.
* Historical Quality.
* Fill rate.
* Current availability.
* Contractual preference.
* Risk.

---

# 29. PREFERRED SUPPLIER

An Inventory Item may have:

* Primary Supplier.
* Secondary Supplier.
* Emergency Supplier.

Preference shall remain configurable.

---

# 30. ALTERNATE SUPPLIER

If the primary Supplier cannot fulfill demand, an alternate may be considered.

Fallback shall still validate:

* Approved status.
* Price.
* Quality.
* Product mapping.
* Lead time.

---

# 31. PURCHASE ORDER

A `PurchaseOrder` represents the restaurant's formal request to a Supplier for goods or services.

Typical attributes:

* Purchase Order ID
* Supplier
* Buyer organization
* Branch / Warehouse
* Order date
* Expected delivery date
* Currency
* Items
* Subtotal
* Charges
* Taxes
* Total
* Payment terms
* Delivery terms
* Status
* Approval references
* Contract reference
* External identifiers

---

# 32. PURCHASE ORDER STATUS

Suggested lifecycle:

```text
DRAFT
→ PENDING_APPROVAL
→ APPROVED
→ SENT
→ ACKNOWLEDGED
→ PARTIALLY_RECEIVED
→ RECEIVED
→ CLOSED
```

Alternative states:

```text
REJECTED
CANCELLED
EXPIRED
DISPUTED
```

---

# 33. PURCHASE ORDER ITEM

Typical attributes:

* Inventory Item
* Supplier Product
* Ordered quantity
* Purchase unit
* Unit price
* Tax
* Discount
* Expected quantity
* Received quantity
* Rejected quantity
* Outstanding quantity

---

# 34. PURCHASE UNIT

Purchasing units may differ from Inventory units.

Example:

```text
Purchased:
1 case

Supplier definition:
12 bottles per case

Inventory base unit:
Bottle
```

Conversion shall be explicit.

---

# 35. PURCHASE ORDER PRICE

The Purchase Order shall preserve the actual agreed Supplier price.

Future Supplier price changes shall not rewrite historical Orders.

---

# 36. PURCHASE ORDER VERSION

Material Purchase Order changes may require versioning.

Examples:

* Quantity.
* Price.
* Expected date.
* Supplier Product.
* Delivery location.

---

# 37. PURCHASE ORDER AMENDMENT

A `PurchaseOrderAmendment` represents an authorized change after Order issuance.

The original Order shall remain historically reconstructable.

---

# 38. PURCHASE ORDER SUBMISSION

A Purchase Order may be sent through:

* Email.
* Supplier API.
* EDI.
* Supplier portal.
* Manual process.

Transport mechanism does not change Purchase Order semantics.

---

# 39. SUPPLIER ACKNOWLEDGMENT

A Supplier may acknowledge:

* Complete acceptance.
* Partial acceptance.
* Changed delivery date.
* Backorder.
* Rejection.

Supplier acknowledgment is evidence of the Supplier's commitment.

---

# 40. SUPPLIER COMMITMENT

A `SupplierCommitment` may preserve:

* Confirmed quantity.
* Confirmed delivery date.
* Confirmed price.
* Exceptions.

This allows comparison between what was ordered and what Supplier promised.

---

# 41. BACKORDER

A `Backorder` occurs when the Supplier cannot immediately provide all ordered quantity.

Possible result:

* Wait.
* Substitute Supplier.
* Split Order.
* Cancel outstanding quantity.

---

# 42. PARTIAL FULFILLMENT

Example:

```text
Ordered:
100 kg

Received:
70 kg

Outstanding:
30 kg
```

The Purchase Order may remain open.

---

# 43. EXPECTED DELIVERY

Purchasing shall track expected Supplier delivery.

Typical attributes:

* Expected date.
* Expected window.
* Destination.
* Shipment reference.

---

# 44. PURCHASE DELIVERY STATUS

Suggested states:

```text
NOT_SHIPPED

IN_TRANSIT

ARRIVING

DELIVERED

PARTIALLY_DELIVERED

FAILED
```

---

# 45. GOODS RECEIPT

A `GoodsReceipt` represents physical receipt of Supplier goods.

Typical attributes:

* Receipt ID
* Purchase Order
* Supplier
* Branch / Warehouse
* Received time
* Received by
* Delivery reference
* Items
* Status

---

# 46. RECEIVING PROCESS

Conceptually:

```text
Supplier Delivery
    ↓
Purchase Order Match
    ↓
Quantity Verification
    ↓
Quality Verification
    ↓
Accept / Hold / Reject
    ↓
Inventory Receipt
```

---

# 47. RECEIPT ITEM

A `GoodsReceiptItem` may preserve:

* Ordered quantity.
* Delivered quantity.
* Accepted quantity.
* Rejected quantity.
* Unit.
* Lot.
* Expiration.
* Supplier Lot.
* Quality result.
* Unit cost.

---

# 48. THREE-WAY MATCH

Where applicable, Purchasing and Finance may compare:

```text
Purchase Order

vs

Goods Receipt

vs

Supplier Invoice
```

Differences may create an exception.

---

# 49. QUANTITY DISCREPANCY

Examples:

* Short delivery.
* Over-delivery.
* Missing line.
* Unexpected Product.

Discrepancies shall remain explicit.

---

# 50. SHORT DELIVERY

Example:

```text
Ordered:
50 cases

Delivered:
44 cases
```

Possible actions:

* Accept partial.
* Maintain balance due.
* Request remaining quantity.
* Cancel outstanding balance.

---

# 51. OVER-DELIVERY

An over-delivery may be:

* Accepted.
* Partially accepted.
* Rejected.

Acceptance may depend on:

* Storage.
* Demand.
* Purchase authorization.

---

# 52. WRONG ITEM DELIVERY

A Supplier may deliver the wrong Product.

The platform shall not silently map it to the ordered Product.

It shall create an exception.

---

# 53. RECEIVING QUALITY CONTROL

Received items may require Quality validation according to `22_Quality_Control.md`.

Examples:

* Temperature.
* Packaging integrity.
* Appearance.
* Expiration.
* Lot.
* Specification.

---

# 54. RECEIVING QUALITY RESULT

Possible states:

```text
ACCEPTED

ACCEPTED_WITH_NOTE

QUALITY_HOLD

PARTIALLY_REJECTED

REJECTED
```

Only accepted usable quantity should become available Inventory.

---

# 55. QUALITY HOLD AT RECEIVING

Goods may physically enter the location but remain unavailable pending review.

This distinction is critical.

---

# 56. SUPPLIER REJECTION

Rejected goods may result from:

* Poor Quality.
* Wrong item.
* Damaged packaging.
* Temperature violation.
* Expiration issue.
* Unauthorized substitution.

---

# 57. RETURN TO SUPPLIER

A `SupplierReturn` represents goods sent back to a Supplier.

Typical attributes:

* Return ID
* Supplier
* Original Receipt
* Items
* Quantity
* Reason
* Status
* Credit expected
* Shipment reference

---

# 58. SUPPLIER RETURN STATUS

Suggested lifecycle:

```text
REQUESTED
→ AUTHORIZED
→ PREPARED
→ DISPATCHED
→ RECEIVED_BY_SUPPLIER
→ CLOSED
```

---

# 59. SUPPLIER CREDIT

Returned or rejected goods may generate:

* Credit note.
* Replacement.
* Refund.
* Price adjustment.

Financial ownership belongs to Accounts Payable / Billing-related systems.

---

# 60. PURCHASE CANCELLATION

A Purchase Order may be cancelled:

* Before Supplier acceptance.
* After Supplier acceptance.
* Partially.
* For remaining balance only.

Commercial consequences shall be preserved.

---

# 61. PURCHASE ORDER CANCELLATION REASON

Possible reasons:

* Demand cancelled.
* Duplicate Order.
* Supplier failure.
* Price change.
* Event cancellation.
* Quality issue.
* Procurement error.

---

# 62. DELIVERY DELAY

Supplier delivery may be delayed.

The platform should preserve:

* Original expected date.
* Revised date.
* Delay.
* Reason when known.

---

# 63. PURCHASE DELAY IMPACT

A delayed Supplier delivery may affect:

```text
Inventory
    ↓
Production
    ↓
Product Availability
    ↓
Orders / Events
    ↓
Customer Commitments
```

This relationship is strategically important to ECIP.

---

# 64. SUPPLIER LEAD TIME

Lead time may be measured as:

```text
Receipt Time - Purchase Order Release Time
```

Other definitions may exist according to process.

---

# 65. LEAD-TIME VARIANCE

Expected and actual lead time shall remain distinct.

Repeated variance may indicate Supplier reliability issues.

---

# 66. SUPPLIER FILL RATE

Conceptually:

```text
Quantity Delivered
/
Quantity Ordered
```

The exact metric should account for accepted quantity where appropriate.

---

# 67. ON-TIME DELIVERY RATE

Measures Supplier delivery compliance relative to promised timing.

---

# 68. SUPPLIER QUALITY RATE

Potential measure:

```text
Accepted Quantity
/
Received Quantity
```

or other configured methodology.

---

# 69. SUPPLIER PERFORMANCE

A `SupplierPerformanceProfile` may aggregate:

* Price competitiveness.
* On-time delivery.
* Fill rate.
* Quality acceptance.
* Response time.
* Dispute frequency.
* Reliability.

This is analytical.

---

# 70. SUPPLIER SCORE

If a Supplier Score exists, its components shall remain explainable.

ECIP shall not reduce Supplier selection to an opaque AI score.

---

# 71. SUPPLIER RISK

Potential Supplier risks include:

* Repeated delays.
* Quality failure.
* Price volatility.
* Supply concentration.
* Financial instability where externally known.
* Geographic risk.

Risk shall preserve evidence and confidence.

---

# 72. SINGLE-SOURCE RISK

An Inventory Item may depend on one Supplier.

Example:

```text
Critical Ingredient:
Only Supplier A approved
```

This represents supply-chain concentration risk.

---

# 73. MULTI-SUPPLIER STRATEGY

Restaurants may maintain multiple approved Suppliers for critical items.

Purchasing Intelligence may recommend diversification where appropriate.

---

# 74. SUPPLIER CONTRACT

A `SupplierContract` may define:

* Products.
* Prices.
* Discounts.
* Minimum volumes.
* Payment terms.
* Delivery service levels.
* Validity.
* Exclusivity.

The Contract model may be canonical and referenced by Purchasing.

---

# 75. CONTRACT PRICE

Where a valid contract applies, Purchase Orders should use governed contract pricing unless an authorized exception exists.

---

# 76. PRICE DISCREPANCY

Example:

```text
PO Unit Price:
$100

Supplier Invoice:
$112
```

This creates a commercial exception.

It shall not silently alter historical Purchase Order terms.

---

# 77. PURCHASE COST

Purchase Cost may include:

```text
Item Cost
+
Freight
+
Taxes
+
Other Charges
-
Supplier Discounts
```

Detailed accounting treatment may occur in Finance.

---

# 78. LANDED COST

A `LandedCost` may represent total cost of acquiring an Inventory Item at a destination.

Potential components:

* Product cost.
* Freight.
* Import costs.
* Taxes.
* Handling.

This may support Inventory valuation and Supplier comparison.

---

# 79. CURRENCY

Supplier prices shall explicitly identify currency.

Multi-currency Purchasing may require:

* Exchange-rate authority.
* Effective rate.
* Conversion evidence.

---

# 80. PAYMENT TERMS

Examples:

```text
CASH

PREPAID

NET_7

NET_15

NET_30

NET_60
```

Terms should be explicit and may derive from Supplier Contract.

---

# 81. ACCOUNTS PAYABLE INTEGRATION

Accepted Supplier invoices may create or update Accounts Payable obligations.

Purchasing shall not duplicate the Account Payable ledger.

---

# 82. SUPPLIER INVOICE

Purchasing may reference Supplier invoices containing:

* Supplier.
* Invoice number.
* Purchase Order.
* Receipt.
* Amount.
* Due date.
* Taxes.
* Status.

Detailed financial lifecycle belongs to Finance.

---

# 83. CENTRAL PURCHASING

Restaurant groups may centralize procurement.

Example:

```text
Corporate Purchasing
    ↓
Central Warehouse
    ↓
Branches
```

The model shall support purchasing ownership different from final consumption location.

---

# 84. BRANCH PURCHASING

Individual Branches may purchase directly.

Authority may vary by:

* Category.
* Amount.
* Supplier.
* Emergency status.

---

# 85. CONSOLIDATED PURCHASING

Requirements from several Branches may be consolidated into one Purchase Order.

Example:

```text
Branch A:
20 cases

Branch B:
15 cases

Branch C:
25 cases

Consolidated:
60 cases
```

Distribution remains traceable.

---

# 86. PURCHASE ALLOCATION

A consolidated Purchase may allocate quantities to:

* Branches.
* Warehouses.
* Events.
* Specific requirements.

---

# 87. EVENT-SPECIFIC PURCHASING

Purchasing for an Event shall preserve the Event reference.

If the Event changes or cancels, procurement consequences should be visible.

---

# 88. SPECIAL-ORDER ITEM

Some procurement may be for a specific Customer or Event rather than regular inventory.

Examples:

* Rare wine.
* Custom cake ingredient.
* Specialty product.

Special-order stock should remain identifiable.

---

# 89. PURCHASE FORECAST

Purchasing may use future demand based on:

* Inventory trends.
* Reservations.
* Events.
* Production Forecast.
* Seasonal patterns.
* Promotions.

Forecasts remain analytical.

---

# 90. PURCHASE RECOMMENDATION

A `PurchaseRecommendation` may suggest:

* Item.
* Quantity.
* Supplier.
* Required date.
* Reason.

It shall preserve:

* Evidence.
* Confidence.
* Expected impact.

A recommendation is not an Order.

---

# 91. PURCHASE QUANTITY RECOMMENDATION

Potential factors include:

```text
Current Available Stock

+ Confirmed Future Demand

+ Forecast Demand

+ Safety Stock

- Existing Open Purchase Orders

- Stock Already In Transit
```

Optimization may be added later.

---

# 92. OPEN PURCHASE ORDER AWARENESS

New purchase recommendations shall consider stock already ordered but not yet received.

Failing to do so may create overstock.

---

# 93. GOODS IN TRANSIT

A `GoodsInTransit` quantity may represent confirmed supplier shipments not yet received.

It shall remain distinct from On-Hand Inventory.

---

# 94. PURCHASING AND INVENTORY

Inventory supplies current stock state.

Purchasing supplies replenishment.

Conceptually:

```text
Inventory Shortage / Forecast
    ↓
Purchase Requirement
    ↓
Purchase Order
    ↓
Goods Receipt
    ↓
Inventory
```

---

# 95. PURCHASING AND PRODUCTION

Production demand may generate future procurement needs.

Production shall not directly create Supplier Orders unless explicit automation and authority permit.

---

# 96. PURCHASING AND RECIPES

Recipes drive Ingredient demand.

Purchasing uses this demand through Inventory requirements.

Recipe definitions shall not contain Supplier commercial terms.

---

# 97. PURCHASING AND QUALITY

Quality Control influences:

* Receipt acceptance.
* Supplier evaluation.
* Lot rejection.
* Supplier return.

Quality failure may also trigger alternate purchasing.

---

# 98. PURCHASING AND EVENTS

Events may create large or unusual demand.

Confirmed Event commercial commitments should be visible to Purchasing.

---

# 99. PURCHASING AND MAINTENANCE

Maintenance may require:

* Spare parts.
* Equipment supplies.
* Specialized service.

The same procurement model may support these acquisitions where appropriate.

---

# 100. PURCHASING AND CASH FLOW

Purchasing decisions affect:

* Cash requirements.
* Accounts Payable.
* Working capital.
* Inventory value.

Financial Intelligence may consume Purchasing data.

---

# 101. EMERGENCY PURCHASING

An `EmergencyPurchase` may allow accelerated workflow.

It shall preserve:

* Emergency reason.
* Requested by.
* Supplier.
* Price.
* Approval.
* Post-review requirement if applicable.

Emergency mode shall not mean ungoverned purchasing.

---

# 102. PETTY-CASH PURCHASE

Some low-value items may be purchased using petty cash.

The transaction shall still be represented appropriately and connected to Expense or Cash Management.

---

# 103. PURCHASE FRAUD / ANOMALY SIGNALS

Potential signals include:

* Unusual Supplier.
* Repeated emergency purchases.
* Large price increase.
* Duplicate Purchase Orders.
* Excess quantity.
* Split Orders below approval threshold.
* Unexpected Supplier bank change.

These are risk signals, not proof of wrongdoing.

---

# 104. DUPLICATE PURCHASE ORDER

The platform may detect likely duplicates based on:

* Supplier.
* Items.
* Quantities.
* Dates.
* Destination.
* Amount.

Detection shall not automatically cancel a valid Order.

---

# 105. PRICE ANOMALY

Example:

```text
Historical average:
$80/kg

New Supplier Quote:
$145/kg
```

This may trigger review.

---

# 106. PURCHASE APPROVAL ANOMALY

Repeated purchasing just below an approval threshold may warrant analysis.

The system shall classify this as an anomaly, not a conclusion.

---

# 107. PURCHASING INTELLIGENCE

Potential insights include:

* Supplier price trends.
* Delivery reliability.
* Quality performance.
* Fill rate.
* Stockout caused by Supplier delays.
* Emergency Purchase frequency.
* Purchase variance.
* Contract utilization.
* Supplier concentration.

---

# 108. PROCUREMENT SAVINGS

Potential savings analysis may compare:

* Contract price.
* Actual purchase price.
* Alternate Supplier.
* Consolidated Purchasing.
* Waste reduction.

Savings shall be calculated using explicit methodology.

---

# 109. PURCHASE PRICE VARIANCE

Conceptually:

```text
Actual Purchase Price
-
Reference / Standard Price
```

The reference methodology shall be explicit.

---

# 110. SUPPLIER PRICE TREND

Historical Supplier prices may support:

* Inflation analysis.
* Budget forecasting.
* Menu pricing decisions.
* Cost intelligence.

---

# 111. SUPPLY RISK ALERT

Potential alerts:

* Critical Order delayed.
* Critical Ingredient backordered.
* Supplier Quality failure.
* Contract expiration.
* Price increase.
* Single-Supplier dependency.
* Event requirement at risk.

---

# 112. PURCHASING ALERT PRIORITY

Alerts should consider:

* Business impact.
* Required date.
* Current stock.
* Alternative Supplier availability.
* Customer commitments.

---

# 113. AI PURCHASING ASSISTANCE

AI may assist with:

* Summarizing purchase needs.
* Comparing quotations.
* Detecting anomalies.
* Recommending Suppliers.
* Explaining stock risk.
* Preparing draft Requisitions or Orders.

---

# 114. AI AUTHORITY LIMIT

AI shall not:

* Invent Supplier prices.
* Fabricate Supplier availability.
* Approve Purchases without authority.
* Change Purchase Orders silently.
* Release rejected goods into Inventory.
* Ignore contractual or Quality restrictions.
* Create unauthorized emergency Purchases.

---

# 115. AUTONOMOUS PURCHASING

Future controlled automation may support low-risk replenishment under strict policies.

Example conditions:

```text
Approved Supplier
+
Contract Price
+
Quantity Within Limit
+
Budget Available
+
No Exception
=
Potential Auto-Approval Candidate
```

This is not required for MVP.

---

# 116. PURCHASING SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
ERP:
Purchase Orders and Supplier master

Inventory System:
Stock state

ECIP:
Purchase Intelligence and orchestration

Accounting:
Supplier invoices and Accounts Payable
```

Ownership shall be explicitly configured.

---

# 117. EXTERNAL SUPPLIER MAPPING

External systems may use different Supplier IDs.

These shall map to canonical Supplier identity.

---

# 118. EXTERNAL PURCHASE ORDER MAPPING

Example:

```text
ECIP:
PO-10025

ERP:
ORD-88213

Supplier Portal:
REQ-455
```

Mappings shall preserve source system.

---

# 119. PURCHASING IMPORT

Historical Supplier and Purchase data may be imported.

Import shall preserve:

* Source.
* Original identifier.
* Item mapping.
* Supplier mapping.
* Timestamp.
* Data quality.

---

# 120. PURCHASING SYNCHRONIZATION

Synchronization may include:

* Suppliers.
* Purchase Orders.
* Status changes.
* Receipts.
* Prices.
* Invoices.
* Returns.

It shall be idempotent and observable.

---

# 121. PURCHASING CONFLICT

Possible conflict:

```text
ECIP:
PO still open

ERP:
PO cancelled
```

or:

```text
Receiving:
100 units received

Supplier:
Claims 80 units shipped
```

Conflicts shall remain explicit until resolved.

---

# 122. PURCHASING AUDIT

Material purchasing actions shall preserve:

* Actor.
* Timestamp.
* Supplier.
* Items.
* Quantity.
* Price.
* Approval.
* Previous state.
* New state.
* External evidence.
* Correlation IDs where applicable.

---

# 123. PURCHASING EVENTS

Initial domain events include:

```text
SupplierCreated
SupplierApproved
SupplierActivated
SupplierSuspended
SupplierBlocked

SupplierProductMapped
SupplierProductUpdated

PurchaseRequirementDetected
PurchaseRequirementReviewed
PurchaseRequirementApproved
PurchaseRequirementCancelled
PurchaseRequirementSatisfied

PurchaseRequisitionCreated
PurchaseRequisitionSubmitted
PurchaseRequisitionApproved
PurchaseRequisitionRejected
PurchaseRequisitionCancelled

SupplierQuotationRequested
SupplierQuotationReceived
SupplierQuotationEvaluated
SupplierSelected

PurchaseOrderCreated
PurchaseOrderSubmittedForApproval
PurchaseOrderApproved
PurchaseOrderRejected
PurchaseOrderSent
PurchaseOrderAcknowledged
PurchaseOrderAmended
PurchaseOrderPartiallyReceived
PurchaseOrderReceived
PurchaseOrderClosed
PurchaseOrderCancelled

SupplierBackorderDetected
SupplierDeliveryDelayed

GoodsReceiptStarted
GoodsReceiptCompleted

PurchaseQuantityDiscrepancyDetected
PurchasePriceDiscrepancyDetected

SupplierGoodsQualityHeld
SupplierGoodsAccepted
SupplierGoodsRejected

SupplierReturnCreated
SupplierReturnAuthorized
SupplierReturnDispatched
SupplierReturnCompleted

SupplierPerformanceUpdated
SupplierRiskDetected

EmergencyPurchaseRequested
EmergencyPurchaseApproved
EmergencyPurchaseCompleted

PurchaseConflictDetected
PurchaseConflictResolved

PurchaseSynchronizationStarted
PurchaseSynchronizationCompleted
PurchaseSynchronizationFailed
```

---

# 124. RELATIONSHIPS

```text
Supplier
    PROVIDES SupplierProduct

SupplierProduct
    MAPS_TO InventoryItem

InventoryState
    MAY_CREATE PurchaseRequirement

Event
    MAY_CREATE PurchaseRequirement

ProductionForecast
    MAY_CREATE PurchaseRequirement

PurchaseRequirement
    MAY_CREATE PurchaseRequisition

PurchaseRequisition
    CONTAINS PurchaseRequisitionItem

PurchaseRequisition
    MAY_REQUEST SupplierQuotation

SupplierQuotation
    PROVIDED_BY Supplier

SupplierQuotation
    MAY_LEAD_TO PurchaseOrder

PurchaseOrder
    SENT_TO Supplier

PurchaseOrder
    CONTAINS PurchaseOrderItem

PurchaseOrder
    MAY_REFERENCE SupplierContract

PurchaseOrder
    MAY_CREATE SupplierCommitment

SupplierDelivery
    FULFILLS PurchaseOrder

GoodsReceipt
    REFERENCES PurchaseOrder

GoodsReceipt
    CREATES InventoryReceipt

GoodsReceipt
    MAY_TRIGGER QualityCheck

RejectedGoods
    MAY_CREATE SupplierReturn

SupplierInvoice
    MAY_REFERENCE PurchaseOrder

SupplierInvoice
    MAY_CREATE AccountPayable

PurchasingHistory
    CONTRIBUTES_TO SupplierPerformance

PurchasingState
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 125. BUSINESS RULES

The following rules apply:

1. Purchase Requirement is distinct from Purchase Requisition and Purchase Order.

2. Stock shortage does not automatically authorize a Purchase.

3. Purchase Orders shall be issued only to Suppliers permitted by policy.

4. Purchase approval shall respect configured authority thresholds.

5. Supplier quotations shall preserve validity and source.

6. Supplier selection shall remain explainable.

7. Historical Purchase Order prices shall not be rewritten by later Supplier price changes.

8. Purchase Order amendments shall remain traceable.

9. Goods Receipt shall remain distinct from Purchase Order.

10. Delivered quantity, accepted quantity and rejected quantity are separate concepts.

11. Quality-Held Supplier goods shall not become available Inventory.

12. Receipt discrepancies shall remain explicit.

13. Purchase returns shall preserve the originating Receipt where possible.

14. Inventory shall only increase through authorized receiving or adjustment mechanisms.

15. AI shall not invent Supplier prices, quantities or delivery commitments.

16. Emergency Purchasing shall remain governed and auditable.

17. External Supplier and Purchase identifiers shall remain integration mappings.

18. Accounts Payable shall remain financially authoritative for supplier obligations.

19. Open Purchase Orders and Goods in Transit shall be considered when generating new replenishment recommendations.

20. Food Safety, Quality and Supplier approval constraints shall override lowest-price optimization.

---

# 126. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Supplier

SupplierStatus

SupplierProduct

SupplierInventoryItemMapping

PurchaseRequirement

PurchaseRequirementSource

PurchaseRequisition

PurchaseRequisitionItem

PurchaseApproval

SupplierQuotationReference

PurchaseOrder

PurchaseOrderItem

PurchaseOrderStatus

SupplierAcknowledgment

ExpectedDelivery

GoodsReceipt

GoodsReceiptItem

ReceivingDiscrepancy

ReceivingQualityReference

SupplierReturn

SupplierPerformanceProfile

ExternalSupplierMapping

ExternalPurchaseOrderMapping

PurchasingHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Automated Supplier Negotiation

Autonomous Purchase Order Approval

AI Supplier Contract Negotiation

Advanced Procurement Optimization

Predictive Supplier Failure Modeling

Dynamic Multi-Supplier Allocation

Autonomous Inter-Branch Procurement Consolidation

Full Procurement Marketplace

Digital Twin Supply Chain Simulation
```

---

# 127. IMPLEMENTATION PRINCIPLE

This document defines the logical Purchasing Model.

It does not prescribe:

* ERP vendor.
* Database schema.
* Supplier portal.
* EDI implementation.
* Accounts Payable implementation.
* Approval UI.
* Procurement optimization algorithm.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
PURCHASE REQUIREMENT

PURCHASE REQUISITION

APPROVAL

SUPPLIER QUOTATION

PURCHASE ORDER

SUPPLIER COMMITMENT

GOODS RECEIPT

QUALITY ACCEPTANCE

INVENTORY RECEIPT

SUPPLIER RETURN

SUPPLIER INVOICE

ACCOUNT PAYABLE
```

---

# 128. FINAL RULE

Before ECIP recommends, creates, modifies or represents a Purchase as completed, it shall be able to determine:

> What operational demand created the Purchase Requirement?

> What Inventory Item, quantity, unit and required date are involved?

> Is stock already available, reserved, committed, in transit or already ordered?

> Is a Purchase Requisition and approval required?

> Which Suppliers are authorized to provide the Item?

> What are their actual prices, lead times, Quality performance and commercial terms?

> Which Supplier and quotation were selected, and why?

> What exactly was ordered?

> What did the Supplier acknowledge?

> What was actually delivered?

> What quantity passed receiving and Quality Control?

> What quantity entered usable Inventory?

> Were there shortages, over-deliveries, price discrepancies, Quality problems or returns?

> What financial obligation was created?

> Does any unresolved purchasing issue threaten Inventory, Production, an Event or a Customer commitment?

> Can the complete purchasing decision and lifecycle be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably use Purchasing information for replenishment, Supplier management, Inventory planning, Production support or executive decision making.

