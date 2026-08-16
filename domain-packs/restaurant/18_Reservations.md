# 18_Reservations.md

**Document ID:** RDM-018
**Document Name:** Reservations
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Reservations Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete lifecycle of restaurant reservations, including availability evaluation, reservation creation, confirmation, modification, cancellation, waitlist handling, check-in, seating and completion.

The Reservations Model connects:

* Customer identity.
* Restaurant location.
* Dining areas.
* Tables and seating capacity.
* Business hours.
* Operational capacity.
* Customer preferences.
* Customer history.
* Loyalty.
* Conversations.
* Dining sessions.
* Events.
* Human escalation.
* Operational intelligence.

A Reservation represents a future service commitment.

It is not the same as a Dining Session, Table Assignment or Customer Visit.

---

# 2. OBJECTIVES

The Reservations Model enables ECIP to:

* Search restaurant availability.
* Create reservations.
* Modify reservations.
* Cancel reservations.
* Confirm reservations.
* Manage reservation holds.
* Manage waitlists.
* Handle walk-ins.
* Support multiple branches.
* Support multiple dining areas.
* Support customer preferences.
* Support accessibility requirements.
* Support special occasions.
* Manage party size.
* Estimate seating availability.
* Prevent overbooking.
* Detect reservation conflicts.
* Manage no-shows.
* Support reminders and confirmations.
* Support conversational booking.
* Optimize restaurant capacity.
* Preserve complete reservation history.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Location
* Resource
* Conversation
* Commitment
* Action Request
* Action Authorization
* Workflow Instance
* Context Snapshot
* Recommendation
* Notification
* Customer History Event
* External Entity Reference

Restaurant-specific Reservation entities remain within the Restaurant Domain Pack.

---

# 4. RESERVATION PRINCIPLE

A Reservation represents a governed future commitment between a Restaurant and a Customer to provide dining capacity under defined conditions.

The platform shall distinguish between:

```text
Availability Search

Reservation Hold

Reservation

Waitlist

Arrival

Check-In

Table Assignment

Dining Session
```

These concepts are related but shall remain independently traceable.

---

# 5. RESERVATION

A `Reservation` represents a confirmed or pending future dining commitment.

Typical attributes include:

* Reservation ID
* Customer
* Branch
* Dining Area preference
* Requested date
* Requested time
* Confirmed time
* Party size
* Adult count
* Child count
* Duration estimate
* Occasion
* Seating preferences
* Accessibility requirements
* Special requests
* Reservation status
* Confirmation status
* Source channel
* Created time
* Expiration time where applicable
* Arrival status
* Conversation references
* External identifiers
* Version

---

# 6. RESERVATION TYPES

Initial Reservation types may include:

```text
STANDARD_DINING

PRIVATE_ROOM

TERRACE

BAR_SEATING

GROUP_RESERVATION

VIP_RESERVATION

EVENT_RELATED

CORPORATE_RESERVATION

SPECIAL_OCCASION
```

The catalog remains configurable.

---

# 7. RESERVATION LIFECYCLE

Suggested lifecycle:

```text
DRAFT
→ PENDING_AVAILABILITY
→ HELD
→ CONFIRMED
→ CHECKED_IN
→ SEATED
→ COMPLETED
```

Alternative states include:

```text
WAITLISTED
CANCELLED
EXPIRED
NO_SHOW
REJECTED
```

---

# 8. DRAFT RESERVATION

A Draft Reservation represents an incomplete booking request.

Typical missing information may include:

* Date.
* Time.
* Branch.
* Party size.
* Customer identity.

Draft state does not reserve capacity.

---

# 9. RESERVATION REQUEST

A `ReservationRequest` represents the Customer's desired booking before availability has been committed.

Typical attributes:

* Customer.
* Preferred Branch.
* Date.
* Time or range.
* Party size.
* Dining Area preference.
* Occasion.
* Accessibility.
* Flexibility.
* Special requirements.

---

# 10. RESERVATION AVAILABILITY

`ReservationAvailability` represents whether restaurant capacity can support a Reservation Request.

