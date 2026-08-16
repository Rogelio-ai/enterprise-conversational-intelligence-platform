# 30_Operational_Incidents.md

**Document ID:** RDM-030
**Document Name:** Operational Incidents
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Operational Incidents Model for the Restaurant Intelligence Platform.

Its purpose is to represent, coordinate and resolve unplanned operational conditions that materially affect restaurant service, production, safety, quality, customer commitments, financial integrity or business continuity.

The Operational Incidents Model connects:

* Kitchen.
* Production.
* Quality Control.
* Inventory.
* Purchasing.
* Ingredient Lifecycle.
* Payments.
* Billing.
* Cash Management.
* Maintenance.
* Reservations.
* Dine-In.
* Take Away.
* Delivery.
* Banquets and Events.
* Employees.
* Customers.
* Service Recovery.
* Human Escalation.
* Notifications.
* Audit.
* Operational Intelligence.
* Executive Intelligence.

An Operational Incident is not merely an error message or support ticket.

It represents a governed business condition requiring coordinated awareness, containment, response, recovery and learning.

---

# 2. OBJECTIVES

The Operational Incidents Model enables ECIP to:

* Detect incidents.
* Register incidents.
* Classify incidents.
* Determine severity.
* Determine business impact.
* Determine affected entities.
* Determine blast radius.
* Coordinate containment.
* Assign ownership.
* Escalate incidents.
* Track response.
* Track mitigation.
* Track recovery.
* Track affected Customer commitments.
* Track financial impact.
* Track operational impact.
* Track safety impact.
* Track root cause.
* Track corrective actions.
* Track preventive actions.
* Preserve incident evidence.
* Support post-incident review.
* Detect recurring incidents.
* Support Operational Intelligence.
* Support Executive Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Incident
* Risk
* Severity
* Impact
* Action
* Action Authorization
* Workflow Instance
* Task
* Employee
* Resource
* Customer
* Commitment
* Context Snapshot
* Evidence Record
* Runtime Event
* Notification
* Recommendation
* Decision
* Audit Event

Restaurant-specific Operational Incident entities remain within the Restaurant Domain Pack.

---

# 4. OPERATIONAL INCIDENT PRINCIPLE

The platform shall distinguish between:

```text
SIGNAL

ANOMALY

OPERATIONAL ISSUE

OPERATIONAL INCIDENT

CRITICAL INCIDENT

SAFETY INCIDENT

CUSTOMER IMPACT

CONTAINMENT

MITIGATION

RECOVERY

ROOT CAUSE

CORRECTIVE ACTION

PREVENTIVE ACTION
```

These concepts shall remain independently traceable.

---

# 5. OPERATIONAL INCIDENT

An `OperationalIncident` represents an unplanned business condition requiring coordinated management.

Typical attributes include:

* Incident ID
* Incident type
* Title
* Description
* Branch
* Detection source
* Detected time
* Start time
* Severity
* Priority
* Current status
* Incident owner
* Impact
* Blast radius
* Affected resources
* Affected services
* Affected Orders
* Affected Customers
* Affected Events
* Affected Employees
* Financial impact
* Safety impact
* Operational impact
* Customer impact
* Current containment
* Root cause status
* Resolution time
* Closure time
* External references

---

# 6. INCIDENT TYPES

Initial Incident types may include:

```text
KITCHEN

PRODUCTION

QUALITY

FOOD_SAFETY

INVENTORY

INGREDIENT

PURCHASING

SUPPLIER

MAINTENANCE

EQUIPMENT

POWER

WATER

GAS

FACILITY

POS

PAYMENT

BILLING

CASH

RESERVATION

DELIVERY

CUSTOMER_SERVICE

STAFFING

SECURITY

COMPLIANCE

INTEGRATION

SYSTEM

OTHER
```

The catalog shall remain configurable.

---

# 7. INCIDENT STATUS

Suggested lifecycle:

```text
DETECTED
→ ACKNOWLEDGED
→ TRIAGED
→ CONTAINING
→ MITIGATING
→ RECOVERING
→ RESOLVED
→ CLOSED
```

Alternative states:

```text
MONITORING

ON_HOLD

ESCALATED

REOPENED

CANCELLED
```

---

# 8. INCIDENT SEVERITY

Suggested severity levels:

```text
SEV-4 — LOW

SEV-3 — MODERATE

SEV-2 — HIGH

SEV-1 — CRITICAL
```

Severity shall be based on impact, not emotional urgency alone.

---

# 9. SEV-4 — LOW

Characteristics may include:

* Localized issue.
* No material Customer impact.
* No safety impact.
* Easy workaround.
* Limited financial effect.

Example:

* One non-critical printer unavailable.

---

# 10. SEV-3 — MODERATE

Characteristics may include:

* One operational area affected.
* Some Customer impact possible.
* Workaround available.
* Limited duration expected.

Example:

* One kitchen station degraded.

---

# 11. SEV-2 — HIGH

Characteristics may include:

