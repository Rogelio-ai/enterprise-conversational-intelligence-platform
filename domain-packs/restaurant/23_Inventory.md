# 23_Inventory.md

**Document ID:** RDM-023
**Document Name:** Inventory
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Inventory Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete operational state of restaurant stock across ingredients, beverages, prepared components, packaging materials, supplies and other controlled inventory items.

The Inventory Model enables ECIP to understand:

* What stock exists.
* Where it is located.
* How much is available.
* How much is reserved.
* How much is unusable.
* What is approaching expiration.
* What is currently committed to production.
* What must be replenished.
* What inventory conditions affect Product availability.

Inventory is not merely a quantity on hand.

It is a governed operational model connecting:

* Ingredients.
* Products.
* Recipes.
* Warehouses.
* Storage locations.
* Purchasing.
* Receiving.
* Production.
* Waste.
* Transfers.
* Reservations.
* Orders.
* Events.
* Cost.
* Quality.
* Compliance.
* Operational Intelligence.

---

# 2. OBJECTIVES

The Inventory Model enables ECIP to:

* Track stock quantities.
* Track stock by location.
* Track stock by lot or batch.
* Track reservations.
* Track committed stock.
* Track available stock.
* Track unusable stock.
* Track expired stock.
* Track inventory movements.
* Track transfers.
* Track adjustments.
* Support recipe availability.
* Support Product offerability.
* Support production planning.
* Support purchasing requirements.
* Detect low stock.
* Detect stockouts.
* Detect excess stock.
* Detect expiration risk.
* Detect inventory variance.
* Support FIFO/FEFO policies.
* Support warehouse operations.
* Preserve complete inventory history.
* Support Inventory Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Resource
* Asset
* Location
* Quantity
* Measurement
* Event
* Action
* Evidence Record
* Policy
* Context Snapshot
* External Entity Reference

Restaurant-specific Inventory entities remain within the Restaurant Domain Pack.

---

# 4. INVENTORY PRINCIPLE

The platform shall distinguish between:

```text
INVENTORY ITEM

STOCK LOCATION

STOCK LOT

ON-HAND QUANTITY

AVAILABLE QUANTITY

RESERVED QUANTITY

COMMITTED QUANTITY

UNUSABLE QUANTITY

INVENTORY MOVEMENT

INVENTORY ADJUSTMENT
```

These concepts shall not be collapsed into one field.

---

# 5. INVENTORY ITEM

An `InventoryItem` represents a stock-controlled restaurant asset.

Typical attributes include:

* Inventory Item ID
* Name
* Item type
* SKU
* Unit of measure
* Ingredient reference
* Product reference where applicable
* Category
* Storage requirements
* Shelf-life policy
* Cost reference
* Status
* External mappings

---

# 6. INVENTORY ITEM TYPES

Examples include:

```text
INGREDIENT

BEVERAGE

PREPARED_COMPONENT

PACKAGING

CLEANING_SUPPLY

OPERATING_SUPPLY

RETAIL_PRODUCT

DISPOSABLE

OTHER
```

---

# 7. INGREDIENT INVENTORY

Ingredients defined in `11_Recipes.md` may map to Inventory Items.

Example:

```text
Ingredient:
Salmon Fillet

Inventory Item:
Fresh Salmon Fillet
```

Ingredient identity and Inventory identity remain distinct where needed.

---

# 8. NON-INGREDIENT INVENTORY

Examples:

* Bottled beverages.
* Disposable containers.
* Napkins.
* Cutlery.
* Cleaning supplies.
* Gift products.

These may be operationally critical even if not part of a Recipe.

---

# 9. STOCK LOCATION

A `StockLocation` represents a physical or logical place where stock is held.

Examples:

* Main warehouse.
* Dry storage.
* Refrigerator.
* Freezer.
* Kitchen station.
* Bar.
* Prep area.
* Delivery staging area.

Stock Locations extend the Restaurant Locations model.

---

# 10. LOCATION HIERARCHY

Example:

```text
Branch
    ↓
Warehouse
    ↓
Cold Storage
    ↓
Shelf / Bin
```

The level of detail may vary by restaurant.

---

# 11. STOCK LOT

A `StockLot` represents a traceable quantity received or produced under common characteristics.

Typical attributes:

* Lot ID
* Inventory Item
* Supplier
* Purchase receipt
* Received quantity
* Remaining quantity
* Received date
* Production date
* Expiration date
* Quality status
* Storage location
* Unit cost

