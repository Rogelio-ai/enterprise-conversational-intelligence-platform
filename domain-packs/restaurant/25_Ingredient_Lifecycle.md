# 25_Ingredient_Lifecycle.md

**Document ID:** RDM-025
**Document Name:** Ingredient Lifecycle
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Ingredient Lifecycle Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of an Ingredient from sourcing and receiving through storage, transformation, reservation, production use, waste, expiration, recall and final disposition.

The Ingredient Lifecycle Model connects:

* Ingredients.
* Suppliers.
* Purchasing.
* Receiving.
* Inventory.
* Storage.
* Lots.
* Quality Control.
* Recipes.
* Production.
* Prepared Components.
* Waste.
* Cost.
* Food Safety.
* Compliance.
* Product availability.
* Customer safety.
* Operational Intelligence.
* Executive Intelligence.

The lifecycle shall preserve complete traceability from source to consumption where operationally and legally required.

---

# 2. OBJECTIVES

The Ingredient Lifecycle Model enables ECIP to:

* Identify each Ingredient.
* Track Ingredient sourcing.
* Track Supplier origin.
* Track lots and batches.
* Track receiving.
* Track Quality status.
* Track storage.
* Track movement.
* Track reservation.
* Track production consumption.
* Track transformation.
* Track yield.
* Track waste.
* Track expiration.
* Track recalls.
* Support allergen reasoning.
* Support Food Safety.
* Support Recipe feasibility.
* Support Product offerability.
* Support cost analysis.
* Support traceability.
* Support waste reduction.
* Detect anomalies.
* Preserve historical evidence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Asset
* Resource
* Material
* Location
* Quantity
* Measurement
* Event
* Evidence Record
* Policy
* Action
* Incident
* External Entity Reference
* Context Snapshot

Restaurant-specific Ingredient entities remain within the Restaurant Domain Pack.

---

# 4. INGREDIENT LIFECYCLE PRINCIPLE

The platform shall distinguish between:

```text
INGREDIENT DEFINITION

SUPPLIER PRODUCT

INGREDIENT LOT

INVENTORY STOCK

QUALITY STATE

STORAGE STATE

RESERVED QUANTITY

PRODUCTION CONSUMPTION

TRANSFORMED OUTPUT

WASTE

FINAL DISPOSITION
```

These concepts shall remain independently traceable.

---

# 5. INGREDIENT

An `Ingredient` represents the canonical restaurant-domain identity of a food, beverage or consumable component used in Recipes or Production.

Typical attributes include:

* Ingredient ID
* Name
* Category
* Base Unit of Measure
* Dietary attributes
* Allergen attributes
* Storage requirements
* Shelf-life rules
* Preparation properties
* Inventory Item mapping
* Status
* External identifiers

---

# 6. INGREDIENT STATUS

Suggested lifecycle states:

```text
DRAFT

ACTIVE

SUSPENDED

DISCONTINUED

ARCHIVED
```

Ingredient lifecycle status is distinct from current stock availability.

---

# 7. INGREDIENT CATEGORIES

Examples:

* Meat
* Poultry
* Seafood
* Dairy
* Produce
* Grain
* Spice
* Oil
* Sauce
* Beverage Base
* Alcohol
* Bakery Ingredient
* Frozen Ingredient
* Dry Ingredient
* Prepared Component Ingredient

The category model shall remain configurable.

---

# 8. RAW INGREDIENT

A `RawIngredient` represents a material requiring transformation or preparation before final service.

Examples:

* Raw beef.
* Fresh vegetables.
* Flour.
* Fresh salmon.

---

# 9. READY-TO-USE INGREDIENT

A `ReadyToUseIngredient` may be consumed with minimal transformation.

Examples:

* Bottled sauce.
* Packaged beverage.
* Prepared garnish.
* Commercial bread product.

---

# 10. INGREDIENT VS INVENTORY ITEM

Ingredient represents semantic food composition.

Inventory Item represents the stock-controlled operational asset.

Example:

```text
Ingredient:
Tomato

Inventory Item A:
Roma Tomato 10 kg case

Inventory Item B:
Organic Tomato 5 kg case
```

Multiple Inventory Items may map to the same Ingredient when policy permits.

---

# 11. SUPPLIER PRODUCT

A Supplier Product represents the commercial form in which an Ingredient is purchased.

