# 22_Quality_Control.md

**Document ID:** RDM-022
**Document Name:** Quality Control
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Quality Control Model for the Restaurant Intelligence Platform.

Its purpose is to represent how the restaurant verifies that Products, Recipes, Production executions, Service outcomes and fulfillment outputs comply with defined quality, safety, presentation and customer-experience standards before being accepted, served, delivered or closed.

The Quality Control Model connects:

* Products.
* Recipes.
* Ingredients.
* Production.
* Kitchen.
* Orders.
* Dine-In.
* Take Away.
* Delivery.
* Events.
* Equipment.
* Employees.
* Food Safety.
* Customer Complaints.
* Service Recovery.
* Operational Incidents.
* Customer History.
* Executive Intelligence.

Quality Control shall be modeled as an evidence-driven validation function.

It shall not be reduced to a subjective "good/bad" flag.

---

# 2. OBJECTIVES

The Quality Control Model enables ECIP to:

* Define quality standards.
* Define quality checkpoints.
* Validate Production outputs.
* Validate Product presentation.
* Validate portion conformity.
* Validate temperature where required.
* Validate Recipe conformity.
* Validate packaging.
* Validate Order completeness.
* Detect quality deviations.
* Detect repeated defects.
* Support rework and remake.
* Block unacceptable output.
* Track quality incidents.
* Trace defects to source.
* Support Customer Complaint resolution.
* Support Supplier and Ingredient analysis.
* Support Equipment problem detection.
* Support Employee training signals.
* Support Operational Intelligence.
* Support Executive Intelligence.
* Preserve complete quality evidence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Policy
* Procedure
* Knowledge Fact
* Evidence Record
* Action
* Action Authorization
* Task
* Incident
* Context Snapshot
* Runtime Event
* Metric Observation
* Recommendation
* Decision

Restaurant-specific Quality Control entities remain within the Restaurant Domain Pack.

---

# 4. QUALITY PRINCIPLE

Quality is the degree to which an actual restaurant output conforms to defined standards and customer commitments.

The platform shall distinguish between:

```text
QUALITY STANDARD

QUALITY CHECK

QUALITY OBSERVATION

QUALITY RESULT

QUALITY DEVIATION

CUSTOMER FEEDBACK

QUALITY INCIDENT

CORRECTIVE ACTION
```

These concepts are related but not equivalent.

---

# 5. QUALITY SCOPE

Quality Control may apply to:

* Ingredient.
* Prepared Component.
* Production Batch.
* Product.
* Order Item.
* Finished Order.
* Packaging.
* Delivery.
* Dining Experience.
* Event Service.
* Equipment-dependent output.
* Service process.

---

# 6. QUALITY STANDARD

A `QualityStandard` defines expected characteristics of an output or process.

Typical attributes include:

* Standard ID
* Name
* Scope
* Target entity type
* Criteria
* Tolerance
* Severity if violated
* Source
* Version
* Effective date
* Approval status
* Status

Examples:

* Steak weight 220 g ± tolerance.
* Soup serving temperature within defined range.
* Delivery package sealed.
* Pizza presentation standard.
* Order completeness requirement.
* Table reset standard.

---

# 7. QUALITY STANDARD TYPES

Initial types may include:

```text
PRODUCT

RECIPE

PORTION

TEMPERATURE

PRESENTATION

PACKAGING

COMPLETENESS

TIMING

SERVICE

SANITATION

EQUIPMENT_DEPENDENT

CUSTOM
```

---

# 8. QUALITY STANDARD SOURCE

Quality Standards may originate from:

* Recipe.
* Restaurant policy.
* Brand standard.
* Food Safety requirement.
* Product specification.
* Supplier specification.
* Customer commitment.
* Applicable regulation.

The source shall be preserved.

---

# 9. QUALITY STANDARD VERSION

Quality Standards shall support versioning.

A historical Quality Result shall reference the standard version applicable at the time of evaluation.

Current changes shall not rewrite historical quality evidence.

---

# 10. QUALITY CHECKPOINT

