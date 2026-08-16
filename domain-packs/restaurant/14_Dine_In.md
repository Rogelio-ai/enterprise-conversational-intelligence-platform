# 14_Dine_In.md

**Document ID:** RDM-014
**Document Name:** Dine In
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Dine-In Service Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of an in-restaurant dining experience, from guest arrival and seating through ordering, service, payment and table release.

The Dine-In Model connects:

* Customer identity.
* Reservation.
* Waitlist.
* Dining Area.
* Table.
* Seat.
* Employee assignment.
* Order.
* Kitchen production.
* Service requests.
* Payment.
* Customer history.
* Loyalty.
* Operational intelligence.
* Conversational context.

Dine-In shall be modeled as an operational service experience, not merely as an Order with a table number.

---

# 2. OBJECTIVES

The Dine-In Model enables ECIP to:

* Recognize arriving customers.
* Associate visits with Reservations.
* Manage walk-in customers.
* Manage waiting and seating.
* Assign Dining Areas and Tables.
* Track dining sessions.
* Associate guests with Seats when needed.
* Associate employees with the dining experience.
* Support table-side ordering.
* Support course management.
* Support service requests.
* Track dining progress.
* Support table transfers.
* Support guest transfers.
* Support split bills.
* Support multiple payments.
* Estimate table availability.
* Improve customer experience.
* Support conversational assistance during the visit.
* Preserve complete historical context.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Conversation
* Interaction
* Context Snapshot
* Commitment
* Action Request
* Action Authorization
* Workflow Instance
* Task
* Location
* Employee
* Customer History Event

Restaurant-specific Dine-In entities remain within the Restaurant Domain Pack.

---

# 4. DINE-IN PRINCIPLE

A Dine-In experience represents a time-bounded service relationship between one or more guests and a restaurant location.

The platform shall distinguish between:

```text
Reservation

Customer Arrival

Waitlist

Dining Session

Table Assignment

Order

Kitchen Production

Service

Payment

Visit Completion
```

These concepts shall remain independently traceable.

---

# 5. DINING SESSION

A `DiningSession` represents one in-restaurant dining experience.

Typical attributes include:

* Dining Session ID
* Branch
* Dining Area
* Customer
* Party
* Reservation reference
* Table assignments
* Start time
* Seating time
* End time
* Service status
* Assigned employees
* Active Orders
* Payment status
* Visit outcome
* Conversation references

Suggested lifecycle:

```text
CREATED
→ WAITING
→ SEATED
→ ACTIVE
→ CHECK_REQUESTED
→ PAYMENT_IN_PROGRESS
→ COMPLETED
```

Alternative states:

```text
CANCELLED
ABANDONED
INTERRUPTED
```

---

# 6. PARTY

A `DiningParty` represents the group being served together.

Typical attributes:

* Party ID
* Primary Customer
* Guest count
* Adult count
* Child count
* Accessibility needs
* Occasion
* Reservation reference
* Status

A Party may contain identified and unidentified guests.

---

# 7. PARTY MEMBER

A `PartyMember` represents a known or anonymous participant in the dining experience.

Examples:

* Customer.
* Spouse.
* Child.
* Business guest.
* Anonymous guest.

Party Member identity is optional unless required by the business process.

---

# 8. CUSTOMER ARRIVAL

Arrival may occur through:

* Reservation check-in.
* Walk-in.
* Waitlist return.
* Event check-in.

Typical information:

* Arrival time.
* Customer identity.
* Party size.
* Reservation reference.
* Requested area.
* Accessibility needs.
* Current waiting estimate.

---

# 9. WALK-IN

A `WalkInRequest` represents a customer seeking immediate seating without an existing Reservation.

Typical attributes:

* Customer.
* Party size.
* Arrival time.
* Preferred area.
* Seating constraints.
* Estimated wait.
* Status.

A Walk-In may become:

* Immediate Dining Session.
* Waitlist Entry.
* Rejected service request.

---

# 10. RESERVATION CHECK-IN

An existing Reservation may transition into a Dine-In Session.

