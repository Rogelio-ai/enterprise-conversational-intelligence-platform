# 16_Delivery.md

**Document ID:** RDM-016
**Document Name:** Delivery
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Delivery Service Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of restaurant orders fulfilled by delivery, from order creation and serviceability validation through kitchen preparation, dispatch, transportation, customer handoff and completion.

The Delivery Model connects:

* Customer identity.
* Delivery address.
* Delivery zone.
* Order.
* Product suitability.
* Pricing.
* Kitchen production.
* Packaging.
* Driver or delivery provider.
* Dispatch.
* Route and ETA.
* Payment.
* Customer notifications.
* Customer history.
* Loyalty.
* Conversational context.
* Operational intelligence.

Delivery shall be modeled as a distinct fulfillment domain rather than as a Take Away Order with transportation added afterward.

---

# 2. OBJECTIVES

The Delivery Model enables ECIP to:

* Validate whether an address can be served.
* Select the appropriate Branch.
* Calculate delivery eligibility.
* Estimate delivery time.
* Resolve delivery fees.
* Coordinate kitchen preparation and dispatch.
* Assign internal or external delivery resources.
* Track delivery progress.
* Notify customers.
* Support contactless delivery.
* Support scheduled delivery.
* Handle failed delivery attempts.
* Handle delays and incidents.
* Preserve delivery evidence.
* Support customer service conversations.
* Support operational capacity management.
* Improve delivery profitability and service quality.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Location
* Contact Point
* Action Request
* Action Authorization
* Action Execution
* Workflow Instance
* Task
* Commitment
* Conversation
* Context Snapshot
* External System
* Connector
* External Entity Reference
* Customer History Event

Restaurant-specific Delivery entities remain within the Restaurant Domain Pack.

---

# 4. DELIVERY PRINCIPLE

A Delivery represents a governed fulfillment process in which a confirmed restaurant Order is transported from an authorized fulfillment location to a Customer-defined destination.

The platform shall distinguish between:

```text
Order

Delivery Fulfillment

Kitchen Production

Packaging

Dispatch

Delivery Resource

Route

ETA

Customer Handoff

Payment

Completion
```

These concepts are related but independently traceable.

---

# 5. DELIVERY ORDER

A `DeliveryOrder` extends the Restaurant Order with delivery-specific fulfillment information.

Typical attributes include:

* Order ID
* Customer
* Origin Branch
* Delivery Address
* Delivery Zone
* Delivery Method
* Delivery Provider
* Driver
* Vehicle
* Requested Delivery Time
* Estimated Ready Time
* Dispatch Time
* Estimated Arrival Time
* Promised Delivery Window
* Actual Delivery Time
* Delivery Fee
* Delivery Status
* Payment Status
* Packaging Status
* Contactless Delivery preference
* Delivery instructions
* Conversation references

---

# 6. DELIVERY FULFILLMENT

A `DeliveryFulfillment` represents the operational execution required to transport and hand over an Order.

Typical attributes:

* Fulfillment ID
* Order
* Origin
* Destination
* Delivery Zone
* Method
* Provider
* Assigned resource
* Status
* Requested window
* Promised window
* Dispatch time
* Current ETA
* Delivery time
* Completion evidence
* Exceptions

---

# 7. DELIVERY METHODS

Initial methods may include:

```text
INTERNAL_DRIVER

INTERNAL_MOTORCYCLE

INTERNAL_VEHICLE

THIRD_PARTY_COURIER

DELIVERY_PLATFORM

CUSTOM_LOGISTICS_PROVIDER
```

The Delivery Model shall remain independent of provider-specific implementations.

---

# 8. DELIVERY ADDRESS

A `DeliveryAddress` represents the destination for a Delivery.

Typical attributes include:

* Address ID
* Customer
* Recipient name
* Street
* Exterior number
* Interior number
* Neighborhood
* City
* State
* Postal code
* Country
* Geographic coordinates
* Reference instructions
* Access instructions
* Delivery notes
* Verification status

Address information shall be collected only to the level required for fulfillment.

---

# 9. ADDRESS VALIDATION

Address validation may include:

* Required fields.
* Postal normalization.
* Geographic validation.
* Delivery-zone membership.
* Customer confirmation.
* External geocoding.

An address being syntactically valid does not imply it is serviceable.

---

# 10. ADDRESS CONFIDENCE

Where coordinates or normalized addresses are derived automatically, confidence should be preserved.

Possible states:

```text
CONFIRMED

HIGH_CONFIDENCE

AMBIGUOUS

UNVERIFIED
```

Ambiguous addresses may require customer clarification.

---

# 11. ADDRESS INSTRUCTIONS

Delivery instructions may include:

* Gate access.
* Building name.
* Floor.
* Apartment.
* Reception desk.
* Landmark.
* Contactless location.

Free text shall be treated carefully and shall not override safety or legal policies.

---

# 12. SAVED DELIVERY ADDRESS

Customers may retain frequently used addresses where consent and policy allow.

Examples:

* Home.
* Office.
* Family address.

Saved addresses shall remain independently editable and revocable.

---

# 13. DELIVERY ZONE

A `DeliveryZone` represents a geographical service area.

Typical attributes:

* Zone ID
* Branch
* Geometry
* Status
* Delivery fee rule
* Minimum order
* Estimated transit baseline
* Service schedule
* Provider eligibility

Zones may be represented as:

* Polygon.
* Radius.
* Postal codes.
* Administrative regions.
* Provider-defined areas.

---

# 14. OVERLAPPING DELIVERY ZONES

Multiple Branches may serve the same destination.

Branch selection may consider:

* Product availability.
* Kitchen capacity.
* Delivery capacity.
* Distance.
* Estimated total time.
* Pricing.
* Branch policy.

Branch assignment shall be deterministic and explainable.

---

# 15. DELIVERY SERVICEABILITY

`DeliveryServiceability` represents whether a requested destination and Order can be delivered.

Suggested states:

```text
SERVICEABLE

SERVICEABLE_WITH_CONDITIONS

TEMPORARILY_UNAVAILABLE

OUTSIDE_SERVICE_AREA

NOT_SERVICEABLE
```

---

# 16. SERVICEABILITY RESOLUTION

Conceptually:

```text
Valid Address
+
Active Delivery Zone
+
Branch Open
+
Delivery Service Active
+
Products Delivery-Eligible
+
Delivery Capacity Available
+
Policy Requirements Met
=
Potentially Serviceable
```

---

# 17. DELIVERY BRANCH SELECTION

The selected Branch becomes the operational origin.

Selection may depend on:

* Address.
* Zone.
* Product availability.
* Inventory.
* Kitchen workload.
* Driver capacity.
* Distance.
* Service level.

A Branch shall not be assigned solely because it is geographically closest.

---

# 18. DELIVERY PRODUCT SUITABILITY

Products may define:

```text
SUITABLE

CONDITIONALLY_SUITABLE

NOT_RECOMMENDED

NOT_ALLOWED
```

Delivery suitability may depend on:

* Quality window.
* Packaging.
* Temperature.
* Travel distance.
* Product stability.

---

# 19. DELIVERY PRODUCT RESTRICTIONS

Examples:

* Dine-in only Products.
* Products with very short quality window.
* Products requiring age verification.
* Products prohibited by Delivery provider.

Restrictions shall be resolved before Order confirmation.

---

# 20. DELIVERY PACKAGING

Delivery Packaging shall consider:

* Product containment.
* Temperature separation.
* Leakage prevention.
* Tamper protection.
* Beverage stability.
* Transport duration.

Packaging requirements derive from Product and Recipe context.

---

# 21. DELIVERY PACKAGING STATUS

Suggested states:

```text
PENDING

IN_PROGRESS

COMPLETED

VERIFIED
```

Kitchen completion alone does not imply dispatch readiness.

---

# 22. DELIVERY BAG / CONTAINER

A Delivery may group Order Items into one or more physical packages.

A `DeliveryPackage` may contain:

* Package ID
* Order Items
* Temperature classification
* Seal ID
* Label
* Weight
* Handoff status

---

# 23. TAMPER EVIDENCE

Where applicable, delivery Packages may use:

* Tamper seal.
* Security label.
* Packaging verification.