Suggested outcomes:

```text
AVAILABLE

AVAILABLE_WITH_ALTERNATIVE

LIMITED_AVAILABILITY

WAITLIST_ONLY

UNAVAILABLE
```

---

# 11. AVAILABILITY RESOLUTION

Reservation availability may depend on:

```text
Branch Open
+
Dining Area Open
+
Table Capacity
+
Existing Reservations
+
Current / Forecast Dining Sessions
+
Expected Duration
+
Staffing Capacity
+
Operational Restrictions
+
Business Policy
=
Potential Availability
```

---

# 12. AVAILABILITY SEARCH

A Customer may search by:

* Exact date and time.
* Time range.
* Day part.
* Flexible date.
* Flexible Branch.
* Party size.
* Dining Area.
* Occasion.

Example:

```text
"Do you have a table for four tomorrow around 8 PM?"
```

ECIP shall resolve actual availability rather than guess.

---

# 13. TIME FLEXIBILITY

A Customer may specify flexibility such as:

```text
Exact:
20:00

Flexible:
19:30–20:30

Day Part:
Dinner

Date Flexible:
Friday or Saturday
```

Flexibility may improve alternative recommendations.

---

# 14. ALTERNATIVE RESERVATION

When the requested slot is unavailable, ECIP may recommend alternatives.

Examples:

* Earlier time.
* Later time.
* Different Dining Area.
* Different Branch.
* Waitlist.

Recommendations shall preserve Customer constraints.

---

# 15. RESERVATION SLOT

A `ReservationSlot` represents a bookable capacity opportunity.

Typical attributes:

* Branch.
* Dining Area.
* Start time.
* Expected duration.
* Party size range.
* Capacity.
* Status.

A Slot does not necessarily correspond to one specific Table.

---

# 16. TABLE-SPECIFIC RESERVATION

Some restaurants may allow reservation of a specific Table.

This should be treated as a stronger resource commitment.

Typical use cases:

* VIP Customer.
* Private Table.
* Customer accessibility need.
* Specific Experience.

Table-specific booking shall only occur if restaurant policy permits it.

---

# 17. CAPACITY-BASED RESERVATION

Many Reservations should reserve capacity rather than an exact Table.

Example:

```text
Reservation:
4 guests at 20:00

Actual Table assignment:
Determined near arrival
```

This provides better operational flexibility.

---

# 18. RESERVATION HOLD

A `ReservationHold` temporarily protects capacity during the booking process.

Typical attributes:

* Hold ID
* Reservation Request
* Capacity
* Start time
* Expiration
* Customer
* Channel
* Status

---

# 19. HOLD LIFECYCLE

Suggested states:

```text
CREATED
→ ACTIVE
→ CONFIRMED
```

Alternative states:

```text
EXPIRED
RELEASED
CANCELLED
```

---

# 20. HOLD EXPIRATION

Holds shall have a defined expiration.

This prevents abandoned booking conversations from consuming capacity indefinitely.

---

# 21. RESERVATION CONFIRMATION

Before confirmation, ECIP should verify:

* Customer identity sufficient.
* Branch open.
* Requested time valid.
* Party size valid.
* Capacity available.
* Relevant requirements feasible.
* Required deposit satisfied where applicable.
* Policy requirements satisfied.

---

# 22. CONFIRMATION CODE

A confirmed Reservation may receive:

* Reservation number.
* Confirmation code.
* QR code.
* External reference.

The canonical Reservation ID remains internal authority.

---

# 23. CUSTOMER CONFIRMATION

The Customer should receive a clear summary such as:

```text
Saturday, August 22
8:00 PM
Downtown Branch
4 guests
Terrace preferred
```

Material details shall be clear before final commitment.

---

# 24. RESERVATION CHANNEL

Reservations may originate from:

* Telephone.
* WhatsApp.
* Web Chat.
* Website.
* Mobile App.
* Walk-in.
* Employee.
* Social channels.
* External reservation platform.

Channel shall not redefine Reservation semantics.

---