Typical attributes include:

* Supplier
* Supplier SKU
* Purchase Unit
* Brand
* Specification
* Unit Conversion
* Price reference
* Lead time
* Approval state

---

# 12. INGREDIENT SPECIFICATION

An `IngredientSpecification` defines acceptable properties.

Examples:

* Weight range.
* Grade.
* Fat percentage.
* Size.
* Origin.
* Packaging.
* Freshness.
* Brand.
* Organic certification.
* Cut specification.

Specifications may be used during Receiving and Quality Control.

---

# 13. APPROVED INGREDIENT SOURCE

An Ingredient may have one or more approved Supplier Products.

The restaurant may define:

* Preferred source.
* Alternate source.
* Emergency source.

Use of non-approved sources may require explicit authorization.

---

# 14. PURCHASE REQUIREMENT

Ingredient demand may create a Purchase Requirement through `24_Purchasing.md`.

Possible sources:

* Low stock.
* Reorder point.
* Production forecast.
* Event demand.
* Safety stock.
* Quality rejection.
* Supplier failure.

---

# 15. PURCHASE ORDER

A Purchase Order requests a specific Supplier Product.

The Ingredient model shall retain the canonical semantic identity through the Supplier Product mapping.

---

# 16. INGREDIENT RECEIVING

Ingredient Receiving represents the physical arrival of purchased Ingredient stock.

Typical evidence includes:

* Purchase Order.
* Supplier.
* Delivered quantity.
* Supplier lot.
* Receiving time.
* Temperature where required.
* Expiration.
* Quality observations.

---

# 17. RECEIVING VALIDATION

Ingredient Receiving may require validation of:

```text
Correct Supplier Product

Correct Quantity

Correct Unit

Packaging Integrity

Expiration / Date

Temperature

Specification Compliance

Quality Status
```

---

# 18. INGREDIENT LOT

An `IngredientLot` represents a traceable quantity sharing a common source or production identity.

Typical attributes include:

* Ingredient Lot ID
* Ingredient
* Inventory Item
* Supplier
* Supplier Lot Number
* Purchase Receipt
* Received Date
* Production Date if known
* Expiration Date
* Quantity
* Unit
* Storage Location
* Quality Status
* Cost reference

---

# 19. LOT IDENTITY

Internal Lot identity shall remain distinct from Supplier Lot identity.

Example:

```text
ECIP Lot:
LOT-000882

Supplier Lot:
SL-782918
```

Both shall remain traceable.

---

# 20. LOT TRACEABILITY

Lot-level traceability may support:

* Food Safety.
* Recall.
* Quality investigation.
* Supplier claims.
* Expiration.
* Batch Production traceability.

---

# 21. LOT QUALITY STATUS

Suggested states:

```text
PENDING_INSPECTION

ACCEPTED

QUALITY_HOLD

REJECTED

RELEASED

EXPIRED

RECALLED
```

Only usable Lot quantities should contribute to normal available stock.

---

# 22. QUALITY INSPECTION

Receiving Quality may validate:

* Appearance.
* Smell.
* Temperature.
* Packaging.
* Labeling.
* Expiration.
* Specification.

The detailed Quality model is defined in `22_Quality_Control.md`.

---

# 23. QUALITY HOLD

A Quality Hold prevents use of the Ingredient Lot pending resolution.

Held stock shall not contribute to Product offerability.

---

# 24. LOT REJECTION

A Lot may be rejected due to:

* Incorrect Product.
* Temperature violation.
* Damaged packaging.
* Poor condition.
* Expiration issue.
* Specification failure.
* Contamination concern.

Rejected stock shall receive explicit disposition.

---

# 25. STORAGE

Accepted Ingredient Lots shall be assigned to valid Storage Locations.

Examples:

* Dry storage.
* Refrigerator.
* Freezer.
* Bar storage.
* Secure alcohol storage.
* Kitchen prep refrigerator.

---

# 26. STORAGE REQUIREMENT

An Ingredient may define:

* Temperature range.
* Humidity range.
* Frozen requirement.
* Separation requirements.
* Light sensitivity.
* Security requirement.

---

# 27. STORAGE ASSIGNMENT

A `StorageAssignment` represents placement of a Lot into a Storage Location.

Typical attributes:

* Lot.
* Location.
* Quantity.
* Start time.
* End time.
* Condition.

---

# 28. STORAGE CONDITION

Where monitoring is available, Storage Condition may include:

* Temperature.
* Humidity.
* Door state.
* Equipment health.

Not every deployment requires IoT instrumentation.

---

# 29. STORAGE EXCURSION

A `StorageExcursion` occurs when a monitored condition leaves the permitted range.

Possible consequences:

* Quality Hold.
* Inspection.
* Waste.
* Compliance incident.

---

# 30. STORAGE LOCATION FAILURE

Examples:

* Refrigerator failure.
* Freezer failure.
* Temperature instability.

Affected Lots shall be identifiable.

---

# 31. STOCK ROTATION

Ingredient rotation may follow:

* FEFO.
* FIFO.
* Explicit lot selection.

Applicable policy shall be defined per Ingredient or Inventory class.

---

# 32. FEFO

For perishable stock:

```text
Use valid Lot with earliest expiration first.
```

FEFO may reduce expiration waste.

---

# 33. FIFO

For non-expiry-dominant inventory:

```text
Use oldest received valid stock first.
```

---

# 34. LOT SELECTION

A `LotSelection` determines which specific Lot is used for a consumption or transfer.

Selection shall consider:

* Quality status.
* Expiration.
* Location.
* Reservation.
* Rotation policy.

---

# 35. INGREDIENT TRANSFER

Ingredient stock may move between:

* Warehouse.
* Kitchen.
* Prep area.
* Branches.
* Central Kitchen.

Transfers shall preserve Lot identity where required.

---

# 36. INTER-BRANCH TRANSFER

Perishable Ingredient transfers may require:

* Temperature control.
* Dispatch timing.
* Receiving verification.
* Lot traceability.

---

# 37. INGREDIENT RESERVATION

Ingredient stock may be reserved for:

* Event.
* Scheduled Order.
* Production Plan.
* Critical requirement.

Reservation protects future demand.

---

# 38. INGREDIENT COMMITMENT

Confirmed production may create committed Ingredient demand.

Reserved and committed quantities shall remain distinguishable.

---

# 39. RECIPE DEMAND

Recipes define theoretical Ingredient demand.

Example:

```text
Recipe:
Grilled Salmon

Ingredient:
Salmon 220 g

Order:
10 portions

Theoretical Demand:
2.2 kg
```

---

# 40. PRODUCTION CONSUMPTION

An `IngredientConsumption` represents Ingredient quantity used by Production.

Typical attributes:

* Consumption ID
* Ingredient
* Lot
* Production Execution
* Quantity
* Unit
* Timestamp
* Employee or system
* Waste component if applicable

---

# 41. THEORETICAL CONSUMPTION

Theoretical Consumption is calculated from:

```text
Recipe Quantity × Produced Quantity
```

It is analytical and planning evidence.

---

# 42. ACTUAL CONSUMPTION

Actual Consumption represents authoritative stock movement where recorded.

Actual and theoretical values may differ.

---

# 43. CONSUMPTION VARIANCE

Conceptually:

```text
Actual Consumption
-
Theoretical Consumption
=
Consumption Variance
```

Repeated variance may indicate:

* Portion inconsistency.
* Waste.
* Recipe mismatch.
* Unrecorded consumption.
* Process issue.

---

# 44. INGREDIENT TRANSFORMATION

Some Ingredients are transformed into Prepared Components.

Example:

```text
Raw Tomatoes
    ↓
Preparation
    ↓
Tomato Sauce
```

The transformation shall preserve input-output relationships where appropriate.

---

# 45. TRANSFORMATION BATCH

A Production Batch may consume multiple Ingredient Lots and produce one or more Prepared Components.

Example:

```text
Ingredient Lots
    ↓
Production Batch
    ↓
Prepared Component Lot
```

---

# 46. TRANSFORMATION TRACEABILITY

Where traceability is required, the platform should preserve:

```text
Source Ingredient Lots
    ↓
Production Batch
    ↓
Prepared Component
    ↓
Final Product
```

---

# 47. INGREDIENT YIELD

An Ingredient may experience yield loss through:

* Trimming.
* Peeling.
* Cooking.
* Cleaning.
* Deboning.
* Portioning.

---

# 48. EXPECTED YIELD

