# 33_Customer_Intelligence.md

**Document ID:** RDM-033
**Document Name:** Customer Intelligence
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Customer Intelligence Model for the Restaurant Intelligence Platform.

Its purpose is to transform every authorized Customer interaction, transaction and behavioral signal into structured, explainable and actionable knowledge that enables ECIP to understand and serve each Customer progressively better over time.

Customer Intelligence shall not be modeled as a CRM record.

It represents the continuously evolving intelligence layer that answers:

```text
WHO IS THIS CUSTOMER?

WHAT DO WE ACTUALLY KNOW?

WHAT HAS THE CUSTOMER TOLD US?

WHAT HAS THE CUSTOMER DONE?

WHAT DOES THE CUSTOMER PREFER?

WHAT DOES THE CUSTOMER NEED NOW?

WHAT HAS HAPPENED IN THE RELATIONSHIP?

WHAT COMMITMENTS ARE ACTIVE?

WHAT MAY THE CUSTOMER WANT NEXT?

WHAT SHOULD THE RESTAURANT REMEMBER?

WHAT SHOULD THE RESTAURANT DO NOW?

WHAT SHOULD THE RESTAURANT NOT DO?
```

The objective is to build a durable Customer understanding that improves every future interaction without confusing facts, observations, preferences, predictions and assumptions.

---

# 2. OBJECTIVES

The Customer Intelligence Model enables ECIP to:

* Recognize returning Customers.
* Resolve Customer identity across channels.
* Build a unified Customer understanding.
* Remember relevant Customer history.
* Understand Customer Preferences.
* Understand purchasing patterns.
* Understand service patterns.
* Understand Channel preferences.
* Understand relationship history.
* Understand Loyalty context.
* Detect important life and dining occasions when explicitly provided or appropriately derived.
* Track Customer commitments.
* Track unresolved issues.
* Track complaints and compliments.
* Track Service Recovery.
* Track unfinished conversations.
* Track abandoned purchase intentions.
* Detect Customer needs.
* Detect Customer Intent.
* Detect Customer Experience changes.
* Detect retention opportunities.
* Detect reactivation opportunities.
* Detect commercial opportunities.
* Detect Customer risk.
* Generate Customer summaries.
* Generate next-best-action recommendations.
* Support personalized service.
* Support Customer Experience Intelligence.
* Support Sales Intelligence.
* Support Marketing Intelligence.
* Support Executive Intelligence.
* Preserve privacy, provenance, confidence and auditability.

---

# 3. RELATIONSHIP WITH EXISTING CUSTOMER DOMAIN DOCUMENTS

This document does not replace:

```text
05_Customer_Profile.md

06_Customer_Preferences.md

07_Customer_Loyalty.md

08_Customer_History.md
```

Those documents define authoritative Customer-domain concepts.

`33_Customer_Intelligence.md` composes information from those domains and other restaurant domains to produce higher-level Customer understanding.

Conceptually:

```text
Customer Profile
        +
Customer Preferences
        +
Customer Loyalty
        +
Customer History
        +
Orders
        +
Reservations
        +
Interactions
        +
Conversations
        +
Complaints
        +
Service Recovery
        +
Sales Behavior
        +
Current Operational Context
        ↓
CUSTOMER INTELLIGENCE
```

---

# 4. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes canonical concepts including:

* Customer
* Identity
* Interaction
* Conversation
* Intent
* Preference
* Customer History Event
* Observation
* Signal
* Prediction
* Recommendation
* Opportunity
* Commitment
* Context Snapshot
* Evidence Record
* Confidence
* Decision
* Action
* Sentiment
* Relationship
* External Entity Reference

Restaurant-specific Customer Intelligence entities remain within the Restaurant Domain Pack.

---

# 5. CUSTOMER INTELLIGENCE PRINCIPLE

ECIP shall distinguish between:

```text
CUSTOMER FACT

CUSTOMER-PROVIDED INFORMATION

OBSERVED BEHAVIOR

EXPLICIT PREFERENCE

INFERRED PREFERENCE

CURRENT INTENT

HISTORICAL PATTERN

PREDICTION

RECOMMENDATION

CUSTOMER COMMITMENT

CUSTOMER INTELLIGENCE INSIGHT
```

These concepts shall never be collapsed into a single undifferentiated Customer profile.

---

# 6. CUSTOMER INTELLIGENCE PROFILE

A `CustomerIntelligenceProfile` represents the composed intelligence view of a Customer.

It may include references to:

* Identity.
* Contact information.
* Preferences.
* Restrictions.
* Purchase history.
* Loyalty.
* Interaction history.
* Reservations.
* Events.
* Complaints.
* Compliments.
* Service Recovery.
* Commercial behavior.
* Relationship state.
* Current commitments.
* Current opportunities.
* Predictions.
* Relevant insights.

It shall be generated from authoritative underlying data rather than becoming an uncontrolled duplicate database.

---

# 7. CUSTOMER 360

The platform may expose a logical `Customer360View`.

Conceptually:

```text
IDENTITY

PROFILE

PREFERENCES

RESTRICTIONS

LOYALTY

PURCHASE HISTORY

INTERACTION HISTORY

CONVERSATIONS

RESERVATIONS

EVENTS

COMPLAINTS

COMPLIMENTS

SERVICE RECOVERY

COMMERCIAL BEHAVIOR

RELATIONSHIP STATE

CURRENT INTENT

ACTIVE COMMITMENTS

CURRENT OPPORTUNITIES

PREDICTIONS
```

Customer 360 is a composed view, not a new source of truth.

---

# 8. CUSTOMER IDENTITY

Customer Intelligence depends on reliable Customer identity.

Potential identifiers include:

* Customer ID.
* Telephone number.
* Email.
* Loyalty account.
* Mobile App account.
* Messaging platform identity.
* External POS Customer ID.

No single identifier shall automatically be assumed universally authoritative.

---

# 9. IDENTITY RESOLUTION

`CustomerIdentityResolution` determines whether multiple identifiers belong to the same Customer.

Example:

```text
Telephone:
+52...

WhatsApp:
+52...

POS Customer:
CUST-18429

Loyalty Account:
LOY-8831

        ↓

Canonical Customer:
CUSTOMER-000184
```

---

# 10. IDENTITY RESOLUTION CONFIDENCE

Identity resolution shall preserve confidence.

Suggested states:

```text
CONFIRMED

HIGH_CONFIDENCE

PROBABLE

AMBIGUOUS

UNRESOLVED
```

Sensitive Customer information shall not be disclosed based on weak identity resolution.

---

# 11. IDENTITY MERGE

Duplicate Customer identities may be merged only through governed identity-resolution rules.

The merge shall preserve:

* Original identifiers.
* Source systems.
* Historical references.
* Merge reason.
* Actor or rule.
* Timestamp.

---

# 12. IDENTITY SPLIT

An incorrect identity merge must be reversible where technically possible.

Customer Intelligence architecture shall support identity correction without destroying historical evidence.

---

# 13. ANONYMOUS CUSTOMER

ECIP shall support anonymous Customers.

Anonymous interactions may still contribute to:

* Aggregate demand.
* Product trends.
* Service trends.
* Channel trends.

They shall not be attached to a known Customer without sufficient identity evidence.

---

# 14. CUSTOMER FACT

A `CustomerFact` represents information considered sufficiently authoritative.

Examples:

* Customer-provided name.
* Verified telephone number.
* Confirmed Loyalty membership.
* Confirmed reservation.
* Completed Order.

Facts shall preserve source and timestamp.

---

# 15. CUSTOMER-PROVIDED INFORMATION

Information explicitly stated by the Customer shall remain distinguishable from externally observed or inferred information.

Example:

```text
Customer says:
"I prefer a quiet table."

Source:
CUSTOMER_EXPLICIT
```

---

# 16. CUSTOMER OBSERVATION

A `CustomerObservation` represents something observed about Customer behavior.

Example:

```text
Observation:
Customer ordered sparkling water on 7 of the last 8 visits.
```

This does not automatically mean:

```text
Explicit Preference:
Customer prefers sparkling water.
```

---

# 17. CUSTOMER SIGNAL

A `CustomerSignal` represents evidence that may contribute to an Intelligence conclusion.

Possible sources include:

```text
CONVERSATION

ORDER

RESERVATION

LOYALTY

COMPLAINT

COMPLIMENT

SERVICE_RECOVERY

CHANNEL_BEHAVIOR

PRODUCT_BEHAVIOR

EVENT

CUSTOMER_FEEDBACK
```

---

# 18. CUSTOMER INSIGHT

A `CustomerInsight` represents an evidence-backed interpretation useful for future service or decision making.

Typical attributes:

* Insight ID.
* Customer.
* Insight type.
* Evidence.
* Confidence.
* Validity period.
* Source.
* Generated time.
* Status.

---

# 19. INSIGHT TYPES

Initial types may include:

```text
BEHAVIORAL_PATTERN

PURCHASE_PATTERN

SERVICE_PATTERN

CHANNEL_PATTERN

PREFERENCE_PATTERN

RELATIONSHIP_PATTERN

EXPERIENCE_PATTERN

LOYALTY_PATTERN

COMMERCIAL_PATTERN

RETENTION_SIGNAL

REACTIVATION_SIGNAL

SPECIAL_OCCASION_SIGNAL

UNMET_NEED

CUSTOMER_RISK
```

---

# 20. INSIGHT STATUS

Suggested lifecycle:

```text
DETECTED
→ VALIDATED
→ ACTIVE
→ SUPERSEDED
→ EXPIRED
```

Alternative states:

```text
REJECTED

DISPUTED

LOW_CONFIDENCE
```

---

# 21. EVIDENCE PROVENANCE

Every material Customer Insight shall preserve:

```text
WHAT DO WE KNOW?

HOW DO WE KNOW IT?

WHEN DID WE LEARN IT?

FROM WHICH SOURCE?

HOW CONFIDENT ARE WE?

IS IT STILL CURRENT?
```

---

# 22. KNOWLEDGE CONFIDENCE

Suggested confidence categories:

```text
CONFIRMED

HIGH

MEDIUM

LOW

UNKNOWN
```

Numeric confidence may additionally be preserved where useful.

---

# 23. KNOWLEDGE FRESHNESS

Customer information may become stale.

Examples:

* Address.
* Preferred Branch.
* Favorite Product.
* Family context.
* Contact preference.

Customer Intelligence should preserve:

* Observed date.
* Last confirmed date.
* Freshness status.

---

# 24. KNOWLEDGE DECAY

Some inferred knowledge should lose confidence over time if not reinforced.

Example:

```text
2024:
Customer frequently ordered Product A.

2026:
No recent evidence.
```

The platform shall not indefinitely treat old behavioral patterns as current truth.

---

# 25. CUSTOMER PREFERENCE INTELLIGENCE

Customer Preferences are governed by `06_Customer_Preferences.md`.

Customer Intelligence may analyze:

* Explicit Preferences.
* Behavioral evidence.
* Preference consistency.
* Preference changes.
* Context-specific Preferences.

---

# 26. EXPLICIT VS INFERRED PREFERENCE

Example:

```text
Explicit:
"I don't like onions."

Observed:
Customer removed onions from 8 Orders.

Inferred:
Likely avoids onions.
```

These shall remain separate.

---

# 27. PREFERENCE CONFIDENCE

An inferred Preference may become stronger through repeated evidence but shall not silently become an explicit Preference.

---

# 28. CONTEXTUAL PREFERENCE

Preferences may depend on context.

Example:

```text
Dine-In:
Wine

Delivery:
Soft drink
```

A single universal Preference may therefore be inaccurate.

---

# 29. NEGATIVE PREFERENCE

Customer Intelligence should also understand dislikes and exclusions.

Examples:

* Does not like spicy food.
* Avoids particular Ingredient.
* Does not want promotional calls.

Negative Preferences may be more operationally important than positive Preferences.

---

# 30. SAFETY-CRITICAL CUSTOMER INFORMATION

Customer information involving:

* Allergies.
* Dietary restrictions with safety implications.
* Other explicitly relevant food-safety constraints.

shall be handled with higher assurance.

---

# 31. ALLERGY INTELLIGENCE BOUNDARY

Customer Intelligence may reference verified allergy information.

It shall not infer a medical allergy merely because a Customer avoids a Product.

Example:

```text
Observation:
Customer always removes peanuts.

Incorrect conclusion:
Customer has peanut allergy.
```

---

# 32. CUSTOMER HISTORY INTELLIGENCE

`08_Customer_History.md` preserves historical events.

Customer Intelligence interprets patterns across that history.

Example:

```text
History:
12 visits

Intelligence:
Customer usually visits Friday evenings.
```

---

# 33. PURCHASE PATTERN

A `CustomerPurchasePattern` may describe:

* Product recurrence.
* Category recurrence.
* Order composition.
* Day/time behavior.
* Channel behavior.
* Spend pattern.

---

# 34. VISIT PATTERN

Potential dimensions include:

* Frequency.
* Day of week.
* Meal period.
* Branch.
* Party size.
* Service type.

---

# 35. CHANNEL PREFERENCE

A Customer may show Channel patterns such as:

```text
Telephone:
Reservations

WhatsApp:
Questions

App:
Delivery Orders
```

Observed behavior shall remain distinct from explicit communication preference.

---

# 36. CUSTOMER JOURNEY

A `CustomerJourney` represents the Customer relationship across multiple interactions.

Example:

```text
Menu Inquiry
    ↓
Reservation
    ↓
Restaurant Visit
    ↓
Order
    ↓
Payment
    ↓
Feedback
    ↓
Future Reservation
```

---

# 37. CROSS-CHANNEL CONTINUITY

Customer context should follow the Customer across authorized channels.

Example:

```text
Customer begins on:
WhatsApp

Later calls:
Telephone

ECIP recognizes:
Same Customer
Same unresolved Reservation request
```

The Customer should not need to restart the interaction unnecessarily.

---

# 38. CONVERSATION CONTINUITY

ECIP should preserve:

* Previous Intent.
* Pending question.
* Unresolved request.
* Promised follow-up.
* Abandoned Order.
* Pending Reservation.
* Human escalation state.

---

# 39. UNFINISHED CONVERSATION

An `UnfinishedConversation` represents a meaningful interaction that ended before resolution.

Possible states:

```text
WAITING_FOR_CUSTOMER

WAITING_FOR_RESTAURANT

WAITING_FOR_EXTERNAL_SYSTEM

ABANDONED

EXPIRED

RESOLVED
```

---

# 40. FUTURE INTENTION

A Customer may explicitly communicate future intent.

Examples:

```text
"I'll call next week to book my daughter's birthday."

"I want catering for December."

"I'll probably order again Friday."
```

Explicit future intentions may be remembered according to privacy and retention policy.

---

# 41. INTENTION VS PREDICTION

The platform shall distinguish:

```text
CUSTOMER SAID:
"I will call next week."

from

MODEL PREDICTS:
Customer may order next week.
```

---

# 42. CUSTOMER INTENT

A `CustomerIntent` represents what the Customer is currently trying to accomplish.

Possible intents include:

```text
ASK_INFORMATION

EXPLORE_MENU

PLACE_ORDER

MODIFY_ORDER

CANCEL_ORDER

MAKE_RESERVATION

MODIFY_RESERVATION

PLAN_EVENT

ASK_FOR_RECOMMENDATION

MAKE_COMPLAINT

GIVE_COMPLIMENT

REQUEST_REFUND

ASK_FOR_HELP

CHECK_STATUS
```

---

# 43. MULTIPLE INTENTS

One interaction may contain multiple Customer intents.

Example:

```text
"Reserve a table for four and tell me whether you have a birthday package."
```

This may create:

```text
RESERVATION INTENT
+
EVENT / COMMERCIAL INTENT
```

---

# 44. INTENT CONFIDENCE

Inferred Intent shall preserve confidence and supporting evidence.

---

# 45. CUSTOMER NEED

A `CustomerNeed` represents the underlying problem the Customer wants solved.

Example:

```text
Stated request:
"Do you have anything ready in 10 minutes?"

Underlying need:
FAST MEAL
```

Needs may be inferred and therefore require confidence.

---

# 46. CUSTOMER GOAL

A Customer Goal may extend beyond one transaction.

Examples:

* Organize birthday dinner.
* Feed family quickly.
* Arrange corporate catering.
* Find allergen-compatible meal.

Understanding Goal can improve multi-step assistance.

---

# 47. CUSTOMER CONTEXT

A `CustomerContextSnapshot` may compose:

```text
Customer Identity
+
Current Intent
+
Current Conversation
+
Current Order / Reservation
+
Relevant Preferences
+
Relevant History
+
Current Experience State
+
Restaurant Operational Context
```

---

# 48. CONTEXT MINIMIZATION

Not every Customer fact belongs in every interaction.

Only relevant information should be introduced into active reasoning.

This reduces:

* Privacy exposure.
* Incorrect personalization.
* Cognitive noise.
* Model context cost.

---

# 49. CUSTOMER RELATIONSHIP STATE

A `CustomerRelationshipState` may represent the current relationship condition.

Examples:

```text
NEW

ACTIVE

FREQUENT

LOYAL

AT_RISK

INACTIVE

REACTIVATED
```

These states are analytical and configurable.

---

# 50. RELATIONSHIP TENURE

Relationship tenure may be measured from:

* First known interaction.
* First purchase.
* Loyalty enrollment.

The chosen definition shall remain explicit.

---

# 51. CUSTOMER VALUE

Customer value may include multiple dimensions:

```text
REVENUE VALUE

MARGIN VALUE

FREQUENCY VALUE

LOYALTY VALUE

RELATIONSHIP VALUE

REFERRAL VALUE
```

Not all dimensions need monetary representation.

---

# 52. CUSTOMER LIFETIME VALUE

Customer Intelligence may consume Customer Lifetime Value from `32_Sales_Intelligence.md`.

It shall not independently redefine the financial methodology.

---

# 53. CUSTOMER IMPORTANCE PRINCIPLE

Customer economic value may influence:

* Relationship-management attention.
* Retention analysis.
* Service personalization.

It shall never justify:

* Unsafe service.
* Ignoring low-value Customers.
* Violating commitments.
* Discriminatory treatment.

---

# 54. CUSTOMER EXPERIENCE STATE

A `CustomerExperienceState` may represent the Customer's current experience condition.

Possible states:

```text
DELIGHTED

POSITIVE

NEUTRAL

FRUSTRATED

DISSATISFIED

SERVICE_RECOVERY_REQUIRED

UNKNOWN
```

These states may be inferred and shall preserve confidence.

---

# 55. SENTIMENT

Sentiment may be derived from:

* Conversation.
* Feedback.
* Complaint.
* Survey.

Possible values:

```text
POSITIVE

NEUTRAL

NEGATIVE

MIXED

UNKNOWN
```

Sentiment is not equivalent to Customer satisfaction.

---

# 56. SENTIMENT TEMPORALITY

A Customer may be dissatisfied with one interaction without being globally dissatisfied with the restaurant.

Sentiment shall therefore be contextual and time-bound.

---

# 57. COMPLAINT INTELLIGENCE

Customer complaints may reveal:

* Service failure.
* Product failure.
* Employee issue.
* Delivery issue.
* Billing issue.
* Operational Incident.
* Repeated systemic problem.

Complaint existence does not automatically prove the alleged cause.

---

# 58. COMPLIMENT INTELLIGENCE

Compliments may reveal:

* High-performing Product.
* Employee recognition.
* Service strength.
* Customer loyalty signal.
* Experience differentiator.

---

# 59. SERVICE RECOVERY INTELLIGENCE

Customer Intelligence should know:

* What failed?
* What was promised?
* What compensation was provided?
* Was the issue resolved?
* Did the Customer return afterward?

This enables evaluation of Service Recovery effectiveness.

---

# 60. CUSTOMER COMMITMENT

A `CustomerCommitment` represents something the restaurant has promised or confirmed to a Customer.

Examples:

* Reservation.
* Delivery time.
* Refund.
* Replacement.
* Callback.
* Event proposal.
* Special accommodation.

---

# 61. COMMITMENT STATUS

Suggested lifecycle:

```text
PROPOSED

CONFIRMED

IN_PROGRESS

FULFILLED

FAILED

CANCELLED

EXPIRED
```

---

# 62. COMMITMENT OWNERSHIP

Every material active Commitment should have an accountable operational owner or authoritative system.

---

# 63. COMMITMENT RISK

Customer Intelligence may detect that a Commitment is at risk.

Example:

```text
Delivery promised:
19:30

Current estimated delivery:
19:55

        ↓

CUSTOMER COMMITMENT AT RISK
```

---

# 64. PROACTIVE SERVICE

Where appropriate, ECIP may act before the Customer complains.

Example:

```text
Detected:
Delivery delay

Action:
Inform affected Customer proactively
```

Authorization and communication policy shall apply.

---

# 65. CUSTOMER EXPECTATION

A `CustomerExpectation` may originate from:

* Explicit Customer statement.
* Restaurant promise.
* Published policy.
* Normal service standard.

The source shall remain explicit.

---

# 66. EXPECTATION GAP

Conceptually:

```text
Expected Experience
-
Observed Experience
=
Experience Gap
```

This may contribute to Customer dissatisfaction analysis.

---

# 67. CUSTOMER FRICTION

A `CustomerFrictionSignal` represents unnecessary difficulty encountered by the Customer.

Examples:

* Repeating information.
* Multiple transfers.
* Payment retry.
* Long response time.
* Repeated unavailable Products.
* Reservation confusion.

---

# 68. FRICTION SCORE

A future Friction Score may combine multiple Customer journey obstacles.

If implemented, methodology shall be explainable.

---

# 69. CUSTOMER EFFORT

Customer effort may consider how much work the Customer must perform to accomplish a Goal.

ECIP should seek to reduce unnecessary Customer effort.

---

# 70. CUSTOMER SATISFACTION

Customer satisfaction may be:

* Explicitly reported.
* Survey-based.
* Behaviorally inferred.

These sources shall remain distinguishable.

---

# 71. CUSTOMER SATISFACTION PREDICTION

A predictive Satisfaction estimate shall never be represented as a Customer's explicit opinion.

---

# 72. CUSTOMER MEMORY

ECIP should maintain useful long-term memory where authorized.

Potential memories include:

* Preferences.
* Previous Orders.
* Relevant occasions.
* Important service history.
* Pending intentions.
* Commitments.

---

# 73. MEMORY VALUE PRINCIPLE

A Customer fact should not be retained merely because it can be retained.

Useful Customer memory should improve:

* Service.
* Safety.
* Continuity.
* Customer Experience.
* Relationship quality.

while respecting retention and privacy requirements.

---

# 74. MEMORY CLASSIFICATION