A `QualityCheckpoint` defines when and where a Quality Check must occur.

Examples:

* Ingredient receiving.
* Before production.
* During cooking.
* At Production completion.
* At Expo.
* Before Packaging.
* Before Delivery dispatch.
* Before Customer handoff.
* During service.
* At Event setup.

---

# 11. CHECKPOINT TYPES

Possible types:

```text
PRE_PRODUCTION

IN_PROCESS

POST_PRODUCTION

PRE_SERVICE

PRE_PACKAGING

POST_PACKAGING

PRE_DISPATCH

PRE_HANDOFF

SERVICE

POST_SERVICE
```

---

# 12. QUALITY CHECK

A `QualityCheck` represents an actual validation against one or more Quality Standards.

Typical attributes:

* Check ID
* Standard
* Target entity
* Checkpoint
* Performed by
* Timestamp
* Method
* Observations
* Measurements
* Result
* Evidence
* Exceptions

---

# 13. QUALITY CHECK METHODS

Examples:

* Visual inspection.
* Temperature measurement.
* Weight measurement.
* Quantity count.
* Packaging verification.
* Checklist.
* Customer confirmation.
* Equipment measurement.
* Automated sensor.
* Computer vision, future.

The method shall be explicit.

---

# 14. QUALITY RESULT

Suggested values:

```text
PASS

PASS_WITH_NOTE

HOLD

FAIL

REWORK_REQUIRED

REJECTED
```

A Quality Result shall be based on defined criteria.

---

# 15. PASS

`PASS` means the evaluated output complies with the applicable standard.

---

# 16. PASS WITH NOTE

`PASS_WITH_NOTE` means the output is acceptable but contains a non-blocking observation.

Example:

* Presentation slightly different but within tolerance.
* Packaging replacement used but still compliant.

---

# 17. HOLD

`HOLD` prevents normal continuation until an issue is reviewed.

Examples:

* Uncertain temperature reading.
* Suspected allergen issue.
* Packaging seal discrepancy.
* Unknown Ingredient Lot.

A held output shall not proceed to Customer fulfillment unless explicitly released by authorized logic.

---

# 18. FAIL

`FAIL` means the output does not meet the applicable standard.

Possible next steps:

* Rework.
* Remake.
* Discard.
* Escalate.
* Correct process.

---

# 19. REJECTED OUTPUT

A rejected Product or Batch shall not be served or delivered.

The disposition shall be explicit.

---

# 20. QUALITY OBSERVATION

A `QualityObservation` represents factual evidence recorded during a Quality Check.

Examples:

* Temperature 58°C.
* Weight 185 g.
* Missing garnish.
* Seal absent.
* Product spilled.
* Incorrect sauce.

Observation shall remain distinct from interpretation.

---

# 21. MEASUREMENT

A `QualityMeasurement` may include:

* Value.
* Unit.
* Target.
* Minimum.
* Maximum.
* Instrument.
* Calibration reference where applicable.
* Timestamp.

---

# 22. TOLERANCE

Quality Standards may define acceptable ranges.

Example:

```text
Target portion:
220 g

Tolerance:
±10 g

Observed:
228 g

Result:
PASS
```

Tolerance shall be explicit rather than inferred by AI.

---

# 23. QUALITY DEVIATION

A `QualityDeviation` represents departure from an applicable Quality Standard.

Typical attributes:

* Deviation ID
* Target
* Standard
* Observation
* Severity
* Detected time
* Source
* Responsible process
* Status
* Root cause
* Corrective action

---

# 24. DEVIATION SEVERITY

Suggested values:

```text
MINOR

MODERATE

MAJOR

CRITICAL
```

Critical deviations may include safety implications.

---

# 25. MINOR DEVIATION

A minor deviation may affect presentation or efficiency without materially affecting Customer safety or Product acceptability.

---

# 26. MAJOR DEVIATION

Examples:

* Wrong Product.
* Missing main component.
* Significant overcooking.
* Severe packaging failure.
* Product unusable.

---

# 27. CRITICAL DEVIATION

Examples may include:

* Confirmed allergen risk.
* Unsafe temperature.
* Contamination concern.
* Food Safety violation.

Critical quality issues shall trigger immediate safety-oriented handling.

---

# 28. QUALITY HOLD

A `QualityHold` formally prevents use, service, sale or movement of a Product, Batch or Ingredient.

Typical attributes:

* Hold ID
* Target
* Reason
* Start time
* Responsible authority
* Status
* Release decision
* Release evidence

---

# 29. HOLD RELEASE

A Quality Hold may be released only when:

* Reinspection passes.
* Corrective action completes.
* Authorized decision determines acceptance.

Release shall be auditable.

---

# 30. QUALITY REWORK

A `QualityRework` represents corrective processing intended to make an unacceptable output compliant.

Examples:

* Replate.
* Reheat where safe and policy permits.
* Correct packaging.
* Add missing component.

Rework shall not be used when Product safety or integrity requires a complete remake.

---

# 31. QUALITY REMAKE

A `QualityRemake` creates a new Production execution.

The failed original output remains historically preserved.

---

# 32. PRODUCT REJECTION

Rejected finished Product may result in:

* Waste.
* Inventory variance.
* Production rework.
* Customer delay.
* Operational incident.

All affected domains should remain linked.

---

# 33. RECIPE CONFORMITY

Quality Control may verify whether Production followed the applicable Recipe.

Possible checks:

* Ingredient selection.
* Quantity.
* Modifier.
* Cooking method.
* Portion.
* Presentation.

---

# 34. MODIFIER CONFORMITY

Example:

```text
Customer ordered:
No onion

Observed:
Onion present

Result:
QUALITY FAIL
```

This is both an Order Accuracy and Product Quality issue.

---

# 35. ALLERGY-SENSITIVE CONFORMITY

For allergy-sensitive Orders, checks may verify:

* Correct Recipe.
* Correct substitution.
* Special process followed.
* Packaging or labeling.
* Required acknowledgment.

Safety procedures shall be policy-driven.

---

# 36. PORTION CONTROL

Quality Control may compare actual portion against the Product or Recipe standard.

Potential consequences of persistent variance:

* Customer inconsistency.
* Cost variance.
* Inventory variance.
* Nutrition variance.

---

# 37. TEMPERATURE CONTROL

Temperature checks may apply to:

* Cooking.
* Holding.
* Refrigeration.
* Serving.
* Delivery packaging.

Detailed Food Safety rules belong to `31_Compliance.md`.

Quality Control records the operational validation.

---

# 38. PRESENTATION CONTROL

Presentation may validate:

* Plating.
* Garnish.
* Product arrangement.
* Correct container.
* Product appearance.

Presentation criteria should be standardized where operationally useful.

---

# 39. PRODUCT COMPLETENESS

Examples:

* All Product components present.
* Correct side included.
* Correct sauce.
* Correct beverage.
* Correct modifiers.

---

# 40. ORDER COMPLETENESS

Before fulfillment, an Order may require completeness validation.

Conceptually:

```text
Expected Order Items
+
Expected Quantities
+
Required Modifiers
+
Required Packaging
=
Complete Order
```

---

# 41. DINE-IN QUALITY CONTROL

Dine-In checks may occur at:

* Kitchen completion.
* Expo.
* Before serving.
* Customer complaint investigation.

---

# 42. TAKE AWAY QUALITY CONTROL

Take Away may validate:

* Product completeness.
* Packaging.
* Label.
* Pickup Order identity.
* Required utensils.
* Holding time.

---

# 43. DELIVERY QUALITY CONTROL

Delivery may additionally validate:

* Tamper evidence.
* Temperature separation.
* Transport suitability.
* Package stability.
* Delivery completeness.

---

# 44. EVENT QUALITY CONTROL

Events may require:

* Setup inspection.
* Menu conformity.
* Guest-count readiness.
* Equipment readiness.
* Buffet presentation.
* Timing checkpoints.

---

# 45. BUFFET QUALITY CONTROL

Potential checks include:

* Product availability.
* Temperature.
* Holding time.
* Appearance.
* Replenishment.
* Cleanliness.

