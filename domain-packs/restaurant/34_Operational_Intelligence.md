# 34_Operational_Intelligence.md

**Document ID:** RDM-034
**Document Name:** Operational Intelligence
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Operational Intelligence Model for the Restaurant Intelligence Platform.

Its purpose is to transform restaurant operational data into structured, explainable and actionable intelligence that allows ECIP to understand the real-time and historical state of restaurant operations.

Operational Intelligence shall enable the platform to answer questions such as:

```text
WHAT IS HAPPENING RIGHT NOW?

WHAT IS WORKING NORMALLY?

WHAT IS DEGRADED?

WHAT IS AT RISK?

WHAT WILL LIKELY BECOME A PROBLEM?

WHAT CUSTOMER COMMITMENTS ARE AFFECTED?

WHAT SHOULD OPERATIONS DO NEXT?

WHAT SHOULD NOT BE CHANGED?

WHAT REQUIRES HUMAN INTERVENTION?
```

Operational Intelligence is not merely a dashboard.

It is the intelligence layer that composes operational evidence from multiple domains into a coherent model of the restaurant's current operational state.

---

# 2. OBJECTIVES

The Operational Intelligence Model enables ECIP to:

* Understand current restaurant operational state.
* Understand Kitchen state.
* Understand Production state.
* Understand Inventory state.
* Understand Ingredient state.
* Understand Equipment state.
* Understand Maintenance state.
* Understand Reservation state.
* Understand Dine-In state.
* Understand Take Away state.
* Understand Delivery state.
* Understand Event state.
* Understand Quality state.
* Understand Compliance state.
* Understand Payment and Cash operational state.
* Detect bottlenecks.
* Detect congestion.
* Detect capacity constraints.
* Detect operational anomalies.
* Detect emerging risks.
* Detect Customer Commitment risks.
* Detect cross-domain operational dependencies.
* Predict operational degradation.
* Recommend corrective operational actions.
* Support real-time decision making.
* Support proactive Customer communication.
* Support operational prioritization.
* Support Executive Intelligence.
* Preserve evidence and explainability.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes canonical concepts including:

* Operational Context
* Context Snapshot
* Resource
* Metric Observation
* Runtime Event
* Incident
* Risk
* Prediction
* Recommendation
* Decision
* Action
* Task
* Commitment
* Evidence Record
* External Entity Reference

Restaurant-specific Operational Intelligence entities remain within the Restaurant Domain Pack.

---

# 4. RELATIONSHIP WITH OTHER INTELLIGENCE DOMAINS

Operational Intelligence shall cooperate with:

```text
32_Sales_Intelligence.md

33_Customer_Intelligence.md
```

and future intelligence domains.

Conceptually:

```text
CUSTOMER INTELLIGENCE
        ↓
What does the Customer need?

SALES INTELLIGENCE
        ↓
What commercial opportunity exists?

OPERATIONAL INTELLIGENCE
        ↓
Can the restaurant actually deliver it safely and reliably?
```

These domains shall remain semantically distinct.

---

# 5. OPERATIONAL INTELLIGENCE PRINCIPLE

The platform shall distinguish between:

```text
OPERATIONAL FACT

OPERATIONAL STATE

OPERATIONAL SIGNAL

OPERATIONAL ANOMALY

OPERATIONAL RISK

OPERATIONAL PREDICTION

OPERATIONAL INSIGHT

OPERATIONAL RECOMMENDATION

OPERATIONAL DECISION

OPERATIONAL ACTION
```

These concepts shall not be collapsed into one undifferentiated status.

---

# 6. OPERATIONAL CONTEXT

An `OperationalContext` represents the current state of the restaurant relevant to decision making.

It may include:

* Branch.
* Time.
* Service period.
* Occupancy.
* Reservation load.
* Active Orders.
* Kitchen load.
* Production backlog.
* Inventory constraints.
* Equipment state.
* Staffing state.
* Delivery capacity.
* Active Incidents.
* Quality Holds.
* Compliance restrictions.
* Payment provider health.

---

# 7. OPERATIONAL CONTEXT SNAPSHOT

A `OperationalContextSnapshot` captures operational state at a specific moment.

Typical attributes include:

* Snapshot ID
* Branch
* Timestamp
* Service period
* Active Orders
* Active Reservations
* Kitchen status
* Production status
* Inventory risks
* Equipment risks
* Delivery status
* Staffing state
* Active Incidents
* Critical restrictions
* Overall Operational Health

Snapshots may support audit, analytics and prediction.

---

# 8. OPERATIONAL HEALTH

A `OperationalHealthAssessment` may summarize overall restaurant operational condition.

Suggested states:

```text
HEALTHY

ATTENTION_REQUIRED

DEGRADED

CONGESTED

CRITICAL

UNAVAILABLE
```

Overall status shall be explainable from underlying domain evidence.

---

# 9. OPERATIONAL HEALTH PRINCIPLE

A high-level operational status shall never hide critical local conditions.

Example:

```text
Overall Branch:
HEALTHY

But:
One critical food-safety issue active
```

The critical condition shall remain visible and actionable.

---

# 10. SERVICE PERIOD

A `ServicePeriod` may represent:

```text
BREAKFAST

LUNCH

DINNER

LATE_NIGHT

EVENT_SERVICE

CUSTOM
```

Operational expectations may differ by Service Period.

---

# 11. OPERATIONAL LOAD

`OperationalLoad` represents aggregate restaurant workload.

Potential inputs:

* Active Customers.
* Active Orders.
* Reservation arrivals.
* Kitchen queue.
* Production tasks.
* Delivery demand.
* Event load.
* Employee availability.

---

# 12. LOAD LEVEL

Suggested states:

```text
LOW

NORMAL

HIGH

VERY_HIGH

SATURATED
```

---

# 13. CAPACITY

Operational Capacity represents the restaurant's ability to accept and fulfill additional demand.

Capacity may exist independently for:

* Dining.
* Kitchen.
* Production.
* Delivery.
* Reservations.
* Employees.
* Equipment.
* Inventory.
* Payments.

---

# 14. CAPACITY PRINCIPLE

Restaurant capacity shall not be represented as one universal number.

Example:

```text
Dining room:
Available

Kitchen:
Saturated

Delivery:
Available

Result:
Restaurant is not universally "available."
```

---

# 15. EFFECTIVE CAPACITY

`EffectiveOperationalCapacity` represents capacity after constraints are considered.

Conceptually:

```text
PHYSICAL CAPACITY
+
AVAILABLE STAFF
+
AVAILABLE EQUIPMENT
+
AVAILABLE INVENTORY
+
ACTIVE OPERATIONAL POLICIES
-
INCIDENT IMPACT
=
EFFECTIVE CAPACITY
```

---

# 16. CAPACITY CONSTRAINT

A `CapacityConstraint` represents a factor limiting throughput or service.

Examples:

```text
STAFFING

EQUIPMENT

KITCHEN_STATION

INVENTORY

SPACE

DELIVERY_DRIVER

PROVIDER

QUALITY_HOLD

COMPLIANCE_RESTRICTION
```

---

# 17. BOTTLENECK

An `OperationalBottleneck` represents a constraint currently limiting system throughput.

Examples:

* Grill backlog.
* Payment terminal outage.
* Delivery-driver shortage.
* Host stand congestion.
* Expo backlog.
* Packaging shortage.

---

# 18. BOTTLENECK ATTRIBUTES

Typical attributes:

* Bottleneck ID.
* Domain.
* Resource.
* Severity.
* Evidence.
* Queue impact.
* Customer impact.
* Estimated duration.
* Recommended action.
* Status.

---

# 19. BOTTLENECK STATUS

Suggested lifecycle:

```text
DETECTED
→ ACTIVE
→ MITIGATING
→ RESOLVED
```

---

# 20. BOTTLENECK ROOT CAUSE

Potential causes include:

```text
DEMAND_SPIKE

STAFF_SHORTAGE

EQUIPMENT_FAILURE

INVENTORY_SHORTAGE

PROCESS_CONSTRAINT

UPSTREAM_DELAY

DOWNSTREAM_CONGESTION

EXTERNAL_PROVIDER

UNKNOWN
```

Root cause shall require evidence.

---

# 21. OPERATIONAL SIGNAL

An `OperationalSignal` represents evidence that may indicate a meaningful change.

Examples:

* Queue depth rising.
* Inventory approaching stockout.
* Reservation arrival spike.
* Delivery ETA increasing.
* Equipment temperature unstable.
* Payment failures increasing.

A Signal does not automatically represent a problem.

---

# 22. OPERATIONAL ANOMALY

An `OperationalAnomaly` represents unexpected behavior relative to normal or expected operation.

Examples:

* Kitchen time suddenly doubles.
* Sales normal but Inventory consumption spikes.
* Order volume low but Delivery delays high.
* Repeated cash discrepancy.

An anomaly is a signal for investigation.

---

# 23. EXPECTED OPERATION

Operational Intelligence may establish baselines from:

* Historical patterns.
* Service standards.
* Current schedule.
* Forecast.
* Configured thresholds.

Baseline methodology shall remain explicit.

---

# 24. ANOMALY CONTEXT

An anomaly shall consider context.

Example:

```text
Kitchen preparation time:
40 minutes
```

may be abnormal on a quiet Tuesday but expected during a major Event.

---

# 25. OPERATIONAL RISK

An `OperationalRisk` represents credible potential for future operational degradation or failure.

Typical attributes:

* Risk ID.
* Domain.
* Evidence.
* Probability.
* Impact.
* Time horizon.
* Affected entities.
* Recommended mitigation.
* Status.

---

# 26. OPERATIONAL RISK LEVEL

Suggested states:

```text
LOW

MODERATE

HIGH

CRITICAL
```

---

# 27. RISK VS INCIDENT

The platform shall distinguish:

```text
RISK:
A problem may occur.

INCIDENT:
A material problem is occurring or occurred.
```

---

# 28. PREDICTIVE OPERATIONAL RISK

Examples:

* Kitchen likely to saturate in 20 minutes.
* Ingredient likely to stock out during Dinner.
* Delivery capacity likely insufficient.
* Critical Equipment showing degradation.

These are predictions and shall preserve confidence.

---

# 29. OPERATIONAL PREDICTION

A `OperationalPrediction` may estimate:

* Queue length.
* Preparation time.
* Occupancy.
* Inventory shortage.
* Equipment failure.
* Delivery delay.
* Customer wait.
* Staffing deficit.

---

# 30. PREDICTION METADATA

Predictions shall preserve:

* Model ID.
* Model Version.
* Generated time.
* Horizon.
* Confidence.
* Evidence references.
* Applicable Branch/domain.

---

# 31. OPERATIONAL FORECAST

An `OperationalForecast` may combine future demand and capacity.

Example:

```text
19:00–20:00

Expected Orders:
120

Kitchen capacity:
95

Expected deficit:
25 Orders equivalent
```

---

# 32. DEMAND FORECAST

Demand may originate from:

* Reservations.
* Historical patterns.
* Events.
* Scheduled Orders.
* Promotions.
* Current demand trajectory.

---

# 33. DEMAND VS CAPACITY

Operational Intelligence shall continuously reason across:

```text
EXPECTED DEMAND

vs

AVAILABLE CAPACITY
```

Potential result:

```text
SURPLUS_CAPACITY

BALANCED

PRESSURE

DEFICIT

CRITICAL_DEFICIT
```

---

# 34. OPERATIONAL PRESSURE

`OperationalPressure` represents increasing strain before failure occurs.

Examples:

* Queue growing.
* Employee utilization very high.
* Capacity buffers disappearing.
* Inventory safety stock being consumed.

---

# 35. OPERATIONAL SATURATION

Saturation occurs when incoming workload is at or above effective capacity and delays are likely to increase.

---

# 36. SATURATION IMPACT

Operational saturation may affect:

* Wait time.
* Order ETA.
* Reservation seating.
* Delivery acceptance.
* Product Recommendations.
* Customer Experience.
* Employee workload.

---

# 37. RESTAURANT OCCUPANCY

Occupancy may include:

* Seats occupied.
* Tables occupied.
* Capacity committed.
* Waiting Customers.
* Reservations arriving soon.

---

# 38. OCCUPANCY FORECAST

Future occupancy may combine:

* Active Dining Sessions.
* Expected departures.
* Upcoming Reservations.
* Waitlist.
* Walk-in trend.

---

# 39. WAITING-TIME INTELLIGENCE

Operational Intelligence may estimate:

* Waitlist time.
* Seating delay.
* Food delay.
* Pickup delay.
* Delivery delay.

Estimates shall preserve uncertainty.

---

# 40. ETA INTELLIGENCE

ETA reasoning may combine:

```text
CURRENT QUEUE

+
PRODUCTION TIME

+
OPERATIONAL LOAD

+
RESOURCE AVAILABILITY

+
KNOWN INCIDENTS

=
ESTIMATED COMPLETION
```