Conceptually:

```text
Reservation
    ↓
Customer Arrives
    ↓
Reservation Check-In
    ↓
Table Assignment
    ↓
Dining Session
```

Reservation remains historically distinct from the actual visit.

---

# 11. NO-SHOW VS LATE ARRIVAL

The Dine-In Model shall distinguish:

* Customer has not arrived yet.
* Customer is late.
* Customer cancelled.
* Customer is a confirmed no-show.

No-show determination shall follow Reservation policy.

---

# 12. WAITLIST INTEGRATION

When seating is unavailable, the Party may enter a Waitlist.

Dine-In consumes Waitlist state but does not replace the Reservation/Waitlist model defined later in `18_Reservations.md`.

---

# 13. WAITING EXPERIENCE

Waiting information may include:

* Queue position.
* Estimated wait.
* Actual wait.
* Waiting Area.
* Notifications.
* Customer preferences.

ECIP may provide proactive updates where appropriate.

---

# 14. TABLE ASSIGNMENT

A `TableAssignment` represents the temporary allocation of one or more Tables to a Dining Session.

Typical attributes:

* Table Assignment ID
* Dining Session
* Table
* Assigned at
* Released at
* Assignment reason
* Employee responsible
* Status

---

# 15. MULTI-TABLE ASSIGNMENT

Large Parties may require multiple Tables.

Example:

```text
Party of 12
    ↓
Table 14 + Table 15 + Table 16
```

Tables may be grouped into one logical Dining Session.

---

# 16. TABLE COMBINATION

Where physically permitted, Tables may be combined.

The resulting configuration shall preserve the underlying resource identities.

---

# 17. TABLE ELIGIBILITY

Table assignment may consider:

* Party size.
* Dining Area.
* Reservation.
* Accessibility.
* Customer preference.
* Table status.
* Cleaning status.
* Operational policy.

A preferred Table shall never override unavailable capacity.

---

# 18. TABLE STATUS

Typical Dine-In operational states:

```text
AVAILABLE
RESERVED
HELD
OCCUPIED
CHECK_REQUESTED
PAYMENT_IN_PROGRESS
DIRTY
CLEANING
OUT_OF_SERVICE
```

Table status shall be derived from authoritative operational state.

---

# 19. TABLE HOLD

A temporary `TableHold` may prevent another allocation while seating is being completed.

A Hold shall have a defined expiration.

---

# 20. SEAT ASSIGNMENT

Where required, Guests may be associated with Seats.

This supports:

* Individual ordering.
* Split checks.
* Course tracking.
* Guest-specific service.

Seat-level management remains optional.

---

# 21. HOST

A Host may participate in:

* Arrival.
* Reservation check-in.
* Waitlist.
* Seating.
* Table assignment.

ECIP may assist the Host by providing relevant Customer and Operational Context.

---

# 22. SERVER ASSIGNMENT

A `ServerAssignment` associates an Employee with a Dining Session or Table.

Typical attributes:

* Employee.
* Dining Session.
* Table.
* Start time.
* End time.
* Role.
* Status.

---

# 23. SERVER SELECTION

Employee assignment may consider:

* Dining Area.
* Shift.
* Workload.
* Skill.
* Language.
* Customer relationship.
* Current assignments.

Routing shall respect restaurant policy.

---

# 24. SERVER WORKLOAD

Potential workload indicators:

* Active Tables.
* Active Guests.
* Active Orders.
* Pending service requests.
* Table turnover.

Workload contributes to operational routing and service intelligence.

---

# 25. DINING SESSION ORDER

A Dining Session may contain one or more Orders.

Examples:

* Initial Order.
* Additional drinks.
* Dessert Order.
* Separate guest Orders.

Order remains governed by `13_Order.md`.

---

# 26. OPEN CHECK

A Dine-In experience may maintain an open commercial check while the Dining Session remains active.

The Check may contain multiple Orders or Order updates depending on POS architecture.

This document does not prescribe whether the operational POS uses one ticket or multiple tickets.

---