---

# 46. INGREDIENT QUALITY

Ingredient Quality may be evaluated at:

* Receiving.
* Storage.
* Pre-production use.

Examples:

* Temperature.
* Appearance.
* Expiration.
* Packaging integrity.
* Supplier conformity.

Detailed Inventory and Ingredient lifecycle remains separate.

---

# 47. RECEIVING QUALITY CHECK

Purchasing receiving may trigger:

```text
Supplier Delivery
    ↓
Quantity Check
    ↓
Quality Check
    ↓
Accept / Hold / Reject
```

This may prevent unsuitable Ingredient Lots from entering usable stock.

---

# 48. SUPPLIER QUALITY ISSUE

Repeated Ingredient failures may create Supplier Quality Intelligence.

Examples:

* Damaged packaging.
* Repeated wrong quantities.
* Poor Ingredient condition.
* Temperature violations.

Purchasing remains authoritative for Supplier management.

---

# 49. PREPARED COMPONENT QUALITY

Prepared Components may require checks before becoming available.

Examples:

* Batch yield.
* Temperature.
* Consistency.
* Appearance.
* Expiration label.

---

# 50. BATCH QUALITY

A Production Batch may be accepted, held or rejected as a whole or partially.

Batch quality shall remain traceable to:

* Recipe Version.
* Ingredient Lots.
* Production execution.
* Employees.
* Equipment.

---

# 51. QUALITY TRACEABILITY

The platform should support:

```text
Customer Complaint
    ↓
Order Item
    ↓
Production Execution
    ↓
Recipe Version
    ↓
Ingredient Lots
    ↓
Supplier / Receiving
```

where data is available.

---

# 52. QUALITY ROOT CAUSE

Potential root-cause categories include:

```text
INGREDIENT

RECIPE

PROCESS

EMPLOYEE_EXECUTION

EQUIPMENT

PACKAGING

STORAGE

TRANSPORT

ORDER_CAPTURE

COMMUNICATION

UNKNOWN
```

Root cause shall require evidence.

---

# 53. ROOT-CAUSE CAUTION

The system shall not blame an Employee merely because the Employee executed the Task.

Example:

```text
Burned Product
```

may result from:

* Equipment temperature fault.
* Recipe timing error.
* Workload overload.
* Human error.

Context is required.

---

# 54. CORRECTIVE ACTION

A `QualityCorrectiveAction` represents an action intended to resolve a specific Quality Deviation.

Examples:

* Remake Product.
* Repair Equipment.
* Retrain process.
* Update Recipe.
* Reject supplier lot.
* Adjust packaging.

Material actions shall use governed authorization.

---

# 55. PREVENTIVE ACTION

A `QualityPreventiveAction` aims to reduce recurrence.

Examples:

* Additional checkpoint.
* Supplier change recommendation.
* Equipment maintenance.
* Process adjustment.
* Training.

Preventive actions are recommendations until authorized.

---

# 56. QUALITY INCIDENT

A `QualityIncident` represents a material Quality problem requiring coordinated management.

Examples:

* Multiple Customers affected.
* Repeated Batch failure.
* Food Safety concern.
* Widespread packaging defect.

Operational Incident lifecycle remains governed by `30_Operational_Incidents.md`.

---

# 57. QUALITY ISSUE VS INCIDENT

A single failed Product may be a Quality Deviation.

Multiple related failures may become an Incident.

The transition shall be policy-driven.

---

# 58. CUSTOMER-REPORTED QUALITY ISSUE

A Customer Complaint may reveal a Quality problem after internal checks passed.

Customer evidence shall not be dismissed merely because internal validation reported PASS.

---

# 59. CUSTOMER QUALITY COMPLAINT

Examples:

* Food cold.
* Product overcooked.
* Item missing.
* Product leaked.
* Wrong modification.
* Poor taste.

Complaint and Quality Deviation shall be linked when appropriate.

---

# 60. COMPLAINT VALIDATION

The restaurant may evaluate:

* Customer report.
* Order.
* Production history.
* Checkpoint evidence.
* Delivery history.

