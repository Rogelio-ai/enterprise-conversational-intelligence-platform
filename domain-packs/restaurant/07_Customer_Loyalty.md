# 07_Customer_Loyalty.md

**Document ID:** RDM-007
**Document Name:** Customer Loyalty
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Customer Loyalty Model for the Restaurant Intelligence Platform.

Its purpose is to represent how the restaurant builds, measures and strengthens long-term customer relationships through loyalty programs, rewards, recognition, benefits, retention strategies and relationship value.

Customer loyalty shall not be reduced to points or discounts.

The model treats loyalty as the result of the complete relationship between the customer and the restaurant.

---

# 2. OBJECTIVES

The Customer Loyalty Model enables ECIP to:

* Recognize loyal customers.
* Preserve loyalty history.
* Manage loyalty memberships.
* Track rewards and benefits.
* Personalize loyalty experiences.
* Improve customer retention.
* Detect potential churn.
* Optimize loyalty incentives.
* Reward valuable behavior.
* Recognize important customer milestones.
* Support customer reactivation.
* Measure loyalty effectiveness.
* Increase Customer Lifetime Value.
* Improve long-term customer relationships.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends the following canonical concepts:

* Customer
* Relationship
* Preference
* Memory Record
* Commitment
* Recommendation
* Opportunity
* Decision
* Action
* Analytical Event

Restaurant-specific loyalty concepts shall remain within the Restaurant Domain Pack.

This document does not redefine canonical customer identity or memory.

---

# 4. LOYALTY PRINCIPLE

Loyalty is broader than a loyalty program.

A customer may be highly loyal even if no points-based program exists.

ECIP shall distinguish between:

```text
Customer Loyalty
        │
        ├── Behavioral Loyalty
        ├── Transactional Loyalty
        ├── Relational Loyalty
        ├── Program Loyalty
        └── Advocacy Loyalty
```

---

# 5. CUSTOMER LOYALTY PROFILE

A `CustomerLoyaltyProfile` represents the restaurant's governed view of the customer's loyalty relationship.

Typical attributes include:

* Customer ID
* Loyalty status
* Memberships
* Current tier
* Points balance
* Reward eligibility
* Visit frequency
* Relationship duration
* Lifetime value
* Retention indicators
* Churn risk
* Referral activity
* Loyalty milestones
* Last engagement
* Status

The Loyalty Profile shall be derived from authoritative loyalty and customer data.

---

# 6. LOYALTY MEMBERSHIP

A `LoyaltyMembership` represents enrollment in a loyalty program.

Typical attributes:

* Membership ID
* Customer ID
* Loyalty program
* Enrollment date
* Membership status
* Tier
* Points balance
* Qualification period
* Expiration date
* Branch or brand scope
* Enrollment channel

Suggested lifecycle:

```text
invited
→ enrolled
→ active
→ suspended
→ expired
→ cancelled
```

---

# 7. LOYALTY PROGRAM

A `LoyaltyProgram` represents a governed customer loyalty scheme.

Examples:

* Points program
* Visit-based program
* Paid membership
* VIP program
* Cashback program
* Subscription program
* Corporate loyalty program
* Family program

Typical attributes:

* Program ID
* Name
* Program type
* Validity
* Eligible branches
* Eligible customers
* Earning rules
* Redemption rules
* Tier rules
* Expiration policy
* Status

---

# 8. PROGRAM TYPES

The model shall support multiple loyalty mechanisms.

## Points-Based

Customers accumulate points.

## Visit-Based

Rewards depend on number of visits.

## Spend-Based

Rewards depend on monetary spend.

## Tier-Based

Benefits depend on loyalty level.

## Subscription-Based

Customers pay for recurring benefits.

## Recognition-Based

Benefits are granted based on relationship or status without explicit points.

## Hybrid

Combines multiple mechanisms.

---

# 9. LOYALTY ACCOUNT

A `LoyaltyAccount` represents the accounting container for program value.

Typical attributes:

* Customer
* Program
* Current balance
* Available balance
* Pending balance
* Expiring balance
* Currency or unit
* Status

The Loyalty Account shall preserve a complete ledger.

---

# 10. LOYALTY LEDGER