---

# 12. LOT TRACEABILITY

Lot tracking may support:

* Food Safety.
* Expiration control.
* Supplier claims.
* Recall.
* Quality investigation.
* Cost traceability.

Not every item requires lot-level tracking.

---

# 13. STOCK BALANCE

A `StockBalance` represents the current quantity of an Inventory Item at a defined Stock Location.

Typical dimensions:

* Item
* Location
* Lot where applicable
* Quantity
* Unit
* Timestamp

---

# 14. ON-HAND QUANTITY

`OnHandQuantity` represents physical stock recorded as present.

Conceptually:

```text
ON_HAND
=
total recorded physical stock
```

This does not imply the entire quantity is usable or available.

---

# 15. AVAILABLE QUANTITY

`AvailableQuantity` represents stock available for new operational use.

Conceptually:

```text
AVAILABLE
=
ON_HAND
-
RESERVED
-
COMMITTED
-
HELD
-
UNUSABLE
```

Exact calculation remains implementation-specific.

---

# 16. RESERVED QUANTITY

Reserved stock is intentionally protected for a future known need.

Examples:

* Event.
* Banquet.
* Scheduled Order.
* Critical production plan.

Reservation does not yet imply physical consumption.

---

# 17. COMMITTED QUANTITY

Committed stock represents quantity already allocated to confirmed production demand.

Examples:

* Confirmed Order.
* Active Production Plan.

---

# 18. QUALITY-HOLD QUANTITY

Stock under Quality Hold shall not be treated as available.

Examples:

* Suspect Ingredient Lot.
* Receiving inspection pending.
* Temperature issue.

---

# 19. UNUSABLE QUANTITY

Unusable stock may include:

* Expired.
* Damaged.
* Contaminated.
* Rejected.
* Spoiled.

Unusable quantity shall remain traceable until proper disposition.

---

# 20. INVENTORY STATUS

Suggested item-level operational states:

```text
AVAILABLE

LOW_STOCK

CRITICAL_STOCK

OUT_OF_STOCK

OVERSTOCK

QUALITY_HOLD

UNAVAILABLE
```

---

# 21. INVENTORY MOVEMENT

An `InventoryMovement` represents a quantity change or relocation.

Typical attributes:

* Movement ID
* Inventory Item
* Lot
* Quantity
* Unit
* Movement type
* Source location
* Destination location
* Reference
* Actor
* Timestamp
* Reason
* Cost reference

---

# 22. MOVEMENT TYPES

Initial types include:

```text
RECEIPT

TRANSFER_IN

TRANSFER_OUT

PRODUCTION_CONSUMPTION

PRODUCTION_OUTPUT

SALE_CONSUMPTION

WASTE

RETURN_TO_SUPPLIER

ADJUSTMENT_IN

ADJUSTMENT_OUT

COUNT_CORRECTION

RESERVATION

RESERVATION_RELEASE

QUALITY_HOLD

QUALITY_RELEASE
```

---

# 23. RECEIPT

A Receipt increases stock after authorized receiving.

Typical flow:

```text
Purchase Order
    ↓
Supplier Delivery
    ↓
Receiving
    ↓
Quality Check
    ↓
Inventory Receipt
```

Detailed Purchasing behavior belongs to `24_Purchasing.md`.

---

# 24. TRANSFER

A Transfer moves stock between authorized locations.

Example:

```text
Main Warehouse
    ↓
Kitchen Cold Storage
```

Transfers shall preserve both source and destination.

---

# 25. INTER-BRANCH TRANSFER

Stock may move between Branches where business policy permits.

Inter-Branch transfers may require:

* Approval.
* Dispatch.
* Receiving confirmation.
* Cost handling.
* Traceability.

---

# 26. TRANSFER LIFECYCLE

Suggested states:

```text
REQUESTED
→ APPROVED
→ DISPATCHED
→ IN_TRANSIT
→ RECEIVED
→ COMPLETED
```

Alternative states:

```text
CANCELLED
REJECTED
PARTIALLY_RECEIVED
```

---

# 27. PRODUCTION CONSUMPTION

Production may consume Inventory Items.

Theoretical consumption originates from Recipe.

Actual Inventory Movement records authoritative physical consumption where implemented.

---

# 28. PRODUCTION OUTPUT

Production may create Prepared Components.

Example:

```text
Raw Ingredients
    ↓
Production Batch
    ↓
Prepared Sauce
    ↓
Prepared Component Inventory
```

---

# 29. WASTE

Waste reduces usable inventory.

Possible reasons:

* Expiration.
* Spoilage.
* Preparation loss.
* Overproduction.
* Quality rejection.
* Damage.
* Customer cancellation after preparation.

Detailed Ingredient lifecycle is defined in `25_Ingredient_Lifecycle.md`.

---

# 30. INVENTORY ADJUSTMENT

An `InventoryAdjustment` corrects recorded inventory.

Reasons may include:

* Physical count discrepancy.
* Data correction.
* Unrecorded waste.
* Receiving error.

Adjustments shall require explicit reason and audit evidence.

---

# 31. POSITIVE ADJUSTMENT

A Positive Adjustment increases recorded stock.

This shall not be used casually to hide receiving or transaction failures.

---

# 32. NEGATIVE ADJUSTMENT

A Negative Adjustment reduces recorded stock.

Large or unusual adjustments may require approval.

---

# 33. PHYSICAL COUNT

A `PhysicalInventoryCount` represents observed physical stock.

Typical attributes:

* Count ID
* Location
* Item
* Lot
* Counted quantity
* Expected quantity
* Variance
* Employee
* Timestamp
* Status

---

# 34. INVENTORY COUNT TYPES

Examples:

* Full inventory.
* Cycle count.
* Spot count.
* Critical-item count.

---

# 35. COUNT VARIANCE

Conceptually:

```text
COUNT VARIANCE
=
PHYSICAL QUANTITY
-
SYSTEM QUANTITY
```

Variance may indicate:

* Waste.
* Theft.
* Portion problems.
* Receiving error.
* Data-entry error.
* Process failure.

Root cause shall not be assumed automatically.

---

# 36. INVENTORY RECONCILIATION

Inventory Reconciliation evaluates discrepancies and may create adjustments after review.

The original expected and counted values shall remain preserved.

---

# 37. UNIT OF MEASURE

Inventory shall support governed measurement units.

Examples:

* kilogram.
* gram.
* liter.
* milliliter.
* piece.
* bottle.
* case.
* package.

---

# 38. UNIT CONVERSION

Purchasing, Inventory and Recipe may use different units.

Example:

```text
Purchased:
1 case = 12 bottles

Inventory:
bottle

Recipe:
milliliters
```

Conversion rules shall be explicit.

---

# 39. BASE INVENTORY UNIT

Each Inventory Item should define a normalized base unit where useful.

This improves:

* Costing.
* Consumption.
* Reconciliation.
* Recipe calculations.

---

# 40. STORAGE REQUIREMENT

Inventory Items may require:

* Ambient storage.
* Refrigeration.
* Freezing.
* Dry storage.
* Secure storage.

Storage rules shall be explicit.

---

# 41. STORAGE TEMPERATURE

Where relevant, stock may define acceptable temperature ranges.

Violations may create:

* Quality Hold.
* Compliance Incident.
* Waste.

---

# 42. SHELF LIFE

An Inventory Item may define expected shelf life.

Shelf life may depend on:

* Supplier.
* Packaging.
* Storage state.
* Open/closed state.
* Production state.

---

# 43. EXPIRATION DATE

Expiration may be defined per Lot.

Expired stock shall not remain normally available.

---

# 44. BEST-BEFORE VS SAFETY EXPIRATION

Where relevant, the model should distinguish:

* Quality-oriented best-before date.
* Safety-oriented expiration/use-by limit.

Policies shall determine allowed use.

---

# 45. FEFO

`First Expired, First Out` may be used where expiration is the primary issue.

Conceptually:

```text
Use stock with earliest valid expiration first.
```

---

# 46. FIFO

`First In, First Out` may be used where receipt chronology governs stock rotation.

The applicable policy shall be explicit.

---

# 47. INVENTORY ALLOCATION

An `InventoryAllocation` links stock to a future or active requirement.

Examples:

* Event.
* Production Plan.
* Scheduled Order.

---

# 48. INVENTORY RESERVATION

Reservation may protect stock from unrelated future consumption.

Typical attributes:

* Reservation ID
* Inventory Item
* Quantity
* Source requirement
* Start time
* Expiration
* Status

---

# 49. RESERVATION EXPIRATION

Inventory reservations shall be released when:

* Requirement cancelled.
* Reservation expires.
* Production completed.
* Event cancelled.