The goal is understanding, not disproving the Customer.

---

# 61. SERVICE QUALITY

Quality Control may also evaluate defined operational service standards.

Examples:

* Order accuracy.
* Reservation setup.
* Event readiness.
* Service Request completion.

Dining Experience remains authoritative for the broader Customer Experience interpretation.

---

# 62. QUALITY VS CUSTOMER PREFERENCE

A Product may fully satisfy Quality Standards while the Customer simply dislikes it.

Example:

```text
Product:
Prepared correctly

Customer:
Does not like the flavor
```

This is Preference / Experience information, not necessarily Quality failure.

---

# 63. QUALITY VS SATISFACTION

High technical quality does not guarantee Customer satisfaction.

Likewise, Customer satisfaction does not prove all technical Quality Standards were met.

These dimensions shall remain separate.

---

# 64. QUALITY CHECK RESPONSIBILITY

Quality Checks may be performed by:

* Cook.
* Chef.
* Expo.
* Manager.
* Receiving employee.
* Automated device.
* External inspector.

Responsible actor shall be preserved.

---

# 65. QUALITY AUTHORIZATION

Some Quality decisions may require authority.

Examples:

* Release held Ingredient.
* Override Product rejection.
* Accept supplier deviation.
* Continue service after major Equipment issue.

High-risk Quality overrides shall require appropriate approval.

---

# 66. QUALITY OVERRIDE

A `QualityOverride` represents an authorized exception.

It shall preserve:

* Original result.
* Override decision.
* Actor.
* Reason.
* Evidence.
* Scope.
* Risk.

AI shall not autonomously override Quality failures.

---

# 67. QUALITY ESCALATION

Escalation may be required for:

* Critical deviation.
* Food Safety concern.
* Repeated defect.
* Customer injury allegation.
* Large Batch rejection.
* Supplier issue.

---

# 68. QUALITY AND PRODUCTION

Production creates output.

Quality Control determines whether that output is acceptable.

Conceptually:

```text
Production Execution
    ↓
Quality Check
    ↓
PASS
or
HOLD
or
REWORK
or
REJECT
```

---

# 69. QUALITY AND KITCHEN

Kitchen provides operational Context such as:

* Station.
* Equipment.
* workload.
* Employees.

Quality uses this Context for diagnosis.

---

# 70. QUALITY AND RECIPE

Recipe defines expected composition and procedure.

Quality verifies conformity.

Quality Control shall not independently redefine the Recipe.

---

# 71. QUALITY AND INVENTORY

Quality may block Ingredient or Prepared Component usage.

Inventory remains authoritative for stock state.

A Quality Hold shall affect usable availability.

---

# 72. QUALITY AND PURCHASING

Quality results may inform:

* Supplier score.
* Supplier claims.
* Receiving rejection.
* Procurement decisions.

Purchasing owns Supplier commercial relationships.

---

# 73. QUALITY AND MAINTENANCE

Repeated Quality problems may indicate Equipment degradation.

Example:

```text
Oven:
Temperature instability

Observed:
Repeated undercooking
```

Quality may create a Maintenance signal.

Maintenance owns repair workflow.

---

# 74. QUALITY AND DELIVERY

Delivery Quality may reveal:

* Route too long.
* Packaging inadequacy.
* Provider mishandling.

Delivery operational evidence is required before conclusions.

---

# 75. QUALITY AND CUSTOMER HISTORY

Significant Customer Quality issues may contribute to Customer History.

Routine internal checks should not all become Customer history.

---

# 76. QUALITY AND SERVICE RECOVERY

A confirmed Quality failure may trigger:

* Replacement.
* Refund.
* Discount.
* Manager contact.

Commercial actions remain subject to authorization.

---

# 77. QUALITY METRIC

Potential metrics include:

* Pass rate.
* Fail rate.
* Rework rate.
* Remake rate.
* Complaint-linked failure rate.
* Batch rejection rate.
* Portion variance.
* Temperature compliance.
* Packaging failure rate.

---

# 78. FIRST-PASS YIELD

