# 15_Take_Away.md

**Document ID:** RDM-015
**Document Name:** Take Away
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Take Away Service Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of restaurant orders prepared for customer pickup, from order creation and scheduling through preparation, readiness, customer arrival, handoff and completion.

The Take Away Model connects:

* Customer identity.
* Order.
* Product availability.
* Kitchen production.
* Pickup scheduling.
* Packaging.
* Customer notifications.
* Customer arrival.
* Pickup handoff.
* Payment.
* Customer history.
* Loyalty.
* Conversational context.
* Operational intelligence.

Take Away shall be modeled as a distinct fulfillment mode and not merely as a Dine-In Order without a table.

---

# 2. OBJECTIVES

The Take Away Model enables ECIP to:

* Create pickup orders.
* Schedule pickup times.
* Estimate readiness.
* Coordinate kitchen preparation.
* Track packaging.
* Notify customers when orders are ready.
* Detect customer arrival.
* Coordinate curbside or in-store pickup.
* Verify the correct customer or authorized recipient.
* Support delayed pickup.
* Support order changes before preparation.
* Support cancellation policies.
* Support payment before or at pickup.
* Track handoff completion.
* Preserve customer history.
* Support conversational pickup assistance.
* Improve pickup operational capacity.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Action Request
* Action Authorization
* Action Execution
* Commitment
* Conversation
* Context Snapshot
* Workflow Instance
* Task
* Location
* Notification
* External Entity Reference
* Customer History Event

Restaurant-specific Take Away entities remain within the Restaurant Domain Pack.

---

# 4. TAKE AWAY PRINCIPLE

A Take Away experience represents a governed fulfillment process in which a Customer receives a prepared Order at a restaurant-controlled pickup point.

The platform shall distinguish between:

```text
Order

Pickup Fulfillment

Kitchen Production

Packaging

Customer Arrival

Handoff

Payment

Completion
```

These concepts are related but shall remain independently traceable.

---

# 5. TAKE AWAY ORDER

A `TakeAwayOrder` extends the canonical Restaurant Order with pickup-specific fulfillment information.

Typical attributes include:

* Order ID
* Customer
* Branch
* Pickup Location
* Pickup Method
* Requested Pickup Time
* Estimated Ready Time
* Promised Pickup Time
* Actual Ready Time
* Customer Arrival Time
* Handoff Time
* Pickup Status
* Payment Status
* Packaging Status
* Recipient
* Conversation references

---

# 6. PICKUP FULFILLMENT

A `PickupFulfillment` represents the operational lifecycle required to deliver a Take Away Order to the Customer.

Typical attributes:

* Fulfillment ID
* Order
* Branch
* Pickup Point
* Pickup method
* Status
* Requested window
* Promised window
* Ready time
* Arrival state
* Handoff verification
* Completion time

---

# 7. PICKUP METHODS

Initial pickup methods may include:

```text
IN_STORE

COUNTER_PICKUP

DEDICATED_PICKUP_AREA

CURBSIDE

DRIVE_THROUGH_PICKUP

LOCKER

AUTHORIZED_THIRD_PARTY_PICKUP
```

The supported methods depend on Branch capabilities.

---

# 8. PICKUP LOCATION

A `PickupLocation` represents the physical point where the Order is handed to the Customer.

Examples:

* Main counter
* Dedicated pickup counter
* Curbside zone
* Drive-through window
* Locker area
* Reception

Pickup Locations extend the Restaurant Locations model.

---

# 9. PICKUP LOCATION STATUS

Suggested states:

```text
OPEN

BUSY

LIMITED_CAPACITY

CLOSED

OUT_OF_SERVICE
```

Closed Pickup Locations shall not accept new commitments.

---

# 10. PICKUP CAPACITY

Pickup capacity may depend on:

* Number of active Orders.
* Available staff.
* Physical holding space.
* Packaging capacity.
* Customer queue.
* Parking or curbside slots.

Capacity contributes to Operational Context.

---

# 11. PICKUP ORDER LIFECYCLE

Suggested high-level lifecycle:

```text
DRAFT
→ CONFIRMED
→ SCHEDULED
→ IN_PREPARATION
→ PACKAGING
→ READY_FOR_PICKUP
→ CUSTOMER_ARRIVED
→ HANDED_OFF
→ COMPLETED
```