# 25. MULTI-CHANNEL CONTINUITY

Example:

```text
Reservation started through Web Chat
    ↓
Customer continues by telephone
    ↓
Same Reservation Request
```

Where identity permits, ECIP should preserve continuity rather than create duplicate bookings.

---

# 26. PARTY SIZE

Party size is one of the most important Reservation constraints.

Typical attributes:

* Total guests.
* Adults.
* Children.
* Infants.
* High chair requirement.

---

# 27. PARTY SIZE CHANGE

A party-size change may require revalidation.

Example:

```text
Original:
4 guests

Requested:
8 guests
```

This may affect:

* Table capacity.
* Dining Area.
* Deposit.
* Time.
* Availability.

---

# 28. LARGE PARTY

Restaurants may define a Large Party threshold.

Large Parties may require:

* Deposit.
* Special menu.
* Credit card guarantee.
* Specific Dining Area.
* Manager approval.

---

# 29. GROUP RESERVATION

A Group Reservation may contain several Tables or related sub-reservations.

This shall preserve one group-level Customer commitment.

---

# 30. DINING AREA PREFERENCE

Customers may request:

* Main Dining Room.
* Terrace.
* Garden.
* Bar.
* Private Room.
* Quiet Area.

A Dining Area preference is not automatically a guarantee.

---

# 31. TABLE PREFERENCE

Examples:

* Window Table.
* Booth.
* Favorite Table.
* Near entrance.
* Away from Kitchen.

The platform shall distinguish:

```text
PREFERENCE

from

CONFIRMED TABLE COMMITMENT
```

---

# 32. ACCESSIBILITY REQUIREMENT

Reservations may include operational requirements such as:

* Wheelchair access.
* Accessible Table.
* Reduced walking distance.
* Space for mobility equipment.

Explicit accessibility requirements shall be treated as constraints when applicable.

---

# 33. CHILD REQUIREMENTS

Examples:

* High chair.
* Booster seat.
* Stroller space.
* Kids Menu.

These may influence Table assignment and resource planning.

---

# 34. OCCASION

Possible occasions include:

* Birthday.
* Anniversary.
* Business meal.
* Family celebration.
* Date.
* Graduation.

Occasion information may support appropriate customer experience and recommendations.

---

# 35. SPECIAL REQUEST

A `ReservationSpecialRequest` may include:

* Cake.
* Decoration.
* Flowers.
* Preferred waiter.
* Quiet area.
* Special dietary arrangement.
* Surprise celebration.

Special requests shall be individually evaluated for feasibility.

---

# 36. SPECIAL REQUEST STATUS

Suggested states:

```text
REQUESTED

UNDER_REVIEW

APPROVED

CONFIRMED

DECLINED

COMPLETED
```

A Reservation may be confirmed while some optional special requests remain unresolved, if clearly communicated.

---

# 37. CUSTOMER PREFERENCES

Reservation Intelligence may use known preferences such as:

* Preferred Branch.
* Preferred Dining Area.
* Favorite Table.
* Preferred time.
* Preferred waiter.

Preferences reduce friction but shall not create unconfirmed assumptions.

---

# 38. CUSTOMER HISTORY

Historical Reservation evidence may support:

* Typical party size.
* Preferred times.
* Cancellation history.
* No-show history.
* Branch usage.

Historical behavior remains evidence rather than explicit preference.

---

# 39. CUSTOMER LOYALTY

Loyalty status may provide benefits such as:

* Priority waitlist.
* Early booking access.
* Preferred seating consideration.

Benefits shall follow explicit program rules.

---

# 40. FAIRNESS PRINCIPLE

Loyalty or VIP treatment shall not silently invalidate confirmed commitments made to other Customers.

Resource allocation rules shall remain governed.

---

# 41. EXPECTED DINING DURATION

Reservation planning may use an estimated Dining Duration.

Possible inputs:

* Party size.
* Day part.
* Customer history.
* Service style.
* Occasion.
* Branch historical performance.

This is a planning estimate.

---

# 42. RESERVATION END TIME

A Reservation may internally calculate an expected release time:

```text
Start Time
+
Estimated Dining Duration
+
Turnover Buffer
=
Expected Capacity Release
```

This supports availability planning.

---

# 43. TURNOVER BUFFER

Turnover may account for:

* Guest departure.
* Cleaning.
* Table reset.

ECIP shall not treat customer departure time as immediate availability.

---

# 44. RESERVATION CAPACITY

Capacity may be managed by:

* Seats.
* Tables.
* Dining Area.
* Service period.
* Restaurant-wide capacity.

Capacity methodology is implementation-specific but shall preserve reliable commitments.

---

# 45. OVERBOOKING

Overbooking means accepting more Reservations than expected physical capacity based on probabilistic assumptions.

The model supports policy-driven overbooking but does not require it.

AI shall never independently decide to overbook.

---

# 46. OVERBOOKING POLICY

Where enabled, policy shall define:

* Allowed scope.
* Maximum excess.
* Time periods.
* Party sizes.
* Risk thresholds.
* Approval requirements.

---

# 47. DOUBLE BOOKING

A Double Booking represents incompatible reservations for the same constrained capacity.

This shall be detected as a conflict.

---

# 48. RESERVATION CONFLICT

Possible conflicts include:

* Same Table committed twice.
* Capacity exceeded.
* Dining Area closed.
* Branch unavailable.
* Event blocks capacity.
* Existing Reservation modified.

Conflicts shall not be silently ignored.

---

# 49. WAITLIST

A `WaitlistEntry` represents a Customer request for service when immediate or requested reservation capacity is unavailable.

Typical attributes:

* Waitlist ID
* Customer
* Branch
* Party size
* Requested time
* Flexible time range
* Dining Area preference
* Priority
* Created time
* Expiration
* Estimated wait
* Status

---

# 50. WAITLIST LIFECYCLE

Suggested lifecycle:

```text
WAITING
→ OPPORTUNITY_AVAILABLE
→ CUSTOMER_CONTACTED
→ ACCEPTED
→ RESERVATION_CREATED
```

Alternative states:

```text
DECLINED
EXPIRED
CANCELLED
NO_RESPONSE
```

---

# 51. WAITLIST PRIORITY

Priority may consider explicit business rules such as:

* Entry time.
* Party size fit.
* Loyalty benefit.
* Operational efficiency.

The policy shall remain explainable and fair.

---

# 52. WAITLIST OPPORTUNITY

When capacity becomes available, ECIP may identify the most appropriate Waitlist candidates.

This is a recommendation until accepted by the Customer.

---

# 53. WAITLIST NOTIFICATION

Where authorized, the Customer may receive:

```text
"A table for four is now available at 8:30 PM. Would you like to reserve it?"
```

Availability may need temporary Hold protection while awaiting response.

---

# 54. WALK-IN WAITLIST

Walk-in Customers may enter the Waitlist when immediate seating is unavailable.

This creates continuity with `14_Dine_In.md`.

---

# 55. RESERVATION MODIFICATION

Customers may request changes to:

* Date.
* Time.
* Party size.
* Branch.
* Dining Area.
* Special requests.

Material changes shall trigger revalidation.

---

# 56. MODIFICATION LIFECYCLE

Suggested flow:

```text
Modification Requested
    ↓
Availability Revalidated
    ↓
Commercial / Policy Impact Checked
    ↓
Customer Confirmation
    ↓
Reservation Updated
```

---

# 57. DATE CHANGE

Changing the date may effectively require a new availability resolution.

The existing Reservation should not be released until the new arrangement is safely committed where possible.

---

# 58. TIME CHANGE

A time modification may impact:

* Capacity.
* Dining Area.
* Duration planning.
* Special services.

---

# 59. BRANCH CHANGE

A Branch change requires:

* New availability evaluation.
* Service capability check.
* Special request revalidation.

It may require a new external reservation mapping.

---

# 60. RESERVATION VERSIONING

Material changes shall preserve historical Reservation versions or equivalent mutation history.

The system should be able to answer:

> What was originally booked?

> What changed?