`FirstPassYield` may measure the percentage of outputs accepted without rework.

Conceptually:

```text
Accepted on first attempt
/
Total evaluated output
```

---

# 79. REWORK RATE

Measures how frequently output requires corrective work before acceptance.

---

# 80. REMAKE RATE

Measures complete replacement frequency.

High Remake Rate may indicate systemic issues.

---

# 81. QUALITY COST

Quality-related cost may include:

* Waste.
* Remake.
* Refund.
* Compensation.
* Additional labor.
* Supplier rejection.

Financial calculations remain governed by appropriate financial domains.

---

# 82. COST OF POOR QUALITY

Aggregated Quality evidence may support a `CostOfPoorQuality` metric.

Potential components:

* Waste.
* Rework.
* Complaints.
* Refunds.
* Lost sales.
* Delivery recovery.

This is analytical.

---

# 83. QUALITY TREND

Trend analysis may identify:

* Increasing failures.
* Improving compliance.
* Product-specific problems.
* Station-specific issues.
* Supplier-related trends.

---

# 84. RECURRING QUALITY DEFECT

A `RecurringQualityDefect` may be identified when similar deviations recur.

Example:

```text
Product:
Steak

Issue:
Repeated underweight portion

Frequency:
12 deviations in 7 days
```

This may trigger root-cause investigation.

---

# 85. DEFECT CLUSTER

Quality Intelligence may detect clusters by:

* Product.
* Recipe.
* Station.
* Employee group.
* Equipment.
* Supplier.
* Branch.
* Time period.

A cluster is an analytical finding, not automatically proof of cause.

---

# 86. QUALITY ALERT

Alerts may be generated for:

* Critical deviation.
* High repeat rate.
* Quality Hold.
* Batch rejection.
* Temperature issue.
* Safety risk.

Alerts shall be actionable and severity-based.

---

# 87. QUALITY DASHBOARD

Future operational views may include:

* Active Holds.
* Current failures.
* Rework queue.
* Product defect trends.
* Supplier issues.
* Branch comparison.

This document does not prescribe UI.

---

# 88. QUALITY INTELLIGENCE

Potential insights include:

* Which Products fail most frequently?
* Which Recipes have highest variance?
* Which Equipment correlates with defects?
* Which Supplier Lots cause recurring issues?
* Which fulfillment channel has most packaging problems?

---

# 89. CUSTOMER QUALITY INTELLIGENCE

Customer feedback may reveal defects not caught internally.

Examples:

* Long-term temperature complaints in Delivery.
* Portion inconsistency.
* Frequent missing modifiers.

This evidence should feed Quality analysis.

---

# 90. EXECUTIVE QUALITY INTELLIGENCE

Potential executive indicators:

* Quality failure rate.
* Waste attributable to Quality.
* Complaint-linked Quality cost.
* Supplier rejection rate.
* Quality trends by Branch.
* Cost of poor Quality.

---

# 91. AI QUALITY ASSISTANCE

AI may assist with:

* Classifying Customer complaints.
* Summarizing Quality evidence.
* Detecting recurring patterns.
* Suggesting likely root-cause candidates.
* Recommending investigation steps.

AI shall not convert unsupported correlations into definitive root causes.

---

# 92. AI QUALITY LIMIT

AI shall not:

* Approve failed Products.
* Override Food Safety.
* Change Quality Standards autonomously.
* Release Quality Holds without authorization.
* Invent measurements.
* Falsify compliance.

---

# 93. AUTOMATED QUALITY CHECKS

Future automation may include:

* Sensor temperature checks.
* Weight devices.
* Computer vision.
* Packaging scanners.

Automated results shall preserve:

* Device.
* Measurement.
* Timestamp.
* Confidence where applicable.
* Calibration status where required.

---

# 94. SENSOR FAILURE

A failed or unreliable measurement device shall not silently produce trusted Quality evidence.

The platform should represent:

```text
MEASUREMENT_UNAVAILABLE

SENSOR_ERROR

CALIBRATION_REQUIRED
```

where applicable.

---