Alternative states include:

```text
CANCELLED
REJECTED
EXPIRED
NO_SHOW
FAILED
```

---

# 12. IMMEDIATE PICKUP

An Immediate Pickup Order is intended for preparation as soon as operationally feasible.

ECIP shall calculate a realistic readiness estimate before confirmation.

---

# 13. SCHEDULED PICKUP

A Scheduled Pickup Order is intended for a future time.

Typical attributes:

* Requested date.
* Requested pickup window.
* Preparation start window.
* Advance-order requirement.

Scheduling shall consider future Branch and Kitchen capacity.

---

# 14. PICKUP WINDOW

A Pickup Window may represent:

```text
12:30–12:40
```

rather than a single exact minute.

Windows may improve operational reliability during peak demand.

---

# 15. REQUESTED PICKUP TIME

The Customer may request a specific time.

Example:

```text
"I'd like to pick it up at 7:00 PM."
```

The requested time does not become a commitment until operational feasibility is validated.

---

# 16. ESTIMATED READY TIME

Estimated Ready Time represents the current operational prediction.

It may depend on:

* Product Recipes.
* Current Kitchen workload.
* Order size.
* Packaging.
* Queue.
* Staffing.
* Equipment availability.

---

# 17. PROMISED PICKUP TIME

Promised Pickup Time represents the time or window communicated as a business commitment.

It shall be based on authorized operational logic.

---

# 18. ESTIMATE VS PROMISE

The model shall distinguish:

```text
Estimated Ready Time
```

from:

```text
Promised Pickup Time
```

A changing estimate does not silently rewrite an existing customer commitment.

---

# 19. TAKE AWAY ORDER CONFIRMATION

Before confirmation, ECIP shall verify:

* Branch open.
* Pickup service active.
* Products offerable.
* Pricing valid.
* Customer restrictions considered.
* Kitchen capacity sufficient.
* Pickup capacity sufficient.
* Requested timing feasible.
* Payment requirements satisfied where applicable.

---

# 20. PRODUCT SUITABILITY

Products may define Take Away suitability.

Suggested states:

```text
SUITABLE

CONDITIONALLY_SUITABLE

NOT_RECOMMENDED

NOT_ALLOWED
```

Product eligibility shall be respected before confirmation.

---

# 21. PACKAGING REQUIREMENT

A Take Away Order may require Packaging.

Examples:

* Food container.
* Beverage cup.
* Bag.
* Insulated container.
* Cutlery.
* Napkins.
* Tamper seal.

Packaging requirements may derive from Product and Order composition.

---

# 22. PACKAGING STATUS

Suggested lifecycle:

```text
NOT_REQUIRED

PENDING

IN_PROGRESS

COMPLETED

VERIFIED
```

---

# 23. PACKAGING ITEM

A `PackagingItem` may represent consumable materials required for fulfillment.

Examples:

* Box.
* Bag.
* Cup.
* Lid.
* Seal.

Packaging inventory may be tracked separately.

---

# 24. PACKAGING RULES

Packaging may depend on:

* Product.
* Temperature.
* Quantity.
* Modifier.
* Transportation method.
* Food safety.
* Customer request.

---

# 25. PACKAGING QUALITY

Packaging verification may consider:

* Correct Items.
* Closed containers.
* Temperature separation.
* Beverage security.
* Required utensils.
* Labels.
* Tamper seals.

---

# 26. ORDER LABEL

A Take Away Order may require a label containing:

* Order number.
* Customer name or pickup identifier.
* Pickup time.
* Item summary.
* Special instructions.

Sensitive data exposure shall be minimized.

---

# 27. CUSTOMER IDENTIFIER

Pickup identification may use:

* Customer name.
* Order number.
* Pickup code.
* Telephone verification.
* App token.
* QR code.

Identity verification requirements shall be risk-appropriate.

---

# 28. AUTHORIZED RECIPIENT

A Customer may authorize another person to collect an Order.

A `PickupRecipient` may include:

* Name.
* Relationship.
* Verification method.
* Authorization evidence.

---

# 29. HIGH-RISK PICKUP

Additional verification may be required for:

* High-value Orders.
* Restricted Products.
* Prepaid corporate Orders.
* Disputed Orders.

---

