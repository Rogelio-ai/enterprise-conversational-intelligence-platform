# 21_Production.md

**Document ID:** RDM-021
**Document Name:** Production
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Production Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete execution lifecycle through which restaurant demand is transformed into prepared, assembled and releasable Products.

The Production Model connects:

* Orders.
* Order Items.
* Recipes.
* Ingredients.
* Prepared Components.
* Kitchen Stations.
* Equipment.
* Employees.
* Production Tasks.
* Batches.
* Work-in-Progress.
* Production Timing.
* Quality Control.
* Waste.
* Inventory Consumption.
* Fulfillment.
* Operational Intelligence.

The Production Model defines **how work is executed**.

`20_Kitchen.md` defines **where and under what operational conditions that work occurs**.

---

# 2. OBJECTIVES

The Production Model enables ECIP to:

* Translate confirmed demand into production work.
* Plan production requirements.
* Create production tasks.
* Sequence production steps.
* Coordinate parallel and dependent work.
* Execute batch production.
* Track work-in-progress.
* Track prepared components.
* Track production timing.
* Track completion.
* Support course synchronization.
* Support scheduled production.
* Support event production.
* Support Take Away and Delivery timing.
* Track remakes and rework.
* Track theoretical consumption.
* Track waste.
* Support Quality Control.
* Detect production variance.
* Preserve complete production history.
* Support operational optimization.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Workflow Definition
* Workflow Instance
* Task
* Action Request
* Action Authorization
* Action Execution
* Action Result
* Resource
* Context Snapshot
* Runtime Event
* Metric Observation
* Incident
* Evidence Record

Restaurant-specific Production entities remain within the Restaurant Domain Pack.

---

# 4. PRODUCTION PRINCIPLE

Production represents the governed execution of restaurant preparation work.

The platform shall distinguish between:

```text
DEMAND

PRODUCTION REQUIREMENT

PRODUCTION PLAN

PRODUCTION TASK

PRODUCTION EXECUTION

WORK IN PROGRESS

PREPARED COMPONENT

FINISHED PRODUCT

QUALITY RESULT

FULFILLMENT
```

These concepts shall not be collapsed into a single Kitchen status.

---

# 5. PRODUCTION REQUIREMENT

A `ProductionRequirement` represents the need to produce one or more units of a Product or Recipe output.

Possible sources include:

* Confirmed Order Item.
* Scheduled Order.
* Reservation forecast.
* Event.
* Buffet replenishment.
* Prep planning.
* Stock replenishment of prepared components.

Typical attributes:

* Requirement ID
* Source type
* Source reference
* Product
* Recipe Version
* Required quantity
* Required completion time
* Priority
* Branch
* Kitchen
* Status

---

# 6. PRODUCTION REQUIREMENT SOURCES

Initial sources may include:

```text
ORDER

EVENT

BANQUET

BUFFET

PREP_PLAN

FORECAST

MANUAL_REQUEST

REPLENISHMENT
```

Source shall always be preserved.

---

# 7. PRODUCTION REQUIREMENT STATUS

Suggested lifecycle:

```text
CREATED
→ VALIDATED
→ PLANNED
→ RELEASED
→ IN_PRODUCTION
→ COMPLETED
```

Alternative states:

```text
BLOCKED
CANCELLED
FAILED
```

---

# 8. PRODUCTION PLAN

A `ProductionPlan` represents the coordinated execution plan for one or more Production Requirements.

Typical attributes:

* Plan ID
* Scope
* Kitchen
* Time window
* Requirements
* Tasks
* Planned resources
* Planned start
* Planned completion
* Status
* Version

---

# 9. PRODUCTION PLAN TYPES

Examples:

* Immediate Order Plan
* Scheduled Order Plan
* Prep Plan
* Batch Plan
* Event Production Plan
* Buffet Replenishment Plan
* Daily Preparation Plan

---

# 10. PRODUCTION PLAN LIFECYCLE