---

# 41. ETA CONFIDENCE

Suggested confidence states:

```text
HIGH

MEDIUM

LOW
```

Customers should not receive false precision when confidence is low.

---

# 42. KITCHEN INTELLIGENCE

Operational Intelligence consumes `20_Kitchen.md`.

Relevant information includes:

* Kitchen status.
* Station load.
* Queue depth.
* Bottlenecks.
* Equipment state.
* Active Employees.
* ETA.

---

# 43. PRODUCTION INTELLIGENCE

Operational Intelligence consumes `21_Production.md`.

Relevant information includes:

* Production Requirements.
* Work In Progress.
* Blocked Tasks.
* Delays.
* Batch state.
* Production readiness.

---

# 44. QUALITY INTELLIGENCE

Operational Intelligence consumes `22_Quality_Control.md`.

Relevant information includes:

* Active Quality Holds.
* Rework.
* Remakes.
* Critical deviations.
* Recurring defects.

---

# 45. INVENTORY INTELLIGENCE

Operational Intelligence consumes `23_Inventory.md`.

Relevant information includes:

* Available stock.
* Critical stock.
* Stockouts.
* Expiration risk.
* Inventory conflicts.
* Packaging availability.

---

# 46. PURCHASING INTELLIGENCE

Operational Intelligence consumes `24_Purchasing.md`.

Relevant information includes:

* Delayed Purchase Orders.
* Critical Goods in Transit.
* Supplier failure.
* Expected replenishment.

---

# 47. INGREDIENT INTELLIGENCE

Operational Intelligence consumes `25_Ingredient_Lifecycle.md`.

Relevant information includes:

* Ingredient shortage.
* Recall.
* Expiration.
* Quality Hold.
* Recipe dependency.

---

# 48. PAYMENT OPERATIONAL INTELLIGENCE

Operational Intelligence consumes `26_Payments.md`.

Relevant information includes:

* Provider health.
* Payment failure rate.
* Pending Payment status.
* Payment conflicts.

---

# 49. BILLING OPERATIONAL INTELLIGENCE

Operational Intelligence consumes `27_Billing.md`.

Relevant information includes:

* Fiscal provider state.
* Billing failure.
* Pending fiscalization.
* Billing conflicts.

---

# 50. CASH OPERATIONAL INTELLIGENCE

Operational Intelligence consumes `28_Cash_Management.md`.

Relevant information includes:

* Open sessions.
* Unreconciled sessions.
* Cash exposure.
* Deposit delays.
* Critical discrepancies.

---

# 51. MAINTENANCE INTELLIGENCE

Operational Intelligence consumes `29_Maintenance.md`.

Relevant information includes:

* Asset availability.
* Work Orders.
* Critical failures.
* Downtime.
* Degraded Equipment.
* Preventive Maintenance overdue.

---

# 52. INCIDENT INTELLIGENCE

Operational Intelligence consumes `30_Operational_Incidents.md`.

Active Incidents shall materially influence the operational context.

---

# 53. COMPLIANCE INTELLIGENCE

Operational Intelligence consumes `31_Compliance.md`.

Relevant conditions include:

* Operating restrictions.
* Expired critical license.
* Critical Non-Conformity.
* Safety restriction.
* Compliance-related shutdown.

---

# 54. RESERVATION INTELLIGENCE

Operational Intelligence consumes `18_Reservations.md`.

Relevant information includes:

* Upcoming arrivals.
* Party size.
* Capacity commitments.
* Waitlist.
* No-show risk where modeled.

---

# 55. DINE-IN INTELLIGENCE

Operational Intelligence consumes Dine-In state including:

* Active Tables.
* Active Dining Sessions.
* Course timing.
* Table turnover.
* Service Requests.
* Customer delays.

---

# 56. TAKE-AWAY INTELLIGENCE

Relevant information includes:

* Active Orders.
* Pickup deadlines.
* Production readiness.
* Pickup backlog.
* Packaging availability.

---

# 57. DELIVERY INTELLIGENCE

Relevant information includes:

* Active deliveries.
* Driver capacity.
* Provider health.
* Dispatch backlog.
* Current ETA.
* Delivery incidents.

---

# 58. EVENT INTELLIGENCE

Operational Intelligence consumes Event state including:

* Guest count.
* Schedule.
* Resource requirements.
* Production demand.
* Space commitments.
* Equipment commitments.

---

# 59. CROSS-DOMAIN DEPENDENCY

Operational Intelligence exists because restaurant domains are interdependent.

Example:

```text
Supplier Delay
    ↓
Ingredient Shortage
    ↓
Product Unavailability
    ↓
Order Change
    ↓
Customer Dissatisfaction
    ↓
Lost Sale
```

ECIP should understand the chain rather than treat each symptom independently.

---

# 60. OPERATIONAL DEPENDENCY GRAPH

The platform may maintain a graph such as:

```text
RESOURCE
    ↓
PROCESS
    ↓
PRODUCT
    ↓
ORDER
    ↓
CUSTOMER COMMITMENT
```

This enables impact reasoning.

---

# 61. IMPACT ANALYSIS

An `OperationalImpactAnalysis` may determine:

* What is affected?
* How many Customers?
* Which Products?
* Which Orders?
* Which future commitments?
* What financial value is at risk?
* What alternatives exist?

---

# 62. FORWARD IMPACT ANALYSIS

Example:

```text
Fryer failure
    ↓
Products requiring fryer
    ↓
Open Orders
    ↓
Future reservations/events
```

---

# 63. BACKWARD CAUSE ANALYSIS

Example:

```text
Customer Order delayed
    ↑
Kitchen Task blocked
    ↑
Required Ingredient unavailable
    ↑
Supplier delivery failed
```

Operational Intelligence may reconstruct contributing causes.

---

# 64. CUSTOMER COMMITMENT RISK

A `OperationalCommitmentRisk` represents operational risk to a confirmed Customer commitment.

Examples:

* Reservation delay.
* Delivery delay.
* Event resource failure.
* Product unavailable after Order confirmation.
* Refund delay.

---

# 65. COMMITMENT-RISK PRIORITY

Customer commitments shall be prioritized by:

* Safety.
* Deadline.
* Severity.
* Number of Customers.
* Business impact.
* Recovery options.

---

# 66. PROACTIVE COMMITMENT MANAGEMENT

Where authorized, ECIP may act before a commitment fails.

Example:

```text
Delivery delay predicted:
25 minutes

Customer promise at risk.

Potential action:
Notify Customer and provide updated ETA.
```