* Multiple Customer commitments at risk.
* Significant operational degradation.
* Important Product or service unavailable.
* Significant financial or quality impact.

Example:

* Main delivery provider unavailable during peak demand.

---

# 12. SEV-1 — CRITICAL

Characteristics may include:

* Safety risk.
* Restaurant-wide service disruption.
* Major financial integrity risk.
* Large number of Customers affected.
* Complete operational shutdown.
* Regulatory concern.

Examples:

* Gas leak.
* Major power outage.
* Payment system charging Customers twice.
* Food Safety recall affecting active Product.

---

# 13. PRIORITY VS SEVERITY

Severity represents business impact.

Priority represents response urgency.

They may differ.

Example:

```text
Severity:
MODERATE

Priority:
URGENT
```

if the issue can quickly become critical.

---

# 14. INCIDENT DETECTION

Incidents may be detected through:

```text
EMPLOYEE_REPORT

CUSTOMER_REPORT

SYSTEM_EVENT

MONITORING

QUALITY_CONTROL

MAINTENANCE

KITCHEN

INVENTORY

PAYMENT_PROVIDER

EXTERNAL_PROVIDER

SENSOR

AI_DETECTION

AUDIT
```

Detection source shall always remain explicit.

---

# 15. INCIDENT SIGNAL

An `IncidentSignal` represents evidence suggesting a potential Incident.

Examples:

* Sudden payment failure spike.
* Refrigeration temperature abnormality.
* Large kitchen delay.
* Repeated Product complaint.
* Inventory mismatch.

A Signal does not automatically equal a confirmed Incident.

---

# 16. INCIDENT CORRELATION

Multiple Signals may belong to the same Incident.

Example:

```text
Sensor:
Freezer temperature rising

Kitchen:
Frozen Product unavailable

Quality:
Affected Ingredient Lots placed on Hold
```

These may represent one underlying refrigeration Incident.

---

# 17. INCIDENT DEDUPLICATION

ECIP should detect likely duplicate Incident reports based on:

* Time.
* Branch.
* Asset.
* Symptom.
* Source.
* Affected service.

Duplicate detection shall not discard independent evidence.

---

# 18. INCIDENT TRIAGE

Triage determines:

* What happened?
* Is it real?
* What is affected?
* How severe is it?
* Is there a safety risk?
* Who owns the response?
* What immediate containment is required?

---

# 19. INCIDENT IMPACT

An `IncidentImpact` may include:

* Operational impact.
* Customer impact.
* Product impact.
* Financial impact.
* Safety impact.
* Employee impact.
* Compliance impact.
* Reputation impact.

---

# 20. BLAST RADIUS

The Incident shall classify scope consistent with the Enterprise Audit Framework.

Suggested scope:

```text
LOCAL

MODULE

CROSS_MODULE

PLATFORM
```

For restaurant operations this may conceptually represent:

```text
LOCAL:
One Asset / Table / Order

MODULE:
One operational domain

CROSS_MODULE:
Several interconnected domains

PLATFORM:
Restaurant-wide or multi-Branch
```

---

# 21. LOCAL INCIDENT

Example:

```text
Table 18:
Payment terminal temporarily unavailable
```

No broader service impact.

---

# 22. MODULE INCIDENT

Example:

```text
Delivery:
All internal drivers unavailable
```

Delivery operations affected while Dine-In remains normal.

---

# 23. CROSS-MODULE INCIDENT

Example:

```text
Walk-in refrigerator failure
    ↓
Ingredient availability
    ↓
Kitchen production
    ↓
Menu availability
    ↓
Customer Orders
```

---

# 24. PLATFORM INCIDENT

Example:

```text
POS outage across all Branches
```

Potentially affecting:

* Orders.
* Payments.
* Kitchen.
* Cash.
* Billing.
* Customer service.

---

# 25. AFFECTED ENTITY

An Incident may affect any number of entities, including:

* Branch.
* Location.
* Equipment.
* Kitchen Station.
* Inventory Item.
* Ingredient Lot.
* Product.
* Menu.
* Order.
* Reservation.
* Event.
* Payment.
* Customer.
* Employee.
* External provider.

---

# 26. AFFECTED SERVICE

Examples:

* Dine-In.
* Take Away.
* Delivery.
* Reservations.
* Events.
* Payments.
* Billing.

The system should determine customer-facing consequences.

---

# 27. CUSTOMER IMPACT

An `IncidentCustomerImpact` may classify:

```text
NONE

POTENTIAL

CONFIRMED

SIGNIFICANT

CRITICAL
```

---

# 28. CUSTOMER COMMITMENT IMPACT

Incidents may threaten:

* Reservation commitments.
* Pickup promises.
* Delivery windows.
* Event commitments.
* Product availability.
* Refund commitments.

Affected Commitments shall be identifiable.

---

# 29. CUSTOMER IMPACT ANALYSIS

Example:

```text
Pizza Oven Failure
    ↓
12 active pizza Orders
    ↓
4 Dine-In Tables
3 Take Away Orders
5 Delivery Orders
```