# 95. QUALITY EVIDENCE

Quality evidence may include:

* Measurement.
* Employee observation.
* Photo reference.
* Sensor output.
* Customer report.
* Production data.
* Packaging scan.

Evidence retention shall follow policy.

---

# 96. QUALITY TRACE

A Quality Trace should allow reconstruction of:

```text
Standard
    ↓
Checkpoint
    ↓
Check
    ↓
Observation / Measurement
    ↓
Result
    ↓
Deviation
    ↓
Corrective Action
    ↓
Final Disposition
```

---

# 97. FINAL DISPOSITION

A `QualityDisposition` represents the final treatment of an evaluated entity.

Suggested values:

```text
ACCEPTED

ACCEPTED_WITH_EXCEPTION

REWORKED_AND_ACCEPTED

REJECTED

DISCARDED

RETURNED_TO_SUPPLIER

HELD
```

---

# 98. QUALITY RECORD RETENTION

Quality records may require retention for:

* Customer disputes.
* Food Safety.
* Supplier claims.
* Audit.
* Operational analysis.

Retention shall follow applicable policy and regulation.

---

# 99. SOURCE OF TRUTH

Authority may vary by Quality data type.

Example:

```text
Recipe:
Recipe Domain

Temperature Measurement:
Quality Device / Employee Record

Production State:
Production Runtime

Customer Complaint:
Customer Interaction

Quality Decision:
Quality Control
```

Quality Control composes evidence but does not replace all source domains.

---

# 100. EXTERNAL QUALITY MAPPING

External systems may use:

* Inspection ID.
* Quality ticket.
* Batch QA record.
* Supplier rejection ID.

These shall map to canonical Quality entities.

---

# 101. QUALITY SYNCHRONIZATION

Synchronization may include:

* Quality Check result.
* Hold.
* Release.
* Rejection.
* Supplier quality event.

Synchronization shall remain idempotent and observable.

---

# 102. QUALITY CONFLICT

Possible conflicts include:

```text
Production:
Product READY

Quality:
Product HOLD
```

Normal fulfillment shall respect Quality Hold.

Another example:

```text
External system:
Batch accepted

ECIP:
Critical Quality failure recorded
```

The conflict shall require authoritative resolution.

---

# 103. QUALITY EVENTS

Initial domain events include:

```text
QualityStandardCreated
QualityStandardUpdated
QualityStandardActivated
QualityStandardRetired

QualityCheckpointCreated
QualityCheckpointUpdated

QualityCheckRequested
QualityCheckStarted
QualityCheckCompleted

QualityPassed
QualityPassedWithNote
QualityHoldPlaced
QualityHoldReleased
QualityFailed
QualityRejected

QualityObservationRecorded
QualityMeasurementRecorded

QualityDeviationDetected
QualityDeviationClassified
QualityDeviationResolved

QualityReworkRequested
QualityReworkStarted
QualityReworkCompleted

QualityRemakeRequested
QualityRemakeCompleted

QualityCorrectiveActionCreated
QualityCorrectiveActionCompleted

QualityPreventiveActionRecommended

QualityIncidentDetected

IngredientQualityRejected
BatchQualityRejected
ProductQualityRejected

OrderCompletenessFailed
PackagingQualityFailed

CustomerQualityComplaintLinked

RecurringQualityDefectDetected

QualityConflictDetected
QualityConflictResolved

QualitySynchronizationStarted
QualitySynchronizationCompleted
QualitySynchronizationFailed
```

---

# 104. RELATIONSHIPS