Expected Yield may be defined by Recipe or Ingredient preparation standards.

Example:

```text
Raw Beef:
10 kg

Expected Usable Yield:
8.2 kg
```

---

# 49. ACTUAL YIELD

Actual Yield represents usable quantity obtained.

---

# 50. YIELD VARIANCE

Conceptually:

```text
Actual Yield
-
Expected Yield
```

Large recurrent variance may indicate:

* Supplier specification issue.
* Process variation.
* Training issue.
* Measurement problem.

---

# 51. TRIM WASTE

Trim Waste represents expected or actual Ingredient material removed during preparation.

Examples:

* Fat.
* Bones.
* Vegetable peel.
* Stems.

---

# 52. PRODUCTION WASTE

Ingredient waste may also occur from:

* Overportion.
* Spill.
* Incorrect preparation.
* Remake.
* Cancelled Product.

---

# 53. SPOILAGE

`IngredientSpoilage` represents deterioration making stock unsuitable.

Potential causes:

* Temperature failure.
* Age.
* Improper storage.
* Packaging failure.
* Contamination.

---

# 54. EXPIRATION

An Ingredient Lot may expire according to:

* Supplier date.
* Internal Food Safety rule.
* Open-container rule.
* Prepared-state rule.

Expired stock shall not remain normally available.

---

# 55. EXPIRATION RISK

An `IngredientExpirationRisk` may identify stock likely to expire before expected use.

Inputs may include:

* Quantity.
* Expiration date.
* Current demand.
* Forecast demand.

This is predictive.

---

# 56. NEAR-EXPIRY STOCK

Near-expiry stock may be:

* Prioritized under FEFO.
* Used in planning.
* Considered for valid operational strategies.

It shall never be used beyond Food Safety or Quality limits.

---

# 57. EXPIRATION-DRIVEN SALES INTELLIGENCE

Where safe and appropriate, the platform may recommend increasing sales of Products using near-expiry Ingredients.

However:

* Product relevance.
* Food Safety.
* Quality.
* Customer preference.
* Business policy.

shall remain mandatory constraints.

---

# 58. WASTE RECORD

An `IngredientWasteRecord` represents final loss of usable Ingredient quantity.

Typical attributes:

* Waste ID
* Ingredient
* Lot
* Quantity
* Unit
* Waste reason
* Location
* Production reference
* Employee
* Timestamp
* Cost
* Disposition

---

# 59. WASTE REASONS

Suggested categories:

```text
EXPIRATION

SPOILAGE

TRIM

OVERPRODUCTION

PREPARATION_ERROR

QUALITY_REJECTION

STORAGE_FAILURE

DAMAGE

CONTAMINATION

CUSTOMER_CANCELLATION

UNKNOWN
```

---

# 60. EXPECTED VS AVOIDABLE WASTE

The model should distinguish:

```text
EXPECTED_PROCESS_WASTE
```

from:

```text
AVOIDABLE_WASTE
```

where methodology permits.

This supports better operational analysis.

---

# 61. WASTE COST

Ingredient Waste Cost may use the applicable Inventory cost methodology.

This is an analytical and financial projection.

---

# 62. WASTE TREND

Waste may be analyzed by:

* Ingredient.
* Branch.
* Kitchen.
* Recipe.
* Supplier.
* Reason.
* Time period.

---

# 63. INGREDIENT RECALL

A `IngredientRecall` represents a requirement to isolate, stop using or remove affected Ingredient Lots.

Possible sources:

* Supplier.
* Regulator.
* Internal Quality investigation.

---

# 64. RECALL LIFECYCLE

Suggested lifecycle:

```text
IDENTIFIED
→ ACTIVE
→ STOCK_ISOLATED
→ TRACE_ANALYSIS
→ DISPOSITION_IN_PROGRESS
→ COMPLETED
```

---

# 65. RECALL SCOPE

A Recall may affect:

* One Supplier Lot.
* Multiple Lots.
* Ingredient.
* Supplier Product.
* Date range.

The scope shall be explicit.

---

# 66. RECALL STOCK ISOLATION

Affected stock shall transition immediately to an unusable or hold state according to policy.

---

# 67. FORWARD TRACEABILITY

The platform should support tracing:

```text
Affected Ingredient Lot
    ↓
Production Batches
    ↓
Prepared Components
    ↓
Products / Orders
    ↓
Customers
```