# 27. TABLE-SIDE ORDERING

Ordering may be captured by:

* Waiter.
* Customer Mobile App.
* QR menu.
* Kiosk-like table terminal.
* Conversational AI.
* Voice interface.

All channels shall create or modify the same governed Order domain.

---

# 28. CONVERSATIONAL ORDERING

Example:

```text
Customer:
"Can we get another bottle of sparkling water?"

ECIP:
Identify Dining Session
Identify Table
Resolve Product
Validate availability
Confirm when necessary
Add authorized Order Item
```

The conversation channel shall not create a separate Dine-In ordering model.

---

# 29. COURSE MANAGEMENT

Dine-In Orders may organize Items by Course.

Examples:

* Drinks.
* Appetizers.
* Main courses.
* Desserts.

Course state may include:

```text
PLANNED
READY_TO_FIRE
FIRED
IN_PREPARATION
READY
SERVED
```

---

# 30. FIRE COURSE

A `CourseFireRequest` signals that Production may begin for a Course.

This may be initiated by:

* Employee.
* Timing policy.
* Customer request.
* Governed automation.

AI shall not prematurely fire Courses without authorized logic.

---

# 31. COURSE PACING

Course pacing may depend on:

* Customer preference.
* Current Course completion.
* Kitchen workload.
* Service policy.
* Occasion.

Examples:

* Fast business lunch.
* Relaxed anniversary dinner.

---

# 32. ITEM SERVING

A prepared Order Item may transition from Ready to Served.

Serving information may include:

* Employee.
* Time.
* Seat.
* Table.
* Quality issue.

---

# 33. SERVICE REQUEST

A `ServiceRequest` represents a customer need during the Dining Session.

Examples:

* Water refill.
* Additional napkins.
* Change utensil.
* Call waiter.
* Request manager.
* Ask about Product.
* Request bill.

Typical attributes:

* Request ID
* Dining Session
* Customer
* Request type
* Priority
* Created time
* Assigned Employee
* Status
* Resolution

---

# 34. SERVICE REQUEST LIFECYCLE

Suggested lifecycle:

```text
CREATED
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
```

Alternative states:

```text
CANCELLED
ESCALATED
FAILED
```

---

# 35. SERVICE REQUEST ROUTING

Routing may consider:

* Request type.
* Assigned waiter.
* Current workload.
* Skill.
* Area.
* Urgency.

Example:

```text
"Could I speak to the manager?"

→ Manager-capable routing
```

---

# 36. CUSTOMER CALL BUTTON / DIGITAL REQUEST

Future channels may create Service Requests through:

* Mobile App.
* QR interface.
* Table device.
* Smart display.
* Voice interface.

These shall map to the same ServiceRequest entity.

---

# 37. SERVICE RESPONSE TIME

The platform may measure:

* Request creation time.
* Acknowledgment time.
* Completion time.

This supports Service Quality Intelligence.

---

# 38. TABLE TRANSFER

A Dining Session may move to another Table.

Reasons:

* Customer request.
* Larger Party.
* Operational issue.
* Accessibility need.
* Table failure.

Transfer shall preserve historical Table assignments.

---

# 39. DINING AREA TRANSFER

Example:

```text
Indoor Dining
    ↓
Customer requests Terrace
    ↓
Availability validated
    ↓
Dining Session transferred
```

The transfer shall not disrupt Order ownership or Payment state.

---

# 40. SERVER TRANSFER

Responsibility may move between Employees.

Reasons:

* Shift change.
* Area reassignment.
* Customer request.
* Workload balancing.

The new Employee should receive relevant context.

---

# 41. HANDOFF BETWEEN EMPLOYEES

Handoff context may include:

* Customer identity.
* Party.
* Active Orders.
* Courses.
* Pending requests.
* Preferences.
* Complaints.
* Payment state.

Customers should not need to repeat known information.

---

# 42. ADDITIONAL GUEST

A Party may grow after seating.

The platform shall consider:

* Table capacity.
* Additional seating.
* Combined Tables.
* Service load.