Stale reservations shall not indefinitely reduce available stock.

---

# 50. STOCKOUT

A `Stockout` occurs when required available quantity reaches zero or becomes insufficient.

Possible consequences:

* Product unavailable.
* Recipe infeasible.
* Purchasing urgency.
* Substitution workflow.

---

# 51. PARTIAL STOCKOUT

An Inventory Item may have enough stock for some, but not all, expected demand.

Example:

```text
Available salmon:
2.2 kg

Required for existing confirmed demand:
1.8 kg

Remaining for new orders:
0.4 kg
```

This should influence offerability.

---

# 52. LOW STOCK

A `LowStockCondition` may occur when quantity falls below a configured threshold.

Thresholds may consider:

* Static minimum.
* Expected demand.
* Lead time.
* Safety stock.

---

# 53. SAFETY STOCK

Safety Stock represents protected buffer stock.

It may be used for:

* Demand uncertainty.
* Supplier delays.
* Critical Ingredients.

---

# 54. REORDER POINT

A `ReorderPoint` may indicate when replenishment should be initiated.

Potential inputs:

```text
Average Demand
+
Supplier Lead Time
+
Safety Stock
```

---

# 55. PAR LEVEL

Restaurants may use a `ParLevel` as the desired standard stock quantity.

Example:

```text
Tomatoes:
Par = 20 kg

Current = 9 kg
```

This may generate replenishment need.

---

# 56. MAXIMUM STOCK LEVEL

A maximum stock threshold may help reduce:

* Waste.
* Expiration.
* Cash tied in inventory.

---

# 57. OVERSTOCK

Overstock occurs when stock materially exceeds expected operational need.

Possible consequence:

* Expiration risk.
* Excess working capital.
* Storage pressure.

---

# 58. INVENTORY SHORTAGE FORECAST

Inventory Intelligence may estimate future shortage based on:

* Current stock.
* Reservations.
* Events.
* Scheduled Orders.
* Historical demand.
* Purchasing lead time.

This is predictive.

---

# 59. INVENTORY SURPLUS FORECAST

Future surplus may indicate:

* Excess purchase.
* Demand decline.
* Event cancellation.
* Forecast error.

---

# 60. RECIPE AVAILABILITY

Recipe execution depends on Inventory.

Conceptually:

```text
Recipe
    ↓
Required Ingredients
    ↓
Available Inventory
    ↓
Recipe Feasibility
```

---

# 61. PRODUCT AVAILABILITY

Inventory contributes to Product offerability.

A Product may become unavailable when one critical required Ingredient is unavailable.

---

# 62. CONDITIONAL PRODUCT AVAILABILITY

A Product may remain available if an authorized substitution exists.

Example:

```text
Regular side unavailable
Authorized alternative available
```

The Customer shall be informed when material.

---

# 63. INVENTORY AND MENU

Menu may display a Product.

Inventory determines whether it can currently be produced.

Menu state and Inventory state shall remain separate.

---

# 64. INVENTORY AND ORDER

Order confirmation may reserve or commit relevant stock according to implementation policy.

Inventory shall not create commercial Orders.

---

# 65. INVENTORY AND PRODUCTION

Production consumes stock and may produce Prepared Components.

This is one of the most important runtime relationships in the model.

---

# 66. INVENTORY AND PURCHASING

Purchasing replenishes stock.

Inventory may generate purchase requirements.

Purchasing owns supplier and Purchase Order lifecycle.

---

# 67. INVENTORY AND EVENTS

Confirmed Events may reserve substantial stock in advance.

Inventory should consider this future committed demand.

---

# 68. INVENTORY AND DELIVERY

Delivery affects Packaging Inventory and may also influence demand forecasting.

---

# 69. INVENTORY AND TAKE AWAY

Take Away may consume:

* Food Ingredients.
* Containers.
* Bags.
* Disposable utensils.

Packaging stock may therefore affect Take Away feasibility.

---

# 70. PACKAGING INVENTORY

Packaging shall be treated as real operational inventory where required.

Example:

```text
Food available
but
required delivery containers out of stock
```

Result:

Delivery offerability may be affected.

---

# 71. BAR INVENTORY

Beverages may require:

* Bottle-level stock.
* Open-bottle estimation.
* Portion consumption.
* Keg tracking.

Detailed implementation may vary.

---

# 72. LIQUID INVENTORY

Some beverage stock may be tracked by:

* Bottle.
* Volume.
* Pour.

The model shall support units appropriate to the item.

---

# 73. PREPARED COMPONENT INVENTORY

Prepared Components from `21_Production.md` may have:

* Quantity.
* Batch.
* Expiration.
* Storage.
* Reservation.
* Consumption.

---

# 74. INVENTORY LOT QUALITY

A Stock Lot may have Quality state:

```text
PENDING_INSPECTION

ACCEPTED

QUALITY_HOLD

REJECTED

RELEASED
```

Only usable stock should contribute to available quantity.

---

# 75. RECALL

A `StockRecall` may identify Lots that must be isolated or removed.

Possible sources:

* Supplier notice.
* Internal Quality issue.
* Regulatory notice.

Recall details may be extended by Compliance.

---

# 76. RECALL IMPACT

Recall may affect:

```text
Stock Lots
    ↓
Prepared Batches
    ↓
Products
    ↓
Orders / Customers
```

where traceability exists.

This is critical for food safety.

---

# 77. INVENTORY COST

Inventory may preserve:

* Unit cost.
* Average cost.
* Lot cost.
* Standard cost reference.

Detailed accounting methodology belongs to financial systems.

---

# 78. WEIGHTED AVERAGE COST

Some restaurants may use weighted average costing.

The Domain Model supports cost references without mandating one methodology.

---

# 79. LOT COST

Lot-level cost may support precise Recipe and margin analysis.

---

# 80. INVENTORY VALUE

Conceptually:

```text
Inventory Value
=
Quantity
×
Applicable Inventory Cost
```

This is an analytical/financial projection.

---

# 81. SHRINKAGE

Inventory Shrinkage represents unexplained stock reduction.

Potential causes:

* Theft.
* Waste not recorded.
* Overportion.
* Receiving error.
* Data error.

Shrinkage shall not be assigned a cause without evidence.

---

# 82. THEORETICAL VS ACTUAL INVENTORY

The platform shall distinguish:

```text
THEORETICAL STOCK
```

from:

```text
PHYSICALLY COUNTED STOCK
```

Differences may support Inventory Intelligence.

---

# 83. THEORETICAL CONSUMPTION

Based on Recipes and completed production:

```text
Expected Ingredient Use
```

---

# 84. ACTUAL CONSUMPTION

Derived from actual Inventory Movements or physical counts where available.

---

# 85. CONSUMPTION VARIANCE

Conceptually:

```text
Actual Consumption
-
Theoretical Consumption
```

Repeated variance may indicate:

* Portion inconsistency.
* Waste.
* Process issue.
* Recipe mismatch.
* Inventory leakage.

---

# 86. INVENTORY INTELLIGENCE

Potential insights include:

* Fast-moving Items.
* Slow-moving Items.
* Low-stock risks.
* Overstock risks.
* Expiration risk.
* High-variance Items.
* Unusual adjustments.
* Supplier-related shortages.
* Product availability risks.

---

# 87. ABC CLASSIFICATION

Inventory may optionally classify Items by business importance.

Example:

```text
A:
High value / critical

B:
Moderate

C:
Low value
```

This is analytical and configurable.

---

# 88. CRITICAL INVENTORY ITEM

A `CriticalInventoryItem` represents stock whose shortage materially affects restaurant operation.

Examples:

* Primary protein.
* Cooking oil.
* Core packaging.
* Key beverage.

Criticality shall be explicitly governed.

---

# 89. INVENTORY ALERT

Potential alerts:

* Stockout.
* Critical Low Stock.
* Expiration approaching.
* Large variance.
* Abnormal adjustment.
* Quality Hold.
* Transfer delay.

Alerts shall be actionable.

---

# 90. EXPIRATION RISK

`ExpirationRisk` may estimate stock likely to expire before consumption.

Potential inputs:

* Current quantity.
* Expiration date.
* Forecast demand.

This is predictive.

---

# 91. INVENTORY-DRIVEN SALES INTELLIGENCE

Where appropriate, Sales Intelligence may consider stock conditions.

Example:

* Promote safe, appropriate overstocked Product.

However:

* Customer relevance.
* Margin.
* Quality.
* Safety.

remain mandatory constraints.

---

# 92. INVENTORY-DRIVEN MENU RESTRICTION

Low or zero stock may trigger:

* Product low availability.
* Product temporary unavailability.
* Product restriction.

This shall be governed rather than inferred casually by AI.