The platform should identify all affected Customers where data permits.

---

# 30. INCIDENT OWNER

Every active Incident should have one accountable Incident Owner.

The owner may be:

* Manager.
* Kitchen Manager.
* Maintenance Manager.
* IT.
* Finance.
* Corporate Operations.

Ownership shall be explicit.

---

# 31. INCIDENT COMMAND

Higher-severity Incidents may require coordinated command.

Possible roles:

* Incident Owner.
* Operational Lead.
* Technical Lead.
* Customer Communication Owner.
* Executive Stakeholder.

This is an operational coordination mechanism, not additional governance infrastructure.

---

# 32. INCIDENT ASSIGNMENT

An Incident may generate Tasks assigned to:

* Employees.
* Departments.
* External providers.

Each Task should remain traceable to the Incident.

---

# 33. ACKNOWLEDGMENT

Incident acknowledgment records that a responsible actor is aware of and accepting response responsibility.

---

# 34. CONTAINMENT

Containment reduces immediate impact or prevents spread.

Examples:

* Disable faulty Equipment.
* Stop selling affected Product.
* Place Ingredient Lot on Hold.
* Stop Payment provider traffic.
* Close Dining Area.
* Stop Delivery acceptance.

Containment is not necessarily final resolution.

---

# 35. CONTAINMENT ACTION

A `ContainmentAction` shall preserve:

* Incident.
* Action.
* Actor.
* Time.
* Scope.
* Result.
* Authorization.
* Evidence.

---

# 36. SAFETY-FIRST CONTAINMENT

If safety is involved, immediate containment may take precedence over normal commercial processes.

Example:

```text
Suspected gas leak
    ↓
Stop affected operation
    ↓
Evacuate if policy requires
    ↓
Call authorized emergency procedure
```

Safety procedures shall remain policy-driven.

---

# 37. MITIGATION

Mitigation reduces operational impact while root cause or permanent repair remains unresolved.

Examples:

* Route Orders to another Kitchen.
* Use alternate Delivery provider.
* Offer alternate Products.
* Use backup Payment provider.
* Move Inventory to another refrigerator.

---

# 38. WORKAROUND

A `Workaround` is a temporary alternate operational path.

Typical attributes:

* Description.
* Scope.
* Start time.
* Risks.
* Restrictions.
* Expiration.
* Owner.

A Workaround shall not silently become permanent architecture.

---

# 39. RECOVERY

Recovery restores normal or acceptable business operation.

Examples:

* Equipment repaired.
* Provider restored.
* Stock replenished.
* Payment service normalized.

---

# 40. SERVICE RESTORATION

An Incident may be considered service-restored before full Root Cause Analysis is complete.

This distinction shall remain explicit.

---

# 41. RESOLUTION

`RESOLVED` means the immediate Incident condition no longer materially affects operation.

Resolution does not necessarily mean all follow-up actions are finished.

---

# 42. CLOSURE

`CLOSED` means:

* Service restored.
* Required evidence captured.
* Root cause disposition recorded where required.
* Corrective actions assigned.
* Customer obligations addressed.
* Required review completed.

---

# 43. REOPENING

An Incident may be reopened if:

* Symptoms return.
* Resolution was incomplete.
* Additional affected scope is discovered.

Reopening shall preserve the original history.

---

# 44. INCIDENT TIMELINE

The system should reconstruct:

```text
Detected
Acknowledged
Triaged
Contained
Mitigated
Service Restored
Resolved
Closed
```

with exact timestamps.

---

# 45. TIME TO ACKNOWLEDGE

Potential metric:

```text
Acknowledged Time
-
Detected Time
```

---

# 46. TIME TO CONTAIN

Potential metric:

```text
Contained Time
-
Detected Time
```

---

# 47. TIME TO RESTORE

Potential metric:

```text
Service Restored Time
-
Incident Start Time
```

---

# 48. TIME TO RESOLVE

Potential metric:

```text
Resolved Time
-
Incident Start Time
```

---

# 49. ROOT CAUSE

A `RootCause` represents the evidence-supported underlying cause of an Incident.

Possible categories:

```text
PROCESS

PEOPLE

EQUIPMENT

SOFTWARE

NETWORK

POWER

SUPPLIER

INVENTORY

QUALITY

CONFIGURATION

CAPACITY

EXTERNAL_PROVIDER

ENVIRONMENTAL

UNKNOWN
```

---

# 50. ROOT CAUSE STATUS

Suggested states:

```text
NOT_REQUIRED

PENDING

INVESTIGATING

IDENTIFIED

UNCONFIRMED

CONFIRMED
```

---

# 51. ROOT CAUSE CAUTION

Correlation shall not automatically become Root Cause.

Example:

```text
Employee present when POS failed
```

does not imply Employee caused the failure.

Evidence shall be required.

---

# 52. CONTRIBUTING FACTOR

An Incident may have multiple contributing factors.

Example:

```text
Delivery delays

Primary cause:
Provider outage

Contributing factor:
Kitchen backlog
```