Suggested lifecycle:

```text
DRAFT
→ VALIDATED
→ RELEASED
→ EXECUTING
→ COMPLETED
```

Alternative states:

```text
REVISED
CANCELLED
FAILED
```

---

# 11. PRODUCTION TASK

A `ProductionTask` represents one executable unit of production work.

Typical attributes:

* Task ID
* Production Plan
* Production Requirement
* Recipe Step
* Product
* Quantity
* Station
* Required Equipment
* Assigned Employee
* Planned start
* Actual start
* Expected completion
* Actual completion
* Status
* Priority

---

# 12. PRODUCTION TASK TYPES

Examples:

```text
PREP

COOK

BAKE

GRILL

FRY

ASSEMBLE

PORTION

PLATE

PACKAGE

HOLD

QUALITY_CHECK

TRANSFER
```

---

# 13. PRODUCTION TASK LIFECYCLE

Suggested lifecycle:

```text
CREATED
→ QUEUED
→ READY
→ IN_PROGRESS
→ COMPLETED
```

Alternative states:

```text
BLOCKED
PAUSED
CANCELLED
FAILED
REWORK_REQUIRED
```

---

# 14. TASK DEPENDENCY

A Production Task may depend on one or more other Tasks.

Example:

```text
Prepare Sauce
    ↓
Cook Pasta
    ↓
Combine
    ↓
Plate
```

Dependencies shall be explicit.

---

# 15. PARALLEL TASKS

Some work may run in parallel.

Example:

```text
Grill Chicken
        +
Prepare Salad
        ↓
Final Assembly
```

Parallel execution affects total expected completion time.

---

# 16. CRITICAL PATH

For multi-step production, the Critical Path represents the dependency sequence that determines earliest possible completion.

Critical-path information may support ETA calculation.

Advanced optimization is not required for MVP.

---

# 17. TASK RELEASE

A Task becomes executable only when:

* Dependencies are satisfied.
* Required resources are available.
* Required Ingredients or prepared components are available.
* Applicable timing conditions are met.

---

# 18. PRODUCTION EXECUTION

A `ProductionExecution` represents the actual performance of a Production Task.

Typical attributes:

* Execution ID
* Task
* Employee
* Station
* Equipment
* Start time
* End time
* Actual quantity
* Actual yield
* Status
* Exceptions
* Quality result

---

# 19. EXECUTION ATTEMPT

A Task may require multiple execution attempts.

Examples:

* Initial preparation fails Quality Control.
* Product is remade.
* Equipment failure interrupts execution.

Each attempt shall remain traceable.

---

# 20. WORK IN PROGRESS

`WorkInProgress` represents production that has begun but is not yet complete.

Examples:

* Steak currently grilling.
* Pizza in oven.
* Dessert being plated.
* Batch cooling.

WIP contributes to real-time operational context.

---

# 21. WIP STATUS

Suggested states:

```text
STARTED

ACTIVE

WAITING

HOLDING

BLOCKED

READY_FOR_NEXT_STEP
```

---

# 22. PRODUCTION QUANTITY

Production shall distinguish:

* Requested quantity.
* Planned quantity.
* Actual quantity.
* Accepted quantity.
* Rejected quantity.
* Waste quantity.

These values may differ.

---

# 23. YIELD

Actual Yield represents usable output produced.

Example:

```text
Planned:
20 portions

Actual:
18 acceptable portions

Rejected:
2 portions
```

Yield variance supports Operational Intelligence.

---

# 24. BATCH PRODUCTION

A `ProductionBatch` represents execution that creates multiple units or quantities together.

Examples:

* Soup.
* Sauce.
* Dough.
* Rice.
* Dessert base.
* Prepared chicken portions.

Typical attributes:

* Batch ID
* Recipe Version
* Planned quantity
* Actual quantity
* Start time
* Completion time
* Expiration
* Storage
* Status

---