where the available data permits.

---

# 68. BACKWARD TRACEABILITY

The platform should also support:

```text
Customer Product
    ↓
Production Execution
    ↓
Ingredient Lots
    ↓
Supplier
```

where traceability exists.

---

# 69. RECALL CUSTOMER IMPACT

If an affected Lot has already been consumed, the system may need to identify:

* Products involved.
* Orders.
* Customers.
* Dates.
* Branches.

Any Customer contact shall follow Compliance and authorized incident procedures.

---

# 70. RECALL DISPOSITION

Affected stock may be:

* Returned to Supplier.
* Destroyed.
* Held for investigation.
* Released if later determined unaffected.

Release requires explicit authority.

---

# 71. INGREDIENT ALLERGEN PROFILE

Ingredient allergen data may include:

* Contains allergen.
* May contain allergen.
* Cross-contact risk.
* Source.
* Effective version.

This contributes to Product allergen reasoning.

---

# 72. ALLERGEN DATA AUTHORITY

Potential sources:

* Supplier declaration.
* Ingredient specification.
* Internal Food Safety classification.

AI shall not infer allergen absence merely because data is missing.

---

# 73. INGREDIENT DIETARY PROFILE

Ingredient attributes may include:

* Animal-derived.
* Plant-based.
* Gluten-containing.
* Dairy-containing.

Dietary classifications shall preserve evidence.

---

# 74. INGREDIENT SUBSTITUTION

A Recipe may permit one Ingredient to be replaced by another.

Ingredient Lifecycle shall ensure the replacement is:

* Available.
* Quality-approved.
* Not expired.
* Correctly traced.

Substitution semantics remain governed by `11_Recipes.md`.

---

# 75. SUPPLIER SUBSTITUTION

A Supplier may propose an alternate Product.

This shall not automatically become an acceptable Ingredient replacement.

Validation may require:

* Specification comparison.
* Quality approval.
* Recipe impact.
* Allergen review.
* Cost review.

---

# 76. INGREDIENT COST

Ingredient cost may originate from:

* Purchase cost.
* Landed cost.
* Average cost.
* Lot cost.

The applicable methodology shall remain explicit.

---

# 77. COST VARIANCE

Ingredient cost changes may affect:

* Recipe Cost.
* Product Margin.
* Menu pricing.
* Executive Intelligence.

Current cost shall not rewrite historical production cost evidence.

---

# 78. SUPPLIER QUALITY IMPACT

Repeated Lot rejection or poor yield may indicate a Supplier problem.

Example:

```text
Supplier A Beef:
Lower purchase price

But:
Higher trim loss
Higher rejection rate
```

Purchasing Intelligence should consider total operational value, not price alone.

---

# 79. EFFECTIVE INGREDIENT COST

An analytical Effective Ingredient Cost may consider:

```text
Purchase Cost
+
Waste
+
Yield Loss
+
Quality Rejection
```

This can provide more realistic Supplier comparison.

---

# 80. INGREDIENT AVAILABILITY

An Ingredient is operationally available only when sufficient valid stock exists.

Conceptually:

```text
On-Hand
-
Reserved
-
Committed
-
Held
-
Expired
-
Rejected
=
Potential Available Quantity
```

---

# 81. INGREDIENT SHORTAGE

An `IngredientShortage` occurs when available quantity is insufficient for required demand.

Potential consequences:

* Recipe infeasibility.
* Product restriction.
* Purchasing urgency.
* Substitution opportunity.

---

# 82. INGREDIENT STOCKOUT

A Stockout represents zero usable quantity for current new demand.

It shall affect relevant Product offerability.

---

# 83. INGREDIENT CRITICALITY

Some Ingredients are operationally critical because they affect many Products.

Examples:

* Cooking oil.
* Core protein.
* Flour.
* Central sauce.
* Packaging-independent staple.

Criticality may support priority decisions.

---

# 84. INGREDIENT DEPENDENCY GRAPH

The platform may represent:

```text
Ingredient
    ↓
Recipes
    ↓
Products
    ↓
Menus
    ↓
Orders
```

This allows fast impact analysis.

---

# 85. INGREDIENT IMPACT ANALYSIS

If one Ingredient becomes unavailable, ECIP should be able to determine:

* Which Recipes are affected.
* Which Products are affected.
* Which Menus are affected.
* Which confirmed Orders are at risk.
* Which Events are at risk.

---

# 86. INGREDIENT AND MENU OFFERABILITY

A Product shall not be represented as safely offerable when a mandatory Ingredient cannot be provided and no approved substitution exists.

---

# 87. INGREDIENT AND EVENTS

Confirmed Events may reserve or consume significant Ingredient quantities.

Event demand shall be included in future availability analysis.

---

# 88. INGREDIENT AND PRODUCTION FORECAST

Production Forecast may estimate future Ingredient demand.

This may support:

* Purchasing.
* Prep.
* Inventory.
* Capacity.

Forecast remains analytical.

---

# 89. INGREDIENT AND CUSTOMER SAFETY

Known Customer Allergies may require reasoning across:

```text
Customer Allergy
+
Product
+
Recipe
+
Ingredient
```

This relationship is safety-critical.

---

# 90. INGREDIENT AND QUALITY CONTROL

Quality Control may place:

* Lot Hold.
* Lot Release.
* Lot Rejection.

Ingredient Lifecycle consumes these authoritative results.

---

# 91. INGREDIENT AND COMPLIANCE

Compliance may define requirements for:

* Food traceability.
* Temperature.
* Recall.
* Storage.
* Record retention.

Detailed compliance policy belongs to `31_Compliance.md`.

---

# 92. INGREDIENT AND PURCHASING

Purchasing controls sourcing and Supplier transactions.

Ingredient Lifecycle follows the material after it enters operational custody.

---

# 93. INGREDIENT AND INVENTORY

Inventory owns balances and movements.

Ingredient Lifecycle provides food-domain meaning, traceability and transformation relationships.

---

# 94. INGREDIENT AND PRODUCTION

Production transforms Ingredients into:

* Prepared Components.
* Finished Products.

Lifecycle evidence shall preserve these transformations where required.

---

# 95. INGREDIENT AND WAREHOUSE OPERATIONS

Warehouse In/Out operations may represent:

* Receiving.
* Internal movement.
* Transfer.
* Production issue.
* Waste.
* Return.

These shall map to governed Inventory Movements.

---

# 96. INGREDIENT ANOMALY

Possible anomaly signals include:

* Unexpected high consumption.
* Repeated Waste.
* Unexpected yield loss.
* Lot disappearing without movement.
* Expiration spike.
* Frequent emergency Purchase.

These are investigation signals, not proof of misconduct.

---

# 97. INGREDIENT SHRINKAGE

Shrinkage represents unexplained reduction.

Potential causes:

* Process loss.
* Theft.
* Measurement error.
* Waste not captured.
* Portion variance.

Cause shall remain unknown until supported by evidence.

---

# 98. INGREDIENT INTELLIGENCE

Potential insights include:

* Consumption trends.
* Waste trends.
* Yield trends.
* Supplier Quality.
* Cost trends.
* Shortage risk.
* Expiration risk.
* Product dependency.
* Substitution opportunities.
* Recall impact.

---

# 99. INGREDIENT EXECUTIVE INTELLIGENCE

Potential KPIs include:

* Ingredient Cost.
* Waste Cost.
* Yield Variance.
* Expiration Loss.
* Supplier rejection rate.
* Critical Ingredient stockout rate.
* Ingredient cost inflation.
* Inventory days.
* Consumption variance.

---

# 100. AI INGREDIENT ASSISTANCE

AI may assist with:

* Explaining shortage impact.
* Summarizing traceability.
* Identifying recurring waste.
* Suggesting investigation priorities.
* Recommending authorized substitute candidates.
* Identifying affected Products.

---

# 101. AI AUTHORITY LIMIT

AI shall not:

* Invent Ingredient quantities.
* Release held Lots.
* Ignore expiration.
* Declare recalled stock safe.
* Invent Supplier specifications.
* Approve substitutions outside policy.
* Modify Recipes autonomously.
* Falsify traceability.

---

# 102. AUTONOMOUS INGREDIENT ACTIONS

Future controlled automation may support low-risk actions such as:

* FEFO lot recommendation.
* Low-stock alert.
* Expiration alert.
* Replenishment suggestion.

High-risk actions such as:

* Recall release.
* Quality override.
* Supplier substitution.
* Ingredient write-off.