> Who changed it?

> When?

---

# 61. RESERVATION CANCELLATION

A Customer may cancel a Reservation.

Cancellation may involve:

* Capacity release.
* Deposit rules.
* Cancellation fee.
* Loyalty implications.
* Waitlist opportunity.

---

# 62. CANCELLATION REASON

Possible reasons:

* Customer plan changed.
* Customer selected another venue.
* Restaurant operational problem.
* Weather.
* Duplicate booking.
* Unknown.

Reason should be captured when available without unnecessary friction.

---

# 63. CANCELLATION POLICY

Policy may depend on:

* Party size.
* Time before Reservation.
* Special Event.
* Deposit.
* Private Room.
* Package.

ECIP shall explain authoritative policy rather than invent exceptions.

---

# 64. RESTAURANT-INITIATED CANCELLATION

A Restaurant may need to cancel due to:

* Closure.
* Emergency.
* Operational failure.
* Event conflict discovered.

This is a serious customer commitment failure and should trigger:

* Customer notification.
* Alternative recommendation.
* Service recovery where applicable.

---

# 65. DEPOSIT

Some Reservations may require a Deposit.

Examples:

* Large Party.
* Private Room.
* Special date.
* High-demand period.

Payment remains governed by `26_Payments.md`.

---

# 66. CREDIT CARD GUARANTEE

Some restaurants may require a valid payment method guarantee.

The Reservation model shall reference authorization evidence without storing sensitive card data.

---

# 67. CONFIRMATION REQUEST

Restaurants may request Customer reconfirmation before the Reservation.

Example:

```text
"Please confirm your reservation for Saturday at 8 PM."
```

---

# 68. REMINDER

Reservation reminders may be sent according to policy and Customer communication preferences.

Possible times:

* 24 hours before.
* Same day.
* Custom interval.

---

# 69. CONFIRMATION STATUS

Suggested values:

```text
NOT_REQUIRED

PENDING

CONFIRMED

DECLINED

NO_RESPONSE
```

---

# 70. NO RESPONSE

No response to a reminder does not automatically mean cancellation unless explicit policy says so.

---

# 71. ARRIVAL STATUS

Suggested states:

```text
EXPECTED

ARRIVED

LATE

SEATED

NO_SHOW
```

---

# 72. LATE ARRIVAL

Restaurants may define a grace period.

Example:

```text
Reservation:
20:00

Grace period:
15 minutes
```

Late arrival handling shall follow policy.

---

# 73. GRACE PERIOD

The grace period may depend on:

* Party size.
* Demand.
* Special Event.
* Table type.

---

# 74. NO-SHOW

A Reservation becomes `NO_SHOW` only after applicable timing and policy conditions are met.

No-show shall not be inferred immediately when the Customer is merely late.

---

# 75. NO-SHOW HISTORY

No-show records may support operational planning.

They shall not be used punitively outside business policy.

---

# 76. NO-SHOW RISK

Customer Intelligence may estimate No-Show Risk based on historical evidence.

This is a prediction and shall preserve confidence.

---

# 77. NO-SHOW MITIGATION

Possible strategies:

* Reminder.
* Confirmation request.
* Deposit.
* Waitlist.
* Controlled overbooking policy.

AI may recommend strategies but shall not autonomously impose penalties without authority.

---

# 78. CHECK-IN

`ReservationCheckIn` records Customer arrival for a confirmed Reservation.

Typical information:

* Reservation.
* Arrival time.
* Actual Party size.
* Employee.
* Status.
* Notes.

---

# 79. ACTUAL PARTY SIZE

Actual arriving Party size may differ from reserved size.

Possible cases:

* Fewer guests.
* More guests.

Larger parties may require new capacity validation.

---

# 80. CHECK-IN WITH FEWER GUESTS

The Restaurant may seat the party according to available policy.

Unused capacity may later be released.

---

# 81. CHECK-IN WITH ADDITIONAL GUESTS

Additional guests may require:

* Different Table.
* Table combination.
* Waiting.
* Alternative Dining Area.