Potential memory categories:

```text
TRANSACTIONAL

PREFERENCE

RELATIONSHIP

SERVICE

SAFETY

COMMERCIAL

TEMPORARY_CONTEXT
```

Different categories may have different retention policies.

---

# 75. TEMPORARY CUSTOMER CONTEXT

Some information may be useful only for the current interaction.

Example:

```text
"I'm driving and need something ready in 15 minutes."
```

This need not become permanent Customer memory.

---

# 76. LONG-TERM CUSTOMER MEMORY

Examples potentially appropriate for longer-term retention:

* Explicit favorite Product.
* Preferred Branch.
* Loyalty membership.
* Explicit communication preference.

Retention remains policy-driven.

---

# 77. PERSONAL OCCASION

A `CustomerOccasion` may represent a relevant occasion explicitly supplied by the Customer or supported by valid business history.

Examples:

* Birthday celebration.
* Anniversary dinner.
* Corporate meeting.
* Family event.

---

# 78. OCCASION PRIVACY

Personal occasion data shall only be retained and used when appropriate under privacy policy.

The platform shall avoid unnecessary personal profiling.

---

# 79. HOUSEHOLD / RELATIONSHIP CONTEXT

Where legitimately known and useful, Customer relationships may include:

* Family member.
* Household member.
* Event organizer.
* Company contact.

These relationships shall not be inferred merely from shared Orders or addresses.

---

# 80. CUSTOMER ROLE

A Customer may have different roles in different contexts:

```text
DINER

PURCHASER

RESERVATION_HOLDER

EVENT_ORGANIZER

COMPANY_CONTACT

DELIVERY_RECIPIENT
```

---

# 81. CUSTOMER ORGANIZATION

For B2B scenarios, a Customer may be associated with an Organization.

Examples:

* Company.
* School.
* Hotel.
* Event organizer.

This can support recurring corporate dining or catering relationships.

---

# 82. CUSTOMER PREFERENCE CHANGE

Customer Preferences may evolve.

Example:

```text
Previous:
Prefers spicy food

Current explicit statement:
"I don't eat spicy food anymore."
```

The latest authoritative Customer statement should supersede stale preference assumptions.

---

# 83. CUSTOMER BEHAVIOR CHANGE

Behavioral changes may create Intelligence signals.

Examples:

* Spending decreases.
* Visit frequency increases.
* Channel changes.
* Product category changes.

The platform should detect the change without automatically assigning a cause.

---

# 84. CUSTOMER INACTIVITY

A Customer may become inactive relative to their own historical pattern.

This is more meaningful than applying one universal inactivity threshold to every Customer.

---

# 85. CUSTOMER INACTIVITY RISK

Customer Intelligence may consume predictive inactivity risk from Sales Intelligence.

It shall preserve:

* Evidence.
* Confidence.
* Model version.
* Time horizon.

---

# 86. CUSTOMER REACTIVATION

A Customer returning after a meaningful inactivity period may be classified as reactivated.

This may create:

* Relationship insight.
* Sales insight.
* Loyalty insight.

---

# 87. CUSTOMER RETENTION

Retention shall be evaluated over defined cohorts and time windows.

The platform shall not treat one repeat visit as universal retention.

---

# 88. CUSTOMER CHURN

For restaurant contexts, exact churn may often be unknowable.

Therefore the platform should often use:

```text
INACTIVITY RISK
```

rather than falsely declaring:

```text
CUSTOMER CHURNED
```

---

# 89. CUSTOMER NEXT-BEST-ACTION

A `CustomerNextBestAction` represents the most appropriate action for the Customer under current context.

Possible Actions:

```text
ANSWER

COMPLETE_ORDER

MAKE_RESERVATION

RESOLVE_COMPLAINT

PROVIDE_STATUS

PROACTIVE_NOTIFICATION

RECOMMEND_PRODUCT

OFFER_AUTHORIZED_RECOVERY

ESCALATE_TO_HUMAN

FOLLOW_UP

NO_ACTION
```

---

# 90. NEXT-BEST-ACTION PRINCIPLE

The best next action is not necessarily the most profitable action.

Example:

```text
Customer has active complaint.

Best action:
Resolve complaint.

Not:
Upsell dessert.
```

---

# 91. CUSTOMER PRIORITY

Customer priority may consider:

* Safety.
* Urgency.
* Active Commitment.
* Service failure.
* Event deadline.
* Current operational context.

Commercial value shall not be the sole priority factor.

---

# 92. CUSTOMER OPPORTUNITY

Customer Intelligence may expose opportunities to other domains.

Examples:

```text
Event Opportunity
→ Sales Intelligence

Service Failure
→ Customer Experience

Loyalty Opportunity
→ Loyalty

Unmet Product Need
→ Menu Intelligence
```

Customer Intelligence detects and contextualizes; specialized domains execute their responsibilities.

---

# 93. CUSTOMER RISK

A `CustomerRiskSignal` may represent risk to the Customer relationship.

Examples:

* Repeated complaints.
* Repeated delivery failures.
* Declining frequency.
* Unresolved refund.
* Repeated unavailable favorite Product.

---

# 94. CUSTOMER RELATIONSHIP RISK

Potential states:

```text
LOW

MODERATE

HIGH

CRITICAL

UNKNOWN
```

These are analytical and shall preserve methodology.

---

# 95. CUSTOMER SAFETY RISK

Safety risk shall remain separate from relationship risk.

Examples:

* Allergen conflict.
* Food Safety concern.
* Unsafe Product recall.

Safety takes precedence.

---

# 96. CUSTOMER COMMUNICATION PREFERENCE

The Customer may explicitly prefer:

* Telephone.
* WhatsApp.
* SMS.
* Email.
* App notification.

Communication Preference shall be respected where technically and legally applicable.

---

# 97. CHANNEL AUTHORIZATION

A known Customer identity does not automatically authorize communication through every known Channel.

Consent and communication policy shall remain separate from identity knowledge.

---

# 98. CUSTOMER CONTACTABILITY

A `CustomerContactabilityState` may represent whether ECIP may contact the Customer for a particular purpose.

Examples:

```text
SERVICE_CONTACT_ALLOWED

TRANSACTIONAL_CONTACT_ALLOWED

MARKETING_CONTACT_ALLOWED

CONTACT_RESTRICTED

UNKNOWN
```

---

# 99. PURPOSE-SPECIFIC CONSENT

Consent may differ by purpose.

Example:

```text
Order notifications:
Allowed

Marketing:
Not allowed
```

The platform shall not collapse all consent into one Boolean flag.

---

# 100. CUSTOMER PRIVACY

Customer Intelligence may contain substantial behavioral information.

Therefore access shall follow:

* Least privilege.
* Purpose limitation.
* Data minimization.
* Retention policy.
* Consent where required.
* Tenant isolation.
* Auditability.

---

# 101. SENSITIVE INFORMATION

Customer Intelligence shall minimize collection and use of unnecessary sensitive personal information.

Restaurant-relevant intelligence should primarily derive from:

* Explicit Customer needs.
* Restaurant interactions.
* Purchase behavior.
* Service history.
* Operational context.

---

# 102. INFERENCE BOUNDARY

ECIP shall not infer sensitive personal attributes merely to improve personalization.

Customer Intelligence is intended to understand the restaurant relationship, not reconstruct the Customer's private life.

---

# 103. CUSTOMER DATA CORRECTION

Customers may provide corrections.

Example:

```text
"My preferred phone number changed."

"I no longer want promotional messages."

"That allergy information belongs to someone else."
```

Corrections shall propagate according to authoritative ownership and audit requirements.

---

# 104. CUSTOMER DATA DELETION

Deletion requests shall be evaluated against:

* Privacy requirements.
* Fiscal retention.
* Transaction retention.
* Compliance obligations.
* Legal holds.

Eligible data may be deleted or anonymized while mandatory records remain preserved.

---

# 105. CUSTOMER DATA EXPORT

Where applicable, Customer data may need to be exported in a structured form.

The platform should distinguish between:

* Customer Profile.
* Transactions.
* Conversations.
* Preferences.
* Consent.
* Derived intelligence.

---

# 106. DERIVED INTELLIGENCE TRANSPARENCY

Derived Customer Intelligence should remain identifiable as derived information.

Example:

```text
Fact:
Purchased vegan dishes 9 times.

Inference:
Likely prefers vegan dishes.

Confidence:
High.
```

---

# 107. CUSTOMER INTELLIGENCE EXPLAINABILITY

For material actions, the platform should be able to explain internally why it reached a Customer-related conclusion.

Example:

```text
Customer Relationship Risk:
HIGH

Evidence:
3 unresolved complaints in 60 days
Purchase frequency down 65%
Last complaint remains open
```

---

# 108. CUSTOMER INTELLIGENCE CONFLICT

Different sources may conflict.

Example:

```text
Customer Profile:
Preferred Branch = Downtown

Recent behavior:
8 consecutive visits = North Branch
```

This may indicate changed behavior but shall not silently overwrite explicit Preference.

---

# 109. CUSTOMER KNOWLEDGE CONFLICT

Another example:

```text
Historical Preference:
No spicy food

Current Customer statement:
"I'd like something very spicy."
```

The current interaction should be handled according to the current explicit statement while long-term Preference may require confirmation before permanent update.

---

# 110. CONFLICT RESOLUTION

Customer Intelligence conflicts may be resolved through:

* Source authority.
* Recency.
* Explicit Customer confirmation.
* Human review.
* Confidence rules.

Resolution shall preserve history.

---

# 111. CUSTOMER INTELLIGENCE TIMELINE

The platform should be able to reconstruct a Customer relationship chronologically.

Example:

```text
First Interaction
    ↓
First Order
    ↓
Preference Captured
    ↓
Loyalty Enrollment
    ↓
Complaint
    ↓
Service Recovery
    ↓
Repeat Visit
    ↓
Event Reservation
```

---

# 112. CUSTOMER RELATIONSHIP SUMMARY

A `CustomerRelationshipSummary` may provide authorized Employees or AI with a concise operational view.

Example:

```text
Returning Customer

Last visit:
12 days ago

Typical behavior:
Dine-In, Friday evenings

Explicit preferences:
Quiet table
Sparkling water

Active issue:
None

Loyalty:
Gold

Current intent:
Reservation for 4

Relevant opportunity:
Birthday dinner

Important constraint:
No verified allergy information
```

---

# 113. SUMMARY MINIMIZATION

Customer summaries shall include only information relevant to the current operational purpose.

---

# 114. HUMAN ESCALATION BRIEFING

When a Conversation transfers to a human, Customer Intelligence may provide:

* Customer identity.
* Current Intent.
* Relevant history.
* Current sentiment.
* Active commitments.
* Relevant Preferences.
* Customer value context where authorized.
* Current issue.
* Actions already attempted.
* Recommended next action.

---

# 115. NO-REPETITION PRINCIPLE

When information has already been reliably obtained during the interaction, the receiving Employee should not unnecessarily ask the Customer to repeat it.

---

# 116. CUSTOMER RECOGNITION

Customer recognition may allow natural continuity.

Example:

```text
"Welcome back. Would you like to continue with the reservation you asked about earlier?"
```

Recognition should remain useful rather than intrusive.

---

# 117. ANTI-CREEPINESS PRINCIPLE

The platform shall not expose remembered information merely because it possesses it.

Personalization should feel relevant and helpful, not invasive.

Example:

Appropriate:

```text
"Would you like your usual sparkling water?"
```

Potentially inappropriate:

```text
"You ordered at exactly 8:13 PM on each of your last four Fridays."
```

---

# 118. CUSTOMER TRUST

Customer trust is a first-class business asset.

Customer Intelligence shall optimize for:

```text
RELEVANCE
+
CONTINUITY
+
HELPFULNESS
+
TRANSPARENCY
+
PRIVACY
=
TRUST
```

---

# 119. CUSTOMER EXPERIENCE LEARNING

The platform may learn which actions improve Customer Experience.

Examples:

* Proactive delay notification.
* Faster escalation.
* Preferred table.
* Product substitution.
* Service Recovery method.

---

# 120. CUSTOMER PREFERENCE LEARNING

Preference learning may combine:

```text
Explicit Statements
+
Repeated Behavior
+
Recommendation Responses
+
Corrections
```

with appropriate confidence.

---

# 121. CUSTOMER COMMERCIAL LEARNING

Commercial learning may include:

* Accepted recommendations.
* Declined recommendations.
* Purchase frequency.
* Product affinity.
* Promotion response.

This feeds `32_Sales_Intelligence.md`.

---

# 122. CUSTOMER SERVICE LEARNING

Service learning may include:

* Preferred interaction style.
* Common questions.
* Escalation needs.
* Friction patterns.
* Resolution effectiveness.

---

# 123. CUSTOMER INTELLIGENCE FEEDBACK LOOP

Conceptually:

```text
INTERACTION
    ↓
OBSERVATION
    ↓
SIGNAL
    ↓
INTELLIGENCE
    ↓
DECISION
    ↓
ACTION
    ↓
CUSTOMER RESPONSE
    ↓
OUTCOME
    ↓
LEARNING
    ↓
BETTER FUTURE INTERACTION
```

This is one of the fundamental intelligence loops of ECIP.

---

# 124. CUSTOMER DIGITAL TWIN

Long-term, Customer Intelligence contributes to a restaurant-specific Customer Digital Twin.

This does not mean creating an unrestricted replica of the person.

It means maintaining a governed digital representation of the Customer's relationship with the restaurant.

Potential components:

```text
Identity

Restaurant Relationship

Preferences

Purchase Behavior

Service History

Loyalty

Interaction Patterns

Current Commitments

Current Context

Relevant Predictions
```

---

# 125. CUSTOMER DIGITAL TWIN BOUNDARY

The Customer Digital Twin shall model:

> The Customer in relation to the restaurant.

It shall not attempt to model:

> The Customer's entire private life.

This boundary is fundamental.

---

# 126. CUSTOMER INTELLIGENCE METRICS

Potential metrics include:

* Known Customer rate.
* Returning Customer rate.
* Customer recognition rate.
* Identity resolution confidence.
* Preference coverage.
* Repeat purchase rate.
* Customer retention.
* Customer inactivity risk.
* Complaint rate.
* Complaint recurrence.
* Service Recovery success.
* Customer friction.
* Customer effort.
* Satisfaction.
* Recommendation acceptance.
* Cross-channel continuity.

---

# 127. KNOWN CUSTOMER RATE

Potential metric:

```text
Transactions associated with reliably known Customers
/
Eligible Customer Transactions
```

---

# 128. CUSTOMER RECOGNITION RATE

Potential metric:

```text
Returning Customers correctly recognized
/
Returning Customers eligible for recognition
```

Incorrect recognition shall be tracked separately.

---

# 129. CUSTOMER IDENTITY ERROR RATE

Potential metric:

```text
Incorrect Identity Resolutions
/
Identity Resolutions
```

Identity accuracy is more important than maximizing match rate.

---

# 130. PREFERENCE COVERAGE

Potential metric:

```text
Customers with useful verified or explicit Preferences
/
Known Active Customers
```

This should not encourage unnecessary data collection.

---

# 131. CUSTOMER RETENTION RATE