shall require authorized controls.

---

# 103. SOURCE OF TRUTH

Authority may vary by information type.

Example:

```text
Purchasing:
Supplier and Purchase Order

Inventory:
Stock Balance and Movement

Quality:
Lot Quality Status

Production:
Ingredient Consumption

ECIP:
Lifecycle Intelligence and Traceability
```

Ownership shall remain explicit.

---

# 104. EXTERNAL INGREDIENT MAPPING

External systems may identify Ingredients through:

* POS Ingredient Code.
* ERP Item ID.
* Supplier SKU.
* Inventory Item ID.

These shall map to canonical Ingredient identity.

---

# 105. INGREDIENT IMPORT

Legacy Ingredient data may be imported.

Import shall preserve:

* Source.
* Original ID.
* Ingredient mapping.
* Unit mapping.
* Supplier mappings.
* Current Lot information if available.
* Data quality.

---

# 106. INGREDIENT SYNCHRONIZATION

Synchronization may include:

* Item definitions.
* Lot states.
* Expiration.
* Quantity.
* Quality status.
* Supplier data.
* Consumption.

It shall remain idempotent and observable.

---

# 107. INGREDIENT CONFLICT

Example:

```text
Inventory:
Lot available

Quality:
Lot rejected
```

Quality state shall prevent normal use.

Another example:

```text
Production:
Lot consumed

Inventory:
Lot still fully available
```

This represents a reconciliation conflict.

---

# 108. INGREDIENT AUDIT

Material Ingredient lifecycle actions shall preserve:

* Actor or source.
* Ingredient.
* Lot.
* Quantity.
* Unit.
* Location.
* Timestamp.
* Reason.
* Related Purchase / Production / Quality reference.
* Previous state.
* New state.

---

# 109. INGREDIENT EVENTS

Initial domain events include:

```text
IngredientCreated
IngredientUpdated
IngredientActivated
IngredientSuspended
IngredientDiscontinued

IngredientSpecificationCreated
IngredientSpecificationUpdated

IngredientSupplierSourceApproved
IngredientSupplierSourceSuspended

IngredientLotCreated
IngredientLotReceived

IngredientLotInspectionRequested
IngredientLotAccepted
IngredientLotQualityHeld
IngredientLotReleased
IngredientLotRejected

IngredientStored
IngredientStorageLocationChanged
IngredientStorageExcursionDetected

IngredientReserved
IngredientReservationReleased
IngredientCommitted
IngredientCommitmentReleased

IngredientTransferred
IngredientTransferReceived

IngredientConsumptionRecorded

IngredientTransformationStarted
IngredientTransformationCompleted

IngredientYieldRecorded
IngredientYieldVarianceDetected

IngredientWasteRecorded
IngredientSpoilageDetected

IngredientExpirationApproaching
IngredientExpired

IngredientShortageDetected
IngredientStockoutDetected

IngredientRecallStarted
IngredientRecallStockIsolated
IngredientRecallTraceCompleted
IngredientRecallCompleted

IngredientSubstitutionRequested
IngredientSubstitutionApproved
IngredientSubstitutionRejected

IngredientConsumptionVarianceDetected
IngredientShrinkageDetected

IngredientConflictDetected
IngredientConflictResolved

IngredientSynchronizationStarted
IngredientSynchronizationCompleted
IngredientSynchronizationFailed
```

---

# 110. RELATIONSHIPS