ECIP shall not promise accommodation until feasibility is known.

---

# 82. SEATING

After check-in, Reservation transitions operationally into a Dining Session.

Conceptually:

```text
Reservation
    ↓
Check-In
    ↓
Table Assignment
    ↓
Dining Session
```

---

# 83. RESERVATION VS DINING SESSION

The Reservation represents the future commitment.

The Dining Session represents what actually happened.

Example:

```text
Reservation:
4 guests at 8 PM

Actual Dining Session:
5 guests seated at 8:12 PM
```

Both records shall remain preserved.

---

# 84. RESERVATION COMPLETION

A Reservation may be considered completed when the Customer is successfully seated and its booking responsibility has been fulfilled.

The Dining Session continues independently.

---

# 85. SPECIAL OCCASION EXPERIENCE

Reservations may trigger operational Tasks such as:

* Birthday setup.
* Anniversary dessert.
* Flower placement.

These shall be tracked as explicit commitments or Tasks.

---

# 86. RESERVATION COMMITMENT

Examples:

```text
Restaurant:
Reserve wheelchair-accessible Table.

Restaurant:
Prepare birthday dessert.

Customer:
Confirm final Party size.
```

Commitments shall remain explicit.

---

# 87. RESERVATION CONVERSATION

A Reservation may have multiple associated Conversations.

Example:

```text
Initial booking
    ↓
WhatsApp modification
    ↓
Telephone confirmation
```

All may reference the same Reservation.

---

# 88. CONVERSATIONAL BOOKING

Example:

```text
Customer:
"I need a table for six this Saturday at 8."

ECIP:
Resolve Branch
Search availability
Identify suitable slots
Ask required clarification
Present options
Receive Customer selection
Create Hold if necessary
Confirm details
Execute Reservation creation
```

---

# 89. AMBIGUOUS RESERVATION REQUEST

Example:

```text
Customer:
"Book my usual table for Friday."
```

ECIP may use:

* Customer history.
* Preference.
* Typical Branch.

But shall confirm material assumptions before final booking.

---

# 90. RESERVATION RECOMMENDATION

If exact availability is unavailable, ECIP may recommend:

* Nearby time.
* Alternate Branch.
* Alternate Dining Area.
* Waitlist.

The recommendation shall optimize Customer intent before restaurant utilization.

---

# 91. PROACTIVE RESERVATION OPPORTUNITY

Where permitted, ECIP may identify relevant opportunities such as:

* Upcoming anniversary.
* Recurring corporate lunch.
* Customer birthday.

This may support customer relationship activity but shall respect communication consent.

---

# 92. CUSTOMER HISTORY

Reservation history may include:

* Created bookings.
* Modifications.
* Cancellations.
* No-shows.
* Completed visits.
* Party size.
* Branch.
* Dining Area.

History provides evidence for future intelligence.

---

# 93. CUSTOMER PREFERENCES

Reservations consume governed preferences.

Examples:

* Terrace.
* Quiet Table.
* Preferred Branch.
* Preferred time.

Preferences do not equal guaranteed booking conditions.

---

# 94. CUSTOMER LOYALTY

Loyalty may affect benefits such as:

* Waitlist priority.
* Special booking access.
* Eligible perks.

Benefits shall follow explicit program policy.

---

# 95. SALES INTELLIGENCE

Reservation context may generate relevant commercial recommendations.

Examples:

* Anniversary package.
* Birthday dessert.
* Private room.
* Preordered wine.
* Banquet opportunity for very large party.

Recommendations shall remain optional.

---

# 96. EVENT CONVERSION

A large or complex Reservation Request may become an Event Inquiry.

Example:

```text
Customer:
"I need a table for 60 people."

Standard Reservation:
Not appropriate.

Result:
Potential Event / Banquet Inquiry
```

Routing shall preserve the original Conversation Context.

---

# 97. OPERATIONAL INTELLIGENCE

Reservation data supports:

* Demand forecasting.
* Occupancy forecasting.
* Staffing planning.
* Table utilization.
* Waitlist management.
* No-show analysis.
* Peak-period detection.

