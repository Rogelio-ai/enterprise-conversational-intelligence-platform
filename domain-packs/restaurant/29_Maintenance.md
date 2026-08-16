# 29_Maintenance.md

**Document ID:** RDM-029
**Document Name:** Maintenance
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Maintenance Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of preventive, predictive and corrective maintenance for restaurant Equipment, Facilities and operational Resources.

The Maintenance Model connects:

* Equipment.
* Restaurant Resources.
* Locations.
* Kitchen.
* Production.
* Quality Control.
* Inventory.
* Purchasing.
* Employees.
* External Service Providers.
* Work Orders.
* Inspections.
* Failures.
* Downtime.
* Spare Parts.
* Operational Incidents.
* Product Availability.
* Customer Commitments.
* Cost.
* Compliance.
* Operational Intelligence.
* Executive Intelligence.

Maintenance shall not be modeled merely as a list of repairs.

It represents the governed lifecycle required to keep restaurant operational assets safe, available and economically reliable.

---

# 2. OBJECTIVES

The Maintenance Model enables ECIP to:

* Track maintainable assets.
* Track Equipment status.
* Track preventive Maintenance schedules.
* Track corrective Maintenance.
* Track inspections.
* Track failures.
* Track work requests.
* Create Maintenance Work Orders.
* Assign technicians.
* Track external service providers.
* Track spare parts.
* Track downtime.
* Track repair costs.
* Track Maintenance history.
* Detect recurring failures.
* Detect overdue preventive Maintenance.
* Support predictive Maintenance.
* Support operational availability.
* Support Production feasibility.
* Support Quality.
* Support Compliance.
* Preserve complete Maintenance evidence.
* Support Maintenance Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Asset
* Resource
* Location
* Employee
* Task
* Work Order
* Action
* Action Authorization
* Incident
* Inspection
* Evidence Record
* Metric Observation
* Context Snapshot
* External Entity Reference

Restaurant-specific Maintenance entities remain within the Restaurant Domain Pack.

---

# 4. MAINTENANCE PRINCIPLE

The platform shall distinguish between:

```text
ASSET

EQUIPMENT STATE

MAINTENANCE REQUIREMENT

MAINTENANCE REQUEST

WORK ORDER

INSPECTION

FAILURE

REPAIR

DOWNTIME

PREVENTIVE MAINTENANCE

CORRECTIVE MAINTENANCE

PREDICTIVE MAINTENANCE
```

These concepts shall remain independently traceable.

---

# 5. MAINTAINABLE ASSET

A `MaintainableAsset` represents any restaurant Resource requiring inspection, servicing, repair or lifecycle management.

Examples include:

* Oven.
* Grill.
* Fryer.
* Refrigerator.
* Freezer.
* Dishwasher.
* HVAC unit.
* Espresso machine.
* Blender.
* POS terminal.
* Generator.
* Electrical panel.
* Water system.
* Delivery vehicle.
* Furniture where relevant.
* Building infrastructure.

Typical attributes include:

* Asset ID
* Resource reference
* Name
* Asset type
* Manufacturer
* Model
* Serial number
* Branch
* Physical Location
* Installation date
* Commission date
* Warranty
* Criticality
* Maintenance policy
* Current operational status
* Current health status
* External identifiers

---

# 6. ASSET TYPE

Initial types may include:

```text
KITCHEN_EQUIPMENT

REFRIGERATION

HVAC

ELECTRICAL

PLUMBING

GAS

POS_EQUIPMENT

IT_INFRASTRUCTURE

SAFETY_EQUIPMENT

DELIVERY_VEHICLE

FACILITY

FURNITURE

OTHER
```

The catalog shall remain configurable.

---

# 7. ASSET STATUS

Suggested lifecycle states:

```text
PLANNED

INSTALLED

ACTIVE

SUSPENDED

OUT_OF_SERVICE

RETIRED

DISPOSED
```

Lifecycle Status shall remain distinct from current Health or Availability.

---

# 8. OPERATIONAL STATUS

Suggested operational states:

```text
AVAILABLE

IN_USE

DEGRADED

LIMITED_CAPACITY

OUT_OF_SERVICE

MAINTENANCE

INSPECTION_REQUIRED

UNKNOWN
```

---

# 9. ASSET HEALTH

A `AssetHealthAssessment` may summarize operational condition.

Suggested values:

```text
HEALTHY

ATTENTION_REQUIRED

DEGRADED

CRITICAL

FAILED

UNKNOWN
```

Health may be derived from:

* Inspections.
* Failure events.
* Sensor evidence.
* Maintenance history.
* Employee reports.

---

# 10. ASSET CRITICALITY

A `AssetCriticality` represents the operational importance of an Asset.

Suggested values:

```text
LOW

MEDIUM

HIGH

CRITICAL
```

Criticality may consider:

* Safety impact.
* Product impact.
* Revenue impact.
* Replacement difficulty.
* Operational redundancy.

---

# 11. CRITICAL ASSET

Examples may include:

* Main walk-in refrigerator.
* Only pizza oven.
* Main electrical panel.
* Fire suppression system.
* Critical POS infrastructure.

Failure of a Critical Asset may significantly affect restaurant operation.

---

# 12. ASSET DEPENDENCY

Assets may support:

* Kitchen Stations.
* Recipes.
* Products.
* Storage Locations.
* Cash Registers.
* Delivery operations.

Dependency mapping enables impact analysis.

---

# 13. EQUIPMENT DEPENDENCY GRAPH

Conceptually:

```text
Asset
    ↓
Kitchen Station / Operational Function
    ↓
Recipes
    ↓
Products
    ↓
Orders
    ↓
Customer Commitments
```

This relationship is essential to operational intelligence.

---

# 14. MAINTENANCE TYPES

The model shall support:

```text
PREVENTIVE

CORRECTIVE

PREDICTIVE

CONDITION_BASED

INSPECTION

CALIBRATION

EMERGENCY

INSTALLATION

UPGRADE
```

---

# 15. PREVENTIVE MAINTENANCE

Preventive Maintenance is scheduled work intended to reduce the probability of failure.

Examples:

* Clean refrigeration condenser.
* Inspect gas connection.
* Replace fryer filter.
* Service HVAC.
* Lubricate moving components.

---

# 16. PREVENTIVE MAINTENANCE PLAN

A `PreventiveMaintenancePlan` defines recurring Maintenance requirements.

Typical attributes include:

* Plan ID
* Asset
* Maintenance procedure
* Frequency
* Trigger type
* Estimated duration
* Required skills
* Required parts
* Responsible role
* Effective date
* Status

---

# 17. PREVENTIVE TRIGGER

Maintenance may be triggered by:

```text
CALENDAR

OPERATING_HOURS

CYCLE_COUNT

DISTANCE

USAGE

CONDITION

MANUAL
```

---

# 18. CALENDAR-BASED MAINTENANCE

Examples:

```text
Daily

Weekly

Monthly

Quarterly

Every 6 months

Annually
```

---

# 19. USAGE-BASED MAINTENANCE

Examples:

* Every 500 operating hours.
* Every 10,000 cycles.
* Every 5,000 km.

Usage evidence may come from:

* Sensors.
* Manual readings.
* External systems.

---

# 20. CONDITION-BASED MAINTENANCE

Maintenance may be triggered by observed Asset condition.

Examples:

* Temperature instability.
* Excess vibration.
* Unusual noise.
* Performance degradation.
* Pressure outside range.

---

# 21. PREDICTIVE MAINTENANCE

Predictive Maintenance uses historical and operational evidence to estimate failure risk before actual failure.

Potential inputs:

* Failure history.
* Sensor trends.
* Usage.
* Maintenance history.
* Performance degradation.
* Quality defects.

Predictive results remain analytical until acted upon.

---

# 22. PREDICTED FAILURE RISK

A `PredictedFailureRisk` may include:

* Asset.
* Failure mode.
* Probability or confidence.
* Expected time horizon.
* Evidence.
* Impact.
* Recommended action.

AI-generated predictions shall remain clearly labeled as predictive.

---

# 23. CORRECTIVE MAINTENANCE

Corrective Maintenance is work performed to restore an Asset after a defect or failure is detected.

Possible sources:

* Equipment failure.
* Employee report.
* Inspection.
* Quality issue.
* Operational incident.
* Sensor alert.

---

# 24. EMERGENCY MAINTENANCE

Emergency Maintenance applies when delay may cause:

* Safety risk.
* Complete operational shutdown.
* Severe product loss.
* Critical Customer impact.

Emergency status shall preserve elevated priority and authorization.

---

# 25. MAINTENANCE REQUIREMENT

A `MaintenanceRequirement` represents identified Maintenance need.

Typical attributes:

* Requirement ID
* Asset
* Requirement type
* Source
* Severity
* Detected time
* Required by
* Business impact
* Status

---

# 26. MAINTENANCE REQUEST

A `MaintenanceRequest` represents a reported Maintenance problem or service need.

Typical attributes:

* Request ID
* Asset
* Branch
* Location
* Reported by
* Description
* Severity
* Symptoms
* Requested time
* Operational impact
* Status

---

# 27. REQUEST SOURCES

A Maintenance Request may originate from:

```text
EMPLOYEE

MANAGER

KITCHEN

QUALITY_CONTROL

SENSOR

INSPECTION

OPERATIONAL_INCIDENT

AI_RECOMMENDATION

EXTERNAL_PROVIDER
```

Source shall always remain explicit.

---

# 28. MAINTENANCE REQUEST STATUS

Suggested lifecycle:

```text
CREATED
→ TRIAGED
→ APPROVED
→ WORK_ORDER_CREATED
→ RESOLVED
```

Alternative states:

```text
REJECTED
DUPLICATE
CANCELLED
```

---

# 29. MAINTENANCE TRIAGE

Triage determines:

* Severity.
* Safety impact.
* Operational impact.
* Asset criticality.
* Immediate containment.
* Required expertise.
* Work priority.

