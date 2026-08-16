# 13_Order.md

**Document ID:** RDM-013
**Document Name:** Order
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Order Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete commercial and operational lifecycle of a restaurant order, independently of the sales channel, service type, Point of Sale system or user interface.

An Order is the central commercial commitment connecting:

* Customer intent.
* Product selection.
* Pricing.
* Promotions.
* Kitchen production.
* Inventory consumption.
* Payment.
* Fulfillment.
* Delivery or pickup.
* Customer history.
* Loyalty.
* Conversational context.

The Order Model shall support both human-created and AI-assisted orders while preserving authorization, traceability and operational integrity.

---

# 2. OBJECTIVES

The Order Model enables ECIP to:

* Create orders.
* Modify orders.
* Cancel orders.
* Track order status.
* Support multiple service types.
* Support multiple sales channels.
* Associate orders with customers.
* Preserve product and price history.
* Apply promotions and loyalty benefits.
* Support modifiers and substitutions.
* Coordinate kitchen production.
* Coordinate delivery and pickup.
* Support split fulfillment.
* Support split payment.
* Support refunds and cancellations.
* Preserve complete audit history.
* Provide conversational order support.
* Detect abandoned orders.
* Support Sales Intelligence.
* Support Executive Intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Customer
* Action Request
* Action Authorization
* Action Execution
* Action Result
* Commitment
* Context Snapshot
* Decision
* Recommendation
* Workflow Instance
* External Entity Reference
* Audit Event

Restaurant-specific Order entities remain within the Restaurant Domain Pack.

This document does not replace canonical action execution or workflow governance.

---

# 4. ORDER PRINCIPLE

An Order represents a governed commercial request for restaurant Products or Services.

The platform shall distinguish between:

```text
Customer Intent

Shopping / Selection Context

Order

Kitchen Production

Payment

Fulfillment

Delivery

Historical Transaction
```

These concepts are related but shall not be collapsed into one entity.

---

# 5. ORDER

An `Order` represents the commercial container for one restaurant transaction or fulfillment request.

Typical attributes include:

* Order ID
* Tenant ID
* Restaurant
* Branch
* Customer
* Service type
* Channel
* Order status
* Fulfillment status
* Payment status
* Currency
* Order subtotal
* Discounts
* Charges
* Taxes
* Total
* Created time
* Confirmed time
* Requested fulfillment time
* Estimated completion time
* Actual completion time
* Source system
* External identifiers
* Conversation reference
* Reservation reference
* Employee or Agent responsible
* Version

---

# 6. ORDER TYPES

Initial Order types may include:

* Dine In
* Take Away
* Delivery
* Drive Through
* Catering
* Banquet
* Buffet-related charge
* Preorder
* Scheduled order
* Corporate order

Detailed service-specific behavior is extended in subsequent domain documents.

---

# 7. ORDER LIFECYCLE

Suggested high-level lifecycle:

```text
DRAFT
→ PENDING_CONFIRMATION
→ CONFIRMED
→ IN_PREPARATION
→ READY
→ FULFILLED
→ COMPLETED
```

Alternative states include:

```text
CANCELLED
REJECTED
EXPIRED
FAILED
PARTIALLY_FULFILLED
```

Payment and production have separate lifecycles and shall not be inferred solely from Order status.

---

# 8. DRAFT ORDER

A Draft Order represents a commercial selection that has not yet become a confirmed commitment.

Draft Orders may originate from:

* Customer conversation.
* Web cart.
* Mobile App.
* Employee entry.
* Kiosk.
* AI recommendation flow.

Draft state permits changes according to business rules.

---

# 9. ORDER CONFIRMATION

Confirmation establishes the restaurant's commercial commitment to process the Order.

Before confirmation, ECIP should verify:

* Product offerability.
* Modifier validity.
* Branch eligibility.
* Service eligibility.
* Pricing.
* Promotions.
* Customer restrictions.
* Operational capacity.
* Fulfillment feasibility.
* Required approvals.

---

# 10. ORDER ITEM

An `OrderItem` represents a selected Product or Product Variant within an Order.

Typical attributes:

* Order Item ID
* Product ID
* Product Version
* Product Variant
* Quantity
* Unit price
* Modifier selections
* Discount allocation
* Promotion reference
* Tax
* Item total
* Preparation notes
* Fulfillment state
* Production state

---

# 11. PRODUCT SNAPSHOT

Each Order Item shall preserve sufficient Product information to reconstruct the historical transaction.

Typical snapshot may include:

* Product name
* Variant
* Size
* SKU
* Menu reference
* Product Version
* Recipe Version when required

Current catalog changes shall not rewrite historical Order Items.

---

# 12. ORDER ITEM QUANTITY

Quantity shall be explicit.

Rules may include:

* Minimum quantity.
* Maximum quantity.
* Integer-only quantity.
* Decimal quantity for applicable products.

Quantity constraints shall derive from Product and business rules.

---

# 13. ORDER ITEM MODIFIER

An `OrderItemModifier` represents a selected Product customization.

Examples:

* Extra cheese.
* No onion.
* Medium rare.
* Salad instead of fries.

It shall preserve:

* Modifier ID.
* Display value.
* Price impact.
* Recipe impact.
* Historical Product reference.

---

# 14. ORDER ITEM SUBSTITUTION

A substitution may replace an Ingredient, Modifier or Product component.

Substitutions shall be:

* Explicitly allowed.
* Customer-confirmed when material.
* Safety-validated.
* Price-resolved.
* Auditable.

AI shall not invent substitutions.

---

# 15. ORDER ITEM NOTES

Free-text notes may support special instructions.

Examples:

* "Sauce on the side."
* "Birthday guest."
* "Please package separately."

Free text shall not override structured safety or production rules.

---

# 16. ORDER ITEM STATUS

Suggested item lifecycle:

```text
ADDED
→ VALIDATED
→ CONFIRMED
→ QUEUED
→ IN_PREPARATION
→ READY
→ SERVED / HANDED_OFF
```

Alternative states:

```text
REMOVED
CANCELLED
REJECTED
UNAVAILABLE
```

---

# 17. ORDER GROUPING

Order Items may be grouped by:

* Course.
* Guest.
* Seat.
* Kitchen station.
* Delivery package.
* Payment party.
* Fulfillment time.

Grouping supports operational coordination.

---

# 18. COURSE

Dine-in Orders may organize Products into Courses.

Examples:

* Appetizer.
* Main course.
* Dessert.

Course timing shall remain distinct from Product identity.

---

# 19. CUSTOMER ASSOCIATION

An Order may be associated with:

* Identified Customer.
* Anonymous Customer.
* Corporate Customer.
* Household.
* Reservation party.

Customer identification may occur before or after Order creation.

---

# 20. ORDER PARTICIPANTS

An Order may involve multiple people.

Examples:

* Ordering Customer.
* Guests.
* Employee.
* Cashier.
* Waiter.
* AI Agent.
* Delivery driver.

Participants shall have explicit roles.

---

# 21. ORDER CHANNEL

Order source channel may include:

* Telephone.
* WhatsApp.
* Web Chat.
* Mobile App.
* Walk-in.
* POS.
* Kiosk.
* Delivery platform.
* Social messaging.

Channel shall not redefine Order semantics.

---

# 22. ORDER SERVICE TYPE

Service type determines fulfillment behavior.

Examples:

```text
DINE_IN
TAKE_AWAY
DELIVERY
DRIVE_THROUGH
CATERING
BANQUET
```

Service-specific rules are extended by dedicated domain documents.

---

# 23. ORDER BRANCH

Every operational Order shall be assigned to a Branch before final confirmation.

Branch assignment may depend on:

* Customer choice.
* Delivery zone.
* Product availability.
* Capacity.
* Service type.
* Operational policy.

---

# 24. ORDER MENU CONTEXT

An Order should preserve the Menu and Menu Version applicable when Products were selected.

This supports:

* Pricing audit.
* Promotion audit.
* Product dispute resolution.
* Historical reconstruction.

---

# 25. ORDER PRICE

Each Order Item shall preserve the Price actually used.

Pricing is resolved by `12_Pricing_and_Promotions.md`.

Order does not own Pricing rules.

It owns the resulting transaction values.