# 30. CUSTOMER ARRIVAL

Customer Arrival represents the Customer becoming physically available for handoff.

Arrival may be:

* Reported manually.
* Detected through App check-in.
* Reported through WhatsApp.
* Reported by telephone.
* Entered by Employee.

---

# 31. ARRIVAL CHECK-IN

Example:

```text
Customer:
"I'm outside for order 4421."
```

ECIP may:

1. Resolve Order.
2. Verify Customer or recipient.
3. Record arrival.
4. Notify pickup staff.
5. Provide pickup instructions.

---

# 32. CURBSIDE ARRIVAL

Curbside pickup may include:

* Parking slot.
* Vehicle description.
* License plate when voluntarily supplied and authorized.
* Arrival time.
* Delivery-to-vehicle task.

Only information needed for the current fulfillment should be collected.

---

# 33. CUSTOMER QUEUE

Multiple Customers may arrive simultaneously.

The platform may track:

* Arrival order.
* Ready Orders.
* Pending Orders.
* Priority exceptions.

Queue management shall not rely solely on order creation time.

---

# 34. ORDER READY

An Order becomes `READY_FOR_PICKUP` only after required preparation and packaging have completed.

Kitchen completion alone may not mean the Order is ready for handoff.

---

# 35. READY VERIFICATION

Before Ready status, the system may verify:

```text
All required Order Items ready
+
Packaging complete
+
Required checks complete
=
Ready for Pickup
```

---

# 36. CUSTOMER NOTIFICATION

ECIP may notify the Customer when:

* Order confirmed.
* Pickup time changes materially.
* Order ready.
* Delay detected.
* Pickup instructions required.

Notifications shall respect consent and channel policies.

---

# 37. READY NOTIFICATION

Example:

```text
"Your order #4421 is ready for pickup at the dedicated pickup counter."
```

Notification shall use authoritative current status.

---

# 38. EARLY CUSTOMER ARRIVAL

A Customer may arrive before the Order is ready.

ECIP should:

* Record arrival.
* Provide current status.
* Provide a realistic updated estimate.
* Avoid falsely marking the Order ready.

---

# 39. LATE ORDER

An Order may miss its promised pickup time.

A delay event should preserve:

* Original promise.
* Current estimate.
* Delay duration.
* Reason where known.
* Customer notification.

---

# 40. PROACTIVE DELAY NOTIFICATION

When material delay is detected before Customer arrival, ECIP may proactively notify the Customer where authorized.

This can reduce unnecessary waiting.

---

# 41. LATE CUSTOMER ARRIVAL

A Customer may arrive after the Order has been ready for an extended period.

Potential consequences:

* Food quality degradation.
* Temperature concern.
* Holding-time limit.
* Re-preparation need.

---

# 42. HOLDING TIME

A prepared Product may have a maximum recommended holding time.

The platform may use:

* Product Quality Window.
* Food safety rules.
* Preparation time.
* Ready time.

---

# 43. PICKUP EXPIRATION

An Order may eventually become unsuitable for normal handoff.

Possible outcomes:

* Continue available.
* Require quality review.
* Require re-preparation.
* Cancel according to policy.

AI shall not decide food safety exceptions independently.

---

# 44. NO-SHOW

A `PickupNoShow` may occur when the Customer fails to collect within the applicable policy window.

No-show handling may depend on:

* Payment state.
* Product perishability.
* Customer contact.
* Business policy.

---

# 45. CUSTOMER CONTACT FOR NO-SHOW

ECIP may contact the Customer where authorized to determine:

* Whether they are still coming.
* Whether pickup should be cancelled.
* Whether a new arrangement is needed.

---

# 46. ORDER HANDOFF

A `PickupHandoff` represents the transfer of the prepared Order to the Customer or authorized recipient.

Typical attributes:

* Fulfillment.
* Recipient.
* Employee.
* Handoff time.
* Verification method.
* Exceptions.
* Status.

---

# 47. HANDOFF VERIFICATION

Before handoff, verify as appropriate:

* Correct Order.
* Correct recipient.
* Required Payment complete.
* Order complete.
* Required restricted-product checks complete.

---

# 48. HANDOFF CONFIRMATION

Handoff confirmation may be:

* Employee confirmation.
* Customer App confirmation.
* Pickup code validation.
* External system confirmation.