---

# 30. MAINTENANCE SEVERITY

Suggested values:

```text
LOW

MODERATE

HIGH

CRITICAL
```

---

# 31. CRITICAL MAINTENANCE CONDITION

Examples:

* Gas leak.
* Fire suppression failure.
* Main refrigeration failure.
* Electrical hazard.
* Water contamination concern.

Critical conditions may require immediate operational shutdown or isolation according to policy.

---

# 32. FAILURE

An `AssetFailure` represents inability of an Asset to perform its required function.

Typical attributes:

* Failure ID
* Asset
* Failure mode
* Detected time
* Severity
* Symptoms
* Operational impact
* Safety impact
* Production impact
* Resolution status

---

# 33. FAILURE MODE

Examples:

```text
NO_POWER

OVERHEATING

UNDER_TEMPERATURE

LEAK

MECHANICAL_FAILURE

ELECTRICAL_FAILURE

SENSOR_FAILURE

COMMUNICATION_FAILURE

PERFORMANCE_DEGRADATION

UNKNOWN
```

---

# 34. FAILURE STATUS

Suggested lifecycle:

```text
DETECTED
→ CONFIRMED
→ CONTAINED
→ UNDER_REPAIR
→ RESTORED
→ CLOSED
```

---

# 35. ASSET DEGRADATION

An Asset may remain usable while performing below normal capacity.

Example:

```text
Oven:
One heating element failed

Result:
Still operational
but capacity reduced
```

The platform shall support degraded operation.

---

# 36. ASSET ISOLATION

A failed or unsafe Asset may need to be isolated.

Isolation prevents normal operational use until authorized release.

---

# 37. WORK ORDER

A `MaintenanceWorkOrder` represents authorized Maintenance work.

Typical attributes include:

* Work Order ID
* Asset
* Branch
* Maintenance type
* Priority
* Problem description
* Work scope
* Assigned technician
* External provider
* Planned start
* Planned completion
* Actual start
* Actual completion
* Required parts
* Labor
* Cost
* Status
* Related Maintenance Request
* Related Incident

---

# 38. WORK ORDER STATUS

Suggested lifecycle:

```text
DRAFT
→ APPROVED
→ SCHEDULED
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
→ VERIFIED
→ CLOSED
```

Alternative states:

```text
ON_HOLD
BLOCKED
CANCELLED
FAILED
```

---

# 39. WORK ORDER PRIORITY

Suggested values:

```text
LOW

NORMAL

HIGH

URGENT

EMERGENCY
```

Priority shall consider:

* Safety.
* Asset criticality.
* Customer impact.
* Production impact.
* Downtime.
* Redundancy.

---

# 40. MAINTENANCE PROCEDURE

A `MaintenanceProcedure` defines standard work to perform.

Typical attributes:

* Procedure ID
* Asset type
* Steps
* Safety requirements
* Required skills
* Required tools
* Required parts
* Expected duration
* Verification steps
* Version

---

# 41. WORK ORDER TASK

A Work Order may contain multiple Tasks.

Examples:

```text
Inspect

Diagnose

Disassemble

Replace Component

Test

Clean

Reassemble

Verify Operation
```

---

# 42. TECHNICIAN

A `MaintenanceTechnician` may be:

* Restaurant Employee.
* Corporate Maintenance Employee.
* External contractor.

Qualification shall remain explicit.

---

# 43. TECHNICIAN SKILL

Maintenance may require:

* Electrical.
* Refrigeration.
* Gas.
* Plumbing.
* HVAC.
* Mechanical.
* IT.
* Specialized manufacturer certification.

---

# 44. EXTERNAL SERVICE PROVIDER

An `MaintenanceServiceProvider` represents an external company or technician.

Typical attributes:

* Provider ID
* Name
* Service categories
* Contact
* Coverage
* Contract
* Response time
* Status
* Performance profile

---

# 45. SERVICE PROVIDER STATUS

Suggested states:

```text
APPROVED

ACTIVE

SUSPENDED

BLOCKED

INACTIVE
```

---

# 46. WARRANTY

An Asset may have Warranty information such as:

* Provider.
* Start date.
* End date.
* Coverage.
* Conditions.
* Contact.

Maintenance decisions may consider active warranty coverage.

---

# 47. WARRANTY CLAIM

A `WarrantyClaim` may be created when a failure appears eligible for warranty repair.

Typical attributes:

* Asset.
* Failure.
* Warranty.
* Claim status.
* Provider.
* Evidence.
* Financial outcome.

---

# 48. SPARE PART

A `SparePart` represents a component used in Maintenance.

Examples:

* Filter.
* Belt.
* Motor.
* Sensor.
* Thermostat.
* Heating element.
* Fuse.

Spare Parts may map to Inventory Items.

---

# 49. SPARE PART REQUIREMENT

A Work Order may require:

* Part.
* Quantity.
* Required date.
* Availability.
* Supplier.

---

# 50. SPARE PART AVAILABILITY