---

# 67. OPERATIONAL RECOMMENDATION

A `OperationalRecommendation` represents a proposed action to improve operational outcome.

Examples:

* Reassign Employee.
* Temporarily restrict Product.
* Start additional prep.
* Switch Payment provider.
* Move stock.
* Update ETA.
* Notify affected Customer.
* Escalate Incident.

---

# 68. RECOMMENDATION ATTRIBUTES

Typical attributes:

* Recommendation ID.
* Context.
* Domain.
* Evidence.
* Expected impact.
* Risk.
* Confidence.
* Required authority.
* Expiration.
* Status.

---

# 69. RECOMMENDATION STATUS

Suggested lifecycle:

```text
CREATED
→ VALIDATED
→ PRESENTED
→ ACCEPTED
→ EXECUTED
→ EVALUATED
```

Alternative states:

```text
REJECTED

EXPIRED

SUPPRESSED
```

---

# 70. OPERATIONAL NEXT-BEST-ACTION

A `OperationalNextBestAction` may determine the most appropriate response under current conditions.

Possible Actions:

```text
CONTINUE_NORMAL_OPERATION

NOTIFY

REASSIGN_RESOURCE

RESTRICT_PRODUCT

START_PREP

ADJUST_CAPACITY

ESCALATE

ACTIVATE_WORKAROUND

PAUSE_ACCEPTANCE

NO_ACTION
```

---

# 71. NO-ACTION PRINCIPLE

Operational Intelligence should not generate unnecessary action merely because variation exists.

Sometimes the best action is:

```text
MONITOR
```

or:

```text
NO_ACTION
```

---

# 72. ACTION AUTHORIZATION

Operational Recommendations do not automatically become Actions.

Examples requiring higher authority may include:

* Close Branch.
* Suspend Product family.
* Reject new Orders.
* Disable Delivery.
* Trigger major purchasing.
* Perform financial adjustment.

---

# 73. AUTOMATED LOW-RISK ACTION

Future low-risk automation may include:

* Update ETA.
* Send internal alert.
* Start monitoring.
* Recalculate capacity.
* Create Task.
* Update operational status.

---

# 74. OPERATIONAL PRIORITIZATION

ECIP may need to prioritize simultaneous problems.

Potential criteria include:

```text
SAFETY

CUSTOMER COMMITMENT

SEVERITY

URGENCY

BLAST RADIUS

REVERSIBILITY

FINANCIAL IMPACT

RECOVERY OPTIONS
```

Safety shall always dominate commercial optimization.

---

# 75. PRIORITY CONFLICT

Example:

```text
Order A:
High-value Customer, moderate delay

Order B:
Allergy-sensitive Product issue
```

Order B shall take priority due to safety.

---

# 76. OPERATIONAL TRADE-OFF

Operational decisions may involve trade-offs.

Example:

```text
Accept more Delivery Orders
vs
Protect existing Delivery commitments
```

The platform should make the trade-off explicit.

---

# 77. SERVICE LEVEL

A `OperationalServiceLevel` may represent expected performance.

Examples:

* Maximum seating delay.
* Pickup target.
* Delivery ETA target.
* Payment provider availability.
* Kitchen preparation target.

---

# 78. SERVICE-LEVEL BREACH

A `ServiceLevelBreach` occurs when actual performance violates a defined operational target or commitment.

This may create:

* Signal.
* Risk.
* Incident.
* Customer Recovery.

depending on severity.

---

# 79. OPERATIONAL SLA VS CUSTOMER PROMISE

Internal targets shall remain distinct from explicit Customer promises.

Example:

```text
Internal target:
20-minute preparation

Customer promise:
30-minute pickup
```

Failure of the internal target does not necessarily mean the Customer commitment failed.

---

# 80. RESOURCE UTILIZATION

Operational Intelligence may measure utilization of:

* Kitchen Stations.
* Tables.
* Equipment.
* Employees.
* Delivery capacity.
* Storage.
* Payment terminals.

---

# 81. UTILIZATION PRINCIPLE

High utilization is not automatically good.

Extremely high utilization may eliminate resilience and increase delay risk.

---

# 82. CAPACITY BUFFER

A `CapacityBuffer` represents spare operational ability before saturation.

Example:

```text
Kitchen utilization:
70%

Remaining effective buffer:
30%
```

---

# 83. RESILIENCE BUFFER

Some capacity may intentionally remain unused to absorb:

* Demand spikes.
* Equipment failure.
* Large walk-in parties.
* Delivery variation.

---

# 84. STAFFING INTELLIGENCE

Operational Intelligence may consume:

* Employees scheduled.
* Employees present.
* Skills.
* Current assignment.
* Workload.

Detailed workforce management may belong to another domain.

---

# 85. STAFFING SHORTAGE

A `StaffingCapacityRisk` may arise when:

* Employee absence.
* Skill mismatch.
* Demand spike.
* Critical Station unstaffed.

---

# 86. STAFF REALLOCATION RECOMMENDATION

Potential recommendation:

```text
Move qualified Employee from low-load Station A
to overloaded Station B.
```

This requires capability and authority validation.

---

# 87. OPERATIONAL QUALITY OF SERVICE

Operational quality may consider:

* Timeliness.
* Completeness.
* Accuracy.
* Reliability.
* Recovery.

This remains distinct from Product Quality.

---

# 88. OPERATIONAL EFFICIENCY

Potential measures include:

* Throughput.
* Cycle time.
* Queue time.
* Resource utilization.
* Waste.
* Rework.
* Delay.

Efficiency shall not be optimized at the expense of Customer Experience, Safety or Quality.

---

# 89. THROUGHPUT

`OperationalThroughput` may measure completed units per time.

Examples:

* Orders/hour.
* Tables/hour.
* Kitchen Items/hour.
* Deliveries/hour.

---

# 90. CYCLE TIME

Cycle Time may be measured for:

* Order.
* Production.
* Reservation seating.
* Delivery.
* Payment.

---

# 91. QUEUE TIME

Queue Time shall remain distinct from processing time.

This separation is essential for bottleneck analysis.

---

# 92. OPERATIONAL VARIANCE

Variance may compare:

```text
ACTUAL

vs

EXPECTED
```

for:

* Time.
* Demand.
* Capacity.
* Waste.
* Inventory.
* Labor.
* Quality.

---

# 93. VARIANCE SIGNIFICANCE

Not every variance is actionable.

Significance should consider:

* Magnitude.
* Duration.
* Recurrence.
* Customer impact.
* Operational context.

---

# 94. TREND DETECTION

Operational Intelligence may detect:

* Gradual degradation.
* Improving throughput.
* Increasing delays.
* Recurrent shortages.
* Repeated peak congestion.

---

# 95. RECURRING OPERATIONAL PATTERN

Example:

```text
Every Friday:
Kitchen congestion begins at 20:15.
```

This may indicate:

* Staffing issue.
* Menu mix.
* Reservation profile.
* Production bottleneck.

Further analysis is required before assigning cause.

---

# 96. OPERATIONAL LEARNING LOOP

Conceptually:

```text
OPERATION
    ↓
OBSERVATION
    ↓
SIGNAL
    ↓
INSIGHT
    ↓
RECOMMENDATION
    ↓
ACTION
    ↓
OUTCOME
    ↓
LEARNING
    ↓
BETTER FUTURE OPERATION
```

---

# 97. OPERATIONAL OUTCOME

An `OperationalOutcome` may measure whether an Action improved:

* Wait time.
* Throughput.
* Capacity.
* Customer impact.
* Cost.
* Quality.
* Incident resolution.

---

# 98. RECOMMENDATION EFFECTIVENESS

A recommendation should eventually be measurable.

Example:

```text
Recommendation:
Temporarily stop accepting Delivery Orders.

Outcome:
Backlog normalized in 18 minutes.
```

This does not automatically prove causal effectiveness without appropriate analysis.

---

# 99. ROOT-CAUSE ASSISTANCE

Operational Intelligence may identify likely contributing causes.

Example:

```text
Order delay
    ↓
Production queue
    ↓
Fryer bottleneck
    ↓
One fryer unavailable
```

Likely cause is evidence-based.

---

# 100. ROOT-CAUSE LIMIT

Operational Intelligence shall not convert correlation into definitive causation.

Formal Root Cause may belong to Operational Incidents, Maintenance, Quality or other responsible domain.

---

# 101. OPERATIONAL DIGITAL TWIN

Long-term, Operational Intelligence contributes to the Digital Twin of the Restaurant.

The operational Digital Twin may represent:

```text
CURRENT RESOURCES

CURRENT CAPACITY

CURRENT DEMAND

CURRENT QUEUES

CURRENT COMMITMENTS

CURRENT RISKS

CURRENT INCIDENTS

CURRENT CONSTRAINTS

EXPECTED FUTURE STATE
```

---

# 102. DIGITAL TWIN PURPOSE

The purpose is not merely visualization.

It enables the platform to reason:

```text
IF WE TAKE THIS ACTION,
WHAT WILL LIKELY HAPPEN?
```

---

# 103. WHAT-IF ANALYSIS

Future capabilities may simulate:

* Accepting additional Orders.
* Closing one Kitchen Station.
* Employee absence.
* Equipment failure.
* Large Reservation arrival.
* Product restriction.

---

# 104. OPERATIONAL SIMULATION BOUNDARY

Simulation results shall remain predictions.

They shall not become authoritative state.

---

# 105. BRANCH OPERATIONAL INTELLIGENCE

Each Branch may have an independent Operational Context.

Potential questions:

* Which Branch is overloaded?
* Which Branch has spare capacity?
* Which Branch has critical stock risk?
* Which Branch has active critical Incident?

---

# 106. MULTI-BRANCH INTELLIGENCE

Restaurant Groups may compare and coordinate Branches.

Potential capabilities:

* Redirect Delivery demand.
* Transfer Inventory.
* Share resources.
* Route Event inquiries.
* Balance Production.

Actual actions require domain authority.

---

# 107. CROSS-BRANCH ASSISTANCE

Example:

```text
Branch A:
Product unavailable

Branch B:
Product available and nearby
```

The platform may suggest alternatives where commercial and operational policy permits.

---

# 108. CENTRAL KITCHEN INTELLIGENCE

Groups with central kitchens may need to understand:

* Production backlog.
* Prepared Component availability.
* Branch demand.
* Transfer requirements.

---

# 109. CLOUD KITCHEN INTELLIGENCE

Cloud Kitchens may require:

* Multi-brand demand.
* Shared Station capacity.
* Delivery provider capacity.
* Brand-specific Product constraints.

---

# 110. OPERATIONAL ANOMALY DETECTION

Potential anomalies include:

```text
ORDER_VOLUME_SPIKE

ORDER_VOLUME_DROP

PREPARATION_TIME_SPIKE

DELIVERY_TIME_SPIKE

INVENTORY_CONSUMPTION_ANOMALY

WASTE_SPIKE

PAYMENT_FAILURE_SPIKE

CASH_DISCREPANCY_SPIKE

EQUIPMENT_DEGRADATION

QUALITY_FAILURE_SPIKE
```

---

# 111. ANOMALY SUPPRESSION

Known expected conditions should suppress false alerts.

Example:

```text
Large Event scheduled tonight
```

A high Production load may therefore be expected rather than anomalous.

---

# 112. OPERATIONAL ALERT

Alerts may include:

```text
KITCHEN_SATURATION_RISK

DELIVERY_CAPACITY_RISK

INVENTORY_SHORTAGE_RISK

CRITICAL_EQUIPMENT_DEGRADED

CUSTOMER_COMMITMENT_AT_RISK

QUALITY_HOLD_IMPACT

PAYMENT_PROVIDER_DEGRADED

RESERVATION_CAPACITY_RISK

EVENT_RESOURCE_RISK
```

---

# 113. ALERT PRIORITY

Alerts should be prioritized to avoid operational noise.

Potential inputs:

* Severity.
* Confidence.
* Urgency.
* Customer impact.
* Blast Radius.
* Existing Incident coverage.

---

# 114. ALERT DEDUPLICATION

Multiple signals caused by the same Incident should not generate overwhelming duplicate alerts.

---

# 115. OPERATIONAL BRIEFING

ECIP may generate a real-time operational briefing.

Example:

```text
Branch Downtown — 20:10

Overall Status:
DEGRADED

Kitchen:
High load
Grill saturated

Orders:
11 potentially delayed

Reservations:
42 arrivals expected in next 45 minutes

Inventory:
Salmon critical stock

Maintenance:
Grill 2 unavailable

Delivery:
Normal

Critical Action:
Protect existing grill-dependent commitments before accepting additional demand.
```

---

# 116. SHIFT HANDOFF INTELLIGENCE

Operational Intelligence may generate a structured shift handoff including:

* Open incidents.
* Critical stock.
* Equipment issues.
* Pending Customer commitments.
* Large upcoming Reservations.
* Event status.
* Unresolved cash or payment issues.

---

# 117. NO-LOSS HANDOFF PRINCIPLE

Important operational knowledge shall survive Employee shift changes.

The platform shall convert transient human knowledge into structured operational continuity.

---

# 118. OPERATIONAL MEMORY

Long-term operational knowledge may include:

* Recurring bottlenecks.
* Typical peak patterns.
* Common Equipment failures.
* Recurring stockouts.
* Effective workarounds.

This knowledge supports future planning.

---

# 119. OPERATIONAL KNOWLEDGE VS CURRENT STATE

The platform shall distinguish:

```text
CURRENT STATE:
What is happening now.

HISTORICAL KNOWLEDGE:
What usually happens.

PREDICTION:
What may happen next.
```

---

# 120. OPERATIONAL INTELLIGENCE METRICS

Potential metrics include:

* Overall Operational Health.
* Order throughput.
* Preparation time.
* Customer wait time.
* Delivery ETA accuracy.
* Kitchen saturation.
* Capacity utilization.
* Bottleneck duration.
* Incident count.
* Resource availability.
* Stockout rate.
* Quality failure rate.
* Service-level breach rate.

---

# 121. OPERATIONAL HEALTH SCORE

If an aggregate score exists, it shall remain explainable.

Example:

```text
Operational Health:
78/100

Drivers:
+ Delivery normal
+ Inventory mostly healthy
- Kitchen congestion
- One critical Equipment outage
- 8 Orders at delay risk
```

---

# 122. SCORE CAUTION

A score shall never hide a critical safety or Compliance issue.

Critical conditions shall override aggregate presentation.

---

# 123. BOTTLENECK DURATION

Potential metric:

```text
Resolved Time
-
Detected Time
```

---

# 124. CAPACITY UTILIZATION

Potential metric:

```text
Current Effective Load
/
Effective Capacity
```

Methodology may differ by operational domain.

---

# 125. ETA ACCURACY

Potential metric:

```text
Actual Completion
-
Promised / Predicted Completion
```

Aggregated error may measure ETA model quality.

---

# 126. COMMITMENT SUCCESS RATE

Potential metric:

```text
Customer Commitments Fulfilled As Promised
/
Total Measurable Commitments
```

---

# 127. OPERATIONAL INCIDENT RATE

Potential metric:

```text
Material Operational Incidents
/
Operating Hours
```

or another explicit methodology.

---

# 128. OPERATIONAL RESILIENCE

Potential resilience dimensions include:

* Redundancy.
* Recovery time.
* Capacity buffer.
* Alternate Supplier.
* Alternate provider.
* Operational fallback.

---

# 129. SINGLE POINT OF FAILURE INTELLIGENCE

Operational Intelligence may identify dependencies such as:

```text
One Oven
→ 35% of Menu

One Delivery Provider
→ 90% of Delivery

One Supplier
→ Critical Ingredient
```

These may become resilience recommendations.

---

# 130. OPERATIONAL COST INTELLIGENCE

Operational inefficiency may generate costs through:

* Waste.
* Rework.
* Overtime.
* Refunds.
* Lost sales.
* Delivery delay.
* Downtime.

Financial systems remain authoritative for final monetary values.

---

# 131. OPERATIONAL EXECUTIVE INTELLIGENCE

Potential executive questions include:

* Where is the operation currently weakest?
* Which Branch is at highest risk?
* What repeatedly causes Customer delays?
* Which bottlenecks cost the most?
* Which Equipment creates most disruption?
* Which Ingredients most often cause Product unavailability?
* Which service channel is operationally inefficient?
* Are Customer commitments being met?
* Where should capacity investment be made?

---

# 132. CONVERSATIONAL OPERATIONAL INTELLIGENCE

Authorized Employees may ask:

```text
"How is the restaurant operating right now?"

"What is our biggest bottleneck?"

"Which orders are at risk?"

"Why are customers waiting?"

"Can we accept more delivery orders?"

"Which products should we temporarily stop selling?"

"What is likely to become a problem in the next hour?"

"What needs my attention right now?"
```

Responses shall use authoritative current data and clearly identify uncertainty.

---

# 133. OWNER-LEVEL OPERATIONAL INTELLIGENCE

The future intelligent owner-advisor may consume this domain to answer questions such as:

```text
"Can I leave the restaurant now?"

"Is anything critical happening?"

"Which branch needs attention?"

"What problem could affect tonight's sales?"

"Which manager should act?"

"What can safely wait until tomorrow?"
```

This document defines the operational intelligence foundation required for that future capability.

---

# 134. CUSTOMER-FACING OPERATIONAL INTELLIGENCE

Customers may receive only the portion of Operational Intelligence relevant to them.

Examples:

```text
"Your order is expected to be ready in approximately 15 minutes."

"We currently have no availability at 8 PM, but 8:30 PM is available."

"That product is temporarily unavailable."
```

Internal operational details shall not be unnecessarily exposed.

---

# 135. AI OPERATIONAL ASSISTANCE

AI may assist with:

* Cross-domain context composition.
* Bottleneck detection.
* Risk detection.
* Signal correlation.
* Impact analysis.
* Operational summarization.
* ETA interpretation.
* Next-best-action recommendation.
* Root-cause candidate generation.
* Shift briefing generation.

---

# 136. AI AUTHORITY LIMIT

AI shall not:

* Invent operational state.
* Invent available capacity.
* Invent stock.
* Declare Equipment healthy without evidence.
* Ignore Quality or Compliance restrictions.
* Override safety.
* Close Incidents without authority.
* Cancel Customer commitments autonomously outside policy.
* Present predictions as facts.
* Perform unauthorized high-impact operational actions.

---

# 137. OPERATIONAL INTELLIGENCE EXPLAINABILITY

Material operational recommendations should be explainable.

Example:

```text
Recommendation:
Temporarily stop accepting new grill-heavy Delivery Orders.

Because:
Grill utilization = 98%
Queue backlog = 31 minutes
Grill 2 = out of service
9 confirmed Orders already at delay risk
```

---

# 138. EVIDENCE HIERARCHY

Operational Intelligence should prefer:

```text
AUTHORITATIVE DOMAIN STATE

↓
DIRECT MEASUREMENT

↓
SYSTEM EVENT

↓
EMPLOYEE OBSERVATION

↓
CUSTOMER REPORT

↓
MODEL INFERENCE
```

depending on the question.

---