Tamper evidence may become part of fulfillment quality control.

---

# 24. DELIVERY FEE

Delivery fee may depend on:

* Zone.
* Distance.
* Order value.
* Customer Loyalty.
* Promotion.
* Provider.
* Time.
* Demand.

Pricing authority remains governed by `12_Pricing_and_Promotions.md`.

---

# 25. MINIMUM ORDER

A Delivery Zone or provider may define a minimum commercial amount.

Eligibility shall be evaluated before Order confirmation.

---

# 26. FREE DELIVERY

Free Delivery may result from:

* Promotion.
* Loyalty benefit.
* Minimum Order threshold.
* Corporate agreement.

Free Delivery changes Price.

It does not remove operational delivery constraints.

---

# 27. REQUESTED DELIVERY TIME

Customers may request:

* Immediate delivery.
* Scheduled delivery.
* Delivery window.

Example:

```text
"Please deliver between 7:30 and 8:00 PM."
```

The requested time is not yet a promise.

---

# 28. IMMEDIATE DELIVERY

Immediate Delivery means fulfillment should begin as soon as operationally feasible.

ECIP shall estimate total time before confirmation.

---

# 29. SCHEDULED DELIVERY

A Scheduled Delivery is intended for a future date or time.

Typical attributes:

* Requested date.
* Requested window.
* Preparation start time.
* Dispatch target.
* Provider reservation if applicable.

---

# 30. PROMISED DELIVERY WINDOW

A `PromisedDeliveryWindow` represents the customer-facing delivery commitment.

Example:

```text
19:20–19:40
```

The promised window shall be based on authorized operational logic.

---

# 31. DELIVERY ETA

Delivery ETA is an estimate of arrival.

It may depend on:

* Kitchen readiness.
* Packaging.
* Dispatch queue.
* Driver availability.
* Route.
* Distance.
* Traffic information when available.
* Historical performance.

---

# 32. ESTIMATE VS COMMITMENT

The platform shall distinguish:

```text
Estimated Arrival Time

from

Promised Delivery Window
```

Changes to estimates shall not silently rewrite historical customer commitments.

---

# 33. END-TO-END DELIVERY TIME

Conceptually:

```text
Total Delivery Time
=
Kitchen Preparation
+
Packaging
+
Dispatch Waiting
+
Transportation
+
Customer Handoff
```

This decomposition is essential for root-cause analysis.

---

# 34. DELIVERY CAPACITY

Delivery capacity may depend on:

* Drivers.
* Vehicles.
* Third-party provider availability.
* Dispatch workload.
* Delivery-zone demand.
* Active trips.
* Branch workload.

---

# 35. DELIVERY CAPACITY STATUS

Suggested states:

```text
AVAILABLE

BUSY

LIMITED

SATURATED

UNAVAILABLE
```

---

# 36. DRIVER

A `DeliveryDriver` extends the Employee/Resource model where the driver is restaurant-controlled.

Typical operational attributes:

* Employee or resource ID
* Availability
* Current assignment
* Vehicle
* Current workload
* Service zones
* Shift
* Skills or certifications

---

# 37. EXTERNAL DRIVER

Third-party drivers remain external resources.

The platform should preserve:

* Provider.
* External driver reference.
* Assignment.
* Status.

ECIP shall not assume employee-level ownership over third-party resources.

---

# 38. VEHICLE

Delivery Vehicles may include:

* Motorcycle.
* Bicycle.
* Car.
* Van.

Vehicle suitability may depend on:

* Distance.
* Package size.
* Weather.
* Capacity.

---

# 39. DELIVERY ASSIGNMENT

A `DeliveryAssignment` associates a Delivery Fulfillment with a Delivery Resource.

Typical attributes:

* Fulfillment
* Driver/provider
* Vehicle
* Assignment time
* Status
* Accepted time
* Released time

---

# 40. ASSIGNMENT STRATEGY

Assignment may consider:

* Availability.
* Distance.
* Capacity.
* Zone.
* Active workload.
* Provider policy.

Advanced optimization may be implemented later.

---

# 41. DELIVERY BATCHING

A Driver may transport multiple compatible Orders on one route.