---

# 43. GUEST DEPARTURE

A Party Member may leave before the complete Dining Session ends.

This may influence:

* Seat state.
* Payment.
* Check split.

The Dining Session itself may remain active.

---

# 44. PARTY MERGE

Two Parties may request to join.

Merge shall validate:

* Table feasibility.
* Order implications.
* Payment implications.
* Reservation constraints.

---

# 45. PARTY SPLIT

A Party may divide into separate Tables or checks.

Operational state shall preserve lineage.

---

# 46. DINING SESSION TIMING

Important timestamps include:

* Arrival.
* Wait start.
* Seating.
* First order.
* First item served.
* Main course served.
* Check requested.
* Payment completed.
* Table released.

These support operational intelligence.

---

# 47. TABLE TURNOVER

Table turnover represents time from one seating cycle to the next.

It may include:

```text
Seat
→ Service
→ Payment
→ Departure
→ Cleaning
→ Available
```

Turnover shall not be reduced merely by pressuring customers to leave.

---

# 48. EXPECTED DINING DURATION

An estimated Dining Duration may depend on:

* Party size.
* Meal period.
* Service type.
* Occasion.
* Historical averages.
* Ordered courses.

The estimate supports capacity planning.

It is not a forced customer deadline unless explicit policies apply.

---

# 49. OCCUPANCY

Dining occupancy may be measured by:

* Tables.
* Seats.
* Guests.
* Dining Areas.

Occupancy contributes to Operational Context.

---

# 50. DINING CAPACITY

Dining capacity shall consider:

* Physical seats.
* Table configurations.
* Out-of-service resources.
* Reserved capacity.
* Accessibility.
* Staffing.
* Business policy.

Physical maximum capacity and usable current capacity are different values.

---

# 51. TABLE CLEANING

After guests leave, a Table may transition to Cleaning.

Typical flow:

```text
OCCUPIED
→ DIRTY
→ CLEANING
→ AVAILABLE
```

ECIP shall not represent the Table as available before cleaning is complete.

---

# 52. CUSTOMER REQUEST FOR CHECK

The customer may request the Check through:

* Employee.
* Mobile App.
* Conversational AI.
* Table interface.

This creates a service/commercial workflow.

---

# 53. CHECK

A `DiningCheck` represents the billable commercial view associated with some or all of a Dining Session.

Typical attributes:

* Check ID
* Dining Session
* Included Order Items
* Subtotal
* Discounts
* Taxes
* Charges
* Total
* Payment status

---

# 54. MULTIPLE CHECKS

One Dining Session may contain multiple Checks.

Example:

```text
Party of 6
    ↓
Check A: Guests 1–2
Check B: Guests 3–4
Check C: Guests 5–6
```

---

# 55. SPLIT CHECK BY GUEST

Where Seat assignment exists, Items may be assigned to individual Guests.

This supports accurate split billing.

---

# 56. SPLIT CHECK BY ITEM

Customers may choose which Items belong to which Check.

Transfer of Items shall preserve audit history.

---

# 57. SPLIT CHECK BY AMOUNT

Some restaurants may allow equal or custom amount splitting.

Payment allocation remains governed by the Payment model.

---

# 58. SHARED ITEMS

Shared Items may require distribution across Checks.

Examples:

* Bottle of wine.
* Shared appetizer.

Allocation rules shall be deterministic.

---

# 59. PAYMENT

Detailed Payment behavior belongs to `26_Payments.md`.

Dine-In shall support:

* One Payment.
* Multiple Payments.
* Partial Payments.
* Mixed Payment methods.
* Tips where applicable.

---

# 60. TIP

Tips or gratuities may be associated with:

* Check.
* Payment.
* Employee distribution rules.

Tip handling depends on jurisdiction and restaurant policy.

This document does not define payroll treatment.

---

# 61. SERVICE CHARGE

Service Charges may apply according to:

* Party size.
* Event.
* Policy.

They remain distinct from discretionary tips.

---

# 62. PAYMENT COMPLETION

