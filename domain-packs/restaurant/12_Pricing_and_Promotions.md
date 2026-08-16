# 12_Pricing_and_Promotions.md

**Document ID:** RDM-012
**Document Name:** Pricing and Promotions
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Pricing and Promotions Model for the Restaurant Intelligence Platform.

Its purpose is to represent how restaurant Products, Services, Packages and commercial offers are priced, discounted, bundled, promoted and made eligible under specific business conditions.

The model shall enable ECIP to determine:

* What price currently applies.
* Which promotion is valid.
* Which customer is eligible.
* Which branch or channel is eligible.
* Whether discounts can be combined.
* Whether approval is required.
* What commercial conditions apply before presenting or executing an offer.

Pricing and Promotions are related but distinct concepts.

---

# 2. OBJECTIVES

The Pricing and Promotions Model enables ECIP to:

* Resolve current Product pricing.
* Support branch-specific prices.
* Support channel-specific prices.
* Support service-type pricing.
* Support scheduled prices.
* Support temporary prices.
* Support customer-segment prices.
* Support corporate pricing.
* Support package pricing.
* Support discounts.
* Support coupons.
* Support loyalty benefits.
* Support Happy Hour.
* Support seasonal promotions.
* Support dynamic bundles.
* Support minimum purchase rules.
* Support promotion eligibility.
* Support promotion combination rules.
* Preserve historical pricing.
* Support margin-aware recommendations.
* Prevent unauthorized discounting.
* Support conversational offer explanation.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Policy
* Knowledge Fact
* Decision
* Recommendation
* Action
* Action Authorization
* Context Snapshot
* Customer
* Location
* Channel
* External Entity Reference

Restaurant-specific Pricing and Promotion entities remain within the Restaurant Domain Pack.

This document does not redefine canonical decision, policy or action execution.

---

# 4. CORE PRINCIPLE

The platform shall distinguish between:

```text
PRODUCT

PRICE

PRICE RULE

PROMOTION

DISCOUNT

COUPON

LOYALTY BENEFIT

BUNDLE

CUSTOMER ELIGIBILITY

OPERATIONAL AVAILABILITY
```

These concepts shall not be collapsed into a single "price" field.

---

# 5. PRICE

A `Price` represents the monetary amount assigned to a Product, Product Variant, Package, Service or other sellable entity under a defined context.

Typical attributes include:

* Price ID
* Sellable entity reference
* Amount
* Currency
* Tax treatment
* Scope
* Effective from
* Effective until
* Branch
* Channel
* Service type
* Customer segment
* Priority
* Source
* Status
* Version

---

# 6. PRICE STATUS

Suggested lifecycle:

```text
DRAFT
→ SCHEDULED
→ ACTIVE
→ SUSPENDED
→ EXPIRED
→ ARCHIVED
```

---

# 7. BASE PRICE

A `BasePrice` represents the default price before context-specific modifications, promotions or discounts.

Example:

```text
Product:
Grilled Salmon

Base Price:
$320 MXN
```

The Base Price may be overridden by a more specific authorized Price Rule.

---

# 8. PRICE SCOPE

A Price may apply at different scopes:

```text
Restaurant Group
Brand
Restaurant
Branch
Service Type
Channel
Customer Segment
Corporate Account
Event
```

More specific scopes may override more general scopes according to configured precedence.

---

# 9. BRANCH-SPECIFIC PRICE

Different branches may have different prices.

Example:

```text
Downtown Branch:
$320

Airport Branch:
$355
```

The Product remains the same canonical Product.

Only the applicable Price changes.

---

# 10. CHANNEL-SPECIFIC PRICE

Prices may vary by channel.

Examples:

* Dine-in
* Web
* Mobile App
* Delivery Platform
* Telephone
* Kiosk

Channel price differences shall be explicit.

---

# 11. SERVICE-TYPE PRICE

Prices may vary by:

* Dine In
* Take Away
* Delivery
* Catering
* Banquet
* Buffet

Example:

```text
Dine In:
$250

Delivery:
$275
```

Differences may reflect packaging, logistics or business policy.