---

# 49. PARTIAL HANDOFF

An Order should normally be fully prepared before pickup.

If business policy permits partial handoff, it shall be explicitly represented.

The Customer shall understand what remains pending.

---

# 50. MISSING ITEM AT HANDOFF

If an Item is missing:

```text
Handoff verification
    ↓
Missing Item detected
    ↓
Fulfillment exception
    ↓
Correction / preparation / refund workflow
```

The Order shall not be silently marked complete.

---

# 51. WRONG ORDER

If the wrong Order is presented, fulfillment shall be stopped and corrected.

This may generate:

* Operational Incident.
* Customer complaint.
* Service recovery action.

---

# 52. PAYMENT BEFORE PICKUP

Take Away may require prepayment.

Possible payment timing:

* At Order confirmation.
* During preparation.
* At pickup.

Payment policies may depend on:

* Order value.
* Channel.
* Customer.
* Scheduled timing.

---

# 53. PAYMENT AT PICKUP

Where permitted, Payment may occur at handoff.

The Order shall not become financially completed until authoritative Payment confirmation exists.

---

# 54. UNPAID ORDER HANDOFF

Handoff of an unpaid Order shall require appropriate policy and authorization.

AI shall not bypass payment requirements.

---

# 55. REFUND

Refunds may be required for:

* Cancelled Item.
* Missing Item.
* Failed fulfillment.
* Customer-approved adjustment.

Detailed Payment behavior belongs to `26_Payments.md`.

---

# 56. CANCELLATION BEFORE PREPARATION

A Customer may cancel before production begins according to policy.

This is generally lower operational impact.

---

# 57. CANCELLATION DURING PREPARATION

If production has started, cancellation may involve:

* Waste.
* Cost.
* Refund restriction.
* Human approval.

---

# 58. CANCELLATION AFTER READY

Cancellation after preparation completion may have more restrictive rules.

ECIP shall explain applicable policy rather than inventing exceptions.

---

# 59. ORDER MODIFICATION

Modification eligibility depends on current state.

Examples:

```text
DRAFT:
Generally modifiable.

CONFIRMED but not started:
Possibly modifiable.

IN_PREPARATION:
Restricted.

READY:
Highly restricted.
```

---

# 60. ADDING ITEMS

Customers may add Products before fulfillment if:

* Operationally feasible.
* New completion time acceptable.
* Pricing resolved.
* Payment handled.

This may change the promised pickup time.

---

# 61. REMOVING ITEMS

Removal shall consider:

* Production state.
* Promotion qualification.
* Payment.
* Loyalty redemption.

Order totals shall be recalculated deterministically.

---

# 62. PICKUP BRANCH CHANGE

A confirmed Order shall not be casually moved between Branches.

A Branch change may require:

* Cancellation and recreation.
* Inventory revalidation.
* Pricing re-resolution.
* Operational reauthorization.

---

# 63. PICKUP TIME CHANGE

Customer-requested timing changes shall validate:

* Kitchen feasibility.
* Product holding constraints.
* Branch schedule.
* Pickup capacity.

---

# 64. CONVERSATIONAL TAKE AWAY

ECIP may support interactions such as:

```text
"I'd like two pizzas to pick up."

"Can I pick them up at 7?"

"Is my order ready?"

"I'm outside."

"Can my daughter pick it up?"

"I'm going to be 20 minutes late."

"Can I add a dessert?"
```

Each request shall map to governed information retrieval or actions.

---

# 65. REORDER FOR PICKUP

Customer History may enable:

```text
"Would you like the same Take Away order as last Friday?"
```

Current Product, Price and availability shall still be validated.

---

# 66. PICKUP INSTRUCTIONS

ECIP may provide:

* Branch address.
* Pickup counter.
* Parking instructions.
* Curbside process.
* Order identification requirements.
* Operating hours.

---

# 67. CUSTOMER PREFERENCES

Relevant preferences may include:

* Preferred Branch.
* Preferred pickup method.
* Preferred pickup time.
* Typical Order.
* Notification channel.

Preferences shall not override operational feasibility.

---

# 68. CUSTOMER HISTORY

Completed Take Away Orders contribute to Customer History.

Potential signals include:

* Pickup frequency.
* Preferred Branch.
* Typical pickup time.
* Order composition.
* Delay history.
* No-shows.