---

# 26. ORDER COMMERCIAL SUMMARY

Typical commercial structure:

```text
Item Subtotal
+
Modifier Charges
+
Packaging
+
Delivery
+
Service Charges
-
Promotions
-
Discounts
-
Loyalty Benefits
+
Taxes
=
Order Total
```

All components shall remain traceable.

---

# 27. ORDER DISCOUNT

Discounts shall preserve:

* Source.
* Authorization.
* Promotion or reason.
* Amount.
* Scope.
* Actor.

Manual discounts require the appropriate canonical Action Authorization.

---

# 28. ORDER PROMOTION

An Order may apply one or more eligible Promotions according to combination rules.

Order shall preserve:

* Promotion ID.
* Promotion Version.
* Benefit amount.
* Qualified items.
* Qualification evidence.

---

# 29. ORDER LOYALTY BENEFIT

Loyalty benefits may affect:

* Price.
* Free Products.
* Points.
* Upgrades.
* Service.

The Loyalty domain remains authoritative for membership and balance.

---

# 30. ORDER TAX

Order shall preserve the tax result applied at transaction time.

Tax authority may remain with:

* POS.
* ERP.
* Fiscal system.

ECIP shall not invent fiscal values.

---

# 31. ORDER CHARGE

Additional charges may include:

* Delivery fee.
* Packaging.
* Service charge.
* Event charge.
* Minimum order surcharge.

Charges shall be explicit and explainable.

---

# 32. ORDER TOTAL

The final total shall be calculated deterministically.

LLMs shall never calculate authoritative Order totals without governed computational logic.

---

# 33. ORDER VALIDATION

Before confirmation, Order validation shall consider:

```text
Products valid
+
Modifiers valid
+
Prices valid
+
Promotions valid
+
Customer constraints satisfied
+
Operational feasibility
+
Branch and service eligibility
=
Order potentially confirmable
```

---

# 34. PRODUCT AVAILABILITY VALIDATION

Every Order Item shall be validated against current Product offerability.

A Product present in the Menu may no longer be operationally available.

---

# 35. CUSTOMER SAFETY VALIDATION

Known safety constraints shall be checked against ordered Products where appropriate.

Examples:

* Allergens.
* Dietary restrictions.
* Age restrictions.

Safety warnings shall not silently alter customer choices without policy.

---

# 36. OPERATIONAL FEASIBILITY

Order confirmation may depend on:

* Kitchen capacity.
* Ingredient availability.
* Equipment.
* Staffing.
* Delivery capacity.
* Pickup capacity.

Operational feasibility shall be part of Context.

---

# 37. ESTIMATED PREPARATION TIME

The Order may receive an estimated preparation time.

This estimate may depend on:

* Product Recipes.
* Kitchen queue.
* Station utilization.
* Quantity.
* Product complexity.

Estimates shall be distinguished from guarantees.

---

# 38. PROMISED TIME

A `PromisedFulfillmentTime` represents the commitment communicated to the Customer.

It may differ from estimated time.

A promised time shall only be issued under authorized operational rules.

---

# 39. SCHEDULED ORDER

Orders may be scheduled for future execution.

Typical attributes:

* Requested date.
* Requested time.
* Preparation start window.
* Fulfillment window.

Scheduling shall consider future operational availability.

---

# 40. PREORDER

A Preorder is an Order created before normal immediate fulfillment.

Examples:

* Tomorrow's lunch.
* Large office order.
* Holiday order.

Preorders may require advance confirmation or deposit.

---

# 41. ORDER CHANGE

A confirmed Order may be modified according to its current lifecycle state.

Examples:

* Add item.
* Remove item.
* Change modifier.
* Change quantity.
* Change service type.

Modification eligibility shall be policy-driven.

---

# 42. ORDER VERSION

Material changes shall increment Order Version or preserve equivalent change history.

Each version should allow reconstruction of:

* Items.
* Pricing.
* Promotions.
* Customer commitments.

---

# 43. CHANGE AFTER PRODUCTION START

When Kitchen Production has already started, changes may require:

* Employee approval.
* Additional charge.
* Waste handling.
* Production cancellation.

