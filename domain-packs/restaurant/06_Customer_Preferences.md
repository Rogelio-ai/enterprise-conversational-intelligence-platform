# 06_Customer_Preferences.md

**Document ID:** RDM-006

**Document Name:** Customer Preferences

**Domain Pack:** Restaurant Intelligence Platform

**Product:** Enterprise Conversational Intelligence Platform (ECIP)

**Version:** 1.0.0

**Status:** ACTIVE

**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Restaurant Customer Preferences Model.

Its purpose is to enable the Restaurant Intelligence Platform to understand, preserve and safely use customer preferences, dietary choices, restrictions, allergies, service expectations and contextual preferences.

Customer preferences are a fundamental component of personalization.

They shall never be treated as static profile fields without provenance, confidence, temporal validity and governance.

---

# 2. OBJECTIVES

The Customer Preferences Model enables ECIP to:

* Personalize conversations.
* Personalize menu recommendations.
* Improve product recommendations.
* Avoid unsuitable recommendations.
* Respect dietary choices.
* Protect customers from known allergens.
* Remember service preferences.
* Remember seating preferences.
* Improve reservation experiences.
* Improve delivery experiences.
* Support personalized promotions.
* Improve human handoffs.
* Detect preference changes.
* Learn from customer behavior without confusing inference with fact.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends the following canonical concepts:

* Customer
* Preference
* Consent
* Memory Record
* Knowledge Fact
* Context Snapshot
* Recommendation
* Risk Assessment

Restaurant-specific preferences extend the canonical `Preference` entity.

This document does not redefine the canonical preference or memory models.

---

# 4. CORE PRINCIPLE

ECIP shall distinguish between:

```text
What the customer explicitly said

What the customer selected

What the customer repeatedly does

What another authorized person reported

What an enterprise system recorded

What the platform inferred

What the platform predicted
```

These are not equivalent sources of truth.

---

# 5. PREFERENCE MODEL

A `CustomerPreference` represents a customer-specific tendency, choice or desired experience.

Typical attributes include:

* Preference ID
* Customer ID
* Preference category
* Preference type
* Preferred value
* Strength
* Scope
* Source
* Confidence
* Verification status
* Effective from
* Effective until
* Last observed
* Consent basis
* Sensitivity classification
* Status

---

# 6. PREFERENCE CATEGORIES

Restaurant preferences may be classified into:

```text
Food Preferences
Beverage Preferences
Dietary Preferences
Dining Preferences
Seating Preferences
Service Preferences
Ordering Preferences
Delivery Preferences
Pickup Preferences
Communication Preferences
Payment Preferences
Promotion Preferences
Event Preferences
Accessibility Preferences
Relationship Preferences
```

Domain-specific categories may be added without modifying the canonical preference model.

---

# 7. FOOD PREFERENCES

Food preferences describe products or characteristics the customer tends to prefer.

Examples:

* Favorite dishes
* Favorite cuisines
* Favorite ingredients
* Preferred proteins
* Preferred side dishes
* Preferred desserts
* Preferred portion sizes
* Preferred preparation styles

Examples:

```text
Prefers grilled salmon

Likes ribeye steak

Prefers vegetables instead of fries

Usually orders soup before the main course
```

---

# 8. FLAVOR PREFERENCES

Examples:

* Sweet
* Savory
* Spicy
* Mild
* Sour
* Bitter
* Smoky
* Creamy
* Fresh
* Rich

Preference strength may be represented.

Example:

```text
Spice preference:

LOW
MEDIUM
HIGH
VERY_HIGH
```

---

# 9. PREPARATION PREFERENCES

Examples:

* Steak doneness
* Egg preparation
* Dressing on the side
* Sauce preference
* No onion
* Extra cheese
* Light salt
* Crispy preparation
* Temperature preference

These preferences may influence future order customization.

---

# 10. BEVERAGE PREFERENCES

Examples:

* Favorite beverages
* Coffee preparation
* Tea preference
* Beverage temperature
* Preferred soft drinks
* Preferred juices
* Preferred wines
* Preferred beer styles
* Preferred cocktails