# 25. BATCH STATUS

Suggested lifecycle:

```text
PLANNED
→ RELEASED
→ IN_PRODUCTION
→ COMPLETED
→ AVAILABLE
```

Alternative states:

```text
HOLD
REJECTED
EXPIRED
DEPLETED
```

---

# 26. BATCH LOT

A Production Batch may receive a Lot identifier to support:

* Traceability.
* Ingredient linkage.
* Quality incidents.
* Expiration management.

---

# 27. BATCH INGREDIENT TRACEABILITY

Where required, a Batch may preserve which Ingredient Lots were consumed.

Example:

```text
Soup Batch B-204
    USED
Vegetable Lot V-882
Cream Lot C-220
```

This supports food safety and recall investigation.

---

# 28. PREPARED COMPONENT

A `PreparedComponent` represents reusable semi-finished output produced before final Product assembly.

Examples:

* Pizza dough.
* Tomato sauce.
* Cooked rice.
* Portion of grilled chicken.
* Dessert cream.
* Salsa.

---

# 29. PREPARED COMPONENT STATUS

Suggested states:

```text
AVAILABLE

LOW

RESERVED

IN_USE

HOLD

EXPIRED

DISCARDED
```

---

# 30. PREPARED COMPONENT INVENTORY

Prepared Components may behave as short-lived operational inventory.

They shall preserve:

* Quantity.
* Unit.
* Batch.
* Production time.
* Expiration.
* Storage location.
* Quality state.

---

# 31. PREP WORK

Prep Work represents production performed before immediate Customer demand.

Examples:

* Chopping vegetables.
* Portioning meat.
* Preparing sauces.
* Making dough.
* Pre-cooking components.

---

# 32. PREP PLAN

A `PrepPlan` represents required prep quantities for a future operating period.

Potential inputs:

* Forecast.
* Reservations.
* Events.
* Historical demand.
* Existing prepared stock.

---

# 33. PREP REQUIREMENT

Example:

```text
Expected Dinner Demand:
80 pasta portions

Current Alfredo Sauce:
20 portions

Required Prep:
60 additional portions
```

---

# 34. OVERPRODUCTION

Overproduction occurs when actual produced quantity materially exceeds demand or planned usable quantity.

Possible consequences:

* Waste.
* Storage.
* Future availability.
* Cost variance.

Overproduction shall be measurable.

---

# 35. UNDERPRODUCTION

Underproduction may cause:

* Product unavailability.
* Delays.
* Additional urgent production.
* Customer commitment risk.

---

# 36. PRODUCTION SCHEDULE

A `ProductionSchedule` may organize production across:

* Day.
* Shift.
* Meal period.
* Event.
* Batch cycle.

This is distinct from Employee scheduling.

---

# 37. SCHEDULED PRODUCTION

Scheduled production may support:

* Future Orders.
* Banquets.
* Catering.
* Buffet.
* Prep.

A scheduled requirement shall have a required completion target.

---

# 38. PRODUCTION WINDOW

Example:

```text
Required Completion:
18:00

Planned Production Window:
16:30–17:45
```

A buffer may be included.

---

# 39. JUST-IN-TIME PRODUCTION

Some Products should be completed near fulfillment time.

Examples:

* Fried food.
* Ice cream dessert.
* Espresso.
* Certain plated dishes.

This minimizes quality degradation.

---

# 40. HOLDING PRODUCTION

Some Products may be prepared ahead and held.

Holding shall respect:

* Food safety.
* Maximum time.
* Temperature.
* Quality window.

---

# 41. PRODUCTION HOLD

A `ProductionHold` represents deliberate temporary pause before the next step.

Examples:

* Resting dough.
* Cooling.
* Holding before plating.

---

# 42. HOLD EXPIRATION

A hold may have:

* Minimum duration.
* Maximum duration.
* Target condition.

Exceeding maximum may create a Quality failure.

---

# 43. PRODUCTION TIMING