Batching shall consider:

* Quality windows.
* Route compatibility.
* Promised delivery times.
* Package constraints.

Customer experience shall not be sacrificed solely for logistical efficiency.

---

# 42. DISPATCH

`Dispatch` represents release of a prepared Delivery to transportation.

Before dispatch, verify:

```text
Order Complete
+
Packaging Verified
+
Delivery Resource Assigned
+
Address Valid
+
Required Payment State
=
Dispatch Eligible
```

---

# 43. DISPATCH STATUS

Suggested lifecycle:

```text
PENDING
→ RESOURCE_ASSIGNED
→ READY_TO_DISPATCH
→ DISPATCHED
```

---

# 44. DRIVER PICKUP

Driver pickup represents transfer from restaurant operations to delivery transportation.

This should preserve:

* Time.
* Driver.
* Packages.
* Verification.
* Exceptions.

---

# 45. DELIVERY ROUTE

A `DeliveryRoute` may represent:

* Origin.
* Destination.
* Ordered stops.
* Expected distance.
* Expected travel time.

Route calculation may be delegated to external routing services.

---

# 46. ROUTE OPTIMIZATION

Advanced route optimization may consider:

* Multiple Orders.
* Traffic.
* Distance.
* Delivery windows.
* Vehicle.
* Quality limits.

This is not required in the initial MVP.

---

# 47. DELIVERY TRACKING

Tracking may expose appropriate states such as:

```text
ORDER_CONFIRMED

PREPARING

READY

DRIVER_ASSIGNED

OUT_FOR_DELIVERY

NEAR_DESTINATION

DELIVERED
```

Customer-facing states should remain simple and understandable.

---

# 48. LOCATION TRACKING

Real-time location may be available for delivery resources.

Location collection shall comply with:

* Employee/privacy policies.
* Provider agreements.
* Purpose limitation.

Tracking shall not exceed operational necessity.

---

# 49. CUSTOMER DELIVERY NOTIFICATIONS

Notifications may include:

* Order confirmation.
* Estimated delivery window.
* Delay.
* Driver dispatch.
* Near-arrival.
* Delivery completion.

Notification policy shall respect customer preferences and consent.

---

# 50. CUSTOMER STATUS INQUIRY

ECIP should support:

```text
"Where is my order?"

"Has it left the restaurant?"

"How much longer?"

"Who is delivering it?"
```

Responses shall use authoritative status and current estimates.

---

# 51. DELAY

A `DeliveryDelay` represents material deviation from the promised or expected timeline.

Potential sources:

* Kitchen.
* Packaging.
* Driver assignment.
* Traffic.
* Address issue.
* Customer unavailable.
* Provider failure.

---

# 52. DELAY ROOT CAUSE

The platform should distinguish:

```text
PREPARATION_DELAY

PACKAGING_DELAY

DISPATCH_DELAY

TRANSPORT_DELAY

ADDRESS_DELAY

CUSTOMER_HANDOFF_DELAY

UNKNOWN
```

This enables better operations and customer communication.

---

# 53. PROACTIVE DELAY COMMUNICATION

Where authorized, ECIP may notify the Customer before they ask.

Example:

```text
"Your order is taking approximately 15 minutes longer than expected because preparation is delayed. The updated estimated arrival is 8:25 PM."
```

The reason should only be stated when known.

---

# 54. ETA UPDATE

Updated ETAs shall preserve:

* Previous estimate.
* New estimate.
* Timestamp.
* Reason where known.

This supports service-level analysis.

---

# 55. CONTACTLESS DELIVERY

A Customer may request contactless handoff.

Typical information:

* Drop-off point.
* Instructions.
* Completion evidence.
* Notification.

Contactless delivery does not remove identity or restricted-product requirements where applicable.

---

# 56. CUSTOMER HANDOFF

A `DeliveryHandoff` represents transfer of the Order to the Customer or authorized recipient.

Typical attributes:

* Delivery
* Recipient
* Handoff time
* Verification
* Handoff method
* Completion evidence
* Exception

---

# 57. DELIVERY RECIPIENT

The recipient may be:

* Customer.
* Family member.
* Receptionist.
* Authorized third party.