Where alcoholic beverages are involved, applicable legal and business policies shall always take precedence over personalization.

---

# 11. DESSERT PREFERENCES

Examples:

* Favorite dessert
* Chocolate preference
* Fruit preference
* Ice cream flavor
* Coffee with dessert
* Birthday dessert preference

Dessert preferences may support contextual cross-selling.

---

# 12. DIETARY PREFERENCES

Dietary preferences represent voluntary dietary choices.

Examples:

* Vegetarian
* Vegan
* Pescatarian
* Low carbohydrate
* Low sodium
* Organic preference
* Plant-based preference
* High-protein preference

A dietary preference shall not automatically be treated as a medical requirement.

---

# 13. DIETARY RESTRICTIONS

A `DietaryRestriction` represents a constraint that should be respected when recommending or preparing food.

Examples may include:

* Ingredient avoidance
* Religious dietary requirements
* Medically motivated dietary constraints
* Temporary dietary restrictions

Restrictions shall be distinguished from ordinary preferences.

Typical attributes:

* Restriction type
* Severity
* Source
* Verification
* Effective period
* Notes

---

# 14. ALLERGIES

A `CustomerAllergy` represents a safety-critical customer constraint.

Examples:

* Peanut
* Tree nut
* Shellfish
* Fish
* Milk
* Egg
* Wheat
* Soy
* Sesame

Typical attributes:

* Allergen
* Customer
* Reported severity
* Source
* Verification status
* Date recorded
* Last confirmed
* Notes
* Status

Allergy information shall receive higher safety priority than ordinary preferences.

---

# 15. ALLERGY SAFETY RULE

A preference may influence a recommendation.

An allergy may prohibit a recommendation.

Therefore:

```text
ALLERGY / SAFETY CONSTRAINT

        overrides

DIETARY RESTRICTION

        overrides

EXPLICIT CUSTOMER REQUEST

        overrides

CUSTOMER PREFERENCE

        overrides

BEHAVIORAL INFERENCE

        overrides

COMMERCIAL OPTIMIZATION
```

No upselling, cross-selling or promotional objective shall override a known safety constraint.

---

# 16. ALLERGY UNCERTAINTY

ECIP shall not infer that a customer has an allergy merely because the customer repeatedly avoids an ingredient.

Example:

```text
Observed:

Customer repeatedly removes peanuts.

Allowed inference:

Customer may prefer dishes without peanuts.

Prohibited conclusion:

Customer is allergic to peanuts.
```

The platform may ask for clarification when relevant.

---

# 17. DINING PREFERENCES

Examples:

* Dine-in
* Take away
* Delivery
* Bar seating
* Outdoor dining
* Private room
* Buffet
* Counter service

The platform may identify patterns while preserving their inferred nature.

---

# 18. SEATING PREFERENCES

Examples:

* Favorite table
* Window table
* Quiet area
* Outdoor seating
* Near entrance
* Away from kitchen
* Booth
* Accessible table
* High chair requirement

Seating preferences shall influence reservations when capacity permits.

They do not guarantee availability.

---

# 19. ATMOSPHERE PREFERENCES

Examples:

* Quiet environment
* Family environment
* Romantic setting
* Business environment
* Outdoor environment
* Live music
* Sports viewing

These preferences may help ECIP recommend:

* Location
* Dining area
* Reservation time
* Event
* Restaurant branch

---

# 20. SERVICE PREFERENCES

Examples:

* Fast service
* Relaxed service
* Minimal interruption
* Frequent attention
* Preferred waiter
* Preferred language
* Course pacing
* Birthday recognition

Service preferences help personalize the complete restaurant experience.

---

# 21. ORDERING PREFERENCES

Examples:

* Frequently repeated order
* Favorite modifications
* Typical side dish
* Typical beverage
* Typical dessert
* Preferred portion
* Common bundle

ECIP may use ordering preferences to reduce conversational friction.

Example:

```text
"Would you like your usual grilled chicken
with vegetables instead of fries?"
```

The customer shall always remain able to change the selection.

---

# 22. DELIVERY PREFERENCES

Examples:

* Preferred delivery address
* Preferred delivery instructions
* Contactless delivery
* Preferred delivery time
* Preferred branch
* Delivery notes

Operational feasibility always takes precedence over preference.

---

# 23. PICKUP PREFERENCES

Examples:

* Preferred branch
* Preferred pickup area
* Vehicle pickup
* Curbside pickup
* Typical pickup time
* Notification preference

---

# 24. COMMUNICATION PREFERENCES

Examples:

Preferred channel:

* Telephone
* WhatsApp
* SMS
* Email
* Web Chat
* Mobile App

Additional preferences:

* Preferred language
* Preferred contact time
* Marketing communication preference
* Order notification preference
* Reservation notification preference

Communication preference shall respect consent and enterprise policy.

---

# 25. PAYMENT PREFERENCES

Examples:

* Cash
* Card
* Digital wallet
* Corporate account

Payment preference may improve customer convenience.

Payment credentials themselves shall not be represented as ordinary customer preferences.

Sensitive payment information shall remain within authorized payment systems.

---

# 26. PROMOTION PREFERENCES

Examples:

* Lunch promotions
* Family promotions
* Birthday promotions
* Seasonal promotions
* New product announcements
* Event promotions

Promotional preferences do not replace marketing consent.

---

# 27. EVENT PREFERENCES

Examples:

* Birthday celebrations
* Anniversaries
* Business dinners
* Family gatherings
* Sports events
* Live music
* Holiday celebrations

These preferences may generate future commercial opportunities.

---

# 28. ACCESSIBILITY PREFERENCES

Examples:

* Wheelchair-accessible seating
* Accessible entrance
* Accessible parking
* Reduced walking distance
* Appropriate seating arrangement

Accessibility requirements should be treated as operational constraints when explicitly requested, not merely as marketing attributes.

---

# 29. CONTEXTUAL PREFERENCES

Not every preference applies universally.

A customer may prefer:

```text
Business lunch
    → quiet table
    → fast service

Family dinner
    → large table
    → family area

Anniversary
    → private area
    → slower service
    → wine
```

Therefore preferences may have context.

Typical scopes include:

* Global
* Restaurant
* Branch
* Channel
* Service type
* Meal period
* Event type
* Companion group
* Seasonal

---

# 30. PREFERENCE SOURCE

Every preference shall preserve its source.

Sources may include:

```text
CUSTOMER_EXPLICIT

CUSTOMER_SELECTION

EMPLOYEE_RECORDED

POS_HISTORY

RESERVATION_HISTORY

ORDER_HISTORY

CONVERSATION_HISTORY

BEHAVIORAL_OBSERVATION

AI_INFERENCE

EXTERNAL_SYSTEM
```

Source is critical for determining authority and confidence.

---

# 31. EXPLICIT PREFERENCES

An explicit preference is directly communicated or selected by the customer.

Examples:

```text
"I prefer a table outside."

"I always drink sparkling water."

"Please don't recommend spicy food."
```

Explicit preferences normally have higher authority than behavioral inference.

---

# 32. OBSERVED PREFERENCES

Observed preferences are derived from repeated behavior.

Example:

```text
Last 8 visits:

7 × sparkling water
1 × still water
```

ECIP may create:

```text
Observed preference:
Sparkling water

Confidence:
HIGH
```

It shall remain classified as observed unless confirmed.

---

# 33. INFERRED PREFERENCES

AI may infer possible preferences from patterns.

Example:

```text
Observation:

Customer frequently orders seafood
and white wine.

Inference:

Possible preference for seafood + white wine pairing.
```

An inference shall preserve:

* Evidence
* Model or rule
* Confidence
* Generation time
* Expiration

Inference is not fact.

---

# 34. PREDICTED PREFERENCES

A prediction estimates what a customer may prefer in a future context.

Example:

```text
Customer historically orders:

Coffee after business lunches.

Prediction:

Coffee may be relevant after today's business lunch.
```

Predictions are temporary and context-dependent.

---

# 35. PREFERENCE CONFIDENCE

Suggested confidence model:

```text
CONFIRMED

HIGH

MEDIUM

LOW

UNKNOWN
```

Confidence shall be influenced by:

* Source authority
* Frequency
* Recency
* Consistency
* Explicit confirmation
* Contradictory evidence

---

# 36. PREFERENCE STRENGTH

Preference strength is different from confidence.

Example:

```text
Preference:
Spicy food

Confidence:
HIGH

Strength:
MODERATE
```

The system may be very confident that the customer moderately likes spicy food.

Suggested strength values:

```text
STRONGLY_DISLIKES

DISLIKES

NEUTRAL

LIKES

STRONGLY_LIKES
```

---

# 37. TEMPORAL VALIDITY

Preferences may change.

Examples:

* Temporary diet
* Seasonal preference
* Changed beverage preference
* New favorite product
* Changed seating preference

Every preference should support:

* First observed
* Last observed
* Last confirmed
* Effective from
* Effective until

ECIP shall not assume that old preferences remain permanently valid.

---

# 38. PREFERENCE CONFLICTS

Conflicting information may exist.

Example:

```text
2025:
Customer prefers indoor seating.

2026:
Customer explicitly requests outdoor seating.
```

Resolution should consider:

1. Safety
2. Explicit current request
3. Explicit recent preference
4. Verified historical preference
5. Observed behavior
6. AI inference

Conflicting evidence shall remain traceable.

---

# 39. NEGATIVE PREFERENCES

The model shall explicitly represent dislikes.

Examples:

* Does not like cilantro
* Avoids spicy food
* Does not want promotional calls
* Dislikes outdoor seating

Absence of a positive preference does not imply dislike.

---

# 40. PREFERENCE LEARNING

The platform may learn from:

* Orders
* Reservations
* Conversations
* Product modifications
* Repeated selections
* Rejected recommendations
* Accepted recommendations
* Compliments
* Complaints

Learning shall create evidence-backed observations or candidates.

It shall not silently create permanent facts.

---

# 41. PREFERENCE CANDIDATE

A `PreferenceCandidate` represents a possible preference detected by the platform.

Example:

```text
Candidate:

Customer may prefer Cabernet Sauvignon.

Evidence:

Selected Cabernet in 6 of last 8 wine orders.

Confidence:

HIGH
```

The candidate may subsequently become:

```text
Confirmed Preference
Observed Preference
Rejected Preference
Expired Candidate
```

---

# 42. CUSTOMER CORRECTION

Customers shall be able to correct preferences.

Example:

```text
ECIP:
"Would you like your usual sparkling water?"

Customer:
"No, I prefer still water now."
```

The platform should:

1. Respect the current request immediately.
2. Record the correction.
3. Reevaluate the previous preference.
4. Preserve appropriate historical provenance.
5. Use the new information in future interactions.

---

# 43. RECOMMENDATION USE

Preferences may influence:

* Product recommendations
* Beverage pairing
* Dessert recommendations
* Menu personalization
* Seating recommendations
* Reservation times
* Branch recommendations
* Promotions
* Event recommendations
* Service style

Recommendation engines shall preserve the reason for the recommendation.

---

# 44. SALES INTELLIGENCE

Preferences enable intelligent cross-selling and upselling.

Example:

```text
Known:

Customer likes grilled seafood.

Known:

Customer prefers dry white wine.

Current order:

Grilled sea bass.

Recommendation:

Relevant dry white wine pairing.
```

This is preferable to random upselling.

---

# 45. RECOMMENDATION REJECTION

Rejected recommendations provide useful evidence.

Example:

```text
Recommendation:
Chocolate dessert

Customer:
"No, I don't like chocolate."
```

This may generate an explicit negative preference.

A simple rejection without explanation shall not automatically create a dislike.

---