A Dining Session does not necessarily end immediately when one Payment completes.

Completion shall consider whether:

* All Checks are settled.
* All service obligations are complete.
* Party has departed.
* Table is released.

---

# 63. CUSTOMER DEPARTURE

Departure represents completion of customer presence.

Typical attributes:

* Departure time.
* Final satisfaction signal.
* Open issue.
* Lost item.
* Follow-up requirement.

---

# 64. DINING SESSION COMPLETION

Before completion, the system should ensure:

* Active Orders resolved.
* Payment state resolved or authorized exception recorded.
* Pending critical Service Requests resolved.
* Required commitments preserved.

---

# 65. TABLE RELEASE

Table release separates:

```text
Customer leaves
```

from:

```text
Table becomes available
```

Cleaning or reset may occur between those events.

---

# 66. LOST AND FOUND

A customer may report an item left at the restaurant.

This may create:

* Service Request.
* Commitment.
* Human escalation.

Detailed Lost and Found modeling may be added later if commercially required.

---

# 67. DINE-IN COMPLAINT

A complaint during service may reference:

* Product.
* Table.
* Employee.
* Wait time.
* Kitchen delay.
* Billing.
* Environment.

The Complaint domain shall preserve the underlying Dine-In context.

---

# 68. SERVICE RECOVERY

Possible recovery actions:

* Replacement Product.
* Manager visit.
* Discount.
* Complimentary Product.
* Follow-up.

Actions shall require appropriate authorization.

---

# 69. QUALITY ISSUE

Examples:

* Wrong temperature.
* Incorrect preparation.
* Delayed Course.
* Missing Item.

Quality issues may trigger:

* Kitchen remediation.
* Customer service action.
* Operational Incident.

---

# 70. CUSTOMER PREFERENCES

Dine-In may use governed preferences such as:

* Favorite Table.
* Preferred Dining Area.
* Preferred waiter.
* Quiet seating.
* Service pace.

Preferences shall not guarantee unavailable resources.

---

# 71. CUSTOMER ALLERGIES

Relevant Allergy information may be surfaced to authorized actors and used during Order validation.

Dine-In shall not create a separate Allergy model.

---

# 72. CUSTOMER HISTORY

The completed Dining Session contributes to Customer History.

Potential historical signals:

* Branch.
* Dining Area.
* Party size.
* Products.
* Duration.
* Employees.
* Complaints.
* Satisfaction.

---

# 73. CUSTOMER LOYALTY

Dine-In may trigger:

* Points earning.
* Milestones.
* Rewards.
* Recognition.

Loyalty domain remains authoritative.

---

# 74. CUSTOMER RECOGNITION

Example:

```text
Customer arrives.

ECIP recognizes:
- Returning customer
- Gold member
- Usually prefers quiet seating
- Previous visit had resolved complaint

Host context:
Relevant information available without exposing unnecessary private history.
```

---

# 75. HUMAN ESCALATION

AI may escalate issues such as:

* Serious complaint.
* Safety concern.
* Pricing dispute.
* Special request.
* Service recovery authorization.

The Human Handoff shall include the relevant Dining Session context.

---

# 76. CONVERSATIONAL DINE-IN ASSISTANT

ECIP may support interactions such as:

```text
"What table am I at?"

"Can we order dessert?"

"Can I get another drink?"

"Where is our main course?"

"Can we split the bill?"

"Can I speak with the manager?"
```

Each request shall map to governed domain actions or information.

---

# 77. ORDER STATUS INQUIRY

A Customer may ask about pending Items.

ECIP may use:

* Order Item status.
* Kitchen Production state.
* Current ETA.

It shall not invent timing.

---

# 78. PROACTIVE SERVICE

Where policy permits, ECIP may identify situations such as:

* Unusually long wait.
* Drink refill opportunity.
* Delayed Course.
* Pending Service Request.

Proactive actions shall avoid excessive interruption.

---

# 79. TABLE INTELLIGENCE

The platform may reason about:

* Current occupancy.
* Expected release.
* Table suitability.
* Customer preference.
* Reservation pressure.

