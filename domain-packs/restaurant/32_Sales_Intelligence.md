# 32_Sales_Intelligence.md

**Document ID:** RDM-032
**Document Name:** Sales Intelligence
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Sales Intelligence Model for the Restaurant Intelligence Platform.

Its purpose is to transform restaurant commercial activity into structured, explainable and actionable intelligence that improves:

* Revenue.
* Margin.
* Conversion.
* Average ticket.
* Customer Lifetime Value.
* Customer retention.
* Product mix.
* Promotion effectiveness.
* Channel performance.
* Opportunity identification.
* Recommendation relevance.
* Sales execution.
* Executive decision making.

Sales Intelligence shall not be modeled as a simple sales-reporting layer.

It represents the intelligence system that continuously interprets:

```text
CUSTOMER

CONTEXT

INTENT

PRODUCT

PRICE

PROMOTION

AVAILABILITY

MARGIN

HISTORY

CHANNEL

OPERATIONAL CAPACITY

COMMERCIAL OPPORTUNITY

RECOMMENDATION

OUTCOME
```

to determine what commercial action, if any, is most appropriate.

---

# 2. OBJECTIVES

The Sales Intelligence Model enables ECIP to:

* Understand sales performance.
* Understand Customer purchase behavior.
* Understand Product performance.
* Understand Category performance.
* Understand promotion performance.
* Understand Channel performance.
* Detect commercial opportunities.
* Detect abandoned opportunities.
* Detect upsell opportunities.
* Detect cross-sell opportunities.
* Detect retention opportunities.
* Detect reactivation opportunities.
* Detect Event and Banquet opportunities.
* Personalize recommendations.
* Optimize recommendation timing.
* Measure recommendation effectiveness.
* Estimate Customer Lifetime Value.
* Estimate purchase propensity.
* Estimate churn or inactivity risk.
* Analyze Product affinity.
* Analyze price sensitivity.
* Analyze Sales Funnel behavior.
* Support Sales Forecasting.
* Support Executive Intelligence.
* Preserve evidence for commercial decisions.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes canonical concepts including:

* Customer
* Opportunity
* Recommendation
* Decision
* Action
* Interaction
* Conversation
* Context Snapshot
* Analytical Event
* Prediction
* Confidence
* Customer History Event
* Product
* Financial Metric
* Evidence Record

Restaurant-specific Sales Intelligence entities remain within the Restaurant Domain Pack.

---

# 4. SALES INTELLIGENCE PRINCIPLE

The platform shall distinguish between:

```text
SALE

SALES EVENT

COMMERCIAL SIGNAL

COMMERCIAL OPPORTUNITY

RECOMMENDATION

OFFER

CUSTOMER RESPONSE

CONVERSION

COMMERCIAL OUTCOME

ANALYTICAL INSIGHT
```

These concepts are related but not equivalent.

---

# 5. SALES INTELLIGENCE SCOPE

Sales Intelligence may reason across:

* Dine-In.
* Take Away.
* Delivery.
* Reservations.
* Banquets.
* Events.
* Telephone.
* WhatsApp.
* Web Chat.
* Mobile App.
* Kiosk.
* External marketplace.
* Future channels.

The intelligence shall remain channel-independent.

---

# 6. SALE

A `Sale` represents a completed or recognized commercial transaction.

Typical attributes include:

* Sale ID
* Customer where known
* Order
* Branch
* Channel
* Service type
* Products
* Quantity
* Gross amount
* Discount
* Tax
* Net amount
* Cost reference
* Margin reference
* Payment state
* Timestamp

The authoritative sales transaction may remain in the POS.

Sales Intelligence consumes normalized commercial evidence.

---

# 7. SALES EVENT

A `SalesEvent` represents a meaningful commercial event in the customer journey.

Examples:

```text
PRODUCT_VIEWED

PRODUCT_REQUESTED

PRODUCT_RECOMMENDED

PROMOTION_PRESENTED

OFFER_ACCEPTED

OFFER_REJECTED

ITEM_ADDED

ITEM_REMOVED

ORDER_CREATED

ORDER_ABANDONED

ORDER_CONFIRMED

PURCHASE_COMPLETED

CUSTOMER_REACTIVATED
```

---

# 8. SALES CONTEXT

A `SalesContext` composes the current commercial state.

Conceptually:

```text
Customer
+
Conversation
+
Current Intent
+
Branch
+
Channel
+
Menu
+
Availability
+
Pricing
+
Promotions
+
Customer History
+
Current Order
+
Operational State
=
Sales Context
```

---

# 9. COMMERCIAL SIGNAL

A `CommercialSignal` represents evidence that may indicate a sales opportunity.

Examples:

* Customer asks about desserts.
* Customer repeatedly purchases wine.
* Customer mentions a birthday.
* Customer requests food for 30 people.
* Customer abandons cart.
* Customer asks whether Delivery is free above a threshold.

A Signal is not automatically an Opportunity.

---

# 10. SIGNAL SOURCES

Possible sources:

```text
CONVERSATION

ORDER

CUSTOMER_HISTORY

RESERVATION

EVENT

LOYALTY

PRODUCT_BEHAVIOR

PROMOTION_RESPONSE

CHANNEL_BEHAVIOR

OPERATIONAL_CONTEXT

ANALYTICS
```

---

# 11. COMMERCIAL OPPORTUNITY

A `CommercialOpportunity` represents an evidence-backed possibility to increase Customer or restaurant value.

Typical attributes:

* Opportunity ID
* Customer
* Opportunity type
* Context
* Evidence
* Estimated value
* Confidence
* Validity window
* Recommended action
* Status
* Outcome

---

# 12. OPPORTUNITY TYPES

Initial types may include:

```text
UPSELL

CROSS_SELL

BUNDLE

PROMOTION

REORDER

RETENTION

REACTIVATION

LOYALTY

EVENT

BANQUET

RESERVATION

DELIVERY

SUBSTITUTION

PRODUCT_DISCOVERY

CUSTOMER_RECOVERY

LIFETIME_VALUE
```