# 46. HUMAN COLLABORATION

Relevant preferences shall be available to authorized employees when useful.

Example handoff:

```text
Customer:
Returning customer

Language:
English

Known preference:
Quiet seating

Dietary restriction:
Vegetarian

Current request:
Anniversary reservation

Suggested action:
Offer quiet terrace table if available
```

Employees should not need to rediscover information already known by ECIP.

---

# 47. PRIVACY AND CONSENT

Preferences may contain personal information.

The platform shall apply:

* Purpose limitation
* Access control
* Data minimization
* Retention policy
* Consent policy
* Correction mechanisms
* Deletion mechanisms
* Auditability

Not everything learned during a conversation should become permanent memory.

---

# 48. SENSITIVE PREFERENCES

Some preference-related information may reveal sensitive information.

Such information shall receive appropriate classification and shall not be collected merely because it may improve personalization.

The system should store the minimum information necessary to provide the intended service safely.

---

# 49. PREFERENCE EVENTS

Initial domain events include:

```text
CustomerPreferenceRecorded

CustomerPreferenceConfirmed

CustomerPreferenceUpdated

CustomerPreferenceCorrected

CustomerPreferenceRevoked

CustomerPreferenceExpired

PreferenceCandidateDetected

PreferenceCandidateConfirmed

PreferenceCandidateRejected

DietaryPreferenceRecorded

DietaryRestrictionRecorded

AllergyRecorded

AllergyConfirmed

AllergyUpdated

AllergyRemoved

SeatingPreferenceRecorded

ServicePreferenceRecorded

CommunicationPreferenceChanged

RecommendationAccepted

RecommendationRejected
```

---

# 50. RELATIONSHIPS

```text
Customer

    HAS CustomerPreference

CustomerPreference

    EXTENDS Preference

Customer

    HAS DietaryPreference

Customer

    MAY_HAVE DietaryRestriction

Customer

    MAY_HAVE CustomerAllergy

CustomerPreference

    SUPPORTED_BY PreferenceEvidence

CustomerPreference

    MAY_ORIGINATE_FROM PreferenceCandidate

CustomerPreference

    APPLIES_TO PreferenceContext

CustomerPreference

    INFLUENCES Recommendation

CustomerAllergy

    CONSTRAINS Recommendation

CustomerAllergy

    CONSTRAINS OrderCustomization

CommunicationPreference

    SUBJECT_TO Consent
```

---

# 51. BUSINESS RULES

The following rules apply:

1. Preferences shall preserve provenance.

2. Explicit customer information takes precedence over inferred preference when equally safe and currently applicable.

3. Current customer requests may override ordinary historical preferences.

4. Safety constraints shall override personalization.

5. Allergies shall never be inferred solely from purchasing behavior.

6. Dietary preferences shall not automatically be interpreted as medical restrictions.

7. AI-generated preferences shall remain classified as inferred until sufficient evidence or confirmation exists.

8. Preference confidence and preference strength are separate concepts.

9. Preferences shall support temporal validity.

10. Contradictory evidence shall not be silently discarded.

11. Marketing consent and promotional preference are separate concepts.

12. Payment credentials shall never be stored as ordinary preferences.

13. Customer corrections shall affect future reasoning.

14. Sensitive information shall only be retained when authorized and necessary.

15. Commercial optimization shall never override safety, consent or explicit customer constraints.

---

# 52. RELATIONSHIP WITH CUSTOMER PROFILE

`05_Customer_Profile.md` defines the overall customer representation.

This document defines the detailed preference subsystem within that profile.

Conceptually:

```text
Customer Profile

├── Identity
├── Relationships
├── History
├── Loyalty
├── Value
│
└── Preferences
    │
    ├── Food
    ├── Beverage
    ├── Dietary
    ├── Seating
    ├── Service
    ├── Delivery
    ├── Communication
    └── Contextual Preferences
```

The Customer Profile references preferences.

It shall not duplicate them.

---

# 53. RELATIONSHIP WITH CUSTOMER MEMORY