A Work Order may be blocked because the required Spare Part is unavailable.

This may create a Purchase Requirement.

---

# 51. MAINTENANCE PURCHASING

Maintenance may generate Procurement demand for:

* Spare Parts.
* External service.
* Replacement Equipment.
* Consumables.

`24_Purchasing.md` remains authoritative for procurement lifecycle.

---

# 52. TOOL REQUIREMENT

Some Work Orders require specialized tools.

Tool availability may affect scheduling.

---

# 53. DOWNTIME

`AssetDowntime` represents time during which an Asset cannot provide normal required service.

Typical attributes:

* Asset.
* Start time.
* End time.
* Duration.
* Cause.
* Planned vs unplanned.
* Operational impact.

---

# 54. PLANNED DOWNTIME

Planned downtime may result from:

* Preventive Maintenance.
* Upgrade.
* Inspection.
* Scheduled replacement.

---

# 55. UNPLANNED DOWNTIME

Unplanned downtime typically results from:

* Failure.
* Emergency.
* Unexpected degradation.

---

# 56. DOWNTIME IMPACT

Downtime may affect:

* Kitchen Station.
* Product availability.
* Storage.
* Delivery.
* Cash Register.
* Customer service.

Impact shall be explicit.

---

# 57. PRODUCT IMPACT

Example:

```text
Pizza Oven:
OUT_OF_SERVICE

Dependent Products:
12 pizzas

Result:
Operationally unavailable
unless alternate production resource exists
```

---

# 58. STORAGE IMPACT

Example:

```text
Walk-in Freezer:
Failed

Affected:
Frozen stock
```

Maintenance shall connect with Inventory and Quality for product protection.

---

# 59. QUALITY IMPACT

Equipment degradation may cause Quality problems.

Examples:

* Oven temperature instability.
* Refrigerator temperature failure.
* Dishwasher malfunction.

Quality evidence may create Maintenance requirements.

---

# 60. CUSTOMER COMMITMENT IMPACT

A Maintenance failure may threaten:

* Existing Orders.
* Events.
* Reservations.
* Delivery promises.

ECIP should support impact analysis.

---

# 61. CONTAINMENT ACTION

Before full repair, an immediate containment action may reduce risk.

Examples:

* Disable Asset.
* Move stock.
* Route production elsewhere.
* Stop offering affected Product.
* Call external technician.

Containment is distinct from permanent repair.

---

# 62. TEMPORARY REPAIR

A temporary repair may restore limited operation.

It shall preserve:

* Temporary nature.
* Validity period.
* Restrictions.
* Required permanent follow-up.

---

# 63. PERMANENT REPAIR

A permanent repair should restore the Asset according to acceptance criteria.

---

# 64. REPAIR VERIFICATION

A Work Order shall not necessarily be considered complete merely because repair work ended.

Verification may include:

* Functional test.
* Safety test.
* Temperature test.
* Production test.
* Quality validation.

---

# 65. RETURN TO SERVICE

An `AssetReturnToService` represents authorization to resume normal use.

Typical prerequisites:

```text
Repair Completed
+
Required Test Passed
+
Safety Conditions Satisfied
+
Quality Conditions Satisfied
=
Return to Service
```

---

# 66. RETURN-TO-SERVICE AUTHORIZATION

Critical Assets may require explicit Manager, Maintenance or Safety approval before normal operation resumes.

---

# 67. MAINTENANCE INSPECTION

An `MaintenanceInspection` evaluates Asset condition.

Possible inspection types:

* Routine.
* Preventive.
* Safety.
* Regulatory.
* Post-repair.
* Pre-opening.

---

# 68. INSPECTION RESULT

Suggested values:

```text
PASS

PASS_WITH_OBSERVATION

MAINTENANCE_REQUIRED

RESTRICTED_USE

FAIL

OUT_OF_SERVICE
```

---

# 69. INSPECTION FINDING

A `MaintenanceFinding` represents an issue identified during Inspection.

It may create:

* Maintenance Requirement.
* Work Order.
* Incident.
* Monitoring recommendation.

---

# 70. CALIBRATION

Some Equipment may require periodic Calibration.

Examples:

* Scales.
* Thermometers.
* Temperature sensors.
* Measuring instruments.

---

# 71. CALIBRATION RECORD

Typical attributes:

* Asset.
* Calibration date.
* Standard used.
* Result.
* Adjustment.
* Next due date.
* Technician.
* Certificate reference.

---

# 72. CALIBRATION STATUS

Suggested values:

```text
VALID

DUE_SOON

OVERDUE

FAILED

OUT_OF_SERVICE
```

---

# 73. OVERDUE MAINTENANCE

Preventive Maintenance becomes overdue when the scheduled trigger passes without required completion.

Overdue status may increase failure risk.

---

# 74. MAINTENANCE BACKLOG

A `MaintenanceBacklog` represents unresolved Work Orders or Requirements.

Backlog may be analyzed by:

* Priority.
* Asset.
* Branch.
* Age.
* Criticality.
* Cost.