Conversational AI shall not assume confirmed Orders remain freely editable.

---

# 44. ORDER CANCELLATION

Cancellation may apply to:

* Entire Order.
* Individual Order Items.

Cancellation rules may depend on:

* Status.
* Production progress.
* Payment.
* Service type.
* Business policy.

---

# 45. CANCELLATION REASON

Typical reasons:

* Customer requested.
* Product unavailable.
* Operational failure.
* Payment failure.
* Duplicate Order.
* Delivery issue.
* Restaurant cancellation.

Cancellation reason shall be preserved.

---

# 46. ORDER REJECTION

An Order may be rejected before confirmation.

Possible reasons:

* Product unavailable.
* Outside service area.
* Branch closed.
* Capacity unavailable.
* Policy violation.
* Payment requirement not met.

Rejection shall provide an explainable reason.

---

# 47. PARTIAL CANCELLATION

Individual Order Items may be cancelled while the remaining Order continues.

Price and payment state shall be recalculated safely.

---

# 48. ORDER FAILURE

Technical execution failure shall be distinguished from business rejection.

Examples:

```text
BUSINESS REJECTION:
Delivery address outside zone.

TECHNICAL FAILURE:
POS unavailable.
```

This distinction is critical for recovery.

---

# 49. ORDER IDEMPOTENCY

Order creation and mutations shall support idempotency where applicable.

This prevents duplicate Orders caused by:

* Network retries.
* Provider retries.
* AI tool retries.
* Customer repeated submissions.

---

# 50. DUPLICATE ORDER DETECTION

The platform may detect potential duplicate Orders based on:

* Customer.
* Product composition.
* Time.
* Amount.
* Channel.
* External identifier.

Detection alone shall not automatically cancel an Order.

---

# 51. ORDER AUTHORIZATION

Different mutations may require different authority levels.

Examples:

Low risk:

* Add Product before confirmation.

Higher risk:

* Cancel paid Order.
* Apply manual discount.
* Change completed transaction.

Authorization shall use the canonical Action Runtime.

---

# 52. AI-ASSISTED ORDER CREATION

Conversational AI may assist a Customer in creating an Order.

Example:

```text
Customer:
"I want two medium pepperoni pizzas and a Coke."

ECIP:
Resolve Products
Resolve sizes
Validate availability
Resolve pricing
Clarify beverage size if required
Present Order summary
Obtain confirmation
Execute authorized Order creation
```

AI understanding is not itself an Order mutation.

---

# 53. ORDER CONFIRMATION BY CUSTOMER

Before a significant commercial commitment, ECIP should provide a clear summary when appropriate.

Example:

```text
2 × Medium Pepperoni Pizza
1 × 1L Coca-Cola
Delivery
Total: $540
Estimated delivery: 45–55 minutes
```

The customer confirms before execution according to policy.

---

# 54. NATURAL LANGUAGE CORRECTION

Example:

```text
Customer:
"Actually make one of the pizzas vegetarian."
```

ECIP should:

1. Identify intended Order Item.
2. Validate requested replacement.
3. Recalculate commercial values.
4. Reconfirm material changes.
5. Execute authorized mutation.

---

# 55. AMBIGUITY RESOLUTION

Example:

```text
Customer:
"Send me the usual."
```

ECIP shall not blindly create an Order.

It may use history to identify likely intent, then ask for confirmation.

---

# 56. REORDER

A previous Order may serve as a template.

Example:

```text
"Would you like the same order as last Friday?"
```

The new Order shall still revalidate:

* Product existence.
* Price.
* Availability.
* Promotions.
* Current customer constraints.

Historical Order data shall not bypass current validation.

---

# 57. ABANDONED ORDER

A Draft Order may become abandoned when the Customer does not complete confirmation.

Potential causes:

* Price concern.
* Product unavailable.
* Customer interruption.
* Payment issue.

Abandoned Orders may contribute to Sales Intelligence.

---

# 58. ORDER RECOVERY

Where appropriate, ECIP may recover a recent Draft Order across channels.

Example:

```text
Web Chat → Telephone
```

Context continuity shall preserve the Draft Order when identity and authorization permit.

---