---

# 12. SCHEDULED PRICE

A Price may apply only during a specified schedule.

Examples:

* Breakfast pricing
* Lunch pricing
* Weekend pricing
* Holiday pricing

Temporal applicability shall be explicit.

---

# 13. TEMPORARY PRICE

Temporary pricing may apply during:

* Events
* Seasonal periods
* Limited campaigns
* Product launches

Temporary Prices shall define expiration.

---

# 14. CUSTOMER-SPECIFIC PRICE

A Price may apply to:

* Corporate customers
* Contract customers
* Membership customers
* Special accounts

Customer-specific pricing shall require explicit eligibility.

---

# 15. CORPORATE PRICE

Corporate agreements may define:

* Negotiated prices
* Fixed menus
* Volume prices
* Event rates
* Delivery rates

Contract validity shall be checked before the price is presented.

---

# 16. PRICE RULE

A `PriceRule` defines the conditions under which a Price applies.

Typical conditions may include:

* Branch
* Channel
* Service type
* Time
* Date
* Customer segment
* Quantity
* Product category
* Membership
* Event
* Order value

---

# 17. PRICE RESOLUTION

Price resolution determines the authoritative current price.

Conceptually:

```text
Product
+
Variant
+
Branch
+
Channel
+
Service Type
+
Customer Context
+
Date/Time
+
Price Rules
=
Applicable Price
```

---

# 18. PRICE PRIORITY

When multiple prices apply, precedence shall be explicit.

Example:

```text
Contract Price
    overrides
Customer-Specific Price
    overrides
Branch-Specific Price
    overrides
Service-Type Price
    overrides
Base Price
```

Actual precedence remains configurable.

---

# 19. PRICE CONFLICT

A conflict exists when multiple equally authoritative Price Rules produce incompatible results.

Conflicts shall be:

* Detected.
* Logged.
* Resolved according to governance.
* Prevented from silently reaching the customer.

---

# 20. PRICE VERSIONING

Prices shall be versioned where required.

Historical Orders shall retain:

* Actual price charged.
* Price source.
* Price version.
* Promotion applied.
* Discount applied.

Current prices shall never rewrite historical transactions.

---

# 21. PRICE COMPONENT

A final selling price may contain components.

Examples:

```text
Base Price
+
Modifier Charges
+
Packaging Charge
+
Service Charge
-
Promotion Discount
-
Loyalty Benefit
+
Tax
```

The model shall support transparent price composition.

---

# 22. MODIFIER PRICE

Modifiers may affect price.

Examples:

* Extra cheese
* Premium side
* Larger size
* Additional protein

Modifier price may depend on context.

---

# 23. SIZE PRICE

Product Variants or Sizes may have independent prices.

Example:

```text
Small:
$120

Medium:
$160

Large:
$200
```

---

# 24. ADD-ON PRICE

Add-Ons may have their own commercial Price.

Where an Add-On maps to a Product, the Product pricing model should be reused when appropriate.

---

# 25. PACKAGE PRICE

A Package may define:

* Fixed price
* Per-person price
* Tiered price
* Minimum quantity
* Optional upgrades

Examples:

* Birthday package
* Banquet package
* Corporate package

---

# 26. QUANTITY PRICING

Pricing may depend on quantity.

Examples:

```text
1–9 units:
$100 each

10–49:
$90 each

50+:
$80 each
```

This is particularly relevant to:

* Catering.
* Banquets.
* Corporate orders.

---

# 27. PER-PERSON PRICING

Some offerings are priced per person.

Examples:

* Buffet
* Banquet
* Catering
* Private events

The model shall support:

* Adult price
* Child price
* Minimum guests
* Age rules

---

# 28. PROMOTION

A `Promotion` represents a temporary or conditional commercial incentive.

Typical attributes:

* Promotion ID
* Name
* Description
* Promotion type
* Effective period
* Eligible products
* Eligible branches
* Eligible channels
* Eligible customers
* Qualification rules
* Benefit
* Combination rules
* Usage limits
* Budget limits
* Priority
* Status

---

# 29. PROMOTION STATUS