---

# 13. OPPORTUNITY STATUS

Suggested lifecycle:

```text
DETECTED
→ QUALIFIED
→ ACTIONABLE
→ PRESENTED
→ ACCEPTED
→ CONVERTED
```

Alternative states:

```text
REJECTED

EXPIRED

SUPPRESSED

NOT_RELEVANT

ABANDONED
```

---

# 14. OPPORTUNITY QUALIFICATION

A potential Opportunity should be validated against:

* Customer relevance.
* Current intent.
* Product availability.
* Kitchen feasibility.
* Inventory.
* Price.
* Promotion eligibility.
* Customer preferences.
* Allergies.
* Service type.
* Timing.
* Customer Experience state.

Only then should it become actionable.

---

# 15. SALES RECOMMENDATION

A `SalesRecommendation` represents a proposed Product, Package, Promotion or Action intended to improve Customer and commercial value.

Typical attributes:

* Recommendation ID
* Customer
* Opportunity
* Recommended entity
* Reason
* Expected value
* Confidence
* Timing
* Channel
* Constraints
* Status
* Outcome

---

# 16. RECOMMENDATION PRINCIPLE

A recommendation should answer:

> Why this Product?

> Why this Customer?

> Why now?

> Is it actually available?

> Is it appropriate?

> Is the recommendation likely to improve the Customer experience?

---

# 17. CROSS-SELL

Cross-Sell recommends a complementary Product.

Example:

```text
Customer orders:
Pizza

Potential Cross-Sell:
Beverage
Dessert
Side
```

Cross-Selling shall be context-sensitive.

---

# 18. UPSELL

Upsell recommends a higher-value version of an existing purchase intention.

Examples:

* Larger size.
* Premium ingredient.
* Better package.
* Higher-value wine.

Upselling shall remain optional.

---

# 19. BUNDLE

A `SalesBundleOpportunity` may combine Products that create Customer and business value.

Examples:

* Family meal.
* Lunch combo.
* Event package.
* Dinner-for-two package.

Bundles may be static or dynamically generated from governed Product and Pricing rules.

---

# 20. DYNAMIC BUNDLE

A Dynamic Bundle may consider:

```text
Current Order
+
Customer Preferences
+
Product Affinity
+
Available Promotions
+
Margin
+
Inventory
+
Kitchen Load
```

Dynamic Bundling shall not invent unauthorized Prices.

---

# 21. PRODUCT AFFINITY

`ProductAffinity` estimates how strongly Products are associated in purchase behavior.

Example:

```text
Customers who buy:
Burger

Frequently also buy:
Fries
Soft Drink
```

Affinity is analytical evidence, not a mandatory recommendation.

---

# 22. CUSTOMER-SPECIFIC AFFINITY

The platform may also learn individual patterns.

Example:

```text
Customer often orders:
Salmon + Sparkling Water
```

Historical behavior shall not automatically become an explicit preference.

---

# 23. NEXT-BEST-OFFER

A `NextBestOffer` is the most appropriate commercial offer under current context.

It may be:

* Product.
* Upgrade.
* Bundle.
* Promotion.
* Event service.
* Loyalty action.
* No offer.

`NO_OFFER` shall be a valid result.

---

# 24. NO-OFFER PRINCIPLE

The platform shall not force a commercial recommendation into every interaction.

Examples where no offer may be appropriate:

* Customer is making a complaint.
* Customer is in a hurry.
* Payment failed.
* Serious Service Recovery is active.
* Customer explicitly declines recommendations.

---

# 25. SALES TIMING

Recommendation timing is part of Sales Intelligence.

Examples:

```text
Before main Product selection:
Menu guidance

After Product selection:
Complementary item

Near meal completion:
Dessert

During complaint:
No sales recommendation
```

---

# 26. RECOMMENDATION FREQUENCY

The system should prevent excessive recommendations.

A Customer shall not experience the platform as continuously attempting to upsell.

---

# 27. RECOMMENDATION SUPPRESSION

A recommendation may be suppressed because of:

```text
CUSTOMER_DECLINED

ACTIVE_COMPLAINT

NEGATIVE_SENTIMENT

PRODUCT_UNAVAILABLE

ALLERGY_CONFLICT

KITCHEN_SATURATED

PROMOTION_INELIGIBLE

FREQUENCY_LIMIT

LOW_RELEVANCE
```

---

# 28. CUSTOMER INTENT

Sales Intelligence shall reason from Customer Intent.

Possible commercial intents include:

```text
EXPLORE_MENU

ORDER

REORDER

COMPARE

SAVE_MONEY

PREMIUM_EXPERIENCE

FAST_SERVICE

FAMILY_MEAL

CELEBRATION

BUSINESS_MEAL

EVENT_PLANNING
```

---

# 29. INTENT CONFIDENCE

Inferred intent shall preserve confidence.

Example:

```text
Intent:
Possible family meal

Confidence:
0.72
```

ECIP shall not treat weak inference as explicit Customer fact.

---

# 30. CUSTOMER PURCHASE HISTORY

Relevant historical signals include:

* Products purchased.
* Categories.
* Frequency.
* Average spend.
* Branch.
* Channel.
* Time of day.
* Promotions used.
* Products rejected.
* Returns or complaints.

---

# 31. REORDER INTELLIGENCE

The platform may identify likely reorder patterns.

Example:

```text
"You usually order the grilled salmon on Fridays. Would you like it again?"
```

Current availability, price and Customer context shall still be validated.

---

# 32. PURCHASE FREQUENCY

Potential metric:

```text
Number of Purchases
/
Time Period
```

Frequency may be calculated by:

* Customer.
* Product.
* Category.
* Channel.

---

# 33. RECENCY

`PurchaseRecency` represents time since the Customer's last relevant purchase.

Recency may contribute to retention and reactivation analysis.

---