Important timestamps include:

* Requirement created.
* Plan released.
* Task queued.
* Task started.
* Task completed.
* Product ready.
* Fulfillment handoff.

---

# 44. PLANNED VS ACTUAL TIME

Production shall preserve:

```text
Planned Start

Actual Start

Planned Completion

Actual Completion
```

Variance supports operational diagnosis.

---

# 45. QUEUE WAIT TIME

Queue Wait Time may be measured as:

```text
Task Start - Task Queue Time
```

This is distinct from actual preparation duration.

---

# 46. PROCESSING TIME

Processing Time:

```text
Task Completion - Task Start
```

---

# 47. TOTAL PRODUCTION LEAD TIME

Conceptually:

```text
Requirement Creation
to
Finished Product Ready
```

This may include multiple tasks and queues.

---

# 48. PRODUCTION DELAY

A `ProductionDelay` represents deviation from the planned or expected production timeline.

Typical attributes:

* Requirement.
* Task.
* Expected completion.
* Actual/revised completion.
* Delay duration.
* Cause.
* Severity.

---

# 49. PRODUCTION DELAY CAUSES

Examples:

```text
QUEUE

EQUIPMENT

STAFFING

INGREDIENT

RECIPE_COMPLEXITY

QUALITY_REWORK

UPSTREAM_TASK

PRIORITY_CHANGE

UNKNOWN
```

---

# 50. BLOCKED PRODUCTION

Production may be blocked due to:

* Missing Ingredient.
* Missing component.
* Equipment failure.
* Station unavailable.
* Required approval.
* Dependency incomplete.

Blocked state shall remain explicit.

---

# 51. PRODUCTION RESUME

When the blocking condition resolves, execution may resume.

The platform shall preserve:

* Block start.
* Block reason.
* Resolution.
* Resume time.

---

# 52. PRODUCTION CANCELLATION

Production may be cancelled due to:

* Order cancellation.
* Event cancellation.
* Product unavailability.
* Operational emergency.

Cancellation shall not erase already incurred work.

---

# 53. CANCELLATION AFTER START

If Production has already begun, the system may need to record:

* Partially consumed Ingredients.
* Waste.
* Work performed.
* Prepared component reuse where safe and allowed.

---

# 54. PRODUCTION REWORK

A `ProductionRework` represents additional work required to correct an unacceptable result.

Reasons:

* Incorrect preparation.
* Quality failure.
* Customer complaint.
* Wrong modifier.
* Damaged Product.

---

# 55. REWORK LIFECYCLE

Suggested flow:

```text
Issue Detected
    ↓
Rework Required
    ↓
Replacement Task Created
    ↓
Rework Executed
    ↓
Quality Revalidated
```

---

# 56. REMAKE

A Remake is a complete replacement production execution.

The original Product remains historically traceable.

---

# 57. PRODUCTION SCRAP

`ProductionScrap` represents output that cannot be served or reused.

Typical causes:

* Burned.
* Incorrect Product.
* Contamination.
* Expired holding time.
* Customer cancellation after completion.

---

# 58. PRODUCTION WASTE

Production Waste may include:

* Ingredient waste.
* Prepared component waste.
* Finished Product waste.

Detailed Ingredient lifecycle remains in `25_Ingredient_Lifecycle.md`.

---

# 59. THEORETICAL CONSUMPTION

Production Requirements may calculate expected Ingredient consumption from Recipe.

Example:

```text
10 × Salmon Product
Recipe:
220 g salmon each

Theoretical consumption:
2.2 kg salmon
```

---

# 60. ACTUAL CONSUMPTION

Actual Ingredient movement may differ because of:

* Waste.
* Yield.
* Overportion.
* Substitution.
* Rework.

Inventory remains authoritative for actual movements.

---

# 61. PRODUCTION VARIANCE

Possible variance measures:

```text
Actual Quantity - Planned Quantity

Actual Time - Planned Time

Actual Consumption - Theoretical Consumption

Actual Yield - Expected Yield
```

---

# 62. PORTION CONTROL

Production may validate portion quantities.

Examples:

* Steak weight.
* Fries portion.
* Soup volume.
* Sauce quantity.

Portion variance affects:

* Cost.
* Inventory.
* Customer consistency.

---

# 63. PRODUCTION STANDARD

A `ProductionStandard` may reference:

* Recipe.
* Portion.
* Timing.
* Temperature.
* Appearance.
* Required checkpoints.

---

# 64. QUALITY CHECK

Quality Control may occur:

* During production.
* At Task completion.
* At Expo.
* Before Packaging.
* Before Fulfillment.

Detailed Quality Control is defined in `22_Quality_Control.md`.

---

# 65. QUALITY STATUS

Production may receive:

```text
PASS

PASS_WITH_NOTE

HOLD

FAIL

REWORK_REQUIRED
```

Only acceptable output should proceed to normal fulfillment.

---

# 66. QUALITY HOLD

A Product on Quality Hold shall not be considered customer-ready.

---

# 67. PRODUCT READY

A Product becomes production-ready when:

```text
Required Tasks Completed
+
Required Quality Checks Passed
=
Production Ready
```

This does not necessarily mean fulfillment-ready.

---

# 68. ORDER READY

For an Order with multiple Items:

```text
All Required Order Items Production Ready
+
Applicable Packaging / Assembly Complete
=
Potential Order Ready
```

Fulfillment domains determine final handoff readiness.

---

# 69. PRODUCTION ASSEMBLY

Some Products require final assembly of multiple components.

Example:

```text
Burger:
Bun
+
Patty
+
Vegetables
+
Sauce
+
Side
```

Assembly may be modeled as a Production Task.

---

# 70. FINALIZATION

Finalization may include:

* Garnish.
* Plate.
* Lid.
* Label.
* Final temperature check.

---

# 71. PLATING

Plating is a production operation for Dine-In Products.

It may reference presentation standards.

---

# 72. PACKAGING

Packaging may be part of production or fulfillment depending on implementation boundaries.

The canonical domain shall preserve clear ownership.

For Take Away and Delivery, fulfillment readiness may require packaging beyond kitchen completion.

---

# 73. MULTI-STATION PRODUCTION

One Product may require multiple Stations.

Example:

```text
Steak Plate

Grill:
Steak

Sauté:
Vegetables

Expo:
Final assembly
```

The Product is not ready until required components converge.

---

# 74. STATION CONVERGENCE

A `ProductionConvergence` represents synchronization of multiple Task outputs.

Potential states:

```text
WAITING_FOR_COMPONENTS

READY_TO_ASSEMBLE

ASSEMBLING

COMPLETE
```

---

# 75. COURSE PRODUCTION

Multiple Products belonging to one Course may require coordinated release.

This connects Production with Dine-In pacing.

---

# 76. ORDER PRIORITY

Production Priority may derive from:

* Customer commitment.
* Service type.
* Promised time.
* Event schedule.
* Recovery requirement.
* Order age.

Priority shall remain governed.

---

# 77. PRIORITY CHANGE

Priority changes shall preserve:

* Original priority.
* New priority.
* Reason.
* Actor or rule.
* Timestamp.

---

# 78. RUSH PRODUCTION

Rush status may be used when policy permits.

Rush shall not bypass:

* Food safety.
* Quality.
* Required preparation steps.

---

# 79. EVENT PRODUCTION

Events may generate structured production plans based on:

* Final guest count.
* Menu.
* Service timeline.
* Batch needs.

Event Production shall preserve link to the Event.

---

# 80. BANQUET PRODUCTION

Banquet Production may differ from immediate restaurant Orders by using:

* High-volume batches.
* Staged preparation.
* Scheduled plating.
* Buffet replenishment.

---

# 81. BUFFET PRODUCTION