---

# 75. MAINTENANCE SLA

Possible service targets include:

* Response time.
* Diagnosis time.
* Repair time.
* Critical failure response.

SLA may differ by Asset criticality and provider contract.

---

# 76. MEAN TIME TO REPAIR

Potential metric:

```text
MTTR
=
Average time from repair start or failure recognition
to restored service
```

The exact methodology shall be consistent.

---

# 77. MEAN TIME BETWEEN FAILURES

`MTBF` may estimate average operating time between relevant failures.

This is an analytical measure.

---

# 78. AVAILABILITY

Asset availability may be calculated from:

* Uptime.
* Downtime.
* Planned downtime.
* Unplanned downtime.

The exact formula shall be explicit.

---

# 79. REPEAT FAILURE

A `RepeatFailure` may be detected when the same or similar Failure Mode recurs within a defined period.

Repeated failures may indicate:

* Incomplete repair.
* Aging Asset.
* Wrong diagnosis.
* Environmental cause.
* Inadequate Maintenance plan.

---

# 80. FAILURE ROOT CAUSE

Potential categories include:

```text
NORMAL_WEAR

IMPROPER_USE

INSUFFICIENT_MAINTENANCE

PART_FAILURE

POWER_ISSUE

ENVIRONMENTAL

INSTALLATION

DESIGN

UNKNOWN
```

Root cause shall require evidence.

---

# 81. ROOT-CAUSE CAUTION

An Asset Failure shall not automatically be blamed on Employee misuse merely because an Employee was using it when it failed.

Maintenance analysis shall consider complete evidence.

---

# 82. CORRECTIVE ACTION

A Maintenance corrective action may include:

* Repair.
* Replace part.
* Change operating procedure.
* Increase inspection frequency.
* Modify Preventive Maintenance Plan.

---

# 83. REPLACEMENT RECOMMENDATION

Maintenance Intelligence may recommend Asset replacement based on:

* Failure frequency.
* Repair cost.
* Downtime.
* Age.
* Efficiency.
* Safety.
* Spare Part availability.

Recommendation does not itself authorize capital expenditure.

---

# 84. REPAIR VS REPLACE

A decision may consider:

```text
Repair Cost

Expected Remaining Life

Downtime

Replacement Cost

Operational Risk

Energy Efficiency

Failure Frequency
```

This is a management decision supported by evidence.

---

# 85. ASSET LIFECYCLE COST

An analytical `AssetLifecycleCost` may include:

* Purchase cost.
* Installation.
* Maintenance.
* Repairs.
* Downtime.
* Energy.
* Replacement parts.

---

# 86. MAINTENANCE COST

Work Order cost may include:

```text
Labor

Parts

External Service

Transportation

Other Direct Costs
```

Detailed accounting remains under financial systems.

---

# 87. COST OF DOWNTIME

Potential downtime cost may include:

* Lost Product sales.
* Waste.
* Customer compensation.
* Additional labor.
* External service cost.

This is analytical and shall preserve methodology.

---

# 88. MAINTENANCE AND INVENTORY

Maintenance may consume Spare Parts and supplies.

Inventory remains authoritative for stock movements.

---

# 89. MAINTENANCE AND PURCHASING

Unavailable Spare Parts or external service may create a Purchase Requirement.

---

# 90. MAINTENANCE AND KITCHEN

Kitchen uses Equipment.

Maintenance owns Equipment service lifecycle.

Kitchen shall consume current Equipment availability.

---

# 91. MAINTENANCE AND PRODUCTION

Equipment failure may block Production Tasks.

Production shall preserve the failure dependency.

---

# 92. MAINTENANCE AND QUALITY

Quality deviations may provide evidence of equipment degradation.

Example:

```text
Repeated undercooking
+
Oven temperature instability
=
Potential Maintenance signal
```

The signal is not proof until evaluated.

---

# 93. MAINTENANCE AND COMPLIANCE

Compliance may require periodic:

* Inspection.
* Calibration.
* Certification.
* Service records.

Maintenance preserves execution evidence.

---

# 94. MAINTENANCE AND OPERATIONAL INCIDENTS

Critical Equipment failures may create Operational Incidents.

Maintenance resolves the Asset-related recovery work.

---

# 95. MAINTENANCE AND PRODUCT AVAILABILITY

An unavailable Asset may make Products:

```text
AVAILABLE

AVAILABLE_WITH_DELAY

AVAILABLE_WITH_ALTERNATE_PROCESS

TEMPORARILY_UNAVAILABLE
```

according to Recipe and operational context.

---

# 96. MAINTENANCE AND RESERVATIONS / EVENTS

Future Event feasibility may depend on critical Equipment availability.

Example:

* Banquet requires specialized oven.
* Event requires projector.
* Private room HVAC unavailable.

---

# 97. MAINTENANCE WINDOW

A `MaintenanceWindow` represents a planned time for work.

Scheduling should consider:

* Business hours.
* Reservations.
* Production.
* Events.
* Customer impact.
* Technician availability.