# 34. MONETARY VALUE

Customer Monetary Value may consider:

* Revenue.
* Margin.
* Frequency.
* Time period.

This is analytical and shall preserve methodology.

---

# 35. RFM ANALYSIS

The platform may support:

```text
RECENCY

FREQUENCY

MONETARY VALUE
```

as one analytical method.

RFM shall not become the sole Customer segmentation model.

---

# 36. CUSTOMER LIFETIME VALUE

`CustomerLifetimeValue` estimates expected long-term economic value of a Customer relationship.

Potential inputs:

* Historical revenue.
* Margin.
* Purchase frequency.
* Retention probability.
* Expected future activity.

CLV is predictive, not guaranteed value.

---

# 37. CLV CONFIDENCE

Customer Lifetime Value shall preserve:

* Model version.
* Time horizon.
* Confidence.
* Data sufficiency.

---

# 38. CUSTOMER VALUE PRINCIPLE

Customer value shall not be used to justify:

* Unsafe treatment.
* Unfair denial of service.
* Ignoring complaints from lower-value Customers.
* Breaking confirmed commitments.

---

# 39. CHURN / INACTIVITY RISK

A `CustomerInactivityRisk` may estimate likelihood that a previously active Customer will not return.

Possible signals:

* Longer-than-normal absence.
* Lower frequency.
* Recent complaint.
* Repeated failed interactions.

This remains predictive.

---

# 40. REACTIVATION OPPORTUNITY

A Customer with increased inactivity risk may become eligible for reactivation activity.

Possible Actions:

* Relevant offer.
* Personalized message.
* Loyalty reminder.
* Event reminder.

Communication consent remains mandatory.

---

# 41. RETENTION OPPORTUNITY

Retention opportunities may arise from:

* Loyalty milestone.
* High purchase frequency.
* Complaint recovery.
* Declining frequency.
* Expiring reward.

---

# 42. CUSTOMER WIN-BACK

A Win-Back campaign may target Customers who have become inactive.

The platform should distinguish:

```text
REACTIVATION RECOMMENDATION

from

AUTHORIZED MARKETING COMMUNICATION
```

---

# 43. CART / ORDER ABANDONMENT

An `AbandonedOrderOpportunity` may occur when the Customer creates meaningful purchase intent but does not complete the Order.

Possible reasons:

* Price.
* Payment failure.
* Product unavailable.
* Customer interruption.
* Delivery time.
* Unknown.

Reason shall not be invented.

---

# 44. ABANDONMENT RECOVERY

Potential recovery:

* Resume unfinished Order.
* Clarify issue.
* Offer authorized relevant alternative.
* Provide Payment retry.

The platform shall avoid manipulative pressure.

---

# 45. UNFINISHED CONVERSATION

A commercial Conversation may end before the Customer completes an intended Action.

ECIP should preserve the unfinished state where meaningful.

---

# 46. PROMOTION INTELLIGENCE

Sales Intelligence evaluates Promotion performance defined in `12_Pricing_and_Promotions.md`.

Potential measures:

* Exposure.
* Acceptance.
* Conversion.
* Incremental revenue.
* Margin effect.
* Customer response.

---

# 47. PROMOTION ELIGIBILITY

Only eligible Promotions may be recommended.

The Sales Intelligence layer shall not override Pricing rules.

---

# 48. PROMOTION CONVERSION

Potential metric:

```text
Customers purchasing after eligible Promotion exposure
/
Customers receiving the Promotion
```

Methodology shall distinguish causation from correlation.

---

# 49. PROMOTION INCREMENTALITY

Advanced analysis may estimate whether the Promotion caused incremental behavior versus subsidizing a purchase that would have happened anyway.

This may be deferred beyond MVP.

---

# 50. DISCOUNT DEPENDENCY

Sales Intelligence may identify Customers or Products highly dependent on Discount activity.

This is analytical, not a reason to unfairly change prices.

---

# 51. PRICE SENSITIVITY

A `PriceSensitivityProfile` may estimate how demand changes relative to Price.

Possible sources:

* Historical purchases.
* Promotion response.
* Product substitutions.
* Purchase abandonment.

This is predictive.

---

# 52. PRICE INTELLIGENCE BOUNDARY

Sales Intelligence may analyze Price behavior.

It shall not independently set authoritative Price.

Pricing remains governed by `12_Pricing_and_Promotions.md`.

---

# 53. PRODUCT SALES PERFORMANCE

Potential Product metrics include:

* Units sold.
* Revenue.
* Gross margin.
* Attach rate.
* Reorder rate.
* Recommendation conversion.
* Complaint rate.
* Return/refund impact.

---

# 54. PRODUCT SALES VELOCITY

Sales Velocity may represent rate of Product sales across a defined period.

This can support:

* Forecasting.
* Inventory planning.
* Promotion planning.

---

# 55. PRODUCT MIX

Product Mix describes distribution of sales across:

* Categories.
* Products.
* Price tiers.
* Service types.

---

# 56. SALES MIX SHIFT

A `SalesMixShift` may identify meaningful movement in Product or Category demand.

Example:

```text
Beverage sales:
-12%

Dessert sales:
+18%
```

The system should investigate before attributing cause.

---

# 57. MENU PERFORMANCE

Menu Intelligence may evaluate:

* Product popularity.
* Margin.
* Conversion.
* Availability.
* Recommendation response.

Menu optimization shall consume Sales Intelligence but remain a separate commercial decision.

---

# 58. MENU ENGINEERING

The platform may support classic or advanced Menu Engineering based on:

* Popularity.
* Contribution Margin.
* Strategic importance.

The methodology shall remain explicit.

---

# 59. PRODUCT CONTRIBUTION MARGIN

Conceptually:

```text
Net Selling Price
-
Applicable Product Cost
=
Contribution Margin
```

Cost source and methodology shall be explicit.

---

# 60. HIGH-REVENUE VS HIGH-MARGIN