Buffet Production may be driven by:

* Current level.
* Expected demand.
* Holding time.
* Replenishment threshold.

---

# 82. BUFFET REPLENISHMENT

A `ReplenishmentRequirement` may be generated when prepared quantity drops below a threshold.

Advanced autonomous replenishment may be deferred.

---

# 83. DELIVERY PRODUCTION

Delivery Production should account for:

* Product quality window.
* Packaging.
* Dispatch target.
* Driver ETA.

Completing too early may reduce Product quality.

---

# 84. TAKE AWAY PRODUCTION

Take Away Production should target the Promised Pickup Time.

Completing too early may increase holding time.

Completing too late creates Customer waiting.

---

# 85. DINE-IN PRODUCTION

Dine-In Production should consider:

* Course pacing.
* Table state.
* Guest progress.
* Service coordination.

---

# 86. PRODUCTION FORECAST INPUT

Future production demand may originate from:

* Reservations.
* Events.
* Historical patterns.
* Scheduled Orders.
* Promotions.

Forecasts support Prep Planning.

---

# 87. PRODUCTION FORECAST

A `ProductionForecast` may estimate:

* Product demand.
* Recipe demand.
* Ingredient demand.
* Station workload.

Forecast is analytical, not authoritative demand.

---

# 88. FORECAST VS ACTUAL DEMAND

The platform shall preserve the difference between:

```text
Forecast Demand

Confirmed Demand

Actual Production
```

---

# 89. PRODUCTION CAPACITY REQUIREMENT

A Production Plan may calculate expected load by Station.

Example:

```text
Grill:
120 production minutes required

Available:
90 production minutes

Result:
Expected capacity deficit
```

---

# 90. CAPACITY DEFICIT

A deficit may lead to recommendations such as:

* Start prep earlier.
* Add qualified staff.
* Use alternate equipment.
* Limit selected offerings.
* Adjust promise times.

Recommendations require appropriate authority.

---

# 91. PRODUCTION BOTTLENECK

A Production Bottleneck may be caused by:

* Station.
* Equipment.
* Ingredient.
* Employee availability.
* Task dependency.
* Quality rework.

This model provides execution evidence for the Kitchen Bottleneck model.

---

# 92. PRODUCTION INTELLIGENCE

Potential intelligence includes:

* Slowest Tasks.
* High-variance Recipes.
* Frequent rework.
* Low-yield batches.
* Bottleneck Products.
* Excessive waste.
* Schedule adherence.

---

# 93. RECIPE PERFORMANCE

Production history may reveal:

* Actual vs baseline preparation time.
* Yield variance.
* Ingredient variance.
* Quality failure rate.

This may support Recipe review.

Production Intelligence shall not directly change the authoritative Recipe.

---

# 94. PRODUCT PRODUCTION PROFILE

A Product Production Profile may summarize:

* Typical time.
* Variance.
* Failure rate.
* Station load.
* Rework rate.

This is analytical evidence.

---

# 95. EMPLOYEE PRODUCTION CONTEXT

Production records may reference Employees.

Performance conclusions shall account for:

* Task complexity.
* Station congestion.
* Equipment.
* Demand.

Raw production time shall not automatically become employee-performance scoring.

---

# 96. EQUIPMENT UTILIZATION

Production Tasks may provide evidence of Equipment use.

Potential metrics:

* Runtime.
* Queue pressure.
* Failure impact.
* Capacity utilization.

---

# 97. MAINTENANCE SIGNAL

Production may reveal Maintenance signals such as:

* Repeated Equipment slowdown.
* Increasing failure frequency.
* Temperature instability.

Maintenance domain remains authoritative for maintenance lifecycle.

---

# 98. PRODUCTION INCIDENT

A Production Incident may include:

* Equipment failure.
* Major batch failure.
* Contamination concern.
* Widespread delay.
* Recipe mismatch.

Operational Incident domain manages incident lifecycle.