---

# 98. LOW-IMPACT SCHEDULING

Where possible, Preventive Maintenance may be scheduled during low-demand periods.

The objective is minimizing operational disruption without deferring required safety work.

---

# 99. MAINTENANCE SCHEDULE CONFLICT

Possible conflict:

```text
Preventive Maintenance:
Friday 19:00

Reservation load:
Peak

Result:
Schedule conflict
```

The system may recommend an alternate window.

---

# 100. MAINTENANCE NOTIFICATION

Notifications may include:

* Preventive Maintenance due.
* Work Order assigned.
* Technician arriving.
* Repair completed.
* Maintenance overdue.
* Asset returned to service.

---

# 101. MAINTENANCE ALERT

Possible alerts:

* Critical failure.
* Preventive Maintenance overdue.
* Calibration expired.
* Repeated failure.
* Repair exceeding expected time.
* Critical spare part unavailable.
* Asset health degraded.

---

# 102. SENSOR DATA

Future deployments may ingest data such as:

* Temperature.
* Vibration.
* Power consumption.
* Runtime.
* Pressure.

Sensor data is evidence.

It shall not automatically become Maintenance truth without validation.

---

# 103. SENSOR ALERT

A Sensor Alert may create a Maintenance Requirement if thresholds or predictive rules indicate risk.

---

# 104. SENSOR FAILURE

The system shall distinguish:

```text
ASSET FAILURE

from

SENSOR FAILURE
```

A bad sensor shall not automatically cause a healthy Asset to be classified as failed.

---

# 105. MAINTENANCE INTELLIGENCE

Potential insights include:

* Failure frequency.
* Critical Asset risk.
* Maintenance backlog.
* Recurring repair.
* Downtime.
* Maintenance cost.
* Repair effectiveness.
* Provider performance.
* Spare Part shortages.

---

# 106. PREDICTIVE MAINTENANCE INTELLIGENCE

Future analytics may identify patterns such as:

```text
Rising temperature variance
+
Longer compressor cycles
+
Previous similar failure history
=
Elevated refrigeration failure risk
```

This remains a prediction until confirmed.

---

# 107. MAINTENANCE EXECUTIVE INTELLIGENCE

Potential KPIs include:

* Asset availability.
* Total downtime.
* Preventive Maintenance compliance.
* Corrective Maintenance rate.
* Emergency Work Orders.
* Maintenance cost.
* Cost by Asset.
* MTTR.
* MTBF.
* Repeat failure rate.
* Maintenance backlog.

---

# 108. PREVENTIVE MAINTENANCE COMPLIANCE

Potential metric:

```text
Preventive Tasks Completed On Time
/
Preventive Tasks Due
```

---

# 109. MAINTENANCE PROVIDER PERFORMANCE

Potential measures:

* Response time.
* Repair time.
* First-time-fix rate.
* Cost.
* Repeat failure.
* SLA compliance.

---

# 110. FIRST-TIME FIX RATE

Measures whether a repair resolved the failure without repeat service in the defined period.

---

# 111. REPAIR EFFECTIVENESS

Repair effectiveness may consider:

* Asset restored.
* Repeat failure.
* Quality improvement.
* Downtime reduction.

---

# 112. MAINTENANCE ANOMALY

Potential anomaly signals include:

* Repeated emergency Work Orders.
* Unusually high repair cost.
* Same Part replaced repeatedly.
* Preventive Maintenance recorded unusually quickly.
* Equipment repeatedly fails immediately after service.

These are investigation signals.

---

# 113. ASSET REPLACEMENT RISK

An Asset may become economically or operationally unsuitable due to:

* Age.
* Cost.
* Failures.
* Downtime.
* Safety concerns.
* Obsolescence.

This may create a replacement Opportunity or recommendation.

---

# 114. MAINTENANCE SOURCE OF TRUTH

Authority may vary by state.

Example:

```text
Maintenance System:
Work Order and service history

Kitchen:
Operational equipment usage

IoT System:
Sensor evidence

Quality:
Quality deviations

ECIP:
Maintenance intelligence and orchestration
```

Ownership shall remain explicit.

---

# 115. EXTERNAL MAINTENANCE MAPPING

External systems may use:

* Equipment ID.
* Service ticket ID.
* Work Order ID.
* Provider job number.
* Warranty claim number.

These shall map to canonical Maintenance entities.

---

# 116. MAINTENANCE IMPORT

Existing Maintenance history may be imported.

Import should preserve:

* Asset mapping.
* Work Order.
* Failure.
* Date.
* Provider.
* Parts.
* Cost.
* Outcome.
* Data quality.

---

# 117. MAINTENANCE SYNCHRONIZATION

Synchronization may include:

* Asset state.
* Work Orders.
* Failures.
* Inspections.
* Maintenance completion.
* External provider state.

It shall be:

* Idempotent.
* Observable.
* Traceable.

---

# 118. MAINTENANCE CONFLICT

Example:

```text
Maintenance System:
Asset repaired

Kitchen:
Asset still reported unavailable
```

or:

```text
Sensor:
Critical temperature issue

Maintenance:
Asset marked healthy
```

Conflicts shall remain explicit until resolved.

---

# 119. MAINTENANCE AUDIT

Material Maintenance actions shall preserve:

* Actor.
* Asset.
* Branch.
* Location.
* Work Order.
* Failure.
* Maintenance type.
* Start/end time.
* Parts.
* Costs.
* Provider.
* Verification.
* Previous state.
* New state.

---

# 120. CONVERSATIONAL MAINTENANCE INTELLIGENCE

Authorized Employees may ask:

```text
"Which equipment is currently out of service?"

"When is the fryer's next maintenance?"

"Why is the pizza oven unavailable?"

"Which maintenance jobs are overdue?"

"What equipment is causing the most downtime?"

"Has refrigerator 2 already been repaired?"
```

Responses shall use authoritative Maintenance evidence.

---

# 121. CUSTOMER-FACING MAINTENANCE CONTEXT

Customers should normally receive only operationally relevant consequences.

Example:

```text
"That product is temporarily unavailable because the equipment required to prepare it is out of service."
```

Internal technical details should not be exposed unnecessarily.

---

# 122. AI MAINTENANCE ASSISTANCE

AI may assist with:

* Classifying Maintenance Requests.
* Summarizing failure history.
* Suggesting likely causes.
* Prioritizing investigation.
* Recommending preventive work.
* Detecting repeat failures.
* Explaining operational impact.

---

# 123. AI AUTHORITY LIMIT

AI shall not:

* Declare an Asset repaired without evidence.
* Return unsafe Equipment to service.
* Bypass inspection requirements.
* Invent sensor readings.
* Falsify Maintenance records.
* Authorize critical repairs outside policy.
* Ignore safety-related failures.
* Create unsupported root-cause conclusions.

---

# 124. AUTOMATED MAINTENANCE ACTIONS

Future controlled automation may support low-risk Actions such as:

* Create preventive Maintenance reminder.
* Create Work Order candidate.
* Alert on overdue inspection.
* Notify responsible employee.

Higher-risk actions such as:

* Shut down major Equipment.
* Return Asset to service.
* Authorize costly repair.
* Replace Asset.

shall use explicit authorization.

---

# 125. MAINTENANCE EVENTS

Initial domain events include:

```text
MaintainableAssetCreated
MaintainableAssetUpdated
MaintainableAssetActivated
MaintainableAssetSuspended
MaintainableAssetRetired

AssetOperationalStatusChanged
AssetHealthChanged

PreventiveMaintenancePlanCreated
PreventiveMaintenancePlanUpdated
PreventiveMaintenanceDue
PreventiveMaintenanceOverdue
PreventiveMaintenanceCompleted

MaintenanceRequirementDetected
MaintenanceRequirementReviewed

MaintenanceRequestCreated
MaintenanceRequestTriaged
MaintenanceRequestApproved
MaintenanceRequestRejected

AssetFailureDetected
AssetFailureConfirmed
AssetFailureContained
AssetFailureResolved

AssetDegradationDetected

MaintenanceWorkOrderCreated
MaintenanceWorkOrderApproved
MaintenanceWorkOrderScheduled
MaintenanceWorkOrderAssigned
MaintenanceWorkOrderStarted
MaintenanceWorkOrderPaused
MaintenanceWorkOrderBlocked
MaintenanceWorkOrderCompleted
MaintenanceWorkOrderVerified
MaintenanceWorkOrderClosed
MaintenanceWorkOrderCancelled

SparePartRequired
SparePartUnavailable
SparePartConsumed

MaintenanceInspectionRequested
MaintenanceInspectionCompleted
MaintenanceInspectionFailed

CalibrationDue
CalibrationCompleted
CalibrationFailed
CalibrationOverdue

AssetDowntimeStarted
AssetDowntimeEnded

TemporaryRepairCompleted
PermanentRepairCompleted

AssetReturnToServiceRequested
AssetReturnedToService

RepeatFailureDetected
MaintenanceAnomalyDetected

WarrantyClaimCreated
WarrantyClaimResolved

MaintenanceConflictDetected
MaintenanceConflictResolved

MaintenanceSynchronizationStarted
MaintenanceSynchronizationCompleted
MaintenanceSynchronizationFailed
```

---

# 126. RELATIONSHIPS