Recipient verification requirements depend on Order risk.

---

# 58. DELIVERY VERIFICATION

Possible verification mechanisms:

* Customer confirmation.
* Delivery code.
* Signature.
* Employee/provider confirmation.
* Application confirmation.

Sensitive or age-restricted Orders may require stronger verification.

---

# 59. DELIVERY PROOF

Delivery completion evidence may include:

* Delivery code.
* Signature.
* Provider confirmation.
* Timestamp.
* Customer confirmation.
* Photo where permitted by policy.

Proof requirements shall be proportional and privacy-aware.

---

# 60. FAILED DELIVERY ATTEMPT

Reasons may include:

* Customer unavailable.
* Incorrect address.
* Access denied.
* Unable to contact Customer.
* Safety issue.
* Recipient refused Order.

A failed attempt shall create an explicit exception state.

---

# 61. DELIVERY RETRY

Retry policy may support:

* Immediate retry.
* Customer contact.
* Rescheduling.
* Return to restaurant.
* Cancellation.

The appropriate action depends on Product condition and business policy.

---

# 62. RETURN TO RESTAURANT

A failed Delivery may require returning the Order.

The platform shall preserve:

* Return reason.
* Time.
* Product condition.
* Refund implications.

---

# 63. DELIVERY CANCELLATION

Cancellation rules may depend on whether the Delivery is:

* Before preparation.
* In preparation.
* Ready.
* Dispatched.
* Near destination.

Later stages generally carry higher operational impact.

---

# 64. CANCELLATION AFTER DISPATCH

Cancellation after dispatch may require:

* Human approval.
* Driver rerouting.
* Refund decision.
* Product disposition.

AI shall not invent exceptions.

---

# 65. DELIVERY MODIFICATION

Some modifications may be allowed before dispatch.

Examples:

* Delivery instructions.
* Recipient.
* Contact number.
* Address correction.

Changing the actual destination may require revalidation of:

* Zone.
* Fee.
* Branch.
* ETA.
* Provider eligibility.

---

# 66. ADDRESS CHANGE AFTER CONFIRMATION

A new address may require:

```text
New Address
    ↓
Revalidation
    ↓
Delivery Zone Resolution
    ↓
Price / Fee Recalculation
    ↓
Operational Feasibility
    ↓
Customer Confirmation
```

---

# 67. ADDRESS CHANGE AFTER DISPATCH

This is a high-impact mutation.

It may require:

* Driver approval.
* Dispatcher intervention.
* Additional fee.
* Route update.
* Customer confirmation.

---

# 68. CUSTOMER UNAVAILABLE

If the Customer cannot receive the Order:

* Attempt contact.
* Follow waiting policy.
* Record evidence.
* Decide retry/return/escalation.

Waiting indefinitely is not a valid implicit state.

---

# 69. DELIVERY INCIDENT

Examples:

* Driver accident.
* Product damaged.
* Package opened.
* Wrong Order.
* Missing Item.
* Delivery significantly delayed.
* Payment problem.
* Provider outage.

Incidents shall link to Operational Incident management.

---

# 70. WRONG ORDER

Delivery of an incorrect Order is a critical fulfillment defect.

The system should support:

* Incident record.
* Replacement.
* Recovery Delivery.
* Refund.
* Customer follow-up.

---

# 71. MISSING ITEM

A Customer may report missing Items after Delivery.

ECIP should be able to:

* Identify Order.
* Identify expected contents.
* Record missing Item.
* Evaluate recovery policy.
* Escalate or execute authorized action.

---

# 72. DAMAGED PRODUCT

Product damage may result from:

* Packaging.
* Transportation.
* Handling.
* Delay.

Root cause should be recorded when determinable.

---

# 73. TEMPERATURE / QUALITY ISSUE

Delivery complaints may include:

* Food arrived cold.
* Product melted.
* Drink spilled.
* Food degraded.

These contribute to Quality Control and Delivery Intelligence.

---

# 74. DELIVERY SERVICE RECOVERY

Possible recovery actions:

* Replacement delivery.
* Partial refund.
* Full refund.
* Authorized credit.
* Loyalty benefit.
* Manager follow-up.