Preferences and memory are related but not equivalent.

```text
Observation

      ↓

Preference Candidate

      ↓

Governance / Validation

      ↓

Customer Preference

      ↓

Customer Memory
```

A preference may be retained through Customer Memory when permitted.

The memory system determines persistence and retention.

---

# 54. RELATIONSHIP WITH MENU INTELLIGENCE

The Menu and Product models shall expose information required to evaluate customer preferences.

Examples:

```text
Product

HAS Ingredient

Product

HAS Allergen

Product

HAS DietaryAttribute

Product

HAS FlavorProfile

Product

SUPPORTS Modification
```

This allows ECIP to match:

```text
Customer Preferences
        +
Menu Knowledge
        +
Operational Availability
        +
Current Context
        ↓
Relevant Recommendation
```

---

# 55. RELATIONSHIP WITH OPERATIONAL CONTEXT

A preference does not guarantee feasibility.

Example:

```text
Customer preference:
Terrace

Operational Context:
Terrace closed because of weather

Result:
Do not promise terrace seating.

Recommended response:
Explain availability and offer the closest suitable alternative.
```

ECIP shall always combine preference with current operational context.

---

# 56. RELATIONSHIP WITH SALES INTELLIGENCE

Customer preferences provide personalization signals for:

* Cross-selling
* Upselling
* Dynamic bundles
* Personalized promotions
* Menu recommendations
* Beverage pairing
* Dessert recommendations
* Event recommendations

Sales Intelligence shall not directly mutate customer preferences.

It consumes governed preference information.

---

# 57. RELATIONSHIP WITH CONVERSATIONAL INTELLIGENCE

During a conversation, ECIP may use preferences to:

* Reduce repeated questions.
* Personalize language.
* Anticipate likely needs.
* Suggest relevant products.
* Detect conflicts.
* Ask useful clarification questions.
* Provide better alternatives.

Example:

```text
Customer:
"I'd like to make a reservation for Saturday."

ECIP knows:

- Usually reserves for four people.
- Prefers quiet seating.
- Usually visits the downtown branch.

ECIP may ask:

"Certainly. Would you like the downtown location and a quiet table for four, as on your previous visits?"
```

Historical information is used to reduce friction, not to make irreversible assumptions.

---

# 58. ANALYTICAL USE

Aggregated preference information may reveal:

* Emerging food trends.
* Growing dietary demand.
* Popular flavor profiles.
* Beverage trends.
* Seating demand.
* Service expectations.
* Unmet menu opportunities.
* Regional preference differences.

Analytics shall use appropriate privacy protections and tenant policies.

---

# 59. IMPLEMENTATION PRIORITY

For the first production release, prioritize:

```text
CustomerPreference

PreferenceCategory

PreferenceEvidence

DietaryPreference

DietaryRestriction

CustomerAllergy

SeatingPreference

ServicePreference

CommunicationPreference

PreferenceCandidate
```

Advanced predictive preference modeling may be introduced after reliable evidence and feedback loops exist.

---

# 60. IMPLEMENTATION PRINCIPLE

This document defines the logical Restaurant Customer Preferences Model.

It does not prescribe:

* Database schema.
* Recommendation algorithm.
* Machine learning model.
* Vector database.
* CRM implementation.
* Loyalty implementation.
* User interface.
* LLM provider.

Implementation shall preserve the semantic separation between:

```text
FACT

EXPLICIT PREFERENCE

OBSERVED BEHAVIOR

INFERENCE

PREDICTION

SAFETY CONSTRAINT
```

This distinction is mandatory for trustworthy Restaurant Intelligence.

---

# 61. FINAL RULE

Customer personalization shall never be based merely on what ECIP thinks it knows.

Every preference used by the platform shall have sufficient context to answer:

> What does the customer prefer?

> How do we know?

> How confident are we?

> Is it still valid?

> In what context does it apply?

> Are we authorized to use it?

> Does any safety or operational constraint override it?

Only then may the preference influence a recommendation, decision or action.

