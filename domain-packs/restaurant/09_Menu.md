# 09_Menu.md

**Document ID:** RDM-009
**Document Name:** Menu
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Menu Model for the Restaurant Intelligence Platform.

Its purpose is to represent how restaurant offerings are organized, published, versioned, scheduled and made available across branches, channels and service contexts.

The Menu Model provides the commercial and operational structure through which products are presented to customers.

The menu is not merely a visual list.

It is a governed business structure that determines:

* What can be offered.
* Where it can be offered.
* When it can be offered.
* Through which channel it can be offered.
* Under which conditions it can be offered.
* Which prices and promotions apply.
* Which products are currently available.

---

# 2. OBJECTIVES

The Menu Model enables ECIP to:

* Understand all available menus.
* Identify the correct menu for a customer context.
* Support multiple branches.
* Support multiple service types.
* Support multiple channels.
* Support multiple languages.
* Support time-based menus.
* Support seasonal menus.
* Support promotional menus.
* Support menu versioning.
* Support product availability.
* Support dynamic operational restrictions.
* Support personalized recommendations.
* Support conversational menu navigation.
* Preserve historical menu context.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Knowledge Item
* Knowledge Fact
* Policy
* Context Snapshot
* Recommendation
* Action
* Location
* Organization
* Channel

Restaurant-specific menu concepts remain within the Restaurant Domain Pack.

This document does not redefine canonical knowledge or context entities.

---

# 4. MENU PRINCIPLE

A menu represents a governed commercial offering.

The platform shall distinguish between:

```text
Menu Structure

Product Catalog

Pricing

Promotion

Availability

Operational Feasibility

Customer Preference
```

These concepts are related but not equivalent.

Example:

```text
Menu:
Dinner Menu

Product:
Grilled Salmon

Price:
$320

Promotion:
10% discount after 8 PM

Availability:
Currently available

Operational context:
Kitchen station saturated

Customer preference:
Likes grilled seafood
```

ECIP shall combine these elements before making a recommendation or promise.

---

# 5. MENU

A `Menu` represents a defined collection of offerings presented under specific business conditions.

Typical attributes include:

* Menu ID
* Name
* Description
* Brand
* Restaurant
* Branch scope
* Service type
* Channel scope
* Language
* Currency
* Effective date
* Expiration date
* Schedule
* Version
* Priority
* Status

Suggested status values:

```text
DRAFT
SCHEDULED
ACTIVE
SUSPENDED
EXPIRED
ARCHIVED
```

---

# 6. MENU TYPES

Examples:

* Breakfast Menu
* Lunch Menu
* Dinner Menu
* All-Day Menu
* Bar Menu
* Dessert Menu
* Beverage Menu
* Kids Menu
* Delivery Menu
* Take Away Menu
* Room Service Menu
* Catering Menu
* Banquet Menu
* Buffet Menu
* Seasonal Menu
* Holiday Menu
* Promotional Menu
* Corporate Menu

A restaurant may operate multiple menus simultaneously.

---

# 7. MENU SCOPE

A menu may apply at different scopes.

Examples:

```text
Restaurant Group

Brand

Restaurant

Branch

Dining Area

Service Type

Channel

Customer Segment

Event
```

The most specific applicable menu shall take precedence according to business policy.

---

# 8. MENU VERSION

A `MenuVersion` represents a specific immutable business version of a menu.

Typical attributes:

* Menu ID
* Version number
* Effective from
* Effective until
* Publication date
* Status
* Created by
* Approved by
* Change reason

Historical transactions shall reference the applicable menu version.

Current menu changes shall not rewrite historical transactions.

---

# 9. MENU VERSIONING PRINCIPLE

Menu changes may include:

* Adding products
* Removing products
* Changing categories
* Changing descriptions
* Changing availability
* Changing pricing references
* Changing schedules
* Changing channel eligibility

These changes shall be traceable.

---

# 10. MENU SECTION

A `MenuSection` organizes menu content.

Examples:

* Appetizers
* Soups
* Salads
* Main Courses
* Pasta
* Seafood
* Steaks
* Desserts
* Beverages
* Wines
* Cocktails
* Kids

Typical attributes:

* Section ID
* Menu
* Name
* Description
* Display order
* Parent section
* Availability
* Status