---

# 53. CORRECTIVE ACTION

A `CorrectiveAction` addresses a known cause or defect.

Examples:

* Repair Equipment.
* Fix software defect.
* Correct process.
* Replace Supplier.
* Update configuration.
* Add missing monitoring.

---

# 54. PREVENTIVE ACTION

A `PreventiveAction` aims to reduce recurrence probability.

Examples:

* Additional preventive Maintenance.
* Capacity increase.
* Better supplier backup.
* Additional training.
* Backup provider.

---

# 55. ACTION STATUS

Suggested lifecycle:

```text
PROPOSED
→ APPROVED
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
→ VERIFIED
```

---

# 56. TEMPORARY VS PERMANENT CORRECTION

The model shall distinguish:

```text
TEMPORARY_WORKAROUND

PERMANENT_CORRECTIVE_ACTION
```

A temporary workaround shall not automatically close systemic risk.

---

# 57. INCIDENT DEPENDENCY

One Incident may cause another.

Example:

```text
Power Failure
    ↓
Refrigeration Failure
    ↓
Ingredient Quality Incident
```

Parent-child relationships should be preserved.

---

# 58. CASCADING INCIDENT

A `CascadingIncident` may represent propagation across domains.

ECIP should avoid treating each downstream symptom as unrelated where shared evidence indicates a common cause.

---

# 59. MASTER INCIDENT

Multiple related Incidents may be linked under one Master Incident for coordinated response.

This shall not erase domain-specific evidence.

---

# 60. KITCHEN INCIDENT

Examples:

* Kitchen saturation.
* Station failure.
* Expo backlog.
* Kitchen closure.

Kitchen remains authoritative for current operational state.

---

# 61. PRODUCTION INCIDENT

Examples:

* Batch failure.
* Production system blocked.
* Major task backlog.
* Widespread remake.

---

# 62. QUALITY INCIDENT

Examples:

* Repeated Product failures.
* Batch Quality rejection.
* Packaging defect affecting many Orders.

---

# 63. FOOD SAFETY INCIDENT

Examples:

* Contamination concern.
* Allergen exposure.
* Unsafe temperature.
* Recall.

Food Safety incidents require heightened priority and Compliance handling.

---

# 64. INVENTORY INCIDENT

Examples:

* Critical stockout.
* Large inventory discrepancy.
* Warehouse failure.
* Inventory synchronization corruption.

---

# 65. PURCHASING INCIDENT

Examples:

* Critical Supplier failure.
* Delivery of unusable critical stock.
* Major procurement delay.

---

# 66. MAINTENANCE INCIDENT

Examples:

* Critical Asset failure.
* Repeated Equipment failure.
* Building infrastructure failure.

---

# 67. PAYMENT INCIDENT

Examples:

* Payment provider outage.
* Duplicate charges.
* Excessive decline spike.
* Settlement discrepancy.

Financial integrity incidents may require rapid escalation.

---

# 68. BILLING INCIDENT

Examples:

* Duplicate fiscal documents.
* Fiscal provider outage.
* Incorrect tax calculation across multiple transactions.

---

# 69. CASH INCIDENT

Examples:

* Large unexplained Cash shortage.
* Missing bank deposit.
* Cash Register outage.
* Cash custody gap.

---

# 70. RESERVATION INCIDENT

Examples:

* Confirmed reservations lost.
* Double-booking.
* Reservation provider unavailable.
* Large capacity error.

---

# 71. DELIVERY INCIDENT

Examples:

* Provider outage.
* Driver accident.
* Large dispatch backlog.
* Widespread Order delay.

---

# 72. STAFFING INCIDENT

Examples:

* Critical understaffing.
* Unexpected mass absence.
* No qualified Employee for critical Station.

Employee privacy shall be respected.

---

# 73. FACILITY INCIDENT

Examples:

* Water outage.
* Power failure.
* Gas issue.
* HVAC failure.
* Flooding.
* Structural problem.

---

# 74. SYSTEM INCIDENT

Examples:

* POS unavailable.
* Database unavailable.
* Network outage.
* ECIP connector failure.
* Integration corruption.

---

# 75. EXTERNAL PROVIDER INCIDENT

Examples:

* Payment provider.
* Delivery provider.
* Reservation system.
* Fiscal provider.
* Telecommunications provider.

Provider state shall be distinguished from internal system state.

---

# 76. INCIDENT AND CUSTOMER EXPERIENCE

Incidents may explain Customer Experience degradation.

Examples:

```text
Kitchen equipment failure
    ↓
Production delay
    ↓
Main course late
    ↓
Customer complaint
```

Experience and Incident evidence should be linked.

---

# 77. INCIDENT AND SALES INTELLIGENCE

During a material Incident, Sales Intelligence may need to adapt.

Example:

```text
Grill unavailable
```

Do not recommend Grill-dependent Products.

---

# 78. INCIDENT-AWARE OFFERABILITY

Product offerability shall consider active Incidents.

A Product may become:

```text
AVAILABLE

AVAILABLE_WITH_DELAY

AVAILABLE_WITH_SUBSTITUTION

TEMPORARILY_UNAVAILABLE
```

---

# 79. INCIDENT-AWARE RESERVATIONS

A Restaurant may need to:

* Restrict new Reservations.
* Reduce capacity.
* Move Customers.
* Close Dining Area.

Such changes shall follow operational authority.

---

# 80. INCIDENT-AWARE DELIVERY

A Delivery Incident may require:

* Extend ETA.
* Stop accepting new Delivery Orders.
* Switch provider.
* Notify Customers.

---

# 81. INCIDENT-AWARE EVENTS

Events may require:

* Resource substitution.
* Space change.
* Equipment replacement.
* Customer communication.

High-value commitments shall receive explicit impact assessment.

---

# 82. CUSTOMER COMMUNICATION

Customer communication should be:

* Accurate.
* Timely.
* Relevant.
* Non-speculative.

ECIP shall not invent Incident causes.

---

# 83. PROACTIVE CUSTOMER COMMUNICATION

Where appropriate, affected Customers may be notified before they complain.

Example:

```text
"We are experiencing a preparation delay. Your updated estimated pickup time is 7:25 PM."
```

Only affected Customers should be contacted where possible.

---

# 84. CUSTOMER COMMUNICATION PLAN

A `CustomerCommunicationPlan` may define:

* Affected Customers.
* Message type.
* Channel.
* Timing.
* Responsible actor.
* Approved content.

---

# 85. INCIDENT COMMUNICATION LEVEL

Possible communication scopes:

```text
INTERNAL_ONLY

AFFECTED_CUSTOMERS

ALL_CURRENT_CUSTOMERS

PUBLIC
```

Public communication shall require appropriate authority.

---

# 86. HUMAN ESCALATION

Human escalation may be mandatory for:

* SEV-1.
* Safety incident.
* Financial integrity incident.
* Major Customer impact.
* Legal or Compliance concern.

---

# 87. ESCALATION PATH

Example:

```text
Employee
    ↓
Shift Manager
    ↓
Branch Manager
    ↓
Regional / Corporate Operations
    ↓
Executive / Specialist
```

Actual paths remain tenant-configurable.

---

# 88. ESCALATION TRIGGER

Triggers may include:

* Severity.
* Duration.
* Customer count.
* Safety impact.
* Financial amount.
* Failure to contain.
* Regulatory requirement.

---

# 89. INCIDENT NOTIFICATION

Notifications may be sent to:

* Incident Owner.
* Managers.
* Responsible Employees.
* External Providers.
* Executives.

Notification frequency should avoid alert fatigue.

---

# 90. INCIDENT COMMAND BRIEFING

For significant Incidents, ECIP may generate a structured briefing including:

```text
What happened

When it started

Current severity

Affected Branches

Affected Customers

Affected Orders

Current containment

Current operational state

Known cause

Unknowns

Actions in progress

Next recommended actions
```

---

# 91. INCIDENT EVIDENCE

Possible evidence includes:

* System logs.
* POS events.
* Sensor readings.
* Employee reports.
* Customer reports.
* Payment-provider events.
* Maintenance records.
* Photos where policy permits.
* Quality measurements.
* Inventory movements.

---

# 92. EVIDENCE PRESERVATION

Incident evidence shall preserve:

* Source.
* Timestamp.
* Integrity.
* Actor.
* Correlation references.

Important evidence should not be overwritten by later summaries.

---

# 93. INCIDENT AUDIT TRAIL

Every material Incident state transition shall preserve:

* Previous state.
* New state.
* Actor or rule.
* Timestamp.
* Reason.
* Evidence.

---

# 94. INCIDENT NOTES

Free-text notes may supplement structured state.

Notes shall not silently replace structured severity, impact or action records.

---

# 95. INCIDENT DECISION LOG

Important Incident decisions may include:

* Close Dining Area.
* Stop Product sales.
* Switch Delivery provider.
* Refund Customers.
* Close Branch.

Decision evidence shall preserve:

* Decision.
* Decision maker.
* Context.
* Time.
* Reason.

---

# 96. INCIDENT SERVICE RECOVERY

Customer-facing failures may require Service Recovery.

Possible actions:

* Replacement.
* Refund.
* Credit.
* Manager contact.
* Follow-up.

Commercial actions require authorization.

---

# 97. MASS CUSTOMER RECOVERY

A large Incident may affect multiple Customers.

Recovery should support controlled bulk workflows without duplicate compensation.

---

# 98. INCIDENT FINANCIAL IMPACT

Potential components:

* Lost sales.
* Refunds.
* Waste.
* Repair.
* Compensation.
* Overtime.
* Provider fees.
* Inventory loss.

Financial impact may be estimated initially and finalized later.

---

# 99. ESTIMATED VS FINAL IMPACT

The platform shall distinguish:

```text
ESTIMATED_IMPACT

FINAL_CONFIRMED_IMPACT
```