---

# 93. INVENTORY AND WASTE INTELLIGENCE

Waste data may reveal:

* Overproduction.
* Low demand.
* Poor storage.
* Recipe variance.
* Supplier quality issues.

---

# 94. INVENTORY AND EXECUTIVE INTELLIGENCE

Potential KPIs include:

* Inventory Turnover.
* Stockout Rate.
* Waste Rate.
* Inventory Value.
* Days of Inventory.
* Inventory Variance.
* Expiration Loss.
* Purchase-to-Consumption efficiency.

---

# 95. MULTI-BRANCH INVENTORY

Restaurant groups may operate centralized or independent Inventory.

Possible models:

* Branch-owned stock.
* Shared warehouse.
* Central warehouse.
* Transfer network.

Ownership shall remain explicit.

---

# 96. CENTRAL WAREHOUSE

A central warehouse may supply multiple Branches.

This may require:

* Replenishment requests.
* Transfers.
* Dispatch.
* Receiving.

---

# 97. INVENTORY OWNERSHIP

Inventory may belong to:

* Restaurant Group.
* Brand.
* Branch.
* Warehouse.

Ownership and physical location are not always identical.

---

# 98. INVENTORY AUTHORIZATION

Sensitive actions may include:

* Large adjustment.
* Stock write-off.
* Inter-Branch transfer.
* Quality release.
* Manual count override.

These may require approval.

---

# 99. AI AUTHORITY LIMIT

AI may:

* Analyze stock.
* Detect risk.
* Recommend replenishment.
* Explain availability.
* Identify likely shortages.

AI shall not:

* Invent stock quantities.
* Perform unauthorized write-offs.
* Release Quality-Hold stock.
* Create arbitrary stock adjustments.
* Ignore expiration or Food Safety rules.

---

# 100. INVENTORY SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Sale consumption

Inventory System:
Stock balance

Purchasing:
Receipts

Production:
Theoretical consumption

ECIP:
Inventory intelligence and orchestration
```

Authoritative ownership shall be explicitly configured.

---

# 101. EXTERNAL INVENTORY MAPPING

External systems may use:

* Item ID.
* Warehouse ID.
* Lot ID.
* Movement ID.

These shall map to canonical Inventory entities.

---

# 102. INVENTORY IMPORT

Existing Inventory may be imported during onboarding.

Import shall preserve:

* Source.
* Item mapping.
* Quantity.
* Unit.
* Location.
* Timestamp.
* Confidence or reconciliation status.

---

# 103. INVENTORY SYNCHRONIZATION

Synchronization may include:

* Balances.
* Movements.
* Lot state.
* Transfers.
* Adjustments.

It shall be:

* Idempotent.
* Observable.
* Traceable.

---

# 104. INVENTORY CONFLICT

Example:

```text
ECIP:
10 kg available

External Inventory:
6 kg available
```

The conflict shall be surfaced and resolved through configured source authority.

AI shall not arbitrarily choose one value.

---

# 105. INVENTORY EVENTS

Initial domain events include:

```text
InventoryItemCreated
InventoryItemUpdated
InventoryItemActivated
InventoryItemDeactivated

StockLocationCreated
StockLocationUpdated

StockLotCreated
StockLotReceived
StockLotQualityHeld
StockLotReleased
StockLotRejected
StockLotExpired

InventoryReceiptRecorded

InventoryTransferRequested
InventoryTransferApproved
InventoryTransferDispatched
InventoryTransferReceived
InventoryTransferCompleted
InventoryTransferCancelled

InventoryReservationCreated
InventoryReservationReleased
InventoryReservationExpired

InventoryCommitted
InventoryCommitmentReleased

InventoryConsumptionRecorded
InventoryProductionOutputRecorded

InventoryWasteRecorded

InventoryAdjustmentRequested
InventoryAdjustmentApproved
InventoryAdjustmentRecorded

PhysicalInventoryCountStarted
PhysicalInventoryCountCompleted
InventoryVarianceDetected
InventoryReconciled

LowStockDetected
CriticalStockDetected
StockoutDetected
OverstockDetected

ExpirationRiskDetected

InventoryRecallStarted
InventoryRecallCompleted

InventoryConflictDetected
InventoryConflictResolved

InventorySynchronizationStarted
InventorySynchronizationCompleted
InventorySynchronizationFailed
```

---

# 106. RELATIONSHIPS

```text
InventoryItem
    STORED_AT StockLocation