---

# 98. RESERVATION FORECAST

Future Reservation load may contribute to expected:

* Guest volume.
* Kitchen demand.
* Staff demand.
* Parking demand.
* Inventory needs.

---

# 99. CAPACITY OPTIMIZATION

Potential optimization goals include:

* Satisfy Customer requests.
* Avoid overbooking.
* Improve Table utilization.
* Reduce wait times.
* Preserve flexibility.

Optimization shall not reduce customer experience to occupancy maximization alone.

---

# 100. TABLE ASSIGNMENT OPTIMIZATION

Reservation may influence future Table planning.

Actual assignment may be delayed until closer to arrival.

This allows adaptation to:

* Cancellations.
* Party-size changes.
* Operational conditions.

---

# 101. HUMAN ESCALATION

Escalation may be required for:

* Large party.
* VIP request outside policy.
* Capacity conflict.
* Private room.
* Special accessibility issue.
* Customer dispute.
* Deposit exception.
* Complex modification.

Handoff shall include relevant Reservation Context.

---

# 102. AI AUTHORITY LIMIT

AI may:

* Search governed availability.
* Present available options.
* Create authorized Reservations.
* Modify permitted fields.
* Cancel according to policy.
* Manage Waitlist interactions.
* Send reminders where authorized.

AI shall not:

* Invent availability.
* Overbook outside policy.
* Guarantee unconfirmed Table preferences.
* Waive required deposits.
* Ignore capacity restrictions.
* Create unauthorized VIP priority.

---

# 103. SOURCE OF TRUTH

Reservation authority may vary by deployment.

Example:

```text
External Reservation System:
Reservation System of Record

ECIP:
Conversational orchestration

POS:
Dining Session / Table operational state
```

Ownership shall be explicitly configured.

---

# 104. EXTERNAL RESERVATION MAPPING

External systems may provide:

* Reservation ID.
* Table ID.
* Guest ID.
* Waitlist ID.

These shall map to canonical ECIP entities.

---

# 105. RESERVATION SYNCHRONIZATION

Synchronization may include:

* Reservation creation.
* Modification.
* Cancellation.
* Check-in.
* No-show.
* Seating.
* Waitlist changes.

Synchronization shall be idempotent and observable.

---

# 106. RESERVATION CONFLICT HANDLING

Possible conflict:

```text
ECIP:
Reservation confirmed

External System:
Slot unavailable
```

This is a critical commitment conflict.

The system shall:

1. Detect conflict.
2. Preserve evidence.
3. Avoid hiding the problem.
4. Trigger remediation or Human escalation.
5. Communicate appropriately with the Customer.

---

# 107. RESERVATION EVENTS

Initial events include:

```text
ReservationRequestCreated

ReservationAvailabilityRequested
ReservationAvailabilityEvaluated

ReservationHoldCreated
ReservationHoldConfirmed
ReservationHoldExpired
ReservationHoldReleased

ReservationCreated
ReservationConfirmed

ReservationModificationRequested
ReservationModified

ReservationCancellationRequested
ReservationCancelled

ReservationReminderScheduled
ReservationReminderSent

ReservationConfirmationRequested
ReservationReconfirmed

WaitlistEntryCreated
WaitlistOpportunityDetected
WaitlistCustomerContacted
WaitlistAccepted
WaitlistDeclined
WaitlistExpired

ReservationCustomerArrived
ReservationCustomerLate

ReservationCheckedIn

ReservationPartySizeChanged

ReservationSeatingRequested
ReservationSeated

ReservationNoShowRecorded

ReservationCompleted

ReservationConflictDetected
ReservationConflictResolved

ReservationSynchronizationStarted
ReservationSynchronizationCompleted
ReservationSynchronizationFailed
```

---

# 108. RELATIONSHIPS