# 139. DATA FRESHNESS

Operational state becomes obsolete quickly.

Every real-time operational fact should preserve:

* Timestamp.
* Source.
* Freshness.
* Synchronization state.

---

# 140. STALE OPERATIONAL DATA

Stale information shall not be represented as current.

Example:

```text
Inventory stock value:
Last synchronized 4 hours ago
```

may not be sufficient to guarantee Product availability.

---

# 141. OPERATIONAL CONFIDENCE

When data is incomplete or stale, Operational Intelligence shall reduce confidence rather than fabricate certainty.

---

# 142. SOURCE OF TRUTH

Authority varies by domain.

Example:

```text
Kitchen:
Kitchen Runtime

Production:
Production Runtime

Inventory:
Inventory System

Maintenance:
Maintenance System

Reservations:
Reservation System

Payments:
Payment Provider / Payment Runtime

ECIP:
Cross-domain operational intelligence
```

Operational Intelligence composes source truth without replacing it.

---

# 143. EXTERNAL OPERATIONAL MAPPING

External systems may use:

* POS state.
* KDS state.
* Delivery provider state.
* Reservation platform state.
* Maintenance ticket.
* Inventory item state.

These shall map to canonical ECIP operational entities.

---

# 144. OPERATIONAL SYNCHRONIZATION

Synchronization shall preserve:

* Source.
* Timestamp.
* Version.
* Event identity.
* Idempotency.
* Failure state.

---

# 145. OPERATIONAL CONFLICT

Example:

```text
KDS:
Product ready

POS:
Order cancelled
```

or:

```text
Inventory:
Ingredient available

Quality:
Ingredient Lot on Hold
```

Conflicts shall remain explicit until resolved.

---

# 146. OPERATIONAL CONFLICT PRIORITY

Where domains conflict, applicable authority and safety rules shall determine the usable operational state.

Example:

```text
Inventory says available
Quality says HOLD

Effective operational state:
UNAVAILABLE
```

---

# 147. OPERATIONAL INTELLIGENCE AUDIT TRAIL

Material Intelligence decisions should preserve:

* Context Snapshot.
* Signals.
* Relevant domain states.
* Recommendation.
* Model/rule version.
* Confidence.
* Human decision.
* Action.
* Outcome.

---

# 148. OPERATIONAL INTELLIGENCE EVENTS

Initial domain events include:

```text
OperationalContextCreated
OperationalContextUpdated
OperationalContextSnapshotCreated

OperationalHealthChanged

OperationalLoadChanged
OperationalCapacityChanged
OperationalCapacityConstraintDetected

OperationalSignalDetected
OperationalSignalResolved

OperationalAnomalyDetected
OperationalAnomalyDismissed
OperationalAnomalyConfirmed

OperationalBottleneckDetected
OperationalBottleneckUpdated
OperationalBottleneckResolved

OperationalRiskDetected
OperationalRiskUpdated
OperationalRiskEscalated
OperationalRiskResolved

OperationalPredictionCreated
OperationalPredictionUpdated
OperationalPredictionExpired

OperationalDemandForecastCreated
OperationalCapacityForecastCreated

OperationalSaturationRiskDetected
OperationalSaturationDetected
OperationalSaturationResolved

OperationalCommitmentRiskDetected
OperationalCommitmentRiskResolved

OperationalRecommendationCreated
OperationalRecommendationValidated
OperationalRecommendationPresented
OperationalRecommendationAccepted
OperationalRecommendationRejected
OperationalRecommendationExecuted
OperationalRecommendationExpired

OperationalNextBestActionCreated
OperationalNextBestActionExecuted

OperationalServiceLevelBreachDetected
OperationalServiceLevelRestored

OperationalImpactAnalysisCreated

OperationalTrendDetected
RecurringOperationalPatternDetected
SinglePointOfFailureDetected

OperationalBriefingCreated
OperationalShiftHandoffCreated

OperationalConflictDetected
OperationalConflictResolved

OperationalIntelligenceSynchronizationStarted
OperationalIntelligenceSynchronizationCompleted
OperationalIntelligenceSynchronizationFailed
```

---

# 149. RELATIONSHIPS

```text
Branch
    HAS OperationalContext

OperationalContext
    REFERENCES KitchenState

OperationalContext
    REFERENCES ProductionState

OperationalContext
    REFERENCES InventoryState

OperationalContext
    REFERENCES MaintenanceState

OperationalContext
    REFERENCES ReservationState

OperationalContext
    REFERENCES DeliveryState

OperationalContext
    REFERENCES IncidentState

OperationalContext
    REFERENCES ComplianceState

OperationalContext
    PRODUCES OperationalHealthAssessment

OperationalContext
    MAY_GENERATE OperationalSignal

OperationalSignal
    MAY_CREATE OperationalAnomaly

OperationalSignal
    MAY_CREATE OperationalRisk

OperationalRisk
    MAY_CREATE OperationalPrediction

OperationalContext
    MAY_CREATE OperationalBottleneck

OperationalBottleneck
    MAY_AFFECT CustomerCommitment

CustomerCommitment
    MAY_CREATE OperationalCommitmentRisk

OperationalRisk
    MAY_CREATE OperationalRecommendation

OperationalRecommendation
    MAY_CREATE OperationalAction

OperationalAction
    PRODUCES OperationalOutcome

OperationalOutcome
    CONTRIBUTES_TO OperationalLearning

OperationalIntelligence
    CONSTRAINS SalesIntelligence

OperationalIntelligence
    INFORMS CustomerIntelligence

OperationalIntelligence
    CONTRIBUTES_TO ExecutiveIntelligence
```

---

# 150. BUSINESS RULES

The following rules apply:

1. Operational Intelligence shall not replace authoritative operational domains.

2. Operational facts, signals, anomalies, risks and predictions shall remain distinct.

3. Current operational state shall preserve data freshness.

4. Stale data shall not be represented as current certainty.

5. Overall Operational Health shall remain explainable.

6. Critical Safety, Quality or Compliance conditions shall override aggregate scores.

7. Restaurant capacity shall be modeled by relevant operational dimension, not as one universal value.

8. Effective Capacity shall account for actual constraints.

9. Bottleneck detection shall preserve evidence.

10. Operational Risks shall remain distinct from active Incidents.

11. Predictions shall preserve confidence, horizon and model/version metadata.

12. Forecast demand shall remain distinct from confirmed demand.

13. Customer Commitment risk shall be explicitly identified.

14. Existing Customer commitments shall normally take precedence over optional new demand when capacity is constrained.