A Product with high revenue is not necessarily high margin.

The platform shall preserve both dimensions.

---

# 61. MARGIN-AWARE RECOMMENDATION

Recommendations may consider Margin, but Margin shall not override:

* Customer relevance.
* Quality.
* Safety.
* Availability.
* Customer intent.

---

# 62. INVENTORY-AWARE SALES INTELLIGENCE

Sales Intelligence may consume Inventory state.

Examples:

* Do not recommend unavailable Product.
* Consider safe excess stock where relevant.
* Avoid driving demand for critically low-stock Ingredient.

---

# 63. KITCHEN-AWARE SALES INTELLIGENCE

Sales Intelligence shall consume Kitchen state.

Example:

```text
Customer wants fast meal.

Grill:
Saturated

Cold Kitchen:
Normal
```

Recommendations may favor operationally realistic options.

---

# 64. INCIDENT-AWARE SALES INTELLIGENCE

Active Incidents may suppress or alter recommendations.

Example:

```text
Delivery provider unavailable
```

Do not recommend Delivery as the next best option.

---

# 65. QUALITY-AWARE SALES INTELLIGENCE

A Product under Quality Hold or recurring active defect should not be aggressively recommended.

---

# 66. EXPERIENCE-AWARE SALES INTELLIGENCE

Customer Experience context shall influence commercial behavior.

Example:

```text
Customer:
Actively dissatisfied

Priority:
Resolve service

Not:
Upsell dessert
```

---

# 67. ALLERGY-AWARE SALES INTELLIGENCE

Recommendations shall exclude Products incompatible with known verified Customer allergy constraints.

Unknown allergen status shall not be treated as safe.

---

# 68. PREFERENCE-AWARE SALES INTELLIGENCE

Customer Preferences may improve recommendations.

Examples:

* Preferred cuisine.
* Preferred spice level.
* Preferred beverage.
* Favorite dessert.

Preferences shall remain distinct from inferred purchase patterns.

---

# 69. OCCASION-AWARE SALES INTELLIGENCE

Occasion may influence relevant recommendations.

Examples:

```text
Birthday:
Dessert / celebration options

Business lunch:
Fast service / shareable starters

Anniversary:
Premium beverage / special dessert
```

Recommendations shall remain appropriate and non-intrusive.

---

# 70. FAMILY CONTEXT

Where known and relevant, household or family context may support:

* Family packages.
* Child-friendly options.
* Shared meals.

The platform shall respect privacy and avoid unnecessary personal inference.

---

# 71. TIME-OF-DAY INTELLIGENCE

Recommendations may vary by:

* Breakfast.
* Lunch.
* Dinner.
* Late night.

Historical behavior may also be time-specific.

---

# 72. DAY-OF-WEEK INTELLIGENCE

Customer and Product patterns may differ by weekday or weekend.

---

# 73. SEASONAL SALES INTELLIGENCE

The platform may identify:

* Seasonal Products.
* Holiday demand.
* Weather-sensitive demand where external context is authorized.
* Event periods.

---

# 74. LOCATION-AWARE SALES INTELLIGENCE

Branch-specific differences may affect:

* Product availability.
* Customer behavior.
* Price.
* Promotions.
* Sales Mix.

---

# 75. CHANNEL SALES INTELLIGENCE

Sales may be analyzed by:

```text
DINE_IN

TAKE_AWAY

DELIVERY

TELEPHONE

WHATSAPP

WEB

APP

KIOSK

MARKETPLACE
```

Channel and fulfillment type shall remain separate dimensions where necessary.

---

# 76. CHANNEL PERFORMANCE

Potential metrics:

* Revenue.
* Conversion.
* Average ticket.
* Margin.
* Abandonment.
* Payment failure.
* Recommendation conversion.
* Customer retention.

---

# 77. CHANNEL COST

Some channels may have different costs:

* Marketplace commission.
* Payment fee.
* Delivery cost.
* Packaging.
* Labor.

Sales Intelligence may evaluate net channel contribution.

---

# 78. SALES FUNNEL

A Restaurant Sales Funnel may include:

```text
INTERACTION
→ INTENT
→ PRODUCT INTEREST
→ ORDER INITIATED
→ PAYMENT INITIATED
→ ORDER CONFIRMED
→ FULFILLMENT COMPLETED
```

Not every channel uses every stage.

---

# 79. FUNNEL STAGE

A `SalesFunnelStage` shall be explicitly defined per commercial flow.

---

# 80. CONVERSION RATE

Potential metric:

```text
Completed Commercial Outcomes
/
Qualified Commercial Opportunities
```

The denominator shall be carefully defined.

---

# 81. CONVERSATION-TO-SALE CONVERSION

For conversational channels:

```text
Commercial Conversations Resulting in Purchase
/
Qualified Commercial Conversations
```

---

# 82. RECOMMENDATION CONVERSION

Potential metric:

```text
Accepted Recommended Items
/
Recommendations Presented
```

This does not by itself prove incremental revenue.

---

# 83. ATTACH RATE

Attach Rate may measure how frequently a complementary Product is added with another Product.

Example:

```text
Dessert Attach Rate
=
Orders with Dessert
/
Eligible Orders
```

---

# 84. UPSELL RATE

Potential metric:

```text
Accepted Upgrades
/
Upsell Opportunities Presented
```

---

# 85. CROSS-SELL RATE

Potential metric:

```text
Accepted Complementary Products
/
Cross-Sell Opportunities Presented
```

---

# 86. AVERAGE TICKET

Conceptually:

```text
Net Sales
/
Number of Completed Orders
```

The methodology should define exclusions and service types.

---

# 87. SALES PER CUSTOMER

Known Customers may support:

```text
Net Customer Sales
/
Active Customers
```

Anonymous Customer sales remain separate.

---

# 88. SALES PER VISIT

Potential metric:

```text
Customer Sales
/
Completed Visits
```

---

# 89. SALES PER TABLE