# 59. ORDER AND CONVERSATION

An Order may be associated with one or more Conversations.

A Conversation may discuss multiple Orders.

The relationship shall remain many-to-many where necessary.

---

# 60. ORDER AND RESERVATION

Dine-in Orders may reference:

* Reservation.
* Dining session.
* Table.

Reservation does not own the Order.

---

# 61. ORDER AND KITCHEN

Confirmed Products requiring preparation generate production work.

Conceptually:

```text
Order
    ↓
Order Items
    ↓
Production Requirements
    ↓
Kitchen Queues
```

Detailed Kitchen behavior belongs to `20_Kitchen.md` and `21_Production.md`.

---

# 62. ORDER AND RECIPE

Recipe determines:

* Ingredient requirements.
* Preparation requirements.
* Station requirements.

Order records the selected Product and modifiers.

---

# 63. ORDER AND INVENTORY

Confirmed or produced Order Items may create theoretical or actual Inventory consumption.

Inventory remains authoritative for stock movement.

---

# 64. ORDER AND PAYMENT

Order commercial obligation and Payment are separate entities.

Conceptually:

```text
Order
    HAS Payment Requirement

Payment
    SETTLES Order
```

An Order may have:

* Zero Payments.
* One Payment.
* Multiple Payments.
* Partial Payments.
* Refunds.

Detailed Payment behavior belongs to `26_Payments.md`.

---

# 65. ORDER PAYMENT STATUS

Suggested high-level statuses:

```text
NOT_REQUIRED
UNPAID
PARTIALLY_PAID
PAID
PARTIALLY_REFUNDED
REFUNDED
PAYMENT_FAILED
```

This shall be derived from Payment evidence.

---

# 66. ORDER AND CASH REGISTER

In-person Orders may be associated with a Cash Register or POS session.

Cash management remains a separate domain.

---

# 67. ORDER AND DELIVERY

Delivery Orders extend the Order Model with:

* Delivery address.
* Zone.
* Driver.
* ETA.
* Tracking.
* Delivery fee.

Detailed behavior belongs to `16_Delivery.md`.

---

# 68. ORDER AND TAKE AWAY

Take Away Orders extend the model with:

* Pickup branch.
* Pickup window.
* Customer arrival.
* Handoff.

Detailed behavior belongs to `15_Take_Away.md`.

---

# 69. ORDER AND DINE IN

Dine-in Orders may include:

* Table.
* Dining session.
* Seat.
* Waiter.
* Courses.

Detailed behavior belongs to `14_Dine_In.md`.

---

# 70. ORDER AND BANQUET

Banquet Orders may be associated with:

* Event.
* Contract.
* Package.
* Deposit.
* Guest count.

Detailed behavior belongs to `17_Banquets_and_Events.md`.

---

# 71. SPLIT ORDER

A business transaction may need to be logically divided.

Examples:

* Different fulfillment methods.
* Separate kitchen timing.
* Separate checks.

The model shall preserve relationships between parent and child Order structures where needed.

---

# 72. SPLIT BILL

Multiple Customers may pay portions of one Dine-in Order.

Payment allocation shall not require duplicating Order Items.

---

# 73. ORDER ITEM TRANSFER

An Item may move between:

* Guest.
* Seat.
* Check.

Transfer shall preserve audit history.

---

# 74. MERGE ORDERS

Where business policy permits, compatible Orders may be merged.

Examples:

* Two tables combined.
* Duplicate Draft Orders.

Merge shall preserve source references.

---

# 75. ORDER PACKAGE

Orders may include Product Bundles or Packages.

The Order shall preserve:

* Package identity.
* Selected components.
* Upgrades.
* Applied price.

---

# 76. ORDER RECOMMENDATION

Sales Intelligence may recommend additional Products before confirmation.

Example:

```text
Current:
2 pizzas

Recommendation:
Family beverage bundle
```

Recommendation shall not automatically mutate the Order.

---

# 77. UPSELL

Upselling may suggest:

* Larger size.
* Premium Product.
* Premium side.
* Better beverage.

Customer approval is required before mutation.

---

# 78. CROSS-SELL

Cross-selling may suggest complementary Products.

Examples:

* Beverage.
* Dessert.
* Appetizer.

Recommendations should be context-aware.

---

# 79. ORDER AND CUSTOMER PREFERENCES

Preferences may support:

* Default modifiers.
* Product recommendations.
* Service type.
* Reorder suggestions.

Preferences shall not create Items without customer authorization.

---

# 80. ORDER AND ALLERGIES

Known allergies may trigger:

* Warning.
* Clarification.
* Product incompatibility notice.
* Human escalation.

They shall never silently alter an Order in ways the customer cannot understand.

---

# 81. ORDER AND CUSTOMER HISTORY

Customer History may support:

* Reordering.
* Typical quantities.
* Preferred Products.
* Abandoned Order recovery.

Every new Order remains a new transaction with current rules.

---

# 82. ORDER AND LOYALTY

Order activity may:

* Earn points.
* Redeem rewards.
* Trigger milestones.

Loyalty updates occur through governed loyalty actions.

---

# 83. ORDER AND PROMOTIONS

Promotion eligibility may depend on final Order contents.

Order changes may therefore cause:

* Promotion activation.
* Promotion removal.
* Price recalculation.

This shall be deterministic.

---

# 84. ORDER AND OPERATIONAL CONTEXT

Operational Context may influence whether the Order can be confirmed.

Examples:

* Kitchen saturated.
* Product unavailable.
* Delivery closed.
* Branch closing soon.

ECIP shall not make commitments disconnected from current operational reality.

---

# 85. ORDER PRIORITY

Orders may have operational priority.

Examples:

* Normal.
* Scheduled.
* Rush.
* VIP event.
* Recovery order.

Priority shall be governed and shall not bypass safety or fairness rules without authorization.

---

# 86. ORDER SLA

Service-type policies may define:

* Preparation target.
* Pickup target.
* Delivery target.

Actual performance may be measured against these objectives.

---

# 87. ORDER INCIDENT

Order-specific incidents may include:

* Missing Product.
* Wrong Product.
* Preparation delay.
* Payment discrepancy.
* Delivery delay.
* Quality issue.

Incidents link to Operational Incident and Customer History domains.

---

# 88. ORDER COMPLAINT

Customer complaints may reference:

* Entire Order.
* Individual Item.
* Delivery.
* Payment.
* Employee interaction.

This enables root-cause analysis.

---

# 89. ORDER SERVICE RECOVERY

Recovery actions may include:

* Replacement.
* Refund.
* Discount.
* Follow-up.

These require governed authorization.

---

# 90. ORDER SOURCE OF TRUTH

The authoritative Order system may vary by deployment.

Examples:

```text
POS:
Operational Order System of Record

ECIP:
Conversational Order Orchestration

Delivery Platform:
External Order origin
```

Ownership shall be explicitly configured.

---

# 91. EXTERNAL ORDER MAPPING

Example:

```text
ECIP Order:
ORD-10025

POS:
TICKET-83882

Delivery Platform:
ORDER-ABC-221
```

External identifiers shall remain mappings.

---

# 92. ORDER SYNCHRONIZATION

Synchronization may include:

* New Orders.
* Status changes.
* Item changes.
* Cancellation.
* Payment status.
* Fulfillment status.

Sync behavior shall be idempotent and auditable.

---

# 93. ORDER CONFLICT

Conflicts may occur when:

* ECIP believes Order is editable but POS has started production.
* POS marks Product unavailable after Draft creation.
* Delivery platform changes Order.

Conflicts shall be resolved using authoritative ownership rules.

---

# 94. ORDER EVENT CATALOG

Initial events include:

```text
OrderCreated
OrderDraftUpdated
OrderValidationStarted
OrderValidated
OrderValidationFailed

OrderConfirmationRequested
OrderConfirmed
OrderRejected

OrderItemAdded
OrderItemUpdated
OrderItemRemoved
OrderItemSubstituted

OrderPriceResolved
OrderPromotionApplied
OrderPromotionRemoved
OrderDiscountApplied

OrderSubmittedToProduction
OrderPreparationStarted
OrderReady

OrderFulfillmentStarted
OrderFulfilled
OrderCompleted

OrderModificationRequested
OrderModified

OrderCancellationRequested
OrderCancelled
OrderItemCancelled

OrderPaymentStatusChanged

OrderDelayed
OrderIncidentDetected

OrderAbandoned
OrderRecovered

OrderSynchronizationStarted
OrderSynchronizationCompleted
OrderSynchronizationFailed
OrderConflictDetected
OrderConflictResolved
```