---

# 99. PRODUCTION TRACEABILITY

The platform should be able to reconstruct:

```text
Order / Event
    ↓
Production Requirement
    ↓
Recipe Version
    ↓
Production Plan
    ↓
Tasks
    ↓
Executions
    ↓
Ingredients / Batches
    ↓
Quality Result
    ↓
Finished Output
```

This is essential for audit, quality and food safety.

---

# 100. PRODUCTION EVIDENCE

Material Production actions should preserve:

* Actor.
* Task.
* Recipe Version.
* Time.
* Quantity.
* Equipment.
* Station.
* Result.
* Exceptions.

---

# 101. PRODUCTION SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Confirmed demand

KDS:
Task execution state

Inventory:
Actual Ingredient movement

ECIP:
Production orchestration and intelligence
```

Ownership shall be explicitly configured.

---

# 102. EXTERNAL PRODUCTION MAPPING

External systems may use:

* Kitchen ticket.
* Prep ticket.
* Batch number.
* KDS task.
* Recipe execution ID.

These shall map to canonical Production entities.

---

# 103. PRODUCTION SYNCHRONIZATION

Synchronization may include:

* Requirement state.
* Task state.
* Ready state.
* Cancellation.
* Batch state.

Synchronization shall be idempotent and observable.

---

# 104. OUT-OF-ORDER EVENTS

Production events may arrive out of sequence.

Runtime logic shall preserve valid lifecycle state and retain conflicting evidence.

---

# 105. PRODUCTION CONFLICT

Examples:

```text
Order:
Cancelled

Production:
Still active
```

or:

```text
Production:
Completed

Quality:
Failed
```

Conflicts shall create explicit resolution rather than silent state mutation.

---

# 106. PRODUCTION EVENTS

Initial domain events include:

```text
ProductionRequirementCreated
ProductionRequirementValidated
ProductionRequirementPlanned
ProductionRequirementReleased
ProductionRequirementCancelled
ProductionRequirementCompleted

ProductionPlanCreated
ProductionPlanValidated
ProductionPlanReleased
ProductionPlanRevised
ProductionPlanCompleted

ProductionTaskCreated
ProductionTaskQueued
ProductionTaskReleased
ProductionTaskStarted
ProductionTaskPaused
ProductionTaskBlocked
ProductionTaskResumed
ProductionTaskCompleted
ProductionTaskFailed
ProductionTaskCancelled

ProductionExecutionStarted
ProductionExecutionCompleted
ProductionExecutionFailed

ProductionBatchCreated
ProductionBatchStarted
ProductionBatchCompleted
ProductionBatchAvailable
ProductionBatchHeld
ProductionBatchRejected
ProductionBatchExpired
ProductionBatchDepleted

PreparedComponentCreated
PreparedComponentReserved
PreparedComponentConsumed
PreparedComponentExpired

ProductionDelayDetected
ProductionETAUpdated

ProductionReworkRequested
ProductionReworkStarted
ProductionReworkCompleted

ProductionWasteRecorded
ProductionYieldVarianceDetected
ProductionConsumptionVarianceDetected

ProductionQualityCheckRequested
ProductionQualityPassed
ProductionQualityFailed

ProductionReady
ProductionConflictDetected
ProductionConflictResolved

ProductionSynchronizationStarted
ProductionSynchronizationCompleted
ProductionSynchronizationFailed
```

---

# 107. RELATIONSHIPS

```text
OrderItem
    MAY_CREATE ProductionRequirement

Event
    MAY_CREATE ProductionRequirement

ProductionRequirement
    REFERENCES Product

ProductionRequirement
    USES RecipeVersion

ProductionRequirement
    BELONGS_TO ProductionPlan

ProductionPlan
    CONTAINS ProductionTask

ProductionTask
    EXECUTED_AS ProductionExecution

ProductionTask
    EXECUTED_AT KitchenStation