This supports Reservation and Operational Intelligence.

---

# 80. TABLE AVAILABILITY FORECAST

Table availability may be predicted from:

* Current Dining Sessions.
* Expected duration.
* Check status.
* Reservations.
* Cleaning time.

Predictions shall preserve uncertainty.

---

# 81. STAFFING INTELLIGENCE

Dine-In state may support:

* Waiter workload.
* Host workload.
* Dining Area staffing.
* Service bottleneck detection.

Operational Intelligence may recommend reassignment.

---

# 82. SALES INTELLIGENCE

Dine-In context may support relevant recommendations.

Examples:

* Beverage pairing.
* Additional appetizer.
* Dessert.
* Coffee.
* Celebration package.

Recommendations shall consider:

* Customer preferences.
* Current Order.
* Time spent.
* Kitchen load.
* Commercial relevance.

---

# 83. UPSELL TIMING

Timing matters.

Example:

A dessert recommendation may be appropriate after Main Course completion.

The same recommendation may be intrusive while the customer is waiting for an overdue appetizer.

ECIP shall consider service state.

---

# 84. SERVICE QUALITY INTELLIGENCE

Potential metrics include:

* Wait-to-seat time.
* Time to first order.
* Time to first item.
* Course delays.
* Service request response.
* Table turnover.
* Complaint rate.
* Satisfaction.

---

# 85. DINING EXPERIENCE SCORE

A `DiningExperienceAssessment` may combine multiple signals.

It shall remain analytical and explainable.

Possible inputs:

* Wait.
* Production delay.
* Service response.
* Complaint.
* Feedback.
* Sentiment.

---

# 86. OPERATIONAL INCIDENT

A Dine-In issue may reveal broader operational problems.

Examples:

* POS outage.
* Kitchen station failure.
* Staffing shortage.
* Dining Area closure.

The Operational Incident domain remains authoritative for incident lifecycle.

---

# 87. DINING SESSION INTERRUPTION

A Dining Session may be interrupted due to:

* Emergency.
* Restaurant closure.
* Customer departure.
* System failure.

Interruption shall preserve unresolved commercial and customer obligations.

---

# 88. OFFLINE RESILIENCE

Where local POS operation continues during temporary ECIP unavailability, later synchronization shall reconcile Dine-In state.

ECIP shall not assume it is the sole operational source of truth.

---

# 89. SOURCE OF TRUTH

Authority may vary by deployment.

Example:

```text
POS:
Order and Check operational authority

Reservation System:
Reservation authority

ECIP:
Conversation and contextual orchestration

Host System:
Table state, if externally managed
```

Ownership shall be explicitly configured.

---

# 90. EXTERNAL DINE-IN MAPPING

External systems may use identifiers such as:

* Table ID.
* Check ID.
* Dining Session ID.
* POS ticket.

These shall map to canonical ECIP entities.

---

# 91. SYNCHRONIZATION

Relevant synchronized state may include:

* Table state.
* Order state.
* Check state.
* Employee assignment.
* Payment state.

Synchronization shall be idempotent and observable.

---

# 92. CONFLICT HANDLING

Possible conflicts:

* ECIP believes Table is available but POS shows occupied.
* Customer requests Item removal after Kitchen preparation.
* Check paid externally while ECIP still shows unpaid.

Resolution shall follow ownership authority rather than AI guesswork.

---

# 93. DINE-IN EVENTS

Initial events include:

```text
DiningSessionCreated
DiningSessionStarted
DiningSessionCompleted
DiningSessionCancelled

PartyArrived
WalkInRegistered
ReservationCheckedIn

PartyWaitStarted
PartySeated

TableHeld
TableAssigned
TableReleased
TableTransferred

SeatAssigned
SeatReleased

ServerAssigned
ServerTransferred

DiningOrderCreated
DiningOrderUpdated

CoursePlanned
CourseFired
CourseServed

ServiceRequestCreated
ServiceRequestAssigned
ServiceRequestCompleted
ServiceRequestEscalated

CheckRequested
CheckCreated
CheckSplit
CheckUpdated

DiningPaymentStarted
DiningPaymentCompleted

CustomerDeparted
TableCleaningStarted
TableCleaningCompleted

DiningComplaintCreated
DiningServiceRecoveryStarted
DiningServiceRecoveryCompleted

DiningDelayDetected
DiningExperienceCompleted
```