Sections may be hierarchical.

---

# 11. MENU ITEM

A `MenuItem` represents the placement of a Product within a Menu.

A Product and a Menu Item are not the same entity.

Example:

```text
Product:
Grilled Salmon

Menu Item A:
Dinner Menu → Seafood

Menu Item B:
Delivery Menu → Main Courses

Menu Item C:
Corporate Menu → Healthy Options
```

Each placement may have different:

* Description
* Display name
* Image
* Price reference
* Availability
* Ordering rules
* Presentation

---

# 12. MENU ITEM ATTRIBUTES

Typical attributes:

* Menu Item ID
* Product ID
* Menu ID
* Menu Section
* Display name
* Description
* Display order
* Price reference
* Image
* Availability
* Recommended flag
* Featured flag
* New flag
* Seasonal flag
* Visibility
* Channel restrictions

---

# 13. PRODUCT REFERENCE

The Menu Model references products defined in:

`10_Product_Catalog.md`

The Menu Model shall not redefine product composition or product identity.

Conceptually:

```text
Menu

    CONTAINS MenuItem

MenuItem

    REFERENCES Product
```

---

# 14. MENU HIERARCHY

Example:

```text
Dinner Menu

├── Appetizers
│   ├── Calamari
│   ├── Bruschetta
│   └── Soup
│
├── Main Courses
│   ├── Steak
│   ├── Salmon
│   └── Pasta
│
├── Desserts
│   ├── Cheesecake
│   └── Tiramisu
│
└── Beverages
    ├── Wine
    ├── Coffee
    └── Soft Drinks
```

The hierarchy supports customer navigation and conversational reasoning.

---

# 15. MENU SCHEDULE

A menu may be available according to schedule.

Examples:

```text
Breakfast:
06:00–11:00

Lunch:
12:00–16:00

Dinner:
17:00–23:00
```

Schedules may depend on:

* Day of week
* Branch
* Holiday
* Event
* Service channel

---

# 16. MENU EFFECTIVE PERIOD

Menus may have temporal validity.

Examples:

* Christmas Menu
* Summer Menu
* Mother's Day Menu
* Valentine's Menu
* Limited-time promotion

Typical attributes:

* Effective from
* Effective until
* Timezone
* Recurrence rules

---

# 17. MENU AVAILABILITY

Menu availability represents whether a menu may currently be used.

Availability may depend on:

* Schedule
* Branch status
* Channel
* Service type
* Holiday
* Event
* Operational condition
* Business policy

---

# 18. MENU ITEM AVAILABILITY

A menu may be active while individual products are unavailable.

Examples:

```text
Dinner Menu:
ACTIVE

Grilled Salmon:
UNAVAILABLE

Steak:
AVAILABLE
```

ECIP shall never assume that an active menu means every menu item is available.

---

# 19. AVAILABILITY STATES

Suggested menu item states:

```text
AVAILABLE

LOW_AVAILABILITY

TEMPORARILY_UNAVAILABLE

SOLD_OUT

SCHEDULED

DISCONTINUED

RESTRICTED
```

Availability may change in real time.

---

# 20. AVAILABILITY SOURCE

Availability may originate from:

* POS
* Inventory system
* Kitchen system
* Employee
* Recipe availability
* Equipment status
* Business policy
* ECIP operational intelligence

Every availability state shall preserve its source.

---

# 21. INVENTORY-DRIVEN AVAILABILITY

Product availability may depend on ingredient availability.

Example:

```text
Product:
Seafood Pasta

Requires:
Shrimp
Pasta
Cream

Shrimp unavailable

Result:
Product may become unavailable
```

The final availability rule belongs to Product and Recipe domains.

---

# 22. KITCHEN-DRIVEN AVAILABILITY

A product may be technically possible but operationally constrained.

Example:

```text
Pizza oven:
Out of service

Products requiring pizza oven:
Operationally unavailable
```

ECIP shall consider this before confirming an order.

---

# 23. SERVICE-TYPE AVAILABILITY

Products may differ by service type.

Example:

```text
Dine-in:
Soufflé available

Delivery:
Soufflé unavailable
```

Possible service scopes:

* Dine In
* Take Away
* Delivery
* Drive Through
* Catering
* Banquet
* Buffet