Suggested lifecycle:

```text
DRAFT
→ APPROVED
→ SCHEDULED
→ ACTIVE
→ SUSPENDED
→ EXPIRED
→ ARCHIVED
```

---

# 30. PROMOTION TYPES

Examples include:

* Percentage Discount
* Fixed Discount
* Buy One Get One
* Bundle
* Free Product
* Free Modifier
* Free Delivery
* Happy Hour
* Seasonal Promotion
* Customer-Specific Offer
* Loyalty Promotion
* Birthday Promotion
* Referral Promotion
* First Purchase Promotion
* Reactivation Promotion
* Volume Promotion

---

# 31. PERCENTAGE DISCOUNT

Example:

```text
20% discount on appetizers
```

Typical attributes:

* Percentage
* Maximum discount
* Eligible products
* Minimum order

---

# 32. FIXED DISCOUNT

Example:

```text
$100 off orders over $800
```

Rules shall define currency and minimum requirements.

---

# 33. BUY-ONE-GET-ONE

Examples:

```text
Buy 1, Get 1 Free

Buy 2, Get 1 at 50%
```

Qualification and benefit Products may differ.

---

# 34. FREE PRODUCT PROMOTION

Example:

```text
Buy main course
→ complimentary dessert
```

The complimentary Product must still be operationally available.

---

# 35. FREE DELIVERY

Eligibility may depend on:

* Order value
* Delivery zone
* Customer tier
* Promotion period

Free delivery shall not bypass delivery feasibility.

---

# 36. HAPPY HOUR

Happy Hour may apply by:

* Time range
* Days
* Branch
* Product category
* Channel

Example:

```text
Monday–Friday
17:00–19:00
Selected beverages
```

---

# 37. SEASONAL PROMOTION

Examples:

* Christmas
* Mother's Day
* Valentine's Day
* Summer
* Independence Day

Seasonal promotions shall have defined validity.

---

# 38. CUSTOMER-SPECIFIC PROMOTION

A Promotion may target:

* Customer
* Segment
* Loyalty tier
* Behavior
* Churn risk
* Birthday
* Anniversary

Eligibility shall be explainable and policy-driven.

---

# 39. PROMOTION ELIGIBILITY

A customer or Order is eligible only if all required conditions are satisfied.

Conceptually:

```text
Promotion Active
+
Date Valid
+
Branch Eligible
+
Channel Eligible
+
Product Eligible
+
Customer Eligible
+
Minimum Conditions Met
+
Usage Limit Available
=
Promotion Eligible
```

---

# 40. PROMOTION QUALIFICATION

Qualification rules may include:

* Minimum order amount
* Minimum quantity
* Required Product
* Required category
* Required membership
* First purchase
* Time window
* Coupon code

---

# 41. PROMOTION BENEFIT

The benefit may be:

* Price reduction
* Free Product
* Upgrade
* Extra quantity
* Free delivery
* Loyalty points
* Service benefit

The benefit shall be modeled separately from eligibility.

---

# 42. DISCOUNT

A `Discount` represents a reduction applied to a Price or Order.

Discounts may originate from:

* Promotion
* Coupon
* Loyalty
* Employee authorization
* Manager authorization
* Contract
* Service recovery

The origin shall always be preserved.

---

# 43. MANUAL DISCOUNT

Manual discounts require explicit authorization.

Typical attributes:

* Reason
* Percentage or amount
* Authorized by
* Approval rule
* Maximum allowed
* Audit evidence

AI shall never invent manual discounts.

---

# 44. DISCOUNT AUTHORIZATION

Example classification:

```text
0–5%
Employee permitted

5–15%
Supervisor approval

15%+
Manager approval
```

Actual thresholds are tenant-configurable.

---

# 45. COUPON

A `Coupon` represents a redeemable entitlement or code.

Typical attributes:

* Coupon ID
* Code
* Promotion reference
* Customer scope
* Issue date
* Expiration
* Usage limit
* Redemption count
* Status

---

# 46. COUPON STATUS

Suggested lifecycle:

```text
ISSUED
→ ACTIVE
→ RESERVED
→ REDEEMED
```

Alternative states:

```text
EXPIRED
CANCELLED
REVOKED
```

---

# 47. COUPON REDEMPTION

Coupon redemption shall verify:

* Validity
* Customer eligibility
* Promotion eligibility
* Usage limit
* Product eligibility
* Order qualification

---

# 48. PROMOTION USAGE LIMIT

Limits may apply:

* Per customer
* Per Order
* Per day
* Per branch
* Globally
* Campaign budget

Usage limits shall be transactional and auditable.

---

# 49. PROMOTION BUDGET

Some campaigns may define:

* Maximum total discount
* Maximum redemptions
* Daily budget
* Branch budget

Budget exhaustion may automatically stop eligibility.

---

# 50. COMBINATION RULES

Promotions may be:

```text
STACKABLE

NON_STACKABLE

STACKABLE_WITH_LOYALTY_ONLY

STACKABLE_WITH_COUPON_ONLY

EXCLUSIVE
```

Combination rules shall be explicit.

---

# 51. PROMOTION CONFLICT

If multiple promotions apply, ECIP shall resolve according to:

* Priority
* Exclusivity
* Customer benefit policy
* Business optimization policy
* Promotion configuration

Resolution shall be deterministic and explainable.

---

# 52. BEST OFFER RESOLUTION

Where policy allows, ECIP may determine the best valid commercial option.

Example:

```text
Promotion A:
10% discount

Promotion B:
Free dessert

Customer preference:
Strongly likes cheesecake

Order value:
$400
```

"Best" may depend on:

* Monetary value
* Customer relevance
* Business policy

It shall not be arbitrarily determined by the AI model alone.

---

# 53. LOYALTY BENEFIT

Loyalty Benefits are governed by `07_Customer_Loyalty.md`.

Pricing and Promotions shall consume loyalty eligibility without duplicating the loyalty account model.

---

# 54. PROMOTION VS LOYALTY

Example:

```text
Promotion:
20% off lunch

Loyalty:
Gold member receives complimentary dessert
```

These benefits may combine only if the applicable rules allow it.

---

# 55. PROMOTION VS CONTRACT PRICE

A corporate Price may prohibit promotions.

Example:

```text
Corporate Contract Price:
$200

Public Promotion:
20% off

Contract:
Not combinable

Applicable:
$200 contract price
```

---

# 56. PROMOTION AND MODIFIERS

Promotions shall explicitly state whether benefits include:

* Base Product only
* Modifiers
* Add-Ons
* Premium upgrades

---

# 57. PROMOTION AND BUNDLES

A Promotion may:

* Discount a bundle.
* Require a bundle.
* Create a temporary bundle.

Temporary promotional bundles shall remain distinguishable from permanent Product Bundles.

---

# 58. DYNAMIC BUNDLE

A `DynamicBundleOffer` may be generated from authorized Product and Pricing rules.

Example:

```text
Customer orders:
Burger

Potential bundle:
Burger + Fries + Beverage
```

Dynamic bundle generation shall respect:

* Current availability
* Promotion rules
* Customer preferences
* Margin constraints
* Operational load

---

# 59. PERSONALIZED PROMOTION

Personalization may consider:

* Customer Preferences
* Customer History
* Loyalty
* Purchase behavior
* Occasion
* Channel
* Time
* Churn risk

Personalized pricing shall be carefully governed.

---

# 60. FAIRNESS PRINCIPLE

The platform shall not create arbitrary or opaque personalized price discrimination.

Personalized commercial treatment should primarily occur through:

* Offers
* Rewards
* Benefits
* Promotions

rather than hidden changes to the same Product's Base Price unless explicitly governed and legally appropriate.

---

# 61. PROMOTION FATIGUE

ECIP may consider:

* Number of recent offers
* Rejected offers
* Communication frequency
* Promotion type repetition

The platform should not maximize offer volume at the expense of customer experience.

---

# 62. SALES INTELLIGENCE

Sales Intelligence may use Pricing and Promotions to optimize:

* Conversion
* Ticket value
* Margin
* Customer satisfaction
* Inventory utilization
* Retention

The objective is not always the highest price.

---

# 63. MARGIN-AWARE RECOMMENDATION

Example:

```text
Product A:
High margin
Low customer relevance

Product B:
Moderate margin
High customer relevance
```

Sales Intelligence may prefer Product B when it creates better expected long-term value.

---

# 64. INVENTORY-AWARE PROMOTION

Promotions may help manage inventory.

Examples:

* Overstock
* Seasonal inventory
* Short shelf life

Commercial actions shall not compromise food safety or customer trust.

---

# 65. EXPIRATION-AWARE PROMOTION

Products approaching operational expiration may be promoted only if:

* Still fully safe and sellable.
* Business policy permits.
* Customer experience is not degraded.

ECIP shall never use promotions to disguise unsafe or unacceptable Products.

---

# 66. KITCHEN-AWARE PROMOTION

The platform should avoid promoting Products that worsen an existing production bottleneck.

Example:

```text
Grill:
95% capacity

Cold Kitchen:
35% capacity
```

Relevant recommendations may favor Products that reduce operational pressure if customer fit remains acceptable.

---

# 67. DELIVERY PRICING

Delivery-related commercial components may include:

* Delivery fee
* Zone surcharge
* Minimum order
* Distance charge
* Free delivery threshold

Delivery pricing shall integrate with the Delivery domain.

---

# 68. PACKAGING CHARGE

Take Away or Delivery Products may carry packaging charges.

Packaging charges shall be transparent according to applicable policy.

---

# 69. SERVICE CHARGE

Service charges may apply based on:

* Party size
* Service type
* Event
* Contract
* Location

Service charges shall remain distinct from Product prices.

---

# 70. TAX

Pricing shall support tax treatment.

Typical attributes:

* Tax category
* Tax rate reference
* Included or excluded
* Jurisdiction
* Effective period

Tax calculation details may be owned by the POS, ERP or fiscal system.

---

# 71. ROUNDING

Rounding rules shall be explicit.

They may differ by:

* Currency
* Tax policy
* Payment method

Rounding shall not be delegated implicitly to AI reasoning.

---

# 72. CURRENCY

Prices shall explicitly identify currency.

Multi-currency operations may require:

* Exchange-rate authority
* Effective date
* Rounding policy

Currency conversion is an integration and financial concern.

---

# 73. PRICE DISPLAY

The customer-facing price may need to display:

* Base amount
* Discount
* Tax
* Service fee
* Delivery fee
* Final total

The actual display requirements depend on jurisdiction and channel.

---

# 74. PRICE EXPLANATION

ECIP should be able to explain:

```text
"Why is it more expensive for delivery?"

"Why didn't the coupon apply?"

"What discount did I receive?"

"Can I combine these promotions?"
```

Responses shall use authoritative Pricing and Promotion rules.

---

# 75. PROMOTION EXPLANATION

The platform shall be able to explain:

* Eligibility
* Benefit
* Restrictions
* Expiration
* Combination rules

This is especially important in conversational channels.

---

# 76. ESTIMATED PRICE

Some Products or Services may require estimation.

Examples:

* Banquets
* Catering
* Events

An estimated price shall be clearly distinguished from a confirmed final Price.

---

# 77. QUOTE

A `Quote` may represent a commercial proposal.

Typical attributes:

* Customer
* Products or Services
* Quantities
* Prices
* Discounts
* Validity
* Terms
* Status

Detailed Event and Banquet quoting may be extended in `17_Banquets_and_Events.md`.

---

# 78. QUOTE STATUS

Suggested lifecycle:

```text
DRAFT
→ PRESENTED
→ ACCEPTED
→ EXPIRED
```

Alternative states:

```text
REJECTED
CANCELLED
REVISED
```

---

# 79. PRICE LOCK

A Quote or Reservation may temporarily lock pricing where business policy allows.

Price lock shall define:

* Locked Price
* Expiration
* Scope
* Conditions

---

# 80. HISTORICAL PRICE

Historical Orders shall preserve:

* Unit Price
* Modifier Price
* Discounts
* Promotions
* Tax
* Final amount

Historical price reconstruction shall not depend solely on today's Price rules.

---

# 81. SOURCE OF TRUTH

Pricing authority may vary by deployment.

Examples:

```text
POS:
Current operational price

ERP:
Contract pricing

ECIP:
Promotion recommendation

Loyalty Platform:
Benefit eligibility
```

The authoritative source shall be explicitly configured.

---

# 82. EXTERNAL PRICE MAPPING

External systems may use:

* Price lists
* Tariffs
* Promotion IDs
* Coupon IDs

These shall map to canonical ECIP entities.

---

# 83. PRICE IMPORT

Pricing may be imported from:

* POS
* ERP
* Spreadsheet
* Pricing system
* Delivery platform

Imported records shall preserve:

* Source
* External identifier
* Version
* Import timestamp
* Validation status

---

# 84. PROMOTION IMPORT

External Promotions shall be normalized into ECIP's canonical Restaurant Promotion Model.

Provider-specific semantics shall remain inside connectors.

---

# 85. SYNCHRONIZATION

Synchronization may update:

* Prices
* Promotion status
* Effective dates
* Eligibility
* Usage limits

Synchronization conflicts shall be explicit.

---

# 86. PRICING EVENTS

Initial events include:

```text
PriceCreated
PriceUpdated
PriceScheduled
PriceActivated
PriceSuspended
PriceExpired

PriceRuleCreated
PriceRuleUpdated

PriceConflictDetected
PriceConflictResolved

PriceResolved

QuoteCreated
QuotePresented
QuoteAccepted
QuoteExpired
```

---

# 87. PROMOTION EVENTS

Initial events include:

```text
PromotionCreated
PromotionApproved
PromotionScheduled
PromotionActivated
PromotionSuspended
PromotionExpired

PromotionEligibilityEvaluated
PromotionQualified
PromotionRejected

DiscountApplied
DiscountRejected
ManualDiscountRequested
ManualDiscountApproved
ManualDiscountDenied

CouponIssued
CouponReserved
CouponRedeemed
CouponExpired
CouponRevoked

PromotionLimitReached
PromotionBudgetExhausted

PromotionConflictDetected
PromotionConflictResolved
```

---

# 88. RELATIONSHIPS

```text
Product
    HAS Price

ProductVariant
    MAY_HAVE Price

Price
    GOVERNED_BY PriceRule

Price
    APPLIES_TO PriceScope

Promotion
    TARGETS Product

Promotion
    MAY_TARGET ProductCategory

Promotion
    HAS EligibilityRule

Promotion
    HAS PromotionBenefit

Promotion
    MAY_ISSUE Coupon

Customer
    MAY_BE_ELIGIBLE_FOR Promotion

LoyaltyMembership
    MAY_ENABLE LoyaltyBenefit

Order
    APPLIES Price

Order
    MAY_APPLY Promotion

Order
    MAY_APPLY Discount

Quote
    CONTAINS Price

Recommendation
    MAY_REFERENCE Promotion

Action
    MAY_EXECUTE DiscountApplication
```

---

# 89. BUSINESS RULES

The following rules apply:

1. Product identity shall remain independent of Price.

2. Price shall always identify currency.

3. Historical Prices shall not be rewritten by current Pricing changes.

4. Price resolution shall be deterministic.

5. Promotion eligibility shall be evaluated before presenting a guaranteed benefit.

6. Promotion activity status alone does not imply customer eligibility.

7. Manual discounts require explicit authority.

8. AI shall not invent Prices or discounts.

9. Loyalty benefits and Promotions shall remain distinct.

10. Promotion combination rules shall be explicit.

11. Current operational availability shall be checked before offering a free or discounted Product.

12. Contract pricing shall follow configured precedence.

13. Personalized commercial offers shall respect fairness and applicable policy.

14. Tax and required charges shall not be hidden.

15. External Price identifiers shall remain integration mappings.

16. Every applied discount shall preserve its source.

17. Promotions shall not override safety or operational restrictions.