Retention methodology shall define:

* Cohort.
* Time period.
* Qualifying activity.

---

# 132. CUSTOMER REPEAT RATE

Potential metric:

```text
Customers with Repeat Purchase
/
Customers with Initial Purchase
```

within a defined period.

---

# 133. CUSTOMER COMPLAINT RATE

Potential metric:

```text
Customers with Complaint
/
Customers Served
```

The denominator shall be defined consistently.

---

# 134. SERVICE RECOVERY SUCCESS

Possible indicators include:

* Issue resolved.
* Customer accepted resolution.
* Customer returned.
* Repeat complaint did not occur.

No single indicator alone necessarily proves recovery success.

---

# 135. CUSTOMER FRICTION RATE

Potential sources:

* Repeated information.
* Transfer count.
* Failed Payment attempts.
* Unresolved requests.
* Excessive wait.

---

# 136. CUSTOMER INTELLIGENCE DASHBOARD

A future Customer Intelligence view may include:

```text
CUSTOMERS

Known Customers
New Customers
Returning Customers
Active Customers
Reactivated Customers

RELATIONSHIP

Retention
Visit Frequency
Loyalty
Customer Value

EXPERIENCE

Complaints
Service Recovery
Sentiment
Friction

INTELLIGENCE

Active Customer Risks
Unmet Needs
Preference Changes
Important Opportunities
```

This document does not prescribe UI.

---

# 137. CUSTOMER INTELLIGENCE ALERTS

Possible alerts include:

```text
CUSTOMER_COMMITMENT_AT_RISK

UNRESOLVED_HIGH_VALUE_COMPLAINT

REPEATED_CUSTOMER_FAILURE

CUSTOMER_RELATIONSHIP_RISK_HIGH

IMPORTANT_CUSTOMER_RETURNED

CUSTOMER_REACTIVATED

CUSTOMER_PREFERENCE_CONFLICT

CUSTOMER_IDENTITY_CONFLICT

CUSTOMER_CONSENT_CHANGED

CUSTOMER_SAFETY_CONSTRAINT_DETECTED
```

Alerts shall be operationally useful and not create unnecessary surveillance.

---

# 138. EXECUTIVE CUSTOMER INTELLIGENCE

Potential executive questions include:

* Are we gaining or losing repeat Customers?
* Which Branches retain Customers best?
* What are Customers asking for that we do not offer?
* What causes Customers to complain repeatedly?
* Which Service Recovery actions work?
* Which Customer segments are growing?
* Where is Customer friction increasing?
* Which Channels create the strongest relationships?
* Are Customer Preferences changing?
* What Customer needs are emerging?

---

# 139. CONVERSATIONAL CUSTOMER INTELLIGENCE

Authorized Employees may ask:

```text
"Who is this customer?"

"What does this customer usually order?"

"Does the customer have any explicit preferences?"

"Is there an unresolved complaint?"

"What happened during the last interaction?"

"Does the customer have an active reservation?"

"What commitments do we have with this customer?"

"What is the best next action?"
```

Responses shall be constrained by authorization and relevance.

---

# 140. CUSTOMER-FACING INTELLIGENCE

ECIP may use Customer Intelligence naturally in interactions.

Examples:

```text
"You still have a reservation for four this Saturday."

"Would you like to continue the order you started earlier?"

"The product you usually order is unavailable today; I can suggest an alternative if you'd like."
```

The system shall avoid overstating uncertain memory.

---

# 141. CUSTOMER INTELLIGENCE AND SALES INTELLIGENCE

Customer Intelligence answers:

```text
WHO IS THE CUSTOMER?

WHAT DO WE KNOW ABOUT THE RELATIONSHIP?

WHAT IS HAPPENING NOW?
```

Sales Intelligence answers:

```text
WHAT COMMERCIAL OPPORTUNITY EXISTS?

WHAT SHOULD WE RECOMMEND?

WHAT COMMERCIAL OUTCOME OCCURRED?
```

The domains cooperate but shall remain semantically distinct.

---

# 142. CUSTOMER INTELLIGENCE AND CUSTOMER EXPERIENCE

Customer Intelligence provides relationship context.

Customer Experience Intelligence evaluates the quality of the Customer's experience.

A negative Experience may become a Customer Intelligence signal.

---

# 143. CUSTOMER INTELLIGENCE AND LOYALTY

Loyalty owns:

* Program membership.
* Points.
* Rewards.
* Tiers.

Customer Intelligence interprets Loyalty behavior in the broader Customer relationship.

---

# 144. CUSTOMER INTELLIGENCE AND RESERVATIONS

Reservations provide:

* Visit intent.
* Party size.
* Occasion.
* Time.
* Branch.

Customer Intelligence may use these facts to improve service continuity.

---

# 145. CUSTOMER INTELLIGENCE AND ORDERS

Orders provide high-value behavioral evidence.

Customer Intelligence may derive patterns but shall not modify authoritative Order history.

---

# 146. CUSTOMER INTELLIGENCE AND EVENTS

Banquets and Events may reveal:

* Corporate relationship.
* Celebration patterns.
* High-value recurring needs.

Event domain remains authoritative for Event execution.

---

# 147. CUSTOMER INTELLIGENCE AND OPERATIONAL INCIDENTS

Operational Incidents may affect specific Customers.

Customer Intelligence should understand:

* Which Customer was affected.
* Which Commitment failed.
* Whether communication occurred.
* Whether Service Recovery occurred.

---

# 148. CUSTOMER INTELLIGENCE AND COMPLIANCE

Compliance constrains:

* Privacy.
* Consent.
* Retention.
* Customer-data access.
* Sensitive information handling.

Customer Intelligence shall consume these constraints.

---

# 149. CUSTOMER INTELLIGENCE AND FUTURE MARKETING INTELLIGENCE

Customer Intelligence may provide authorized signals to future Marketing Intelligence.

Examples:

* Reactivation candidate.
* Product interest.
* Event interest.
* Channel Preference.

Marketing authorization and consent remain separate.

---

# 150. AI CUSTOMER INTELLIGENCE

AI may assist with:

* Intent detection.
* Conversation summarization.
* Customer-history summarization.
* Preference candidate detection.
* Behavioral pattern detection.
* Customer friction detection.
* Customer relationship risk detection.
* Unmet need detection.
* Next-best-action recommendation.
* Cross-channel context reconstruction.

---

# 151. AI AUTHORITY LIMIT

AI shall not:

* Invent Customer facts.
* Invent Customer Preferences.
* Convert inference into explicit fact.
* Invent allergies.
* Invent consent.
* Merge Customer identities without sufficient evidence.
* Reveal Customer information to unauthorized actors.
* Infer unnecessary sensitive attributes.
* Ignore Customer corrections.
* Hide uncertainty.
* Manipulate Customers.
* Override safety or Compliance constraints.

---

# 152. CUSTOMER INTELLIGENCE PREDICTION

Predictions may include:

* Likely next Product.
* Likely next visit period.
* Inactivity risk.
* Likely Channel.
* Likely Customer need.

Predictions shall preserve:

* Model.
* Model version.
* Confidence.
* Time horizon.
* Evidence references.

---

# 153. PREDICTION EXPIRATION

Predictions shall have a validity horizon.

An old prediction shall not remain indefinitely actionable.

---

# 154. CUSTOMER INTELLIGENCE RECOMMENDATION

A recommendation may suggest:

* Next Employee action.
* Next Customer-facing response.
* Follow-up.
* Service Recovery.
* Product recommendation.
* Escalation.

Recommendation remains distinct from authorized Action.

---

# 155. HUMAN OVERRIDE

Authorized Employees may correct or reject AI-generated Customer Intelligence.

Such overrides should preserve:

* Original recommendation.
* Human decision.
* Reason where material.
* Timestamp.

---

# 156. CUSTOMER SOURCE OF TRUTH

Authority varies by information type.

Example:

```text
Customer Profile:
Identity and profile facts

Customer Preferences:
Explicit preferences

Loyalty:
Program state

POS / Orders:
Transaction history

Reservations:
Reservation state

Customer History:
Historical relationship events

Compliance:
Consent and retention constraints

ECIP Customer Intelligence:
Cross-domain interpretation and intelligence
```

Customer Intelligence composes truth without replacing authoritative domains.

---

# 157. EXTERNAL CUSTOMER MAPPING

External systems may use:

* POS Customer ID.
* Loyalty ID.
* Delivery marketplace Customer reference.
* Messaging identity.
* CRM Customer ID.

These shall map to canonical Customer identity.

---

# 158. CUSTOMER DATA IMPORT

Historical Customer information may be imported.

Import shall preserve:

* Source.
* External ID.
* Original timestamps.
* Confidence.
* Data quality.
* Consent status where available.
* Mapping state.

Imported assumptions shall not automatically become confirmed Customer facts.

---

# 159. CUSTOMER SYNCHRONIZATION

Synchronization may include:

* Profile changes.
* Contact information.
* Loyalty state.
* Orders.
* Reservations.
* Customer Preferences.
* Consent.

Synchronization shall remain:

* Idempotent.
* Observable.
* Auditable.

---

# 160. CUSTOMER INTELLIGENCE CONFLICT EXAMPLE

```text
POS:
Customer telephone = A

Loyalty:
Customer telephone = B

WhatsApp:
Customer currently authenticated as B
```

The platform shall not silently choose one without identity-resolution rules.

---

# 161. CUSTOMER AUDIT TRAIL

Material Customer Intelligence changes should preserve:

* Customer.
* Intelligence type.
* Previous value.
* New value.
* Source.
* Evidence.
* Confidence.
* Actor or model.
* Timestamp.
* Reason where applicable.

---

# 162. CUSTOMER MEMORY AUDITABILITY

For material remembered information, the platform should be able to answer:

```text
Why do we remember this?

Who supplied it?

When?

Has it been corrected?

Is it still valid?

Are we authorized to use it?
```

---

# 163. CUSTOMER INTELLIGENCE EVENTS

Initial domain events include:

```text
CustomerIntelligenceProfileCreated
CustomerIntelligenceProfileUpdated

CustomerIdentityObserved
CustomerIdentityResolved
CustomerIdentityResolutionFailed
CustomerIdentityConflictDetected
CustomerIdentityMerged
CustomerIdentitySplit

CustomerFactRecorded
CustomerFactCorrected

CustomerObservationRecorded
CustomerSignalDetected

CustomerInsightCreated
CustomerInsightValidated
CustomerInsightRejected
CustomerInsightExpired
CustomerInsightSuperseded

CustomerPreferenceCandidateDetected
CustomerPreferenceConflictDetected
CustomerPreferenceChangeDetected

CustomerPurchasePatternDetected
CustomerVisitPatternDetected
CustomerChannelPatternDetected
CustomerBehaviorChangeDetected

CustomerIntentDetected
CustomerIntentChanged
CustomerNeedDetected
CustomerGoalDetected

CustomerRelationshipStateChanged
CustomerRelationshipRiskDetected

CustomerExperienceStateChanged
CustomerSentimentChanged
CustomerFrictionDetected

CustomerComplaintLinked
CustomerComplimentLinked
CustomerServiceRecoveryLinked

CustomerCommitmentCreated
CustomerCommitmentAtRisk
CustomerCommitmentFulfilled
CustomerCommitmentFailed

CustomerFutureIntentionRecorded
CustomerUnfinishedConversationDetected
CustomerConversationResumed

CustomerInactivityDetected
CustomerReactivationDetected

CustomerOccasionDetected

CustomerConsentChanged
CustomerContactabilityChanged

CustomerNextBestActionRecommended
CustomerNextBestActionExecuted
CustomerNextBestActionRejected

CustomerKnowledgeConflictDetected
CustomerKnowledgeConflictResolved

CustomerPredictionCreated
CustomerPredictionExpired

CustomerIntelligenceSynchronizationStarted
CustomerIntelligenceSynchronizationCompleted
CustomerIntelligenceSynchronizationFailed
```

---

# 164. RELATIONSHIPS

```text
Customer
    HAS CustomerIntelligenceProfile

CustomerIntelligenceProfile
    REFERENCES CustomerProfile

CustomerIntelligenceProfile
    REFERENCES CustomerPreferences

CustomerIntelligenceProfile
    REFERENCES CustomerLoyalty

CustomerIntelligenceProfile
    REFERENCES CustomerHistory

Customer
    HAS CustomerIdentity

CustomerIdentity
    MAPS_TO ExternalCustomerIdentity

Customer
    HAS CustomerObservation

CustomerObservation
    MAY_CREATE CustomerSignal

CustomerSignal
    MAY_CREATE CustomerInsight

Customer
    MAY_HAVE CustomerPurchasePattern

Customer
    MAY_HAVE CustomerVisitPattern

Customer
    MAY_HAVE CustomerChannelPattern

Customer
    HAS CustomerInteraction

CustomerInteraction
    MAY_HAVE CustomerIntent

CustomerIntent
    MAY_REVEAL CustomerNeed

Customer
    MAY_HAVE CustomerGoal

Customer
    MAY_HAVE CustomerCommitment

CustomerCommitment
    MAY_BECOME AT_RISK

Customer
    MAY_HAVE CustomerRelationshipState

Customer
    MAY_HAVE CustomerExperienceState

Customer
    MAY_HAVE CustomerRelationshipRisk

Customer
    MAY_HAVE CustomerFutureIntention

Customer
    MAY_HAVE UnfinishedConversation

CustomerIntelligence
    MAY_CREATE CustomerNextBestAction

CustomerIntelligence
    INFORMS SalesIntelligence

CustomerIntelligence
    INFORMS CustomerExperienceIntelligence

CustomerIntelligence
    CONTRIBUTES_TO ExecutiveIntelligence
```

---

# 165. BUSINESS RULES

The following rules apply:

1. Customer Intelligence shall not replace authoritative Customer-domain data.

2. Customer 360 shall remain a composed view.

3. Facts, observations, Preferences, inferences and predictions shall remain distinguishable.

4. Explicit Customer statements shall preserve their provenance.

5. Inferred Preferences shall not silently become explicit Preferences.

6. Behavioral patterns shall not automatically become Customer facts.

7. Allergy or safety-critical information shall not be inferred from ordinary purchase behavior.

8. Customer identity shall not be resolved solely for the purpose of maximizing data aggregation.

9. Ambiguous identities shall remain ambiguous until sufficient evidence exists.

10. Incorrect Customer identity merges shall be correctable.

11. Customer knowledge shall preserve source, timestamp and confidence where material.

12. Customer knowledge may become stale and shall support freshness management.

13. Temporary context shall not automatically become long-term memory.

14. Customer memory shall have a legitimate restaurant-related purpose.

15. Customer corrections shall take precedence over stale derived assumptions.

16. Current explicit Customer intent shall take precedence over conflicting historical prediction.

17. Customer consent shall remain purpose-specific.

18. Customer identity knowledge does not imply permission for Marketing communication.

19. Customer value shall not override Safety, Compliance, fairness or confirmed commitments.

20. Customer dissatisfaction shall influence Sales behavior.

21. Customer Experience state shall remain contextual and time-bound.

22. Customer Commitment state shall be explicit and traceable.

23. At-risk Customer commitments should support proactive action where authorized.