Every loyalty balance change shall be represented through an auditable transaction.

Examples:

```text
PointsEarned
PointsRedeemed
PointsExpired
PointsAdjusted
PointsReversed
BonusGranted
RewardConverted
```

A balance shall not be modified without ledger evidence.

---

# 11. LOYALTY TRANSACTION

A `LoyaltyTransaction` represents one change in loyalty value.

Typical attributes:

* Transaction ID
* Membership
* Transaction type
* Amount
* Balance before
* Balance after
* Source transaction
* Order reference
* Promotion reference
* Branch
* Timestamp
* Expiration date
* Actor
* Reason
* Reversal reference

---

# 12. EARNING RULES

Points or benefits may be earned through:

* Purchases
* Visits
* Specific products
* Specific categories
* Promotional campaigns
* Referrals
* Reviews
* Events
* Birthdays
* Customer anniversaries
* Registration
* Reactivation
* Strategic customer behavior

Earning rules shall be explicit and versioned.

---

# 13. REDEMPTION RULES

Rewards may be redeemed for:

* Products
* Discounts
* Free items
* Upgrades
* Experiences
* Priority access
* Delivery benefits
* Reservation benefits
* Event benefits

Rules may include:

* Minimum balance
* Maximum redemption
* Valid products
* Valid branches
* Valid dates
* Customer tier
* Combination restrictions

---

# 14. LOYALTY TIER

A `LoyaltyTier` represents a recognized relationship level.

Examples:

```text
Member
Silver
Gold
Platinum
VIP
```

Tier names are configurable.

Typical attributes:

* Tier ID
* Name
* Qualification criteria
* Validity
* Benefits
* Priority
* Renewal requirements

---

# 15. TIER QUALIFICATION

Qualification may consider:

* Spend
* Visits
* Relationship duration
* Points earned
* Referral value
* Subscription
* Customer segment
* Strategic relationship

The platform shall preserve the reasons for tier assignment.

---

# 16. TIER PROGRESSION

Suggested lifecycle:

```text
Current Tier
    ↓
Qualification Evaluation
    ↓
Upgrade / Maintain / Downgrade
    ↓
Customer Notification
    ↓
Benefit Update
```

Unexpected downgrades or removals should be explainable.

---

# 17. CUSTOMER RECOGNITION

Loyal customers may receive recognition independent of monetary rewards.

Examples:

* Personalized greeting
* Preferred seating
* Priority reservation handling
* Special event invitations
* Complimentary item
* Preferred employee routing
* Early access
* Personalized menu suggestions

Recognition shall respect customer preferences and business policies.

---

# 18. REWARD

A `Reward` represents a benefit that may be granted or redeemed.

Typical attributes:

* Reward ID
* Reward type
* Description
* Value
* Eligible customer
* Eligibility rule
* Issue date
* Expiration
* Redemption status
* Redemption constraints

---

# 19. REWARD TYPES

Examples:

* Free product
* Percentage discount
* Fixed-value discount
* Complimentary dessert
* Complimentary beverage
* Free delivery
* Priority reservation
* Birthday benefit
* Upgrade
* Event invitation
* Exclusive product

---

# 20. REWARD STATUS

Suggested lifecycle:

```text
created
→ available
→ reserved
→ redeemed
```

Alternative states:

```text
expired
cancelled
revoked
```

---

# 21. PERSONALIZED REWARDS

ECIP may select relevant rewards using:

* Customer preferences
* Purchase history
* Loyalty level
* Current occasion
* Product affinity
* Branch availability
* Margin
* Operational capacity
* Campaign objectives

Example:

```text
Customer:
Regular seafood customer

Known preference:
Dry white wine

Available benefit:
Free dessert OR beverage upgrade

Recommendation:
Offer beverage upgrade if operationally and commercially appropriate
```

Rewards should produce perceived customer value, not merely reduce price.

---

# 22. CUSTOMER MILESTONES

Important loyalty milestones may include:

* First purchase
* Tenth visit
* One-year relationship
* 100th order
* Customer birthday
* Membership anniversary
* Tier upgrade
* Significant spending milestone
* First referral

Milestones may trigger governed recognition or rewards.

---

# 23. CUSTOMER BIRTHDAYS