```text
Branch
    HAS MaintainableAsset

MaintainableAsset
    LOCATED_AT RestaurantLocation

MaintainableAsset
    MAY_SUPPORT KitchenStation

MaintainableAsset
    MAY_SUPPORT StorageLocation

MaintainableAsset
    HAS PreventiveMaintenancePlan

MaintainableAsset
    MAY_HAVE MaintenanceRequest

MaintenanceRequest
    MAY_CREATE MaintenanceWorkOrder

AssetFailure
    MAY_CREATE MaintenanceRequest

AssetFailure
    MAY_CREATE OperationalIncident

MaintenanceWorkOrder
    EXECUTED_BY Employee

MaintenanceWorkOrder
    MAY_USE MaintenanceServiceProvider

MaintenanceWorkOrder
    MAY_REQUIRE SparePart

SparePart
    MAY_MAP_TO InventoryItem

MaintenanceWorkOrder
    MAY_CREATE PurchaseRequirement

MaintenanceWorkOrder
    PRODUCES MaintenanceEvidence

MaintenanceInspection
    EVALUATES MaintainableAsset

CalibrationRecord
    APPLIES_TO MaintainableAsset

AssetState
    CONTRIBUTES_TO KitchenContext

AssetState
    CONTRIBUTES_TO ProductOfferability

MaintenanceHistory
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 127. BUSINESS RULES

The following rules apply:

1. Maintainable Asset identity shall remain distinct from Work Order identity.

2. Asset lifecycle status shall remain distinct from current operational status.

3. Preventive Maintenance shall use explicit schedules or triggers.

4. Corrective Maintenance shall preserve the failure or defect that created the need.

5. Asset Failure and Asset Degradation shall remain distinct where appropriate.

6. Critical safety failures shall override Production and commercial objectives.

7. An Asset under Maintenance or Safety isolation shall not be represented as normally available.

8. Temporary repair shall remain distinguishable from permanent repair.

9. Return to Service shall require evidence appropriate to Asset risk.

10. Maintenance Work Orders shall preserve responsible actor, provider and execution history.

11. Spare Part usage shall remain traceable.

12. Maintenance-generated Purchasing needs shall follow procurement governance.

13. Quality issues may create Maintenance signals, but correlation alone shall not prove Equipment failure.

14. Repeat failures shall remain historically visible after repair.

15. AI shall not invent failure resolution, inspection success or Asset health.

16. Maintenance conflicts shall remain explicit until reconciled.

17. External identifiers shall remain integration mappings.

18. Maintenance costs shall preserve their source without redefining financial accounting.

19. Preventive Maintenance overdue status shall not be silently cleared without completion or authorized rescheduling.

20. Every material Maintenance decision and state transition shall be reconstructable and auditable.

---

# 128. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
MaintainableAsset

AssetType

AssetOperationalStatus

AssetCriticality

AssetHealthAssessment

PreventiveMaintenancePlan

PreventiveMaintenanceSchedule

MaintenanceRequirement

MaintenanceRequest

MaintenanceRequestStatus

AssetFailure

FailureMode

MaintenanceWorkOrder

MaintenanceWorkOrderStatus

MaintenancePriority

MaintenanceProcedureReference

MaintenanceTechnicianReference

ExternalServiceProviderReference

SparePartRequirement

AssetDowntime

MaintenanceInspection

CalibrationRecord

RepairVerification

AssetReturnToService

MaintenanceCostReference

OperationalImpact

ExternalMaintenanceMapping

MaintenanceHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced IoT Equipment Monitoring

Predictive Failure Models

Autonomous Maintenance Scheduling

Automatic Spare-Part Procurement

Advanced Repair-vs-Replace Optimization

Digital Twin Equipment Simulation

Computer Vision Equipment Inspection

Autonomous Root-Cause Diagnosis

Advanced Energy Efficiency Optimization

Multi-Site Maintenance Route Optimization
```

---

# 129. IMPLEMENTATION PRINCIPLE

This document defines the logical Maintenance Model.

It does not prescribe:

* CMMS vendor.
* Database schema.
* IoT hardware.
* Maintenance mobile application.
* Technician scheduling algorithm.
* Purchasing implementation.
* Accounting implementation.
* Predictive model.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
ASSET

ASSET STATE

MAINTENANCE PLAN

MAINTENANCE REQUIREMENT

MAINTENANCE REQUEST

FAILURE

WORK ORDER

INSPECTION

CALIBRATION

REPAIR

DOWNTIME

RETURN TO SERVICE

MAINTENANCE HISTORY
```

---

# 130. FINAL RULE

Before ECIP concludes that a restaurant Asset is healthy, degraded, unavailable, repaired or safe to return to service, it shall be able to determine:

> What Asset is involved?

> Where is it located?

> What restaurant processes, Products or Resources depend on it?

> What is its current authoritative operational state?

> Is the condition a planned Maintenance event, degradation or confirmed Failure?

> What Maintenance Requirement or Request exists?

> Is there an active Work Order?

> Who is responsible for the work?

> Are required skills, Spare Parts and external providers available?

> How long has the Asset been unavailable?

> What operational, Quality, Inventory or Customer commitments are affected?

> Was the repair temporary or permanent?

> What inspection, test or verification was performed after repair?

> Has the Asset been explicitly authorized to return to service?

> Is Preventive Maintenance current or overdue?

> Are there repeated failures indicating a systemic issue?

> Can the complete Maintenance lifecycle, including failure, repair, cost, downtime and verification, be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably use Maintenance information to determine operational availability, Product offerability, Production feasibility, service commitments or executive decisions.