These remain historical evidence, not automatic preferences.

---

# 69. CUSTOMER LOYALTY

Take Away may participate in:

* Loyalty earning.
* Reward redemption.
* Promotions.
* Customer milestones.

Eligibility shall be resolved before confirmation.

---

# 70. SALES INTELLIGENCE

Potential recommendations may include:

* Beverage.
* Dessert.
* Family-size upgrade.
* Pickup bundle.

Recommendation timing should occur before the Order becomes operationally difficult to change.

---

# 71. OPERATIONAL INTELLIGENCE

Take Away activity supports analysis of:

* Pickup demand.
* Kitchen load.
* Peak pickup times.
* Customer waiting.
* Packaging bottlenecks.
* Handoff delays.
* No-show rates.

---

# 72. PICKUP BOTTLENECK

A bottleneck may arise from:

* Kitchen.
* Packaging.
* Counter staffing.
* Customer queue.
* Payment.
* Pickup-space congestion.

The platform shall identify the responsible stage when possible.

---

# 73. PICKUP ETA INTELLIGENCE

Estimated readiness may use:

```text
Order composition
+
Recipe times
+
Current kitchen queue
+
Packaging workload
+
Historical performance
=
Estimated Ready Time
```

Predictions shall preserve uncertainty.

---

# 74. CUSTOMER WAIT TIME

For Customers already present:

```text
Customer Wait Time =
Handoff Time - Arrival Time
```

This metric is different from Order preparation duration.

---

# 75. READY-TO-HANDOFF TIME

Potential operational metric:

```text
Ready-to-Handoff =
Handoff Time - Ready Time
```

This helps identify pickup-counter or customer-arrival issues.

---

# 76. QUALITY INTELLIGENCE

Potential Take Away quality signals include:

* Packaging failures.
* Missing Items.
* Temperature complaints.
* Long holding time.
* Wrong Order handoff.

These contribute to Quality Control and Executive Intelligence.

---

# 77. TAKE AWAY INCIDENT

Examples:

* Order delayed.
* Packaging unavailable.
* Customer cannot locate pickup point.
* Wrong Order.
* Missing Product.
* POS synchronization failure.

Incidents shall remain traceable to the Fulfillment.

---

# 78. SERVICE RECOVERY

Possible actions:

* Re-prepare Item.
* Refund.
* Apply authorized compensation.
* Escalate to Manager.
* Schedule follow-up.

Service recovery shall use governed authorization.

---

# 79. EMPLOYEE RESPONSIBILITIES

Employees may participate as:

* Order taker.
* Kitchen staff.
* Packaging employee.
* Pickup counter employee.
* Manager.

Responsibilities shall remain explicit.

---

# 80. HUMAN ESCALATION

Escalation may be required for:

* Cancellation dispute.
* Payment discrepancy.
* Serious delay.
* Quality issue.
* Missing Order.
* Restricted Product verification.

Handoff should include the full relevant pickup context.

---

# 81. SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Order operational authority

Kitchen System:
Production status

ECIP:
Conversation and orchestration

Pickup App:
Customer arrival signal
```

Ownership shall be explicitly configured.

---

# 82. EXTERNAL TAKE AWAY MAPPING

External identifiers may include:

* POS Order ID.
* Pickup ticket.
* Kitchen ticket.
* External pickup reference.

Mappings shall use canonical external-reference mechanisms.

---

# 83. SYNCHRONIZATION

Relevant synchronized state may include:

* Order status.
* Production status.
* Ready status.
* Payment status.
* Handoff status.

Synchronization shall be idempotent and observable.

---

# 84. CONFLICT HANDLING

Examples:

```text
ECIP:
Order still in preparation

POS:
Order cancelled
```

or:

```text
ECIP:
Order ready

Kitchen:
One Item still pending
```

Conflicts shall be resolved through authoritative ownership rules.

---

# 85. TAKE AWAY EVENTS

Initial domain events include:

```text
TakeAwayOrderCreated

PickupFulfillmentCreated

PickupTimeRequested
PickupTimeConfirmed
PickupTimeChanged

PickupPreparationStarted

PickupPackagingStarted
PickupPackagingCompleted

TakeAwayOrderReady

PickupReadyNotificationSent