24. Customer Intelligence shall minimize unnecessary disclosure of personal history.

25. Personalization shall be relevant rather than intrusive.

26. Sensitive personal attributes shall not be unnecessarily inferred.

27. AI-generated Customer Intelligence shall preserve uncertainty.

28. Predictions shall remain distinguishable from facts.

29. Recommendations shall remain distinguishable from authorized Actions.

30. Cross-channel Customer continuity shall preserve authorization boundaries.

31. External Customer identifiers shall remain integration mappings.

32. Customer Intelligence synchronization shall be idempotent and auditable.

33. Customer knowledge conflicts shall remain explicit until resolved.

34. Every material Customer Intelligence conclusion shall be explainable from evidence.

35. Every interaction should improve future Customer understanding only when the information is relevant, legitimate and appropriately retained.

---

# 166. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
CustomerIntelligenceProfile

Customer360View

CustomerIdentityReference

CustomerIdentityResolution

CustomerIdentityConfidence

CustomerFactReference

CustomerObservation

CustomerSignal

CustomerInsight

CustomerInsightConfidence

CustomerKnowledgeFreshness

ExplicitPreferenceReference

InferredPreferenceCandidate

CustomerPurchasePattern

CustomerVisitPattern

CustomerChannelPattern

CustomerIntent

CustomerIntentConfidence

CustomerNeed

CustomerContextSnapshot

CustomerRelationshipState

CustomerExperienceState

CustomerSentimentReference

CustomerComplaintReference

CustomerServiceRecoveryReference

CustomerCommitment

CustomerCommitmentRisk

CustomerFutureIntention

UnfinishedConversation

CustomerRelationshipSummary

CustomerNextBestAction

CustomerContactabilityState

CustomerConsentReference

CustomerKnowledgeConflict

ExternalCustomerMapping

CustomerIntelligenceHistory
```

---

# 167. FIRST PRODUCTION INTELLIGENCE LOOP

The first production version should prove the following end-to-end loop:

```text
CUSTOMER CONTACTS RESTAURANT
        ↓
IDENTITY RESOLUTION
        ↓
RELEVANT CUSTOMER CONTEXT RETRIEVED
        ↓
CURRENT INTENT DETECTED
        ↓
RELEVANT HISTORY + PREFERENCES COMPOSED
        ↓
CURRENT RESTAURANT CONTEXT ADDED
        ↓
NEXT-BEST-ACTION DETERMINED
        ↓
ACTION / RESPONSE EXECUTED
        ↓
CUSTOMER RESPONSE OBSERVED
        ↓
OUTCOME RECORDED
        ↓
USEFUL CUSTOMER KNOWLEDGE UPDATED
```

This loop is more important for the first production release than implementing advanced predictive Customer modeling.

---

# 168. DEFERRED CAPABILITIES

Unless required by the first commercial pilot, defer:

```text
Advanced Customer Lifetime Prediction

Deep Churn Prediction

Autonomous Customer Segmentation

Advanced Behavioral Embeddings

Customer Similarity Graphs

Real-Time Customer Propensity Models

Advanced Journey Optimization

Reinforcement Learning Next-Best-Action

Autonomous Relationship Management

Cross-Enterprise Customer Identity Network

Advanced Customer Digital Twin Simulation

Predictive Life-Event Modeling

Large-Scale Autonomous Personalization
```

These capabilities may become strategically important later but are not required to prove the core Customer Intelligence architecture.

---

# 169. IMPLEMENTATION PRINCIPLE

This document defines the logical Customer Intelligence Model.

It does not prescribe:

* CRM.
* Customer Data Platform.
* Identity provider.
* Recommendation engine.
* Vector database.
* Graph database.
* Data warehouse.
* Machine-learning algorithm.
* LLM.
* Marketing automation platform.
* User interface.

Implementation shall preserve the semantic distinction between:

```text
CUSTOMER

IDENTITY

FACT

OBSERVATION

SIGNAL

EXPLICIT PREFERENCE

INFERRED PREFERENCE

INTENT

NEED

HISTORY

COMMITMENT

EXPERIENCE STATE

RELATIONSHIP STATE

INSIGHT

PREDICTION

RECOMMENDATION

ACTION

OUTCOME
```

---

# 170. ARCHITECTURAL PRINCIPLE

Customer Intelligence shall be implemented as an intelligence composition layer over authoritative restaurant domains.

Conceptually:

```text
                    CUSTOMER PROFILE
                           │
                    CUSTOMER PREFERENCES
                           │
                     CUSTOMER LOYALTY
                           │
                     CUSTOMER HISTORY
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
      ORDERS          RESERVATIONS       CONVERSATIONS
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                   CUSTOMER INTELLIGENCE
                           │
            ┌──────────────┼──────────────┐
            │              │              │
         CONTEXT         INSIGHT      PREDICTION
            │              │              │
            └──────────────┼──────────────┘
                           │
                  NEXT-BEST-ACTION
                           │
            ┌──────────────┼──────────────┐
            │              │              │
          SERVICE         SALES       ESCALATION
            │              │              │
            └──────────────┼──────────────┘
                           │
                        OUTCOME
                           │
                        LEARNING
```

Customer Intelligence therefore becomes one of the central intelligence capabilities of ECIP without becoming the owner of every underlying domain.

---

# 171. LONG-TERM INTELLIGENCE PRINCIPLE

The strategic objective is not merely to remember Customers.

It is to create institutional Customer knowledge.

Today, restaurant Customer knowledge is frequently fragmented across:

```text
Employee memory

POS history

Telephone conversations

WhatsApp messages

Reservations

Delivery platforms

Complaints

Loyalty systems

Manager knowledge
```

ECIP shall progressively transform this fragmented knowledge into:

```text
PERSISTENT

STRUCTURED

EXPLAINABLE

CONTEXTUAL

CHANNEL-INDEPENDENT

OPERATIONALLY USEFUL

PRIVACY-GOVERNED

ENTERPRISE CUSTOMER INTELLIGENCE
```

This allows the restaurant itself—not merely individual Employees—to learn from every Customer relationship.

---

# 172. FINAL RULE

Before ECIP represents something as Customer Intelligence or uses it to make a Customer-related decision, it shall be able to determine:

> Who is the Customer, and how confidently has identity been resolved?

> What information is authoritative fact?

> What information was explicitly provided by the Customer?

> What information is only an observation?

> What information is an inferred Preference or behavioral pattern?

> What information is predictive?

> What is the source of each material piece of knowledge?

> When was it learned?

> Is it still current?

> Is it relevant to the present interaction?

> Is the platform authorized to use it for this purpose?

> What is the Customer currently trying to accomplish?

> Is the current Intent explicit or inferred?

> What relevant Preferences, restrictions, history and commitments exist?

> Is there any unresolved complaint, Service Recovery or Customer Commitment?

> Is there an active operational condition affecting the Customer?

> What is the current Customer Experience state?

> What action would best serve the Customer now?

> Should a commercial recommendation be made, or suppressed?

> Is human escalation more appropriate?

> What should the restaurant remember from this interaction?

> What should remain temporary and not become permanent memory?

> What should the system learn from the Customer's response and final outcome?

> Can the complete path from evidence through Customer Intelligence, decision, Action and outcome be reconstructed and audited?

Only after these conditions are resolved may ECIP reliably use Customer Intelligence to personalize service, preserve relationship continuity, support commercial decisions and improve future interactions.

The objective of Customer Intelligence is not to accumulate the maximum possible amount of Customer data.

The objective is to transform the minimum relevant and legitimate Customer information into **continuously improving institutional knowledge that allows the restaurant to recognize, understand, serve and retain each Customer better over time—across every communication channel—without sacrificing privacy, trust, safety or explainability.**