---

# 24. CHANNEL-SPECIFIC MENU

Different channels may expose different menus.

Examples:

* Web Menu
* Telephone Menu
* Delivery Platform Menu
* Kiosk Menu
* Mobile App Menu

The underlying Product Catalog remains shared.

---

# 25. MULTI-CHANNEL CONSISTENCY

ECIP shall preserve semantic consistency across channels.

A product shall not accidentally become a different business entity simply because it appears through another channel.

Provider-specific identifiers remain integration concerns.

---

# 26. BRANCH-SPECIFIC MENUS

Branches may have different offerings.

Example:

```text
Downtown branch:
Full seafood menu

Airport branch:
Reduced express menu
```

Branch-specific configuration may affect:

* Products
* Prices
* Availability
* Schedules
* Promotions

---

# 27. MULTI-BRAND MENU SUPPORT

A physical location may operate multiple brands.

Each brand may expose independent menus while sharing:

* Kitchen
* Ingredients
* Inventory
* Employees
* Equipment

The model shall preserve brand ownership.

---

# 28. MENU LANGUAGE

Menus may support multiple languages.

Example:

```text
Menu:
Dinner

Languages:
Spanish
English
French
```

Localized fields may include:

* Name
* Description
* Ingredient descriptions
* Warnings
* Category names

---

# 29. MENU LOCALIZATION

Localization may additionally include:

* Currency
* Tax presentation
* Portion terminology
* Regional terminology
* Measurement units
* Legal disclosures

Localization shall not create independent products unnecessarily.

---

# 30. MENU DESCRIPTION

Descriptions may include:

* Product characteristics
* Preparation
* Main ingredients
* Portion guidance
* Flavor profile
* Accompaniments

Descriptions should accurately reflect authoritative product and recipe information.

---

# 31. CUSTOMER-FACING DESCRIPTION

A customer-facing description may differ from an internal operational description.

Example:

```text
Customer:
"Grilled salmon with herb butter and seasonal vegetables."

Kitchen:
"SALMON 220G / MEDIUM / HERB BUTTER / VEG MIX"
```

These representations shall remain linked to the same product.

---

# 32. MENU IMAGES

Menu items may reference:

* Product image
* Alternate image
* Channel-specific image

Image metadata may include:

* Asset ID
* Version
* Alt text
* Usage rights
* Status

Images remain content assets rather than core product identity.

---

# 33. MENU TAGS

Menu items may expose governed tags.

Examples:

* Popular
* Chef Recommended
* New
* Seasonal
* Vegetarian
* Vegan
* Gluten-Free
* Spicy
* Premium

Tags shall derive from authoritative information whenever they imply dietary or safety characteristics.

---

# 34. DIETARY ATTRIBUTES

Menu items may reference dietary attributes defined by Product and Recipe knowledge.

Examples:

* Vegetarian
* Vegan
* Contains gluten
* Gluten-free according to policy
* Contains nuts
* Dairy-free

Safety-related claims shall be governed carefully.

---

# 35. ALLERGEN DISCLOSURE

Menu presentation may include known allergen information.

The Product and Recipe domains remain authoritative for allergen composition.

ECIP shall not invent allergen claims.

---

# 36. MENU ITEM MODIFIERS

Menu items may expose allowed modifications.

Examples:

* Cooking temperature
* Side selection
* Sauce selection
* Extra ingredients
* Remove ingredients
* Size selection

Modifier definitions belong primarily to Product Catalog.

The Menu determines whether they are exposed in a given context.

---

# 37. MENU ITEM ORDERING RULES

Examples:

* Maximum quantity
* Minimum quantity
* Requires modifier
* Requires age verification
* Requires advance notice
* Dine-in only
* Cannot be delivered

ECIP shall evaluate these rules before accepting an order.

---

# 38. MENU ITEM VISIBILITY

A product may exist in the catalog without being visible.

Possible states:

```text
VISIBLE

HIDDEN

INTERNAL_ONLY

EMPLOYEE_ONLY

INVITATION_ONLY
```

Visibility and availability are different concepts.

---

# 39. FEATURED ITEMS

A menu may feature products based on:

* Business strategy
* Seasonal campaign
* Chef recommendation
* Customer context
* Inventory strategy
* Marketing campaign