AI-generated estimates shall remain clearly labeled.

---

# 100. INCIDENT BUSINESS CONTINUITY

Major Incidents may require continuity actions such as:

* Alternate Branch.
* Alternate Kitchen.
* Backup provider.
* Manual operation.
* Restricted Menu.
* Temporary service model.

---

# 101. DEGRADED MODE

A Restaurant may continue operating in a degraded mode.

Example:

```text
Card Payments unavailable

Available:
Cash + Bank Transfer
```

Degraded operation shall be explicit.

---

# 102. MANUAL FALLBACK

If systems fail, controlled manual operations may continue where policy permits.

Examples:

* Manual Order capture.
* Cash-only operation.
* Paper Reservation list.

Recovery shall later reconcile manual evidence back into authoritative systems.

---

# 103. INCIDENT RECOVERY RECONCILIATION

After service restoration, systems may require reconciliation of:

* Orders.
* Payments.
* Cash.
* Inventory.
* Reservations.
* Production.

Restoration does not imply reconciliation is complete.

---

# 104. POST-INCIDENT REVIEW

A `PostIncidentReview` may be required for significant Incidents.

Typical contents:

* Summary.
* Timeline.
* Impact.
* Root cause.
* What worked.
* What failed.
* Corrective actions.
* Preventive actions.
* Owners.
* Due dates.

---

# 105. POST-INCIDENT REVIEW REQUIREMENT

Suggested policy:

```text
SEV-1:
Mandatory

SEV-2:
Normally required

SEV-3:
When recurring or materially instructive

SEV-4:
Optional
```

Actual policy remains configurable.

---

# 106. LESSON LEARNED

A `LessonLearned` may represent a reusable organizational insight derived from an Incident.

It shall be supported by evidence and should not become policy automatically.

---

# 107. RECURRING INCIDENT

A `RecurringIncidentPattern` may be detected when similar Incidents repeat.

Examples:

* Friday Payment failures.
* Repeated fryer breakdown.
* Frequent stockouts of same Ingredient.
* Repeated Delivery provider delays.

---

# 108. INCIDENT CLUSTER

Clusters may be analyzed by:

* Branch.
* Asset.
* Product.
* Supplier.
* Provider.
* Time period.
* Domain.
* Root cause.

A cluster is analytical evidence, not automatically a confirmed common cause.

---

# 109. INCIDENT TREND

Potential trends include:

* Incident count.
* Severity distribution.
* Time to acknowledge.
* Time to contain.
* Time to resolve.
* Customer impact.
* Repeat Incident rate.

---

# 110. OPERATIONAL RESILIENCE

Incident history may support assessment of:

* Recovery speed.
* Fallback effectiveness.
* Provider dependency.
* Asset redundancy.
* Process robustness.

---

# 111. SINGLE POINT OF FAILURE

A `SinglePointOfFailure` may be identified when one Resource can disable a critical service.

Examples:

* Only pizza oven.
* Only Payment provider.
* Only refrigerated storage.
* One Internet connection.

This may create a resilience recommendation.

---

# 112. INCIDENT PREVENTION INTELLIGENCE

Potential recommendations:

* Add backup Equipment.
* Add alternate Supplier.
* Add second Payment provider.
* Increase safety stock.
* Improve preventive Maintenance.
* Improve staff coverage.

Recommendations shall remain distinct from approved investments.

---

# 113. INCIDENT KPIs

Potential metrics include:

* Total Incident count.
* Incidents by severity.
* Incidents by Branch.
* Customer-impacting Incidents.
* Safety Incidents.
* Repeat Incident rate.
* Mean Time to Acknowledge.
* Mean Time to Contain.
* Mean Time to Restore.
* Mean Time to Resolve.
* Financial impact.

---

# 114. MTTA

`Mean Time to Acknowledge`:

```text
Average(
Acknowledgment Time - Detection Time
)
```

---

# 115. MTTC

`Mean Time to Contain`:

```text
Average(
Containment Time - Detection Time
)
```

---

# 116. MTTR

For Incident Management, `Mean Time to Restore` or `Mean Time to Resolve` shall be explicitly named to avoid ambiguity.

---

# 117. CUSTOMER IMPACT RATE

Potential metric:

```text
Customer-Impacting Incidents
/
Total Incidents
```

---

# 118. INCIDENT COST

Potential Incident Cost may aggregate:

```text
Operational Loss
+
Waste
+
Refunds
+
Repair
+
Compensation
+
Additional Labor
```

Methodology shall remain explicit.

---

# 119. EXECUTIVE INCIDENT INTELLIGENCE

Potential executive questions include:

* What is repeatedly disrupting the business?
* Which Branch has the highest operational risk?
* Which Assets create the most downtime?
* Which providers cause the most incidents?
* Which incidents cost the most?
* Which incidents most affect Customers?
* Are response times improving?

---

# 120. CONVERSATIONAL INCIDENT INTELLIGENCE

Authorized Employees may ask:

```text
"What is happening in the kitchen?"

"Why are delivery orders delayed?"

"Which incidents are still open?"

"Are any customers affected?"

"What is the most critical problem right now?"

"What caused yesterday's outage?"

"What actions are still pending?"
```

Responses shall use current authoritative Incident evidence.

---

# 121. CUSTOMER-FACING INCIDENT QUESTIONS

Customers may ask:

```text
"Why is my order delayed?"

"Is the restaurant open?"

"Can you still deliver?"

"Why can't I order pizza?"
```

ECIP shall answer with only the appropriate operationally relevant information.

---

# 122. INCIDENT AI ASSISTANCE

AI may assist with:

* Signal correlation.
* Incident classification.
* Severity recommendation.
* Impact summarization.
* Root-cause candidate generation.
* Timeline summarization.
* Action recommendations.
* Post-incident review drafting.

---

# 123. AI AUTHORITY LIMIT

AI shall not:

* Invent an Incident.
* Hide an Incident.
* Declare a Root Cause without evidence.
* Close a critical Incident without required authority.
* Override safety procedures.
* Fabricate resolution.
* Accuse Employees or Suppliers without evidence.
* Communicate unsupported causes to Customers.
* Perform unauthorized financial recovery.

---

# 124. AUTOMATED INCIDENT ACTIONS

Future controlled automation may support low-risk actions such as:

* Create Incident from high-confidence signal.
* Notify Incident Owner.
* Update operational status.
* Recalculate Customer ETA.
* Recommend Product restriction.

Higher-risk actions such as:

* Close Branch.
* Suspend critical Product family.
* Issue mass Refunds.
* Public communication.
* Safety shutdown.

shall require explicit authorization where policy demands it.

---

# 125. INCIDENT SOURCE OF TRUTH

Authority may vary by information type.

Example:

```text
Kitchen:
Kitchen state

Maintenance:
Equipment failure

Quality:
Quality status

Payment Provider:
Payment state

ECIP:
Incident coordination and cross-domain intelligence
```

The Incident domain composes operational truth without replacing all source domains.

---

# 126. EXTERNAL INCIDENT MAPPING

External systems may provide:

* Monitoring alert ID.
* Maintenance ticket.
* Provider Incident ID.
* Support ticket.
* Safety report.

These shall map to canonical Incident identity.

---

# 127. INCIDENT SYNCHRONIZATION

Synchronization may include:

* External Incident status.
* Provider recovery.
* Maintenance repair.
* Payment provider outage.
* Monitoring alerts.

Synchronization shall remain:

* Idempotent.
* Observable.
* Auditable.

---

# 128. INCIDENT CONFLICT

Examples:

```text
Maintenance:
Equipment repaired

Kitchen:
Equipment still unavailable
```

or:

```text
Provider:
Service restored

ECIP:
Failures continue
```

Conflicts shall remain explicit until operational state is verified.

---

# 129. INCIDENT EVENTS

Initial domain events include:

```text
IncidentSignalDetected
IncidentSignalCorrelated

OperationalIncidentCreated
OperationalIncidentAcknowledged
OperationalIncidentTriaged

IncidentSeverityChanged
IncidentPriorityChanged
IncidentBlastRadiusChanged

IncidentOwnerAssigned
IncidentEscalated

IncidentImpactDetected
CustomerImpactDetected
CustomerCommitmentAtRiskDetected

IncidentContainmentStarted
ContainmentActionExecuted
IncidentContained

IncidentMitigationStarted
WorkaroundActivated
WorkaroundDeactivated

IncidentRecoveryStarted
ServiceRestored

OperationalIncidentResolved
OperationalIncidentClosed
OperationalIncidentReopened

IncidentRootCauseInvestigationStarted
IncidentRootCauseIdentified
IncidentRootCauseConfirmed

IncidentContributingFactorIdentified

IncidentCorrectiveActionCreated
IncidentCorrectiveActionAssigned
IncidentCorrectiveActionCompleted
IncidentCorrectiveActionVerified

IncidentPreventiveActionRecommended
IncidentPreventiveActionApproved
IncidentPreventiveActionCompleted

CustomerIncidentNotificationCreated
CustomerIncidentNotificationSent

IncidentServiceRecoveryStarted
IncidentServiceRecoveryCompleted

IncidentFinancialImpactEstimated
IncidentFinancialImpactFinalized

PostIncidentReviewCreated
PostIncidentReviewCompleted

RecurringIncidentPatternDetected
SinglePointOfFailureDetected

IncidentConflictDetected
IncidentConflictResolved

IncidentSynchronizationStarted
IncidentSynchronizationCompleted
IncidentSynchronizationFailed
```

---

# 130. RELATIONSHIPS