Dine-In analysis may evaluate revenue per Table or Table-hour.

This belongs to Sales/Operational Intelligence intersection.

---

# 90. SALES PER LABOR HOUR

Potential operational-financial metric:

```text
Sales
/
Labor Hours
```

Employee productivity conclusions shall still consider operational context.

---

# 91. SALES PER SEAT-HOUR

Dining utilization analysis may combine Sales with capacity.

---

# 92. SALES FORECAST

A `SalesForecast` estimates future demand.

Potential dimensions:

* Branch.
* Product.
* Category.
* Channel.
* Meal period.
* Day.
* Customer segment.

---

# 93. FORECAST INPUTS

Possible inputs include:

* Historical sales.
* Reservations.
* Events.
* Promotions.
* Seasonality.
* Day of week.
* Current trend.

---

# 94. FORECAST VS CONFIRMED DEMAND

The platform shall preserve:

```text
FORECAST DEMAND

CONFIRMED DEMAND

ACTUAL SALES
```

as separate concepts.

---

# 95. SALES FORECAST CONFIDENCE

Forecasts shall preserve:

* Model version.
* Confidence.
* Horizon.
* Data freshness.

---

# 96. REVENUE FORECAST

Revenue Forecast estimates future sales value.

It shall remain distinguishable from actual revenue.

---

# 97. PRODUCT DEMAND FORECAST

Product-level forecasting may support:

* Inventory.
* Production.
* Purchasing.
* Staffing.

---

# 98. SALES ANOMALY

Possible Sales anomalies include:

* Sudden Product sales drop.
* Unexpected sales spike.
* Large Discount concentration.
* Unusual Refund pattern.
* Channel conversion collapse.
* Average ticket anomaly.

These are investigation signals.

---

# 99. LOST SALE

A `LostSale` represents identifiable commercial demand that did not convert.

Potential reasons:

```text
PRODUCT_UNAVAILABLE

PRICE

WAIT_TIME

DELIVERY_UNAVAILABLE

PAYMENT_FAILURE

CUSTOMER_DECLINED

COMPETITOR

UNKNOWN
```

Reason shall remain evidence-based.

---

# 100. UNMET DEMAND

Customer requests for unavailable or nonexistent Products may create an `UnmetDemandSignal`.

Examples:

* Repeated request for vegan option.
* Repeated request for Product no longer offered.
* Repeated request for Delivery outside current zone.

---

# 101. MISSING MENU OPPORTUNITY

Aggregated Unmet Demand may reveal a possible Menu opportunity.

Example:

```text
147 requests in 60 days:
Gluten-free dessert
```

This becomes an analytical Opportunity, not an automatic Product decision.

---

# 102. COMPETITOR MENTION

Conversation may reveal competitor references.

Examples:

* Price comparison.
* Product comparison.
* Delivery comparison.
* Event venue comparison.

Competitor mentions are Customer-supplied evidence unless externally verified.

---

# 103. COMPETITOR LOSS SIGNAL

If the Customer explicitly says:

```text
"I ordered elsewhere because your delivery time was too long."
```

the platform may classify the lost-sale reason with strong evidence.

---

# 104. CUSTOMER SEGMENT

Sales Intelligence may segment Customers using:

* Behavioral patterns.
* Purchase frequency.
* Product affinity.
* Channel behavior.
* Loyalty state.

Sensitive personal attributes shall not be inferred or used inappropriately.

---

# 105. SEGMENT EXAMPLES

Possible non-sensitive commercial segments:

```text
FREQUENT_DINER

DELIVERY_HEAVY

WEEKEND_CUSTOMER

HIGH_FREQUENCY_LOW_TICKET

EVENT_CUSTOMER

LAPSED_CUSTOMER

NEW_CUSTOMER
```

---

# 106. SEGMENT DYNAMICITY

Segments may change over time.

They shall not become permanent identity labels.

---

# 107. NEW CUSTOMER

A new Customer may require:

* Lower-confidence personalization.
* More exploratory recommendations.
* Avoidance of unsupported assumptions.

---

# 108. RETURNING CUSTOMER

Returning Customers may benefit from:

* Reorder suggestions.
* Recognized preferences.
* Loyalty context.
* Relevant historical recommendations.

---

# 109. HIGH-VALUE CUSTOMER

High Customer Value may influence:

* Retention priority.
* Relationship management.
* Personalized recognition.

It shall not override fairness or safety.

---

# 110. EVENT SALES INTELLIGENCE

Large party inquiries may be detected as Event Opportunities.

Example:

```text
Customer:
"Can you serve dinner for 45 people?"
```

Sales Intelligence should route this into `17_Banquets_and_Events.md`.

---

# 111. RESERVATION SALES INTELLIGENCE

Reservation context may create opportunities such as:

* Special occasion package.
* Preordered wine.
* Private room.

---

# 112. DELIVERY SALES INTELLIGENCE

Delivery recommendations shall account for:

* Product suitability.
* Packaging.
* Expected transit.
* Delivery fee.
* Delivery capacity.

---

# 113. TAKE-AWAY SALES INTELLIGENCE

Take Away recommendations may consider:

* Travel stability.
* Packaging.
* Pickup timing.
* Customer history.

---

# 114. DINE-IN SALES INTELLIGENCE

Dine-In may support:

* Course-aware selling.
* Beverage pairing.
* Dessert recommendation.
* Occasion-aware upgrades.

---

# 115. PAYMENT-AWARE SALES INTELLIGENCE

Sales Intelligence shall not continue aggressive selling during unresolved Payment failure.

Payment resolution takes priority.

---

# 116. LOYALTY SALES INTELLIGENCE

Sales recommendations may include:

* Reward eligibility.
* Points opportunity.
* Loyalty milestone.

Loyalty rules remain authoritative.

---

# 117. SALES OPPORTUNITY VALUE

Potential Opportunity value may estimate:

* Incremental revenue.
* Incremental margin.
* Retention value.
* Lifetime value effect.