```text
Ingredient
    MAY_MAP_TO InventoryItem

Supplier
    PROVIDES SupplierProduct

SupplierProduct
    MAY_MAP_TO Ingredient

Ingredient
    HAS IngredientSpecification

IngredientLot
    INSTANCE_OF Ingredient

IngredientLot
    SOURCED_FROM Supplier

IngredientLot
    STORED_AT StockLocation

IngredientLot
    HAS QualityStatus

IngredientLot
    MAY_BE_RESERVED_FOR ProductionRequirement

Recipe
    USES Ingredient

ProductionExecution
    CONSUMES IngredientLot

ProductionBatch
    CONSUMES IngredientLot

ProductionBatch
    PRODUCES PreparedComponent

IngredientLot
    MAY_GENERATE IngredientWasteRecord

IngredientLot
    MAY_BE_AFFECTED_BY IngredientRecall

IngredientRecall
    MAY_IMPACT ProductionBatch

ProductionBatch
    MAY_IMPACT OrderItem

IngredientState
    CONTRIBUTES_TO RecipeFeasibility

IngredientState
    CONTRIBUTES_TO ProductOfferability

IngredientHistory
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 111. BUSINESS RULES

The following rules apply:

1. Ingredient identity shall remain distinct from Supplier Product and Inventory Item identity.

2. Every material Ingredient quantity shall identify its Unit of Measure.

3. Lot traceability shall be preserved where required.

4. Only Quality-approved and non-expired stock shall contribute to normal usable availability.

5. Quality Hold shall override commercial or production demand.

6. Ingredient reservations and commitments shall remain separately traceable.

7. Actual Consumption and theoretical Recipe Consumption shall remain separate concepts.

8. Ingredient transformation shall preserve source-output traceability where required.

9. Yield loss, Waste and Consumption Variance shall not be silently merged.

10. Expired or recalled stock shall not remain normal production-eligible inventory.

11. Ingredient substitution shall require explicit Recipe and safety compatibility.

12. Missing allergen data shall not be interpreted as allergen absence.

13. Supplier substitution shall not automatically imply Recipe compatibility.

14. Waste records shall preserve reason where known.

15. Recall actions shall preserve complete audit and trace evidence.

16. AI shall not release, reclassify or consume restricted Ingredient Lots without authority.

17. Current Ingredient state shall contribute to Product and Recipe feasibility.

18. External identifiers shall remain integration mappings.

19. Historical Ingredient state shall not be rewritten to hide Quality, Waste or reconciliation problems.

20. Food Safety and Customer Safety shall override inventory, cost and sales optimization.

---

# 112. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Ingredient

IngredientCategory

IngredientSpecification

IngredientInventoryMapping

IngredientSupplierMapping

IngredientLot

IngredientLotQualityStatus

IngredientExpiration

IngredientStorageRequirement

IngredientStorageAssignment

IngredientReservation

IngredientCommitment

IngredientConsumption

IngredientTransformationReference

IngredientYield

IngredientWasteRecord

IngredientShortage

IngredientStockout

IngredientRecall

IngredientAllergenProfile

IngredientDietaryProfile

IngredientSubstitutionReference

ExternalIngredientMapping

IngredientHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced IoT Cold-Chain Monitoring

Predictive Ingredient Spoilage Models

Autonomous Ingredient Substitution

Advanced Yield Optimization

AI Supplier-Specification Comparison

Automated Recall Customer Impact Orchestration

Advanced Ingredient Cost Simulation

Digital Twin Ingredient Flow

Autonomous Waste Reduction Optimization
```

---

# 113. IMPLEMENTATION PRINCIPLE

This document defines the logical Ingredient Lifecycle Model.

It does not prescribe:

* Inventory database schema.
* Purchasing implementation.
* IoT hardware.
* Food Safety software.
* Traceability vendor.
* Recipe engine.
* AI model.
* Waste optimization algorithm.

Implementation shall preserve the semantic distinction between:

```text
INGREDIENT

SUPPLIER PRODUCT

INGREDIENT LOT

INVENTORY STOCK

QUALITY STATE

STORAGE STATE

RESERVATION

COMMITMENT

CONSUMPTION

TRANSFORMATION

YIELD

WASTE

EXPIRATION

RECALL

FINAL DISPOSITION
```

---

# 114. FINAL RULE

Before ECIP concludes that an Ingredient is available, safe, consumable, substitutable or responsible for a Product impact, it shall be able to determine:

> What canonical Ingredient is involved?

> Which Supplier Product and Supplier provided it?

> Which Lot is being referenced?

> When was it received?

> What Quantity and Unit remain?

> Where is it stored?

> What Quality status applies?

> Is it expired, held, rejected or recalled?

> What quantity is reserved or committed?

> Which Recipes and Products depend on it?

> Which Production executions have consumed it?

> Which Prepared Components or finished Products were produced from it?

> What Waste or Yield variance has occurred?

> Are there any allergen, dietary or Food Safety implications?

> Does a shortage affect any confirmed Order, Event or Customer commitment?

> Can the complete path from Supplier to final consumption or disposition be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably use Ingredient information for Production, Product offerability, Purchasing, Customer Safety, Quality Control or business intelligence.