```text
Branch
    MAY_HAVE OperationalIncident

OperationalIncident
    HAS IncidentSignal

OperationalIncident
    HAS IncidentImpact

OperationalIncident
    HAS IncidentOwner

OperationalIncident
    MAY_AFFECT Customer

OperationalIncident
    MAY_AFFECT Order

OperationalIncident
    MAY_AFFECT Reservation

OperationalIncident
    MAY_AFFECT Event

OperationalIncident
    MAY_AFFECT Product

OperationalIncident
    MAY_AFFECT IngredientLot

OperationalIncident
    MAY_AFFECT MaintainableAsset

OperationalIncident
    MAY_AFFECT ExternalProvider

OperationalIncident
    MAY_CREATE Task

OperationalIncident
    MAY_REQUIRE ContainmentAction

OperationalIncident
    MAY_USE Workaround

OperationalIncident
    MAY_HAVE RootCause

OperationalIncident
    MAY_HAVE ContributingFactor

OperationalIncident
    MAY_CREATE CorrectiveAction

OperationalIncident
    MAY_CREATE PreventiveAction

OperationalIncident
    MAY_CREATE CustomerCommunicationPlan

OperationalIncident
    MAY_CREATE ServiceRecovery

OperationalIncident
    MAY_HAVE PostIncidentReview

OperationalIncident
    MAY_BE_PARENT_OF OperationalIncident

OperationalIncident
    MAPS_TO ExternalEntityReference

IncidentHistory
    CONTRIBUTES_TO OperationalIntelligence
```

---

# 131. BUSINESS RULES

The following rules apply:

1. A Signal is not automatically an Incident.

2. Incident severity shall be based on actual or credible potential business impact.

3. Every active material Incident shall have an accountable owner.

4. Blast Radius shall remain explicit.

5. Safety impact shall override commercial optimization.

6. Containment shall remain distinct from permanent resolution.

7. Workaround shall remain distinguishable from corrective action.

8. Service restoration shall not automatically mean Incident closure.

9. Customer-impacting incidents shall identify affected Customer commitments where possible.

10. Root cause shall require evidence.

11. Correlation shall not automatically be treated as causation.

12. Incident history shall never be rewritten to hide operational failures.

13. Employee attribution shall require evidence.

14. Customer communication shall not state unsupported causes.

15. High-risk financial recovery actions shall require authorization.

16. Incident relationships across domains shall preserve authoritative source ownership.

17. External Incident identifiers shall remain integration mappings.

18. Recurring Incidents shall support systemic analysis.

19. Manual fallback operations shall be reconciled after restoration.

20. Post-Incident Review shall not create additional governance layers unless required by severity or policy.

21. AI may assist Incident Management but shall not override safety, financial or operational authority.

22. Every material Incident decision, Action and state transition shall be reconstructable and auditable.

---

# 132. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
OperationalIncident

IncidentType

IncidentStatus

IncidentSeverity

IncidentPriority

IncidentSignal

IncidentImpact

IncidentBlastRadius

IncidentOwner

AffectedEntityReference

CustomerImpactReference

CustomerCommitmentImpact

ContainmentAction

Workaround

IncidentTask

IncidentEscalation

ServiceRestoration

IncidentResolution

RootCauseReference

CorrectiveAction

PreventiveActionReference

IncidentTimeline

IncidentEvidence

ExternalIncidentMapping

IncidentAuditHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced AI Incident Correlation

Autonomous Root-Cause Analysis

Predictive Incident Prevention

Advanced Cross-Branch Incident Command

Automatic Public Incident Communication

Autonomous Business Continuity Replanning

Digital Twin Incident Simulation

Advanced Operational Resilience Scoring

Autonomous Incident Remediation
```

---

# 133. IMPLEMENTATION PRINCIPLE

This document defines the logical Operational Incidents Model.

It does not prescribe:

* Incident Management software.
* Monitoring vendor.
* CMMS.
* POS implementation.
* Alerting platform.
* Communication provider.
* Root Cause Analysis methodology.
* Database schema.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
SIGNAL

INCIDENT

SEVERITY

IMPACT

BLAST RADIUS

OWNER

CONTAINMENT

MITIGATION

WORKAROUND

RECOVERY

RESOLUTION

ROOT CAUSE

CORRECTIVE ACTION

PREVENTIVE ACTION

POST-INCIDENT REVIEW
```

---

# 134. FINAL RULE

Before ECIP represents an Operational Incident as detected, contained, resolved or closed, it shall be able to determine:

> What happened?

> What evidence supports the Incident?

> Which Branch, Asset, Product, Order, Customer or service is affected?

> What is the current severity and priority?

> What is the Blast Radius?

> Is there any Safety, Quality, Financial or Compliance risk?

> Which Customer commitments are currently at risk?

> Who owns the Incident?

> What containment has already been executed?

> What temporary workaround is active?

> Has normal service actually been restored?

> What is known about Root Cause, and what remains uncertain?

> What corrective or preventive Actions remain open?

> Were affected Customers appropriately informed or compensated where required?

> Are there unresolved system reconciliation tasks?

> Is the Incident recurring or evidence of a Single Point of Failure?

> Can the complete Incident lifecycle, including detection, impact, decisions, Actions, recovery and learning, be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably represent the Incident as operationally contained, resolved or permanently closed.