Estimated values shall remain clearly predictive.

---

# 118. EXPECTED COMMERCIAL VALUE

Conceptually:

```text
Probability of Conversion
×
Expected Incremental Value
=
Expected Commercial Value
```

This is analytical.

---

# 119. CUSTOMER VALUE VS RESTAURANT VALUE

The best recommendation should seek mutual value.

An offer that increases revenue but reduces Customer trust may be commercially harmful long term.

---

# 120. SHORT-TERM VS LONG-TERM OPTIMIZATION

Sales Intelligence shall distinguish:

```text
Immediate Revenue

from

Long-Term Relationship Value
```

Examples:

* Do not oversell.
* Do not recommend irrelevant expensive Products.
* Do not exploit Customer confusion.
* Preserve trust.

---

# 121. SALES DECISION

A `SalesDecision` may determine:

* Present recommendation.
* Suppress recommendation.
* Route to Event specialist.
* Offer authorized promotion.
* Resume abandoned order.

The decision shall preserve evidence where material.

---

# 122. RECOMMENDATION EXPLAINABILITY

The platform should be able to explain internally:

```text
Recommended:
Cheesecake

Because:
Customer purchased it 4 of last 5 visits
Current dessert inventory available
No allergy conflict known
Dessert timing appropriate
```

This does not mean all internal reasoning should be exposed to the Customer.

---

# 123. CUSTOMER RESPONSE

A `RecommendationResponse` may be:

```text
ACCEPTED

DECLINED

IGNORED

ASKED_FOR_ALTERNATIVE

NOT_PRESENTED

UNKNOWN
```

---

# 124. DECLINED RECOMMENDATION

Repeated rejection of the same recommendation should reduce future repetition.

---

# 125. SALES LEARNING LOOP

Conceptually:

```text
Context
    ↓
Recommendation
    ↓
Customer Response
    ↓
Commercial Outcome
    ↓
Learning
    ↓
Future Recommendation
```

This feedback loop is central to Sales Intelligence.

---

# 126. OUTCOME ATTRIBUTION

Sales Intelligence shall distinguish between:

```text
Recommended Product Purchased

and

Product Purchased Because of Recommendation
```

The first is observable.

The second may require causal inference.

---

# 127. SALES EXPERIMENT

Future implementations may support controlled experiments such as:

* Recommendation strategy A vs B.
* Promotion presentation.
* Bundle configuration.

Experiments shall follow governed experimentation rules.

---

# 128. SALES PERFORMANCE BY EMPLOYEE

Sales data may reference Employees.

Performance analysis shall account for:

* Shift.
* Traffic.
* Customer mix.
* Product availability.
* Service type.

Raw upsell totals shall not automatically define Employee quality.

---

# 129. SALES PERFORMANCE BY BRANCH

Potential comparison dimensions:

* Revenue.
* Margin.
* Average ticket.
* Conversion.
* Product Mix.
* Customer retention.
* Lost sales.

---

# 130. SALES PERFORMANCE BY CHANNEL

Potential questions:

* Which Channel converts best?
* Which Channel has highest margin?
* Which Channel has highest abandonment?
* Which Channel creates the best repeat Customers?

---

# 131. SALES PERFORMANCE BY PRODUCT

Potential questions:

* Which Products generate most revenue?
* Which Products generate most margin?
* Which Products are frequently requested but unavailable?
* Which Products convert well when recommended?

---

# 132. SALES PERFORMANCE BY CUSTOMER COHORT

Cohorts may be based on:

* First purchase period.
* Acquisition channel.
* Loyalty enrollment.
* Behavioral pattern.

Sensitive classification shall be avoided.

---

# 133. SALES TREND

Trend analysis may detect:

* Growth.
* Decline.
* Seasonality.
* Channel shifts.
* Product shifts.
* Customer behavior changes.

---

# 134. EXECUTIVE SALES INTELLIGENCE

Potential executive indicators include:

* Net sales.
* Revenue growth.
* Gross margin.
* Contribution margin.
* Average ticket.
* Sales by Branch.
* Sales by Channel.
* Sales by Product.
* Promotion effectiveness.
* Lost sales.
* Customer Lifetime Value.
* Retention.
* Reactivation.
* Recommendation conversion.
* Sales Forecast.

---

# 135. SALES INTELLIGENCE DASHBOARD

A future view may include:

```text
TODAY

Revenue
Orders
Average Ticket
Margin
Conversion
Lost Sales

OPPORTUNITIES

Upsell Opportunities
Cross-Sell Opportunities
Event Leads
Reactivation Opportunities

RISKS

Product Availability
Sales Decline
Abandonment
Customer Inactivity
```

This document does not prescribe UI.

---

# 136. SALES ALERT

Possible alerts include:

```text
SALES_DROP

PRODUCT_DEMAND_SPIKE

HIGH_LOST_SALES

ABANDONMENT_SPIKE

PROMOTION_UNDERPERFORMING

RECOMMENDATION_CONVERSION_DROP

HIGH_VALUE_CUSTOMER_AT_RISK

EVENT_OPPORTUNITY_DETECTED
```

Alerts shall be actionable.

---

# 137. SALES OPPORTUNITY PRIORITY

Opportunities may be prioritized by:

* Customer relevance.
* Expected value.
* Confidence.
* Urgency.
* Expiration.
* Operational feasibility.

---

# 138. SALES DATA QUALITY

Commercial Intelligence quality depends on:

* Correct Customer identity.
* Correct Order data.
* Correct Product mapping.
* Correct pricing.
* Correct Channel.
* Correct historical timestamps.

Low-quality inputs shall reduce confidence.

---

# 139. ANONYMOUS SALES

Sales may occur without known Customer identity.

Anonymous sales remain valid for:

* Product analysis.
* Branch analysis.
* Demand forecasting.

But cannot support Customer-level personalization.

---

# 140. CUSTOMER IDENTITY RESOLUTION