Featured status shall not imply personalized recommendation.

---

# 40. MENU RECOMMENDATIONS

Conversational intelligence may navigate the menu by meaning rather than only categories.

Example:

```text
Customer:
"What do you have that's light and not spicy?"
```

ECIP should combine:

```text
Menu
+
Product attributes
+
Recipe knowledge
+
Customer preferences
+
Operational availability
```

to produce relevant options.

---

# 41. CONTEXTUAL MENU

A `ContextualMenu` represents a dynamically filtered view of one or more authoritative menus.

It may consider:

* Branch
* Time
* Channel
* Service type
* Customer
* Preferences
* Allergies
* Operational availability
* Promotion eligibility

A ContextualMenu is a projection.

It does not replace the authoritative Menu.

---

# 42. PERSONALIZED MENU

A personalized menu may reorder or highlight available products for a customer.

Example:

```text
Customer:
Vegetarian

Context:
Lunch

Result:
Vegetarian lunch-compatible products highlighted first
```

Personalization shall not hide necessary information or misrepresent availability.

---

# 43. MENU SEARCH

ECIP shall support semantic queries such as:

```text
"Do you have something with chicken?"

"What desserts don't have chocolate?"

"What can I order for four people?"

"What can arrive in less than 30 minutes?"

"What vegetarian dishes do you have?"
```

Search results shall use current menu and operational context.

---

# 44. MENU KNOWLEDGE

Menu information shall be accessible as governed enterprise knowledge.

The platform should understand relationships such as:

```text
Menu Item

REFERENCES Product

Product

HAS Recipe

Recipe

USES Ingredient

Product

HAS Dietary Attribute

Product

MAY_HAVE Modifier
```

This enables contextual reasoning.

---

# 45. MENU PRICING

Pricing is defined in:

`12_Pricing_and_Promotions.md`

The Menu may reference the applicable price.

The Menu shall not become the authoritative pricing engine.

---

# 46. MENU PROMOTIONS

Promotions may affect items displayed in a menu.

Examples:

* Happy Hour
* Combo
* Seasonal promotion
* Customer-specific promotion

Promotion eligibility shall be evaluated separately.

---

# 47. MENU BUNDLES

Menus may expose:

* Combos
* Packages
* Bundles
* Meal deals

Product composition and pricing belong to their respective domain models.

---

# 48. MENU AND LOYALTY

Loyalty may influence:

* Visible benefits
* Member-exclusive products
* Reward eligibility
* Personalized recommendations

Customer tier shall not alter base product semantics.

---

# 49. MENU AND CUSTOMER PREFERENCES

Customer Preferences may influence menu ranking.

Example:

```text
Customer:
Strongly likes seafood

Menu:
20 available main courses

Result:
Relevant seafood options may be ranked higher
```

Preferences do not change the actual menu.

---

# 50. MENU AND ALLERGIES

Allergies may constrain menu recommendations.

Example:

```text
Customer allergy:
Shellfish

Menu item:
Seafood pasta contains shrimp

Result:
Do not recommend as suitable
```

The platform may still display the product when appropriate, but it shall not represent it as safe for that customer.

---

# 51. MENU AND CUSTOMER HISTORY

History may support:

* Reorder suggestions
* Product familiarity
* Previously accepted modifiers
* Previously rejected recommendations

Example:

```text
"You ordered the grilled salmon on your last three visits. Would you like it again?"
```

Current availability shall always be checked.

---

# 52. MENU AND SALES INTELLIGENCE

Sales Intelligence may use Menu data for:

* Cross-selling
* Upselling
* Product affinity
* Margin-aware recommendation
* Seasonal suggestions
* Dynamic bundle generation

The Menu domain remains authoritative for what can be offered.

---

# 53. MENU AND INVENTORY

Inventory influences current offerability.

Possible logic:

```text
Menu Item
    ↓
Product
    ↓
Recipe
    ↓
Ingredients
    ↓
Inventory Availability
    ↓
Offerability
```

This relationship may be real-time.

---

# 54. MENU AND KITCHEN

Kitchen capacity may influence:

* Estimated preparation time
* Temporary availability
* Recommendation ranking

Example:

```text
Product A:
Available
Preparation time: 35 min

Product B:
Available
Preparation time: 10 min

Customer:
Needs quick lunch
```