```text
QualityStandard
    APPLIES_TO TargetEntity

QualityStandard
    HAS QualityCheckpoint

QualityCheckpoint
    TRIGGERS QualityCheck

QualityCheck
    PRODUCES QualityObservation

QualityCheck
    MAY_PRODUCE QualityMeasurement

QualityCheck
    PRODUCES QualityResult

QualityResult
    MAY_CREATE QualityDeviation

QualityDeviation
    MAY_CREATE QualityHold

QualityDeviation
    MAY_REQUIRE QualityRework

QualityDeviation
    MAY_REQUIRE QualityRemake

QualityDeviation
    MAY_CREATE CorrectiveAction

ProductionExecution
    SUBJECT_TO QualityCheck

ProductionBatch
    SUBJECT_TO QualityCheck

PreparedComponent
    SUBJECT_TO QualityCheck

Order
    MAY_REQUIRE CompletenessCheck

DeliveryPackage
    MAY_REQUIRE PackagingQualityCheck

CustomerComplaint
    MAY_REFERENCE QualityDeviation

QualityDeviation
    MAY_CREATE OperationalIncident

QualityEvidence
    SUPPORTS QualityDecision
```

---

# 105. BUSINESS RULES

The following rules apply:

1. Quality evaluation shall use explicit Standards whenever applicable.

2. Historical Quality Results shall preserve the Standard Version used.

3. Quality Observation shall remain distinct from Quality interpretation.

4. Failed or held output shall not proceed to normal fulfillment unless explicitly released.

5. Critical safety-related deviations shall override commercial and throughput objectives.

6. Rework shall not replace Remake when Product integrity requires full replacement.

7. Failed Production evidence shall remain traceable after Remake.

8. Customer complaints may reveal Quality failures even when internal checks passed.

9. Quality shall not be confused with Customer preference or satisfaction.

10. Root-cause conclusions shall require evidence.

11. AI shall not autonomously override a Quality failure or Hold.

12. Quality checks shall preserve the responsible actor or device.

13. Measurements shall preserve value, unit and method.

14. External Quality identifiers shall remain integration mappings.

15. Quality decisions and overrides shall remain auditable.

16. Quality Control shall not silently redefine Recipes, Products or Food Safety policy.

17. Repeated Quality deviations should support systemic analysis.

18. Quality evidence shall remain protected according to applicable access and retention policy.

---

# 106. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
QualityStandard

QualityStandardVersion

QualityCheckpoint

QualityCheck

QualityObservation

QualityMeasurement

QualityResult

QualityDeviation

QualityHold

QualityRework

QualityRemakeReference

QualityDisposition

ProductionQualityReference

OrderCompletenessCheck

PackagingQualityCheck

CustomerQualityComplaintReference

QualityCorrectiveAction

ExternalQualityMapping

QualityHistory
```

Defer unless required by the first commercial pilot:

```text
Computer Vision Quality Inspection

Advanced Sensor Network Integration

Predictive Quality Failure Models

Autonomous Root-Cause Diagnosis

Advanced Supplier Quality Prediction

Digital Twin Quality Simulation

Autonomous Quality Process Optimization
```

---

# 107. IMPLEMENTATION PRINCIPLE

This document defines the logical Quality Control Model.

It does not prescribe:

* Quality Management System vendor.
* Database schema.
* Sensor technology.
* Computer vision implementation.
* Food Safety management software.
* Supplier system.
* AI model.
* Quality scoring algorithm.

Implementation shall preserve the semantic distinction between:

```text
QUALITY STANDARD

QUALITY CHECKPOINT

QUALITY CHECK

OBSERVATION

MEASUREMENT

QUALITY RESULT

DEVIATION

HOLD

REWORK

REMAKE

CORRECTIVE ACTION

FINAL DISPOSITION
```

---

# 108. FINAL RULE

Before ECIP represents a Product, Batch, Order or fulfillment output as Quality-approved, it shall be able to determine:

> What Quality Standard applies?

> Which Standard Version was effective?

> At what checkpoint should validation occur?

> What was actually observed or measured?

> Who or what performed the check?

> Did the result fall within the allowed criteria or tolerance?

> Was any deviation detected?

> Does the output require Hold, Rework, Remake or Rejection?

> Is there any Food Safety implication?

> Was a Quality override requested or granted?

> What evidence supports the final Quality decision?

> Does the issue indicate a broader operational or recurring defect?

> Can the complete Quality lifecycle be reconstructed and audited?

Only after these conditions are resolved may ECIP represent the evaluated output as acceptable for continued production, service, packaging, delivery or customer fulfillment.