When multiple channels identify the same Customer, ECIP should use governed identity resolution.

Incorrect identity merging may create inappropriate recommendations.

---

# 141. SALES PRIVACY

Sales Intelligence may process:

* Purchase history.
* Behavioral patterns.
* Customer Preferences.
* Interaction history.
* Predictions.

Access and use shall follow:

* Purpose limitation.
* Consent where required.
* Least privilege.
* Retention policy.
* Privacy requirements.

---

# 142. SENSITIVE INFERENCE LIMIT

Sales Intelligence shall not make inappropriate inferences about Customers based on sensitive personal attributes.

Recommendations should be grounded in restaurant-relevant behavior and explicit context.

---

# 143. SALES FAIRNESS

Personalization shall not become unfair treatment.

Examples:

* Different authorized promotions may be legitimate.
* Hidden discriminatory treatment based on protected attributes is not.

---

# 144. AI SALES ASSISTANCE

AI may assist with:

* Intent classification.
* Opportunity detection.
* Recommendation generation.
* Product affinity analysis.
* Customer behavior summarization.
* Sales trend explanation.
* Lost-sale classification.
* Forecast interpretation.
* Conversation-to-sales reasoning.

---

# 145. AI AUTHORITY LIMIT

AI shall not:

* Invent Product availability.
* Invent Price.
* Invent Promotion eligibility.
* Invent Customer preferences.
* Ignore Allergy constraints.
* Override active Incidents.
* Manipulate Customers.
* Apply unauthorized Discounts.
* Claim causal sales impact without evidence.
* Mark inferred intent as explicit Customer fact.

---

# 146. AUTONOMOUS SALES ACTIONS

Future controlled automation may support:

* Present low-risk recommendation.
* Resume an abandoned Order.
* Offer already-authorized Promotion.
* Suggest Loyalty benefit.

Higher-impact actions such as:

* Custom Discount.
* Dynamic Price change.
* Large Credit.
* High-value Event negotiation.

shall require explicit authority.

---

# 147. SALES SOURCE OF TRUTH

Authority may vary by information type.

Example:

```text
POS:
Completed Sales

Pricing:
Authoritative Price

Inventory:
Availability

Kitchen:
Operational feasibility

Customer Domain:
Customer Profile and Preferences

ECIP:
Sales Intelligence and recommendation orchestration
```

Sales Intelligence composes these domains without replacing them.

---

# 148. EXTERNAL SALES MAPPING

External systems may use:

* POS Sale ID.
* Marketplace Order ID.
* CRM Opportunity ID.
* Campaign ID.
* Recommendation ID.

These shall map to canonical Sales Intelligence entities.

---

# 149. SALES IMPORT

Historical sales data may be imported.

Import shall preserve:

* Source.
* Original identifier.
* Product mapping.
* Customer mapping where available.
* Branch.
* Channel.
* Timestamp.
* Price.
* Quantity.
* Data quality.

---

# 150. SALES SYNCHRONIZATION

Synchronization may include:

* Completed sales.
* Product lines.
* Discounts.
* Customer references.
* Channel.
* Refunds.

It shall remain:

* Idempotent.
* Observable.
* Auditable.

---

# 151. SALES CONFLICT

Example:

```text
POS:
Product sold

Inventory:
Product impossible due to zero stock
```

or:

```text
ECIP:
Recommendation accepted

Order:
Recommended Product absent
```

Conflicts shall remain explicit for analysis.

---

# 152. SALES AUDIT TRAIL

Material intelligent sales actions should preserve:

* Customer context.
* Opportunity.
* Recommendation.
* Source evidence.
* Constraints checked.
* Action taken.
* Customer response.
* Outcome.
* Timestamp.
* AI/model version where applicable.

---

# 153. MODEL VERSIONING

Predictions and Recommendations generated by AI or analytical models should preserve:

* Model ID.
* Model Version.
* Timestamp.
* Confidence.
* Relevant feature/evidence references.

This supports reproducibility and auditability.

---

# 154. SALES INTELLIGENCE EVENTS

Initial domain events include:

```text
SalesEventRecorded

CommercialSignalDetected
CommercialSignalDismissed

CommercialOpportunityDetected
CommercialOpportunityQualified
CommercialOpportunitySuppressed
CommercialOpportunityExpired

SalesRecommendationCreated
SalesRecommendationValidated
SalesRecommendationPresented
SalesRecommendationSuppressed

SalesRecommendationAccepted
SalesRecommendationDeclined
SalesRecommendationIgnored

CrossSellOpportunityDetected
UpsellOpportunityDetected
BundleOpportunityDetected

ReorderOpportunityDetected
RetentionOpportunityDetected
ReactivationOpportunityDetected
EventSalesOpportunityDetected

AbandonedOrderDetected
AbandonedOrderRecovered

LostSaleDetected
LostSaleReasonClassified

UnmetDemandDetected
MissingMenuOpportunityDetected

CustomerInactivityRiskDetected
CustomerLifetimeValueCalculated

ProductAffinityUpdated
PriceSensitivityUpdated

SalesForecastCreated
SalesForecastUpdated

SalesAnomalyDetected
SalesMixShiftDetected

PromotionSalesOutcomeRecorded

SalesConversionRecorded

SalesIntelligenceConflictDetected
SalesIntelligenceConflictResolved

SalesSynchronizationStarted
SalesSynchronizationCompleted
SalesSynchronizationFailed
```

---

# 155. RELATIONSHIPS