```text
Customer
    MAKES ReservationRequest

ReservationRequest
    PRODUCES ReservationAvailability

ReservationRequest
    MAY_CREATE ReservationHold

ReservationHold
    MAY_BECOME Reservation

Customer
    HAS Reservation

Reservation
    OCCURS_AT Branch

Reservation
    MAY_PREFER DiningArea

Reservation
    HAS PartySize

Reservation
    MAY_HAVE SpecialRequest

Reservation
    MAY_REQUIRE Deposit

Reservation
    MAY_CREATE Commitment

Reservation
    MAY_ENTER Waitlist

WaitlistEntry
    MAY_CREATE Reservation

Reservation
    MAY_CHECK_IN_AS ReservationCheckIn

Reservation
    MAY_CREATE DiningSession

Conversation
    MAY_REFERENCE Reservation

Reservation
    GENERATES CustomerHistoryEvent

Reservation
    MAPS_TO ExternalEntityReference
```

---

# 109. BUSINESS RULES

The following rules apply:

1. A Reservation represents a future commitment, not an actual Dining Session.

2. A Reservation Request does not reserve capacity.

3. A Hold temporarily reserves capacity and shall have an expiration.

4. Availability shall be verified before Reservation confirmation.

5. Customer Table or Dining Area preferences shall not be represented as guaranteed unless explicitly committed.

6. Party-size increases shall trigger capacity revalidation.

7. Material Reservation changes shall trigger applicable availability and policy revalidation.

8. Reservation version history shall remain traceable.

9. Reservation cancellation shall release applicable capacity.

10. No-show shall only be recorded according to applicable timing and policy.

11. Waitlist position and priority shall follow explicit business rules.

12. AI shall not invent availability.

13. AI shall not bypass deposit, capacity or overbooking policies.

14. External Reservation identifiers shall not replace canonical identities.

15. Reservation synchronization shall preserve authoritative ownership.

16. Confirmed Reservation conflicts shall be treated as material customer commitment failures.

17. Seating transitions Reservation responsibility into Dine-In operational responsibility.

18. Historical Reservation evidence shall remain available after the visit.

---

# 110. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
ReservationRequest

ReservationAvailability

ReservationSlot

ReservationHold

Reservation

ReservationStatus

ReservationConfirmation

ReservationModification

ReservationCancellation

PartySize

DiningAreaPreference

SpecialRequest

WaitlistEntry

WaitlistOpportunity

ReservationReminder

ReservationCheckIn

ReservationNoShow

ReservationConversationReference

ExternalReservationMapping

ReservationHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Probabilistic Overbooking

AI Table Assignment Optimization

Advanced No-Show Prediction

Dynamic Reservation Duration Prediction

Autonomous Waitlist Optimization

Cross-Branch Capacity Optimization

Advanced Revenue Management for Reservations
```

---

# 111. IMPLEMENTATION PRINCIPLE

This document defines the logical Reservations Model.

It does not prescribe:

* Reservation vendor.
* Database schema.
* Table map user interface.
* Optimization algorithm.
* POS implementation.
* Notification provider.
* Payment implementation.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
RESERVATION REQUEST

AVAILABILITY

RESERVATION HOLD

RESERVATION

WAITLIST

CHECK-IN

TABLE ASSIGNMENT

DINING SESSION
```

---

# 112. FINAL RULE

Before ECIP creates, changes or confirms a Reservation, it shall be able to determine:

> Who is making the Reservation?

> Which Branch, date and time are requested?

> What is the actual Party size?

> What preferences, accessibility needs or special requirements apply?

> What capacity is actually available?

> Is the requested Dining Area or Table a preference or a guaranteed commitment?

> Is a Hold required while the Customer confirms?

> Are any Deposit, guarantee or cancellation policies applicable?

> Are there conflicts with existing Reservations, Events or operational capacity?

> What alternative options exist if the requested slot is unavailable?

> Has the Customer clearly confirmed the material details?

> What happens if the Customer modifies, cancels, arrives late or does not arrive?

> Can the Reservation transition cleanly into the actual Dining Session?

> Can every material Reservation decision and Action be reconstructed and audited?

Only after these conditions are resolved may ECIP represent a Reservation as validly held, confirmed, modified, cancelled, waitlisted, checked in or completed.