ECIP may prioritize Product B.

---

# 55. MENU AND DELIVERY

Delivery Menu may exclude products based on:

* Packaging suitability
* Distance
* Preparation stability
* Delivery time
* Food quality constraints

This shall be explicitly governed.

---

# 56. MENU AND EVENTS

Special events may activate dedicated menus.

Examples:

* Wedding
* Corporate banquet
* Mother's Day
* New Year's Eve

Event menus may require:

* Deposit
* Minimum party size
* Preselection
* Advance booking

---

# 57. MENU AND BUFFET

Buffet menus may represent:

* Buffet concept
* Included items
* Rotation schedule
* Price
* Service period
* Restrictions

Buffet operations shall be modeled explicitly where required.

---

# 58. MENU AND PACKAGES

Restaurant packages may combine:

* Food
* Beverage
* Service
* Event resources
* Reservation capacity

The Menu may expose the package as a commercial offering.

---

# 59. MENU AVAILABILITY RESOLUTION

The final availability of a menu item may depend on multiple conditions.

Conceptually:

```text
Menu Active
+
Item Visible
+
Product Active
+
Schedule Valid
+
Branch Eligible
+
Channel Eligible
+
Inventory Sufficient
+
Required Equipment Operational
+
Business Policy Allows
=
Potentially Offerable
```

Additional customer-specific constraints may further restrict recommendations.

---

# 60. OFFERABILITY

`Offerability` represents whether a product may currently be offered in a specific context.

Typical output:

```text
OFFERABLE

OFFERABLE_WITH_CONDITIONS

TEMPORARILY_UNAVAILABLE

NOT_AVAILABLE_IN_CONTEXT

PROHIBITED
```

Offerability is context-dependent.

---

# 61. MENU RESOLUTION

When multiple menus apply, ECIP shall resolve the appropriate menu context.

Example:

```text
Branch:
Downtown

Time:
19:30

Channel:
WhatsApp

Service:
Delivery
```

Applicable result may be:

```text
Downtown Delivery Dinner Menu
Version 17
```

---

# 62. MENU PRIORITY

Where multiple menus overlap, business rules may define priority.

Example:

```text
Private Event Menu

overrides

Holiday Menu

overrides

Service-Specific Menu

overrides

Standard Menu
```

Priority rules shall be explicit and configurable.

---

# 63. MENU FALLBACK

If no specialized menu applies, the platform may fall back to an authorized default menu.

Fallback shall never expose products that are unavailable for the requested service context.

---

# 64. MENU PUBLICATION

Suggested lifecycle:

```text
Draft
    ↓
Review
    ↓
Approved
    ↓
Scheduled
    ↓
Published
    ↓
Active
    ↓
Archived
```

Publication workflow may vary by restaurant.

---

# 65. MENU APPROVAL

Significant menu changes may require approval according to business policy.

Examples:

* Price-impacting publication
* Allergen claim
* New alcoholic product
* Corporate menu
* Brand-wide menu

---

# 66. MENU CHANGE HISTORY

Changes shall preserve:

* Actor
* Timestamp
* Previous version
* New version
* Reason
* Approval
* Effective time

This enables audit and historical reconstruction.

---

# 67. MENU IMPORT

Menus may originate from:

* POS
* ERP
* Existing menu database
* File import
* External delivery platform

Imported menu data shall map to the canonical Restaurant Domain Model.

External provider structures shall not become the internal canonical model.

---

# 68. MENU SYNCHRONIZATION

When an external POS is authoritative, ECIP may synchronize:

* Menus
* Menu sections
* Product mappings
* Availability
* Channel visibility

Synchronization shall preserve:

* Source
* External identifier
* Timestamp
* Sync status
* Conflict state

---

# 69. MENU CONFLICT

A conflict may occur when:

* ECIP and POS disagree
* Two external systems provide different prices
* Product is active in one system and inactive in another
* Channel availability differs

Conflict resolution shall follow source-of-truth rules.

---

# 70. MENU SOURCE OF TRUTH

The authoritative source may vary by restaurant deployment.

Examples:

```text
POS:
Product activation and price

ECIP:
Conversation-specific menu presentation

Inventory:
Stock availability

Kitchen:
Operational feasibility
```