---

# 94. RELATIONSHIPS

```text
Branch
    HAS DiningSession

Customer
    PARTICIPATES_IN DiningSession

DiningSession
    HAS DiningParty

DiningParty
    HAS PartyMember

DiningSession
    MAY_REFERENCE Reservation

DiningSession
    HAS TableAssignment

TableAssignment
    REFERENCES Table

DiningSession
    MAY_HAVE SeatAssignment

DiningSession
    HAS ServerAssignment

ServerAssignment
    REFERENCES Employee

DiningSession
    HAS Order

DiningSession
    HAS ServiceRequest

DiningSession
    MAY_HAVE DiningCheck

DiningCheck
    REFERENCES OrderItem

DiningCheck
    SETTLED_BY Payment

Conversation
    MAY_REFERENCE DiningSession

DiningSession
    GENERATES CustomerHistoryEvent
```

---

# 95. BUSINESS RULES

The following rules apply:

1. A Dining Session represents the actual customer visit, not the Reservation itself.

2. Every active Dining Session shall belong to one Branch.

3. A Dining Session may use one or multiple Tables.

4. Table assignments shall respect current capacity and status.

5. A Table shall not be simultaneously allocated to incompatible active Dining Sessions.

6. Customer preferences may influence seating but shall not override operational feasibility.

7. Order lifecycle remains governed by `13_Order.md`.

8. Production lifecycle remains separate from Dining Session lifecycle.

9. Payment lifecycle remains separate from Dining Session lifecycle.

10. Service Requests shall preserve responsibility and resolution.

11. Material table, check and Order transfers shall remain auditable.

12. Recommendations shall not automatically mutate Orders.

13. AI-assisted actions shall use governed authorization.

14. Current operational state shall be checked before promising a Table, Product or timing.

15. Employee handoffs shall preserve relevant context.

16. Customer history shall be created from completed evidence rather than assumptions.

17. External operational authority shall remain explicitly defined.

---

# 96. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
DiningSession

DiningParty

CustomerArrival

WalkInRequest

ReservationCheckIn

TableAssignment

TableStatus

ServerAssignment

DiningOrderReference

ServiceRequest

CheckRequest

DiningCheckReference

CustomerDeparture

TableRelease

DiningSessionHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Seat-Level Ordering

Advanced Course-Pacing Automation

Predictive Table Turn Optimization

Autonomous Staff Rebalancing

Advanced Multi-Party Check Orchestration

Smart Table Hardware Integration
```

---

# 97. IMPLEMENTATION PRINCIPLE

This document defines the logical Dine-In Service Model.

It does not prescribe:

* POS schema.
* Reservation software.
* Table map UI.
* Kitchen Display System.
* Payment implementation.
* Employee scheduling system.
* Table optimization algorithm.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
RESERVATION

ARRIVAL

WAITLIST

DINING SESSION

TABLE ASSIGNMENT

ORDER

PRODUCTION

SERVICE REQUEST

CHECK

PAYMENT

TABLE RELEASE
```

---

# 98. FINAL RULE

Before ECIP makes or executes a Dine-In commitment, it shall be able to determine:

> Who is being served?

> Is this a Reservation, Walk-In or Waitlist arrival?

> What is the current Party size?

> Which Dining Area and Tables are actually available?

> Are relevant customer seating or accessibility preferences known?

> Which Employees are responsible?

> What Orders and Courses are currently active?

> Are there pending Service Requests or complaints?

> What is the current Check and Payment state?

> What operational condition affects the customer experience?

> Does the requested action require Customer confirmation or Employee authorization?

> Can the complete Dining Session be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably coordinate the in-restaurant dining experience.