InventoryItem
    MAY_HAVE StockLot

StockLot
    HAS StockBalance

InventoryItem
    MAY_REFERENCE Ingredient

InventoryItem
    MAY_REFERENCE Product

StockLot
    MAY_REFERENCE Supplier

InventoryMovement
    AFFECTS StockBalance

InventoryTransfer
    MOVES InventoryItem

ProductionRequirement
    MAY_RESERVE InventoryItem

ProductionExecution
    CONSUMES InventoryItem

ProductionBatch
    MAY_PRODUCE InventoryItem

Recipe
    REQUIRES Ingredient

Ingredient
    MAPS_TO InventoryItem

Event
    MAY_RESERVE InventoryItem

PurchaseReceipt
    CREATES InventoryReceipt

QualityHold
    MAY_BLOCK StockLot

InventoryState
    CONTRIBUTES_TO ProductOfferability

InventoryHistory
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 107. BUSINESS RULES

The following rules apply:

1. Inventory quantities shall always identify their Unit of Measure.

2. Inventory Item identity shall remain distinct from Ingredient and Product identity.

3. On-Hand quantity shall not be interpreted automatically as Available quantity.

4. Reserved, committed, held and unusable quantities shall reduce usable availability as applicable.

5. Expired or rejected stock shall not contribute to normal Product offerability.

6. Every Inventory Movement shall preserve its source and reason.

7. Transfers shall preserve source and destination.

8. Inventory Adjustments shall be explicit and auditable.

9. Historical Inventory Movements shall not be rewritten to hide reconciliation issues.

10. Physical Counts and system balances shall remain distinct until reconciliation.

11. Recipe-based consumption is theoretical unless backed by authoritative Inventory movement.

12. Quality Hold shall override normal stock availability.

13. Lot traceability shall be preserved where required.

14. Inventory reservations shall expire or release when the underlying requirement no longer exists.

15. AI shall not invent stock balances or adjust them without authorization.

16. External identifiers shall remain integration mappings.

17. Current Inventory state shall contribute to Product and Recipe feasibility.

18. Food Safety and Quality constraints shall override commercial inventory optimization.

---

# 108. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
InventoryItem

InventoryItemType

StockLocation

StockBalance

StockLot

InventoryMovement

InventoryMovementType

InventoryReceipt

InventoryTransfer

InventoryReservation

InventoryCommitment

InventoryAdjustment

PhysicalInventoryCount

InventoryVariance

AvailableQuantity

LowStockCondition

StockoutCondition

ExpirationDate

InventoryQualityStatus

InventoryExternalMapping

InventoryHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Demand-Based Safety Stock

Predictive Inventory Optimization

Autonomous Replenishment

Advanced Multi-Branch Rebalancing

AI Purchase Quantity Optimization

Advanced Expiration Optimization

Digital Twin Inventory Simulation

Autonomous Stock Transfer Optimization
```

---

# 109. IMPLEMENTATION PRINCIPLE

This document defines the logical Inventory Model.

It does not prescribe:

* Database schema.
* ERP implementation.
* Warehouse Management System.
* Barcode hardware.
* RFID implementation.
* Purchasing system.
* Inventory forecasting algorithm.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
INVENTORY ITEM

STOCK LOT

STOCK LOCATION

ON-HAND STOCK

AVAILABLE STOCK

RESERVED STOCK

COMMITTED STOCK

QUALITY-HOLD STOCK

INVENTORY MOVEMENT

PHYSICAL COUNT

INVENTORY VARIANCE
```

---

# 110. FINAL RULE

Before ECIP concludes that stock is available, unavailable, low, excess or suitable for Product production, it shall be able to determine:

> Which Inventory Item is involved?

> At which Branch and Stock Location is it stored?

> In which Unit of Measure is it tracked?

> Which Lots exist?

> What quantity is physically recorded?

> What quantity is reserved or committed?

> What quantity is under Quality Hold or otherwise unusable?

> What quantity is actually available for new demand?

> Are any Lots expired or approaching expiration?

> What recent Movements explain the current balance?

> Is there any Inventory conflict or unreconciled Physical Count?

> What future confirmed demand will consume this stock?

> Does current stock state affect any Product, Recipe, Order, Event or Customer commitment?

> Can every material Inventory change be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably use Inventory information for Product offerability, Production, Purchasing, Customer commitments or business intelligence.