Ownership shall be explicitly configured.

---

# 71. MENU EVENTS

Initial domain events include:

```text
MenuCreated
MenuUpdated
MenuApproved
MenuScheduled
MenuActivated
MenuSuspended
MenuExpired
MenuArchived

MenuVersionCreated
MenuVersionPublished

MenuSectionCreated
MenuSectionUpdated
MenuSectionRemoved

MenuItemAdded
MenuItemUpdated
MenuItemRemoved
MenuItemVisibilityChanged
MenuItemAvailabilityChanged

MenuScheduleChanged

ContextualMenuGenerated

MenuSynchronizationStarted
MenuSynchronizationCompleted
MenuSynchronizationFailed
MenuConflictDetected
MenuConflictResolved
```

---

# 72. RELATIONSHIPS

```text
Restaurant
    HAS Menu

Branch
    OFFERS Menu

Menu
    HAS MenuVersion

Menu
    CONTAINS MenuSection

MenuSection
    CONTAINS MenuItem

MenuItem
    REFERENCES Product

Menu
    APPLIES_TO ServiceType

Menu
    MAY_APPLY_TO Channel

Menu
    HAS Schedule

MenuItem
    MAY_REFERENCE Price

MenuItem
    MAY_BE_AFFECTED_BY Promotion

MenuItem
    HAS Availability

MenuVersion
    PRESERVES HistoricalMenuState

ContextualMenu
    DERIVED_FROM Menu

CustomerPreference
    MAY_INFLUENCE ContextualMenu

CustomerAllergy
    MAY_CONSTRAIN Recommendation

OperationalContext
    MAY_CONSTRAIN Offerability
```

---

# 73. BUSINESS RULES

The following rules apply:

1. A Menu represents an offering structure, not a Product Catalog.

2. A Product may appear in multiple menus.

3. A Menu Item references exactly one canonical restaurant Product.

4. Menu version history shall remain traceable.

5. Current menu changes shall not rewrite historical transactions.

6. Menu visibility and product availability are separate concepts.

7. An active menu does not imply every menu item is available.

8. Menu availability shall consider time, branch, service type and channel.

9. Customer-specific personalization shall not modify authoritative menu content.

10. Known allergies and safety constraints shall override commercial recommendation logic.

11. ECIP shall verify current offerability before confirming a product.

12. Provider-specific menu identifiers shall remain behind integration mappings.

13. Menu descriptions shall not contradict authoritative Product or Recipe information.

14. Price authority shall remain with the Pricing domain or configured source system.

15. Operational constraints may temporarily prevent an otherwise valid menu item from being offered.

16. Menu history shall preserve sufficient information for audit and customer dispute resolution.

---

# 74. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Menu

MenuVersion

MenuSection

MenuItem

MenuSchedule

MenuScope

MenuItemAvailability

MenuItemVisibility

ServiceTypeEligibility

ChannelEligibility

BranchEligibility

Offerability

ExternalMenuMapping
```

The following may be introduced later when commercially required:

```text
Advanced Contextual Menu Ranking

Fully Personalized Menu Ordering

Advanced Semantic Menu Discovery

Multi-Brand Menu Optimization

Autonomous Menu Composition

Dynamic Menu Simulation
```

---

# 75. IMPLEMENTATION PRINCIPLE

This document defines the logical Menu Model.

It does not prescribe:

* Database schema.
* POS implementation.
* Frontend menu layout.
* Mobile menu implementation.
* Search engine.
* Recommendation algorithm.
* Pricing engine.
* Inventory algorithm.
* Kitchen scheduling algorithm.

Implementation shall preserve the semantic separation between:

```text
MENU

PRODUCT

PRICE

PROMOTION

AVAILABILITY

OFFERABILITY

RECOMMENDATION
```

---

# 76. FINAL RULE

Before ECIP offers or recommends any restaurant item, it shall be able to determine:

> Which menu applies?

> Which menu version is currently valid?

> Is the product actually part of that menu?

> Is it visible through this channel?

> Is it allowed for this service type?

> Is it available at this branch?

> Is it operationally feasible right now?

> Is it compatible with known customer constraints?

> What authoritative price and promotion apply?

Only after these conditions are resolved may the platform represent the item as currently offerable.