All commercial mutations shall be governed.

---

# 75. PAYMENT

Detailed Payment behavior belongs to `26_Payments.md`.

Delivery may support:

* Prepaid.
* Payment on delivery.
* Mixed methods where allowed.

---

# 76. PAYMENT ON DELIVERY

Where permitted, Payment may be collected by:

* Internal Driver.
* Delivery provider.
* Mobile terminal.

Payment completion must be authoritative and reconciled.

---

# 77. CASH ON DELIVERY

Cash handling may require:

* Driver cash responsibility.
* Change.
* Cash reconciliation.
* Security rules.

Detailed Cash behavior belongs to `28_Cash_Management.md`.

---

# 78. DELIVERY PROMOTIONS

Promotions may affect:

* Product prices.
* Delivery fee.
* Minimum Order.
* Bundles.

Eligibility shall be revalidated when Order or destination changes materially.

---

# 79. DELIVERY LOYALTY

Delivery Orders may:

* Earn loyalty value.
* Redeem rewards.
* Receive loyalty delivery benefits.

The Loyalty domain remains authoritative.

---

# 80. CUSTOMER PREFERENCES

Relevant delivery preferences may include:

* Preferred address.
* Preferred Branch.
* Contactless delivery.
* Delivery instructions.
* Preferred notification channel.

Preferences shall not override current feasibility or safety.

---

# 81. CUSTOMER HISTORY

Completed Delivery contributes historical evidence such as:

* Address usage.
* Order history.
* Delivery time.
* Delays.
* Complaints.
* Preferred service patterns.

Historical behavior shall not automatically become a confirmed preference.

---

# 82. CONVERSATIONAL DELIVERY

ECIP should support interactions such as:

```text
"Can you deliver to my office?"

"How long will it take?"

"Where is my order?"

"Please leave it with reception."

"I'm at a different address now."

"An item is missing."

"The food arrived cold."
```

Each request shall map to governed information or Action workflows.

---

# 83. SALES INTELLIGENCE

Delivery context may support:

* Delivery-compatible recommendations.
* Bundles.
* Beverage additions.
* Free-delivery threshold suggestions.

Recommendations shall account for:

* Delivery suitability.
* Quality window.
* Packaging.
* Delivery ETA.

---

# 84. DELIVERY-AWARE RECOMMENDATION

A Product that is excellent for Dine-In may be a poor Delivery recommendation.

Recommendation Intelligence shall use Delivery suitability and expected transit time.

---

# 85. OPERATIONAL INTELLIGENCE

Delivery provides signals for:

* Zone demand.
* Driver utilization.
* Branch fulfillment performance.
* Delay causes.
* Provider performance.
* Delivery capacity.
* Average transit time.
* Customer handoff time.

---

# 86. DELIVERY PERFORMANCE

Potential metrics include:

* Order-to-ready time.
* Ready-to-dispatch time.
* Dispatch-to-delivery time.
* End-to-end delivery time.
* On-time rate.
* Failed delivery rate.
* Cost per delivery.
* Complaints per delivery.
* Provider success rate.

---

# 87. DELIVERY SLA

Service objectives may define:

* Maximum preparation-to-dispatch delay.
* Delivery window compliance.
* Failed-attempt response.

SLA may vary by Zone, provider or service level.

---

# 88. DELIVERY PROVIDER

A `DeliveryProvider` represents an external logistics provider.

Typical attributes:

* Provider ID
* Name
* Connector
* Coverage
* Service status
* Supported Branches
* Capabilities

---

# 89. PROVIDER CAPABILITY

Capabilities may include:

* Dispatch request.
* Driver assignment.
* Real-time tracking.
* ETA.
* Proof of delivery.
* Cancellation.
* Webhook events.

Provider capabilities shall be normalized behind the Integration layer.

---

# 90. PROVIDER HEALTH

Provider status may be:

```text
OPERATIONAL

DEGRADED

UNAVAILABLE
```

A degraded provider may affect current delivery offerability.

---

# 91. PROVIDER FALLBACK

If configured, ECIP may select another authorized provider when the primary provider is unavailable.

Fallback shall consider:

* Price.
* Coverage.
* ETA.
* Policy.

---

# 92. DELIVERY PLATFORM ORDER

Some Orders may originate in third-party Delivery Platforms.

The platform shall distinguish:

* Order origin.
* Delivery fulfillment provider.
* System of record.

These are not necessarily the same entity.

---

# 93. SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Order authority

ECIP:
Delivery orchestration

External Provider:
Driver and route authority

Payment Gateway:
Payment authority
```

Ownership shall be explicitly configured.

---

# 94. EXTERNAL DELIVERY MAPPING

External identifiers may include:

* Provider Delivery ID.
* Driver ID.
* Route ID.
* Tracking ID.
* Platform Order ID.

Canonical ECIP identities shall remain primary internally.

---

# 95. DELIVERY SYNCHRONIZATION

Synchronization may include:

* Assignment status.
* Driver status.
* Dispatch.
* ETA.
* Delivery completion.
* Failure.
* Cancellation.

Synchronization shall be idempotent and observable.

---

# 96. OUT-OF-ORDER EVENTS

External providers may send events late or out of sequence.

Example:

```text
Delivered webhook
arrives before
OutForDelivery webhook
```

Event handling shall preserve monotonic business correctness where appropriate.

---

# 97. DELIVERY CONFLICT

Possible conflicts:

* ECIP considers Delivery active while provider marks cancelled.
* Provider says Delivered but Customer disputes receipt.
* Driver assigned after Order cancellation.

Conflicts shall create explicit resolution workflows.

---

# 98. DELIVERY IDEMPOTENCY

Provider calls such as:

* Create Delivery.
* Cancel Delivery.
* Reassign Delivery.

shall use idempotency where supported.

Duplicate external deliveries are critical defects.

---

# 99. DELIVERY AUDIT

Material actions shall preserve:

* Actor.
* Source.
* Timestamp.
* Previous state.
* New state.
* External response.
* Correlation ID.
* Trace ID.

---

# 100. DELIVERY EVENTS

Initial domain events include:

```text
DeliveryRequested
DeliveryServiceabilityEvaluated
DeliveryServiceable
DeliveryRejected

DeliveryBranchAssigned
DeliveryZoneAssigned

DeliveryFulfillmentCreated

DeliveryTimeRequested
DeliveryWindowPromised
DeliveryETAUpdated

DeliveryPackagingStarted
DeliveryPackagingCompleted

DeliveryReadyForDispatch

DeliveryResourceRequested
DeliveryDriverAssigned
DeliveryDriverAssignmentFailed

DeliveryDispatchStarted
DeliveryDispatched

DeliveryOutForDelivery
DeliveryNearDestination

DeliveryCustomerContactAttempted

DeliveryHandoffStarted
DeliveryHandoffCompleted
DeliveryCompleted

DeliveryDelayDetected

DeliveryAddressChangeRequested
DeliveryAddressChanged

DeliveryFailedAttempt
DeliveryRetryScheduled
DeliveryReturnedToRestaurant

DeliveryCancellationRequested
DeliveryCancelled

DeliveryIncidentDetected

DeliveryMissingItemReported
DeliveryQualityIssueReported

DeliveryServiceRecoveryStarted
DeliveryServiceRecoveryCompleted

DeliverySynchronizationStarted
DeliverySynchronizationCompleted
DeliverySynchronizationFailed

DeliveryConflictDetected
DeliveryConflictResolved
```

---

# 101. RELATIONSHIPS

```text
Customer
    PLACES Order

Order
    HAS DeliveryFulfillment

DeliveryFulfillment
    ORIGINATES_AT Branch

DeliveryFulfillment
    DELIVERS_TO DeliveryAddress

DeliveryAddress
    BELONGS_TO DeliveryZone

DeliveryFulfillment
    MAY_USE DeliveryProvider

DeliveryFulfillment
    MAY_HAVE DeliveryAssignment

DeliveryAssignment
    REFERENCES DeliveryDriver

DeliveryDriver
    MAY_OPERATE Vehicle

DeliveryFulfillment
    CONTAINS DeliveryPackage

DeliveryFulfillment
    HAS PromisedDeliveryWindow