---

# 95. RELATIONSHIPS

```text
Customer
    PLACES Order

Order
    CONTAINS OrderItem

OrderItem
    REFERENCES Product

OrderItem
    REFERENCES ProductVariant

OrderItem
    HAS OrderItemModifier

Order
    USES MenuVersion

Order
    APPLIES Price

Order
    MAY_APPLY Promotion

Order
    MAY_USE LoyaltyBenefit

Order
    MAY_REFERENCE Reservation

Order
    MAY_REQUIRE Payment

Order
    GENERATES ProductionWork

Order
    MAY_REQUIRE Delivery

Order
    MAY_REQUIRE Pickup

Conversation
    MAY_REFERENCE Order

Order
    MAY_CREATE Commitment

Order
    MAY_GENERATE CustomerHistoryEvent

Order
    MAPS_TO ExternalEntityReference
```

---

# 96. BUSINESS RULES

The following rules apply:

1. An Order shall have one canonical identity.

2. Order Items shall preserve historical Product references.

3. Current Product changes shall not rewrite historical Orders.

4. Authoritative totals shall be calculated deterministically.

5. AI shall not invent Prices, Promotions or Order Items.

6. Order confirmation requires successful applicable validation.

7. Product offerability shall be checked before confirmation.

8. Known safety constraints shall receive appropriate validation.

9. Customer confirmation shall be obtained for material commercial changes when required.

10. Recommendations shall not automatically mutate Orders.

11. Confirmed Order modification shall respect operational state.

12. Order cancellation shall respect Payment and Production status.

13. Order creation and mutations shall support idempotency where applicable.

14. Payment state and Order state shall remain separate.

15. Production state and Order state shall remain separate.

16. External system IDs shall not replace canonical Order identity.

17. Order history shall preserve complete commercial traceability.

18. Actions affecting confirmed Orders shall use governed authorization.

---

# 97. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Order

OrderItem

OrderItemModifier

OrderStatus

OrderItemStatus

ServiceType

OrderCustomerReference

OrderBranchReference

OrderMenuContext

OrderCommercialSummary

OrderValidation

OrderConfirmation

OrderModification

OrderCancellation

OrderConversationReference

OrderExternalMapping

OrderSynchronization

OrderAuditHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Split-Order Orchestration

Advanced Multi-Party Ordering

Complex Course Optimization

Autonomous Order Recovery

Predictive Order Composition

Advanced Cross-Channel Cart Collaboration
```

---

# 98. IMPLEMENTATION PRINCIPLE

This document defines the logical Order Model.

It does not prescribe:

* POS schema.
* Database schema.
* Kitchen runtime.
* Payment implementation.
* Delivery runtime.
* Frontend cart.
* Ordering user interface.
* AI model.
* Recommendation algorithm.

Implementation shall preserve the distinction between:

```text
CUSTOMER INTENT

DRAFT ORDER

CONFIRMED ORDER

ORDER ITEM

PRODUCTION

PAYMENT

FULFILLMENT

HISTORICAL TRANSACTION
```

---

# 99. FINAL RULE

Before ECIP confirms or modifies an Order, it shall be able to determine:

> Who is ordering?

> Which Branch and Service Type apply?

> Which Products, Variants, quantities and Modifiers are requested?

> Are all requested Items currently offerable?

> Are customer safety constraints relevant?

> Which Prices, Promotions, Discounts and Loyalty Benefits apply?

> What is the authoritative final total?

> Can the restaurant operationally fulfill the Order?

> What preparation or fulfillment time can reasonably be communicated?

> Does the Customer need to confirm any clarification or material change?

> Is the requested mutation authorized?

> Can the resulting commercial transaction be completely reconstructed and audited?

Only after these conditions are satisfied may ECIP execute the corresponding Order action.