Birthday information may be used when:

* Provided by the customer or an authorized source.
* Retention is permitted.
* Appropriate communication consent exists where required.

Possible actions:

* Birthday greeting
* Personalized reward
* Reservation suggestion
* Event promotion

Birthdays shall not automatically trigger unwanted marketing communications.

---

# 24. CUSTOMER ANNIVERSARIES

The platform may recognize:

* Loyalty membership anniversary
* First visit anniversary
* Restaurant relationship anniversary

These may support customer appreciation initiatives.

---

# 25. RELATIONSHIP EVENTS

Restaurant-specific events may be remembered where relevant.

Examples:

* Wedding anniversary
* Recurring family celebrations
* Annual corporate events

Such information shall follow memory, sensitivity and consent policies.

---

# 26. REFERRAL

A `Referral` represents customer-driven acquisition of another customer.

Typical attributes:

* Referring customer
* Referred party
* Referral date
* Referral channel
* Conversion status
* Reward
* Attribution

Suggested lifecycle:

```text
created
→ contacted
→ converted
→ rewarded
```

---

# 27. CUSTOMER ADVOCACY

Advocacy signals may include:

* Referrals
* Positive reviews
* Recommendations
* Social engagement
* Repeated group visits
* Corporate introductions

Advocacy shall not be inferred solely from sentiment.

---

# 28. CUSTOMER RETENTION

Retention represents the restaurant's ability to maintain an active relationship.

Signals may include:

* Visit frequency
* Purchase recurrence
* Time since last visit
* Engagement
* Complaint history
* Recommendation acceptance
* Loyalty participation

Retention metrics shall remain distinct from individual customer treatment decisions.

---

# 29. CHURN RISK

A `ChurnRiskAssessment` represents the estimated likelihood that a previously active customer will reduce or stop engagement.

Potential signals:

* Reduced visit frequency
* Reduced spend
* Unresolved complaint
* Repeated service problems
* Expired rewards
* Negative sentiment
* Abandoned orders
* Competitor mentions

Typical attributes:

* Customer
* Risk level
* Confidence
* Evidence
* Contributing factors
* Evaluation time
* Validity
* Recommended intervention

Churn risk is a prediction, not a fact.

---

# 30. CUSTOMER REACTIVATION

A previously active customer may become a reactivation opportunity.

Possible strategies:

* Personalized message
* Relevant product announcement
* Birthday or anniversary contact
* Targeted reward
* Service recovery
* Event invitation

Reactivation shall respect communication consent and frequency policies.

---

# 31. SERVICE RECOVERY LOYALTY

Complaints and service failures may require loyalty-preserving actions.

Examples:

* Apology
* Follow-up
* Complimentary item
* Refund workflow
* Manager contact
* Future benefit

Service recovery shall be based on:

* Severity
* Customer impact
* Restaurant responsibility
* Customer history
* Policy
* Human approval requirements

Customer value alone shall not determine compensation.

---

# 32. LOYALTY AND COMPLAINTS

A valuable loyal customer with an unresolved complaint represents both:

* Customer experience risk
* Retention risk

ECIP should prioritize resolution appropriately.

However, customer tier shall never justify ignoring valid complaints from customers without loyalty status.

---

# 33. CUSTOMER LIFETIME VALUE

`CustomerLifetimeValue` represents an estimated economic relationship value over time.

Potential inputs include:

* Historical purchases
* Frequency
* Average ticket
* Margin
* Retention probability
* Engagement
* Expected future behavior

CLV shall be:

* Versioned
* Time-bound
* Explainable
* Confidence-scored where predictive

---

# 34. CLV PRINCIPLE

Customer Lifetime Value is a decision-support metric.

It shall not be treated as an intrinsic measure of a person's importance.

CLV may influence:

* Retention investment
* Marketing allocation
* Commercial recommendations

It shall not override:

* Safety
* Fairness
* Customer rights
* Policy
* Service obligations

---

# 35. LOYALTY SCORE

A `LoyaltyScore` may summarize relationship strength.

Potential dimensions:

```text
Recency
Frequency
Spend
Relationship duration
Engagement
Advocacy
Satisfaction
Program participation
```

A score is an analytical artifact.