DeliveryFulfillment
    MAY_HAVE DeliveryRoute

DeliveryFulfillment
    COMPLETES_WITH DeliveryHandoff

Conversation
    MAY_REFERENCE DeliveryFulfillment

DeliveryFulfillment
    MAY_CREATE Commitment

DeliveryFulfillment
    MAY_GENERATE CustomerHistoryEvent

DeliveryFulfillment
    MAPS_TO ExternalEntityReference
```

---

# 102. BUSINESS RULES

The following rules apply:

1. Delivery is a fulfillment mode extending the Order model.

2. Every confirmed Delivery shall have one operational origin Branch.

3. Delivery address validity does not imply serviceability.

4. Delivery Zone applicability shall be verified before commitment.

5. All ordered Products shall be eligible for Delivery.

6. Delivery fee shall be determined through governed Pricing rules.

7. Requested Delivery Time and Promised Delivery Window are separate concepts.

8. Estimated ETA shall remain distinguishable from customer commitment.

9. Kitchen completion shall not automatically imply dispatch readiness.

10. Required Packaging shall be completed before normal dispatch.

11. A Delivery resource shall be assigned before dispatch where required.

12. Delivery status from external providers shall be normalized and audited.

13. AI shall not invent driver status, ETA or proof of delivery.

14. Address changes shall trigger appropriate serviceability and pricing revalidation.

15. Known Product quality windows shall constrain delivery feasibility.

16. Payment requirements shall be respected before or during handoff according to policy.

17. Failed Delivery attempts shall create explicit resolution state.

18. Customer complaints shall not silently overwrite authoritative provider evidence; disputes shall remain explicit.

19. External IDs shall not replace canonical Delivery identities.

20. Material Delivery actions shall use governed authorization and remain auditable.

---

# 103. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
DeliveryFulfillment

DeliveryAddress

DeliveryZone

DeliveryServiceability

DeliveryMethod

OriginBranchAssignment

RequestedDeliveryTime

PromisedDeliveryWindow

DeliveryETA

DeliveryFeeReference

DeliveryPackage

DeliveryProvider

DeliveryAssignment

Dispatch

DeliveryStatus

DeliveryHandoff

FailedDeliveryAttempt

DeliveryDelay

DeliveryCancellation

DeliveryConversationReference

ExternalDeliveryMapping

DeliveryHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Dynamic Route Optimization

Multi-Order Route Batching Optimization

Predictive Traffic Models

Autonomous Provider Arbitrage

Advanced Geospatial Demand Forecasting

Real-Time Driver Location Intelligence Beyond Operational Need

Autonomous Delivery Network Optimization
```

---

# 104. IMPLEMENTATION PRINCIPLE

This document defines the logical Delivery Service Model.

It does not prescribe:

* Routing provider.
* Maps provider.
* Geocoding implementation.
* Driver Mobile App.
* POS schema.
* Delivery-platform integration.
* Payment implementation.
* Optimization algorithm.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
ORDER

DELIVERY SERVICEABILITY

DELIVERY FULFILLMENT

PACKAGING

DISPATCH

DELIVERY RESOURCE

ROUTE

ETA

HANDOFF

PAYMENT

FULFILLMENT COMPLETION
```

---

# 105. FINAL RULE

Before ECIP commits to, updates or completes a Delivery, it shall be able to determine:

> Who is placing and receiving the Order?

> What is the validated Delivery Address?

> Which Delivery Zone applies?

> Which Branch should fulfill the Order?

> Are all Products actually suitable and available for Delivery?

> What Delivery fee and commercial conditions apply?

> What Delivery time can reasonably be promised?

> Is the Kitchen and Delivery operation capable of fulfilling that promise?

> Has Packaging been completed correctly?

> Which Delivery resource or provider is responsible?

> What is the latest authoritative status and ETA?

> Has the Customer requested any material address or fulfillment change?

> Was the Order actually handed to the correct recipient?

> Are there unresolved delays, quality issues, Payment problems or disputes?

> Can every material Delivery decision and Action be reconstructed and audited?

Only after these conditions are resolved may ECIP represent the Delivery as correctly committed, in progress or successfully completed.