15. Sales Intelligence shall consume Operational Intelligence rather than override it.

16. Product Recommendations shall respect current operational feasibility.

17. No Action or Monitor are valid operational recommendations.

18. High-impact Actions shall require appropriate authority.

19. AI shall not override Safety, Quality, Compliance or financial controls.

20. Root-cause hypotheses shall remain distinct from confirmed causes.

21. Cross-domain conflicts shall remain explicit until resolved.

22. Source ownership shall remain preserved.

23. Every material operational recommendation shall be explainable from current evidence.

24. Operational Intelligence shall optimize Customer commitments, Safety, Quality and sustainable throughput before short-term sales maximization.

25. Operational knowledge should survive Employee and shift changes.

26. Cross-domain operational reasoning shall remain auditable.

---

# 151. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
OperationalContext

OperationalContextSnapshot

OperationalHealthAssessment

OperationalLoad

OperationalCapacity

EffectiveOperationalCapacity

CapacityConstraint

OperationalSignal

OperationalAnomaly

OperationalRisk

OperationalBottleneck

OperationalImpactAnalysis

CustomerCommitmentRiskReference

OperationalRecommendation

OperationalNextBestAction

KitchenStateReference

ProductionStateReference

InventoryStateReference

MaintenanceStateReference

ReservationStateReference

DeliveryStateReference

IncidentStateReference

ComplianceStateReference

OperationalAlert

OperationalBriefing

OperationalConflict

ExternalOperationalMapping

OperationalIntelligenceHistory
```

---

# 152. FIRST PRODUCTION INTELLIGENCE LOOP

The first implementation should prove this end-to-end loop:

```text
REAL-TIME DOMAIN EVENTS
        ↓
NORMALIZED OPERATIONAL STATE
        ↓
OPERATIONAL CONTEXT
        ↓
SIGNALS / CONSTRAINTS DETECTED
        ↓
CUSTOMER COMMITMENTS EVALUATED
        ↓
RISK / BOTTLENECK DETECTED
        ↓
NEXT-BEST OPERATIONAL ACTION
        ↓
HUMAN OR AUTHORIZED AUTOMATION
        ↓
OUTCOME OBSERVED
        ↓
OPERATIONAL KNOWLEDGE UPDATED
```

This loop is more important for production readiness than implementing advanced predictive optimization.

---

# 153. DEFERRED CAPABILITIES

Unless required by the first commercial pilot, defer:

```text
Advanced Multi-Agent Operational Control

Autonomous Restaurant Scheduling

Autonomous Dynamic Capacity Reallocation

Deep Predictive Bottleneck Models

Advanced Demand-Capacity Optimization

Reinforcement Learning Operations

Fully Autonomous Order Admission Control

Advanced Cross-Branch Resource Optimization

Predictive Staffing Optimization

Real-Time Digital Twin Simulation

Autonomous Incident Remediation

Autonomous Business Continuity Replanning
```

---

# 154. IMPLEMENTATION PRINCIPLE

This document defines the logical Operational Intelligence Model.

It does not prescribe:

* Data warehouse.
* Stream processor.
* Event bus.
* Digital Twin technology.
* Machine-learning algorithm.
* Monitoring vendor.
* BI platform.
* Graph database.
* Vector database.
* LLM.
* User interface.

Implementation shall preserve the semantic distinction between:

```text
OPERATIONAL FACT

OPERATIONAL CONTEXT

SIGNAL

ANOMALY

RISK

BOTTLENECK

PREDICTION

IMPACT

RECOMMENDATION

DECISION

ACTION

OUTCOME
```

---

# 155. ARCHITECTURAL PRINCIPLE

Operational Intelligence shall be implemented as a composition and reasoning layer over authoritative restaurant runtimes.

Conceptually:

```text
KITCHEN ──────────────┐
PRODUCTION ───────────┤
QUALITY ──────────────┤
INVENTORY ────────────┤
PURCHASING ───────────┤
INGREDIENTS ──────────┤
MAINTENANCE ──────────┤
RESERVATIONS ─────────┤
DINE-IN ──────────────┤
TAKE AWAY ────────────┤
DELIVERY ─────────────┤
EVENTS ───────────────┤
PAYMENTS ─────────────┤
CASH ─────────────────┤
INCIDENTS ────────────┤
COMPLIANCE ───────────┘
          │
          ▼
OPERATIONAL INTELLIGENCE
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
 CONTEXT  RISK  BOTTLENECK
    │     │     │
    └─────┼─────┘
          ▼
NEXT-BEST OPERATIONAL ACTION
          │
    ┌─────┼──────────┐
    ▼     ▼          ▼
 EMPLOYEE AGENT   AUTOMATION
    │     │          │
    └─────┼──────────┘
          ▼
        OUTCOME
          │
          ▼
       LEARNING
```

---

# 156. LONG-TERM STRATEGIC PRINCIPLE

Traditional restaurant systems record what happened.

Operational Intelligence must understand:

```text
WHAT IS HAPPENING

WHY IT MATTERS

WHAT WILL LIKELY HAPPEN NEXT

WHO WILL BE AFFECTED

WHAT SHOULD BE DONE
```

This capability is essential for transforming ECIP from an information system into the operational brain of the restaurant.

---

# 157. FINAL RULE

Before ECIP represents the restaurant as healthy, overloaded, degraded, at risk or requiring operational intervention, it shall be able to determine:

> What is the current authoritative state of each relevant operational domain?

> How fresh is that information?

> What is the current demand?

> What is the effective capacity?

> Which Resources are constrained?

> Where are queues growing?

> Which Bottlenecks are active?

> Which Equipment, Ingredients or Employees constrain operation?

> Are there Quality, Safety or Compliance restrictions?

> Are active Incidents already explaining the condition?

> Which Customer commitments are affected or likely to be affected?

> What future demand is expected?

> What risks are factual and what risks are predictive?

> What confidence supports each prediction?

> What alternatives or Workarounds are available?

> What operational action would create the best outcome?

> Does that Action require Human authorization?

> What happens if no Action is taken?

> What happened after the Action?

> Did the intervention improve the operational result?

> Can the complete path from operational evidence through context, risk, recommendation, Action and outcome be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably represent, explain, predict or optimize restaurant operation.

The objective of Operational Intelligence is not merely to tell management what happened.

The objective is to make the restaurant **continuously aware of its own operational state, capable of detecting problems before they become failures, and increasingly capable of protecting Customer commitments, Safety, Quality and profitability with minimal human intervention.**