ProductionTask
    MAY_REQUIRE Equipment

ProductionTask
    MAY_DEPEND_ON ProductionTask

ProductionBatch
    PRODUCES PreparedComponent

PreparedComponent
    MAY_BE_CONSUMED_BY ProductionTask

ProductionExecution
    MAY_GENERATE ProductionWaste

ProductionExecution
    PRODUCES QualityResult

ProductionRequirement
    COMPLETES_AS ProductionReady

ProductionState
    CONTRIBUTES_TO KitchenContext

ProductionHistory
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 108. BUSINESS RULES

The following rules apply:

1. Production shall only execute against valid Production Requirements.

2. Production Requirements shall preserve their source.

3. Production shall use an explicit Recipe Version when applicable.

4. Production Plans shall not redefine Recipes.

5. Task dependencies shall be respected.

6. Parallel execution shall not bypass dependency requirements.

7. Production quantity, yield and waste shall remain separately measurable.

8. Batch output shall preserve traceability where required.

9. Prepared Components shall preserve Production Batch origin.

10. Production-ready status requires all mandatory Tasks and Quality conditions to be satisfied.

11. Quality Hold output shall not proceed to normal fulfillment.

12. Cancellation shall not erase already executed Production work.

13. Rework and Remake shall preserve the failed original execution.

14. Production Priority changes shall be explicit and auditable.

15. Actual Ingredient Consumption remains authoritative in Inventory.

16. Production may calculate theoretical consumption but shall not overwrite actual Inventory evidence.

17. AI shall not alter Recipes, bypass Quality or invent Production completion.

18. External Production identifiers shall remain integration mappings.

19. Production state transitions shall be reconstructable.

20. Safety and Quality override throughput and commercial optimization.

---

# 109. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
ProductionRequirement

ProductionRequirementSource

ProductionPlan

ProductionTask

ProductionTaskDependency

ProductionTaskStatus

ProductionExecution

WorkInProgress

ProductionBatch

PreparedComponent

ProductionQuantity

ProductionTiming

ProductionDelay

ProductionRework

ProductionWasteReference

ProductionQualityReference

ProductionReady

ProductionExternalMapping

ProductionHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Constraint-Based Production Scheduling

Autonomous Production Planning

Advanced Critical Path Optimization

Predictive Yield Modeling

AI-Based Prep Quantity Optimization

Autonomous Batch Replenishment

Advanced Multi-Kitchen Production Routing

Digital Twin Production Simulation
```

---

# 110. IMPLEMENTATION PRINCIPLE

This document defines the logical Production Model.

It does not prescribe:

* KDS vendor.
* Database schema.
* Production scheduling algorithm.
* Inventory implementation.
* IoT system.
* Recipe system.
* AI model.
* Optimization engine.

Implementation shall preserve the semantic distinction between:

```text
DEMAND

PRODUCTION REQUIREMENT

PRODUCTION PLAN

PRODUCTION TASK

PRODUCTION EXECUTION

WORK IN PROGRESS

BATCH

PREPARED COMPONENT

QUALITY RESULT

FINISHED PRODUCT

FULFILLMENT
```

---

# 111. FINAL RULE

Before ECIP represents production as planned, executing, delayed or completed, it shall be able to determine:

> What confirmed demand created the Production Requirement?

> Which Product and Recipe Version apply?

> What quantity is required and by when?

> Which Tasks must be performed?

> What dependencies exist between those Tasks?

> Which Kitchen Stations, Employees and Equipment are required?

> Which Ingredients or Prepared Components are needed?

> What work has actually started?

> What remains in progress or blocked?

> What quantity and yield were actually produced?

> Did any rework, waste or Quality failure occur?

> Has the finished output passed the required Quality conditions?

> Is the output production-ready, or merely partially complete?

> What effect does current Production state have on Customer commitments?

> Can the complete execution path be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably coordinate, explain, optimize or act upon restaurant Production.