The underlying dimensions shall remain available for explanation.

---

# 36. CUSTOMER HEALTH

A `CustomerRelationshipHealth` indicator may classify a relationship as:

```text
GROWING
HEALTHY
AT_RISK
DECLINING
DORMANT
REACTIVATION_OPPORTUNITY
```

This status should combine multiple signals rather than one metric.

---

# 37. LOYALTY OPPORTUNITY

A `LoyaltyOpportunity` represents a possible action that may strengthen the relationship.

Examples:

* Enroll customer in program
* Offer unused benefit
* Recognize milestone
* Resolve unresolved issue
* Invite to relevant event
* Prevent reward expiration
* Recommend tier upgrade
* Recover dormant customer

---

# 38. NEXT BEST LOYALTY ACTION

ECIP may recommend a `NextBestLoyaltyAction`.

Examples:

```text
No action

Recognize customer

Offer reward

Remind of expiring benefit

Request feedback

Resolve complaint

Invite to event

Recommend loyalty enrollment

Trigger human follow-up
```

The best loyalty action may intentionally be **no commercial action**.

---

# 39. LOYALTY FATIGUE

Excessive loyalty communications or promotions may reduce customer satisfaction.

The system should consider:

* Recent offers
* Communication frequency
* Repeated reward types
* Rejected offers
* Customer communication preferences

Loyalty optimization shall not mean maximizing the number of promotions.

---

# 40. LOYALTY PERSONALIZATION

Loyalty treatment may depend on context.

Example:

```text
Customer:
Gold member

Current context:
Birthday dinner

Known preferences:
Quiet area
Chocolate dessert

Current operation:
Preferred area available

Possible experience:
Recognize birthday
Honor seating preference
Offer eligible personalized benefit
```

The objective is a coherent experience, not a sequence of disconnected offers.

---

# 41. LOYALTY AND BRANCHES

Programs may operate at:

* Restaurant group level
* Brand level
* Restaurant level
* Branch level

Benefits may vary by branch.

ECIP shall verify benefit applicability before promising it.

---

# 42. MULTI-BRAND LOYALTY

A Restaurant Group may support:

* Independent programs per brand
* Shared group program
* Transferable points
* Cross-brand benefits

The model shall preserve program ownership and scope.

---

# 43. CORPORATE CUSTOMER LOYALTY

Corporate customers may have different loyalty mechanisms.

Examples:

* Volume benefits
* Preferred pricing
* Event benefits
* Account manager
* Priority reservation
* Corporate credits

Corporate loyalty should remain distinguishable from individual consumer loyalty.

---

# 44. FAMILY AND HOUSEHOLD LOYALTY

Where business policy allows, loyalty may support:

* Shared household account
* Family rewards
* Parent-managed benefits
* Household milestones

Identity, consent and ownership rules shall remain explicit.

---

# 45. LOYALTY ENROLLMENT

Enrollment may occur through:

* POS
* Mobile App
* Web
* Telephone
* WhatsApp
* Employee
* Kiosk
* Customer portal

The same membership shall remain recognizable across channels.

---

# 46. CONVERSATIONAL ENROLLMENT

ECIP may assist with loyalty enrollment.

Example:

```text
Customer:
"Do you have a rewards program?"

ECIP:
Explains program terms

Customer:
Requests enrollment

ECIP:
Collects permitted information
Obtains required consent
Creates or requests membership
Confirms enrollment
```

Enrollment actions shall follow policy and authorization.

---

# 47. LOYALTY DURING CONVERSATION

Conversational Intelligence may use loyalty information to:

* Recognize membership
* Explain balance
* Explain rewards
* Identify available benefits
* Resolve missing points
* Recommend relevant redemption
* Detect expiring benefits
* Escalate loyalty disputes

The customer should not need to know which backend system stores the information.

---

# 48. LOYALTY BALANCE INQUIRY

ECIP may answer questions such as:

```text
"How many points do I have?"

"When do my points expire?"

"What can I redeem?"

"Why didn't I receive points?"

"What benefits does my tier include?"
```

Responses shall use authoritative loyalty data.

---

# 49. MISSING LOYALTY CREDIT

A customer may report missing loyalty value.

The platform should support:

```text
Customer claim
    ↓
Transaction identification
    ↓
Eligibility verification
    ↓
Policy evaluation
    ↓
Automatic correction
or
Human approval
    ↓
Audit evidence
```

AI shall not arbitrarily modify loyalty balances.

---

# 50. LOYALTY FRAUD AND ABUSE

Potential risks include:

* Duplicate memberships
* Unauthorized point transfers
* Reward duplication
* Manipulated transactions
* Employee abuse
* Account takeover
* Referral abuse

Suspicious behavior may trigger:

* Additional verification
* Temporary hold
* Human review
* Fraud investigation

Fraud suspicion shall not automatically imply customer guilt.

---

# 51. LOYALTY AUTHORIZATION

Actions shall be risk-classified.

Examples:

Low risk:

* View balance
* View benefits

Moderate risk:

* Redeem standard reward

Higher risk:

* Manual point adjustment
* Merge accounts
* Restore expired points
* Transfer large balances

Sensitive actions may require explicit employee approval.

---

# 52. REWARD RESERVATION

Some rewards may need temporary reservation during a transaction.

Example:

```text
Reward selected
    ↓
Reward reserved
    ↓
Order completed
    ↓
Reward redeemed
```

If the transaction fails:

```text
Reward released
```

This prevents duplicate redemption.

---

# 53. LOYALTY EXPIRATION

The platform shall understand:

* Point expiration
* Reward expiration
* Membership expiration
* Tier qualification expiration

Expiration policies shall be explicit.

Where permitted, ECIP may notify customers before value expires.

---

# 54. EXPIRATION INTELLIGENCE

ECIP may detect opportunities such as:

```text
Customer has 2,000 points expiring in 7 days.

Customer normally visits on weekends.

Relevant recommendation:
Inform customer during an appropriate interaction.
```

This should not produce excessive unsolicited messaging.

---

# 55. PROMOTIONS VS LOYALTY

Promotions and loyalty are separate concepts.

A promotion may be available to anyone.

A loyalty benefit depends on a customer relationship or membership.

Example:

```text
Promotion:
20% off lunch

Loyalty Benefit:
Gold members receive complimentary dessert
```

Both may coexist according to combination rules.

---

# 56. LOYALTY BENEFIT COMBINATION

Rules shall determine whether benefits can combine with:

* Promotions
* Coupons
* Packages
* Discounts
* Corporate rates
* Other rewards

ECIP shall evaluate rules before making a promise.

---

# 57. LOYALTY AND CUSTOMER PREFERENCES

Loyalty information and preferences work together.

Example:

```text
Available rewards:
Dessert
Beverage
Appetizer

Customer preferences:
Strongly likes cheesecake
Does not drink alcohol

Recommended reward:
Cheesecake benefit
```

Loyalty determines eligibility.

Preferences determine relevance.

---

# 58. LOYALTY AND OPERATIONAL CONTEXT

Eligibility does not guarantee current availability.

Example:

```text
Reward:
Free cheesecake

Operational state:
Cheesecake unavailable

ECIP:
Do not promise unavailable reward.
Offer an authorized equivalent if policy permits.
```

---

# 59. LOYALTY AND SALES INTELLIGENCE

Loyalty information may support:

* Retention
* Cross-selling
* Upselling
* Reward optimization
* Tier progression
* Customer reactivation

Sales optimization shall not unnecessarily consume customer benefits when a better long-term action exists.

---

# 60. LOYALTY AND CUSTOMER INTELLIGENCE

Customer Intelligence may calculate:

* Loyalty probability
* Churn risk
* Relationship health
* CLV
* Program engagement
* Reward responsiveness

Loyalty remains the owner of program state.

Customer Intelligence consumes loyalty information for analysis.

---

# 61. LOYALTY AND HUMAN ESCALATION

Human handoff may include relevant loyalty context.

Example:

```text
Customer:
Gold Member

Relationship:
4 years

Current points:
8,450

Issue:
Missing points from previous purchase

History:
No previous loyalty disputes

Recommended action:
Verify order and apply standard correction policy if eligible
```

Only relevant information should be included.

---

# 62. LOYALTY MEMORY

Relationship milestones may contribute to governed customer memory.

Examples:

* Long-term member
* Preferred benefit types
* Historical milestone recognition
* Repeatedly unused benefit

Transactional balances shall remain in authoritative loyalty systems rather than being recreated as memory facts.

---

# 63. LOYALTY ANALYTICS

Potential metrics include:

* Enrollment rate
* Active membership rate
* Reward redemption rate
* Points liability
* Tier distribution
* Retention by tier
* Visit frequency
* Incremental revenue
* Reward cost
* Reactivation rate
* Churn rate
* Program ROI

---

# 64. LOYALTY PROGRAM EFFECTIVENESS

A loyalty program should be evaluated by more than enrollment.

Important questions include:

* Are customers returning more frequently?
* Is retention improving?
* Are rewards relevant?
* Are rewards generating incremental behavior?
* Are benefits profitable?
* Are customers satisfied?
* Are inactive customers reactivating?
* Does the program create unnecessary discount dependency?

---

# 65. LOYALTY EVENTS

Initial domain events include:

```text
LoyaltyProgramCreated
LoyaltyProgramActivated
LoyaltyProgramUpdated

CustomerEnrolledInLoyalty
LoyaltyMembershipActivated
LoyaltyMembershipSuspended
LoyaltyMembershipCancelled

PointsEarned
PointsRedeemed
PointsExpired
PointsAdjusted
PointsReversed

RewardIssued
RewardReserved
RewardReleased
RewardRedeemed
RewardExpired
RewardRevoked

LoyaltyTierAssigned
LoyaltyTierUpgraded
LoyaltyTierMaintained
LoyaltyTierDowngraded

LoyaltyMilestoneReached

ReferralCreated
ReferralConverted
ReferralRewarded

ChurnRiskDetected
CustomerReactivationOpportunityDetected
CustomerReactivated

LoyaltyDisputeCreated
LoyaltyDisputeResolved
```

---

# 66. RELATIONSHIPS

```text
Customer
    HAS CustomerLoyaltyProfile

Customer
    ENROLLED_IN LoyaltyProgram

LoyaltyMembership
    BELONGS_TO Customer

LoyaltyMembership
    PARTICIPATES_IN LoyaltyProgram

LoyaltyMembership
    HAS LoyaltyAccount

LoyaltyAccount
    CONTAINS LoyaltyTransaction

LoyaltyMembership
    HAS LoyaltyTier

Customer
    ELIGIBLE_FOR Reward

Reward
    MAY_BE_REDEEMED_IN Order

Customer
    MAKES Referral

CustomerLoyaltyProfile
    HAS CustomerLifetimeValue

CustomerLoyaltyProfile
    MAY_HAVE ChurnRiskAssessment

ChurnRiskAssessment
    MAY_GENERATE LoyaltyOpportunity

LoyaltyOpportunity
    MAY_GENERATE Recommendation

Recommendation
    MAY_REQUEST Action
```

---

# 67. BUSINESS RULES

The following rules apply:

1. A loyalty membership belongs to an identified customer or authorized customer entity.

2. Loyalty balances shall be backed by an auditable ledger.

3. ECIP shall not modify points, tiers or benefits without an authorized action.

4. Loyalty program rules shall be versioned.

5. Eligibility shall be verified before promising a reward.

6. Reward availability and operational feasibility shall be verified before confirmation.

7. Loyalty tier shall not override safety, fairness or customer rights.

8. Customer Lifetime Value shall remain a decision-support metric.

9. Churn risk shall remain classified as a prediction.

10. Promotions and loyalty benefits are separate concepts.

11. Benefit combination rules shall be evaluated before redemption.

12. Expiration shall follow the authoritative loyalty policy.

13. Sensitive loyalty changes may require human approval.

14. Program membership shall remain consistent across supported channels.

15. Customer communication related to loyalty shall respect communication consent and preferences.

16. Loyalty shall optimize long-term relationship value, not simply maximize reward issuance.

---

# 68. RELATIONSHIP WITH CUSTOMER PROFILE

`05_Customer_Profile.md` defines the customer's overall relationship profile.

This document defines loyalty-specific state and intelligence.

Conceptually:

```text
Customer Profile

├── Identity
├── Preferences
├── History
├── Relationships
├── Customer Value
│
└── Loyalty
    ├── Membership
    ├── Account
    ├── Points
    ├── Tier
    ├── Rewards
    ├── Milestones
    ├── Retention
    └── Churn Risk
```

The Customer Profile references loyalty data.

It shall not duplicate authoritative balances or program rules.

---

# 69. RELATIONSHIP WITH CUSTOMER HISTORY

Customer History provides behavioral evidence such as:

* Visits
* Orders
* Spend
* Reservations
* Complaints
* Redemptions

Loyalty Intelligence may use this evidence for:

* Tier qualification
* Milestones
* Retention analysis
* Relationship health
* Churn analysis

---

# 70. RELATIONSHIP WITH CUSTOMER PREFERENCES

Customer Preferences determine relevance.

Customer Loyalty determines eligibility and relationship state.

Example:

```text
Loyalty:
Customer eligible for one complimentary dessert.

Preferences:
Customer strongly prefers cheesecake.

Restaurant:
Cheesecake available.

Result:
Cheesecake becomes a highly relevant benefit.
```

---

# 71. RELATIONSHIP WITH CONVERSATIONAL INTELLIGENCE

Conversational Intelligence shall be able to understand loyalty intents such as:

```text
LOYALTY_ENROLLMENT

LOYALTY_BALANCE_INQUIRY

LOYALTY_REWARD_INQUIRY

LOYALTY_REDEMPTION

LOYALTY_MISSING_POINTS

LOYALTY_TIER_INQUIRY

LOYALTY_ACCOUNT_PROBLEM

LOYALTY_BENEFIT_EXPLANATION

LOYALTY_CANCELLATION
```

These domain intents map to canonical Conversation and Action concepts.

---

# 72. RELATIONSHIP WITH ACTION INTELLIGENCE

Loyalty-related mutations shall execute through the canonical Action Runtime.

Examples:

```text
EnrollCustomerInLoyalty

RedeemReward

AdjustLoyaltyPoints

RestoreLoyaltyPoints

MergeLoyaltyAccounts

AssignLoyaltyTier
```

The Loyalty domain shall not create an alternative action execution mechanism.

---

# 73. RELATIONSHIP WITH EXTERNAL LOYALTY SYSTEMS

The restaurant may use an existing third-party loyalty system.

In this case:

```text
ECIP
    ↕
Canonical Loyalty Model
    ↕
Loyalty Connector
    ↕
External Loyalty Platform
```

ECIP shall not expose provider-specific structures to the conversational core.

The authoritative source of points and membership state shall be explicitly defined.

---

# 74. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
LoyaltyProgram
LoyaltyMembership
LoyaltyAccount
LoyaltyTransaction
LoyaltyTier
Reward
RewardEligibility
RewardRedemption
LoyaltyMilestone
CustomerLoyaltyProfile
```

The following may be implemented later if they are not required for the initial commercial customer:

```text
Advanced CLV prediction
Advanced churn prediction
Referral optimization
Autonomous reward optimization
Cross-brand loyalty orchestration
Advanced loyalty simulations
```

This preserves the production-first strategy.

---

# 75. IMPLEMENTATION PRINCIPLE

This document defines the logical Customer Loyalty Model.

It does not prescribe:

* Database schema.
* Loyalty vendor.
* CRM implementation.
* Recommendation algorithm.
* Machine learning algorithm.
* Marketing platform.
* User interface.
* Payment system.
* Point valuation method.

Implementation shall preserve the separation between:

```text
LOYALTY STATE
LOYALTY PROGRAM RULE
CUSTOMER BEHAVIOR
CUSTOMER VALUE
PREDICTION
RECOMMENDATION
AUTHORIZED ACTION
```

---

# 76. FINAL RULE

Customer loyalty shall be optimized as a long-term relationship, not as a discount mechanism.

Every loyalty decision should be able to answer:

> What is the current relationship with this customer?

> What benefit is the customer actually eligible for?

> What evidence supports this eligibility?

> Is the benefit relevant to this customer?

> Is it operationally available?

> Is using it now beneficial to the customer relationship?

> Is the proposed action authorized?

> Can the resulting change be audited?

Only after these questions are resolved should ECIP recommend or execute a loyalty action.