CustomerArrivalReported
CustomerArrivalConfirmed

CurbsideSlotAssigned

PickupHandoffStarted
PickupHandoffCompleted

PickupRecipientAuthorized
PickupRecipientVerified

PickupDelayDetected

PickupCustomerNoShowDetected

PickupOrderModificationRequested
PickupOrderModified

PickupOrderCancellationRequested
PickupOrderCancelled

PickupExceptionDetected

PickupServiceRecoveryStarted
PickupServiceRecoveryCompleted

PickupFulfillmentCompleted
```

---

# 86. RELATIONSHIPS

```text
Customer
    PLACES Order

Order
    HAS PickupFulfillment

PickupFulfillment
    OCCURS_AT Branch

PickupFulfillment
    USES PickupLocation

PickupFulfillment
    MAY_HAVE PickupRecipient

PickupFulfillment
    REQUIRES Packaging

PickupFulfillment
    HAS PromisedPickupTime

PickupFulfillment
    MAY_HAVE CustomerArrival

PickupFulfillment
    COMPLETES_WITH PickupHandoff

Conversation
    MAY_REFERENCE PickupFulfillment

PickupFulfillment
    MAY_CREATE ServiceRequest

PickupFulfillment
    MAY_GENERATE CustomerHistoryEvent
```

---

# 87. BUSINESS RULES

The following rules apply:

1. Take Away is a fulfillment mode extending the Order model.

2. Every Take Away Fulfillment belongs to one confirmed Branch.

3. Pickup timing shall be validated before becoming a customer commitment.

4. Estimated Ready Time and Promised Pickup Time are separate concepts.

5. Kitchen completion does not automatically imply Ready-for-Pickup status.

6. Required packaging shall be complete before normal handoff.

7. Customer arrival and Order readiness are independent states.

8. Product holding limits and food safety shall be respected.

9. Customer identity or recipient verification shall be appropriate to Order risk.

10. AI shall not bypass Payment, verification or cancellation policies.

11. Order modification shall respect current Production state.

12. Product, Price and Promotion validity shall be rechecked when material Order changes occur.

13. Take Away completion requires authoritative handoff evidence.

14. External identifiers shall not replace canonical identities.

15. Synchronization shall preserve source authority.

16. Service recovery actions shall be auditable and authorized.

---

# 88. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
PickupFulfillment

PickupMethod

PickupLocation

RequestedPickupTime

EstimatedReadyTime

PromisedPickupTime

PackagingStatus

ReadyForPickup

CustomerArrival

PickupRecipient

PickupHandoff

PickupDelay

PickupCancellation

PickupConversationReference

PickupExternalMapping

PickupHistory
```

Defer unless required by the first commercial pilot:

```text
Smart Locker Integration

Automatic Geofence Arrival Detection

Advanced Curbside Vehicle Recognition

Predictive Pickup Slot Optimization

Autonomous Pickup Capacity Balancing

Advanced Holding-Time Optimization
```

---

# 89. IMPLEMENTATION PRINCIPLE

This document defines the logical Take Away Service Model.

It does not prescribe:

* POS schema.
* Kitchen Display System.
* Packaging inventory implementation.
* Mobile App.
* Curbside hardware.
* Geofencing technology.
* Payment implementation.
* AI model.
* Pickup optimization algorithm.

Implementation shall preserve the distinction between:

```text
ORDER

PRODUCTION

PACKAGING

READY STATE

CUSTOMER ARRIVAL

PICKUP HANDOFF

PAYMENT

FULFILLMENT COMPLETION
```

---

# 90. FINAL RULE

Before ECIP commits to or completes a Take Away fulfillment, it shall be able to determine:

> Who is placing or collecting the Order?

> Which Branch and Pickup Location apply?

> Are the requested Products currently offerable for Take Away?

> What Pickup time did the Customer request?

> What timing can the restaurant realistically promise?

> What preparation and Packaging remain pending?

> Is the Order truly ready for pickup?

> Has the Customer or authorized recipient arrived?

> Is any Payment or verification still required?

> Has the complete correct Order been handed over?

> Are there any delays, quality risks or unresolved exceptions?

> Can every material fulfillment action be reconstructed and audited?

Only after these conditions are resolved may ECIP represent a Take Away Order as successfully fulfilled.