18. Price conflicts shall not be silently resolved by an LLM.

---

# 90. RELATIONSHIP WITH MENU

`09_Menu.md` determines which offerings are presented.

This document determines which Price and Promotion apply.

Conceptually:

```text
Menu Item
    ↓
Product
    ↓
Applicable Price
    ↓
Eligible Promotions
    ↓
Customer-Facing Commercial Offer
```

---

# 91. RELATIONSHIP WITH PRODUCT CATALOG

`10_Product_Catalog.md` owns Product identity and structure.

Pricing references Products and Variants without redefining them.

---

# 92. RELATIONSHIP WITH CUSTOMER PROFILE

Customer Profile may provide:

* Identity
* Segment
* Relationship context

These may affect pricing or Promotion eligibility when explicitly governed.

---

# 93. RELATIONSHIP WITH CUSTOMER PREFERENCES

Preferences affect offer relevance.

They shall not independently determine eligibility.

Example:

```text
Customer likes cheesecake.

Promotion:
Free dessert.

Result:
Cheesecake may be recommended if eligible and available.
```

---

# 94. RELATIONSHIP WITH CUSTOMER LOYALTY

Loyalty may provide:

* Tier
* Points
* Benefit eligibility

Pricing consumes that information without duplicating loyalty state.

---

# 95. RELATIONSHIP WITH CUSTOMER HISTORY

Historical information may support:

* Promotion responsiveness
* Price sensitivity analysis
* Campaign effectiveness

Historical behavior alone shall not authorize a discount.

---

# 96. RELATIONSHIP WITH ORDER

The Order domain shall persist the commercial result actually applied.

This includes:

* Price
* Promotion
* Discount
* Tax
* Charge
* Final total

Pricing rules remain the basis for calculation.

---

# 97. RELATIONSHIP WITH SALES INTELLIGENCE

Sales Intelligence consumes:

* Applicable Prices
* Margin
* Promotions
* Customer relevance
* Operational feasibility

to recommend commercially intelligent actions.

---

# 98. RELATIONSHIP WITH ACTION INTELLIGENCE

Mutating commercial actions shall use the canonical Action Runtime.

Examples:

```text
ApplyPromotion
RedeemCoupon
ApplyManualDiscount
CreateQuote
LockPrice
```

Direct uncontrolled Price mutation by agents is prohibited.

---

# 99. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Price

BasePrice

PriceScope

PriceRule

PriceResolution

Promotion

PromotionEligibilityRule

PromotionBenefit

Discount

Coupon

CombinationRule

ManualDiscountAuthorization

Quote

ExternalPriceMapping

ExternalPromotionMapping
```

Defer unless required:

```text
Advanced Dynamic Pricing

Autonomous Price Optimization

Advanced Price Elasticity Models

AI-Generated Personalized Pricing

Advanced Promotion Simulation

Autonomous Campaign Budget Allocation
```

---

# 100. IMPLEMENTATION PRINCIPLE

This document defines the logical Pricing and Promotions Model.

It does not prescribe:

* Database schema.
* POS pricing engine.
* Tax engine.
* Promotion algorithm.
* Loyalty system.
* Recommendation model.
* Dynamic pricing algorithm.
* User interface.

Implementation shall preserve the semantic distinction between:

```text
PRODUCT

PRICE

PRICE RULE

PROMOTION

DISCOUNT

COUPON

LOYALTY BENEFIT

QUOTE

FINAL TRANSACTION VALUE
```

---

# 101. FINAL RULE

Before ECIP presents or applies a commercial offer, it shall be able to determine:

> What Product or Service is being priced?

> Which Price is authoritative in the current context?

> Which Price Rule caused that Price to apply?

> Which Promotions are active?

> Is this customer and Order actually eligible?

> Can multiple benefits be combined?

> Is any manual authorization required?

> Is the discounted or free Product currently available?

> What taxes, charges and fees apply?

> What final amount will the customer actually pay?

> Can the complete commercial decision be reconstructed and audited?

Only after these conditions are resolved may ECIP present, recommend or execute a pricing or promotional action.