```text
Customer
    GENERATES SalesEvent

SalesEvent
    MAY_CREATE CommercialSignal

CommercialSignal
    MAY_CREATE CommercialOpportunity

CommercialOpportunity
    MAY_CREATE SalesRecommendation

SalesRecommendation
    RECOMMENDS Product

SalesRecommendation
    MAY_REFERENCE Promotion

SalesRecommendation
    HAS RecommendationResponse

RecommendationResponse
    MAY_CREATE SalesConversion

Order
    MAY_RESULT_FROM CommercialOpportunity

Order
    GENERATES Sale

Sale
    CONTRIBUTES_TO CustomerHistory

Sale
    CONTRIBUTES_TO ProductPerformance

Sale
    CONTRIBUTES_TO ChannelPerformance

Sale
    CONTRIBUTES_TO SalesForecast

CustomerHistory
    CONTRIBUTES_TO CustomerLifetimeValue

CustomerHistory
    CONTRIBUTES_TO CustomerInactivityRisk

InventoryState
    CONSTRAINS SalesRecommendation

KitchenState
    CONSTRAINS SalesRecommendation

QualityState
    CONSTRAINS SalesRecommendation

IncidentState
    CONSTRAINS SalesRecommendation

CustomerPreference
    INFORMS SalesRecommendation

SalesIntelligence
    CONTRIBUTES_TO ExecutiveIntelligence
```

---

# 156. BUSINESS RULES

The following rules apply:

1. Sales Intelligence shall remain distinct from authoritative Sales transactions.

2. A Commercial Signal shall not automatically become an Opportunity.

3. A Commercial Opportunity shall require evidence and relevance.

4. Recommendation generation shall validate current Product offerability.

5. Pricing and Promotion eligibility shall remain authoritative outside Sales Intelligence.

6. Sales Intelligence shall consume, not override, Inventory, Kitchen, Quality and Incident state.

7. Customer Allergy and safety constraints shall override commercial opportunity.

8. Active Customer dissatisfaction may suppress sales recommendations.

9. No recommendation is a valid intelligent outcome.

10. Customer purchase history shall not automatically become explicit preference.

11. AI-inferred intent shall preserve confidence.

12. Customer Lifetime Value shall remain predictive.

13. Customer value shall not justify unsafe, unfair or discriminatory treatment.

14. Recommendation outcome shall distinguish observation from causal attribution.

15. Lost-sale reasons shall not be invented.

16. Sales Forecast shall remain distinct from confirmed demand.

17. Product Margin shall not override Customer relevance.

18. Sales automation shall respect frequency and consent limits.

19. AI shall not invent Price, availability, Promotions or Customer facts.

20. External Sales identifiers shall remain integration mappings.

21. Model-generated Recommendations and Predictions shall preserve model/version metadata where required.

22. Sales Intelligence decisions shall remain explainable and auditable.

23. Short-term revenue optimization shall not override long-term Customer relationship value.

24. Every interaction should improve either Customer value, business value or future commercial knowledge without degrading trust.

---

# 157. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
SalesEvent

SalesContext

CommercialSignal

CommercialOpportunity

CommercialOpportunityType

CommercialOpportunityStatus

SalesRecommendation

RecommendationReason

RecommendationConstraint

RecommendationResponse

CrossSellOpportunity

UpsellOpportunity

ReorderOpportunity

EventSalesOpportunity

AbandonedOrderOpportunity

LostSale

UnmetDemandSignal

ProductAffinity

CustomerPurchaseRecency

CustomerPurchaseFrequency

CustomerMonetaryValue

CustomerLifetimeValueReference

CustomerInactivityRiskReference

ProductSalesPerformance

ChannelSalesPerformance

SalesConversion

AverageTicket

SalesForecastReference

SalesIntelligenceExternalMapping

SalesIntelligenceHistory
```

Defer unless required by the first commercial pilot:

```text
Advanced Causal Promotion Incrementality

Real-Time Dynamic Bundle Optimization

Advanced Price Elasticity Modeling

Autonomous Dynamic Pricing

Advanced Churn Prediction

Deep Customer Lifetime Value Modeling

Reinforcement Learning Recommendation Engine

Advanced Cross-Channel Attribution

Autonomous Campaign Optimization

Sales Digital Twin Simulation

Fully Autonomous Commercial Negotiation
```

---

# 158. IMPLEMENTATION PRINCIPLE

This document defines the logical Sales Intelligence Model.

It does not prescribe:

* Recommendation engine.
* Machine-learning algorithm.
* CRM.
* Campaign platform.
* Pricing engine.
* POS implementation.
* Analytics database.
* BI platform.
* AI model.
* User interface.

Implementation shall preserve the semantic distinction between:

```text
SALE

SALES EVENT

COMMERCIAL SIGNAL

OPPORTUNITY

RECOMMENDATION

OFFER

CUSTOMER RESPONSE

CONVERSION

LOST SALE

FORECAST

PREDICTION

ANALYTICAL INSIGHT
```

---

# 159. FINAL RULE

Before ECIP recommends a Product, Promotion, Package, Event, upsell, cross-sell or other commercial action, it shall be able to determine:

> Who is the Customer, if known?

> What is the Customer currently trying to accomplish?

> What commercial signals support the Opportunity?

> Is the intent explicit or inferred?

> What Customer history and Preferences are relevant?

> Are there Allergy, dietary or safety constraints?

> Which Products are actually available?

> Can the Kitchen realistically fulfill them?

> Are there active Quality, Inventory or Operational Incident restrictions?

> What Price and Promotion rules currently apply?

> Is the recommendation relevant to the current service type and Channel?

> Is this the right moment to recommend something, or should no commercial action be taken?

> Has the Customer recently declined similar recommendations?

> What Customer value does the recommendation create?

> What restaurant value does it create?

> Is the recommendation optimized only for short-term revenue, or also for long-term Customer trust and value?

> What evidence and model version support the recommendation?

> What was the Customer's response?

> Did the recommendation actually convert?

> What should the system learn from the outcome?

> Can the complete path from signal through Opportunity, Recommendation, response and commercial result be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably present, suppress, evaluate or learn from a commercial recommendation.

The objective of Sales Intelligence is not to make ECIP sell more at any cost.

The objective is to enable ECIP to make **the right commercial decision for the right Customer, in the right context, at the right moment**, increasing long-term Customer value and restaurant profitability simultaneously.

