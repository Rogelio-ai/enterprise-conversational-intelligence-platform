# 10_Product_Catalog.md

**Document ID:** RDM-010
**Document Name:** Product Catalog
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Product Catalog Model for the Restaurant Intelligence Platform.

Its purpose is to represent the complete set of commercial products that a restaurant can sell, serve, include in packages, recommend, modify, prepare, deliver or associate with promotions.

The Product Catalog is the authoritative restaurant-domain representation of product identity and product structure.

It is independent from:

* Menu placement.
* Current price.
* Promotion.
* Current availability.
* Inventory balance.
* Customer recommendation.
* Sales channel.

A Product may exist even when it is not currently visible, priced, available or published in a menu.

---

# 2. OBJECTIVES

The Product Catalog Model enables ECIP to:

* Understand what the restaurant sells.
* Distinguish products from menu items.
* Support product categories and hierarchies.
* Support variants.
* Support sizes and presentations.
* Support modifiers and customization.
* Support product bundles and packages.
* Support products across multiple menus.
* Support multiple branches and brands.
* Support multiple sales channels.
* Support recipe linkage.
* Support nutritional and dietary knowledge.
* Support allergen knowledge.
* Support operational availability.
* Support Sales Intelligence.
* Support customer-specific recommendations.
* Preserve product history and external mappings.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Knowledge Item
* Knowledge Fact
* Policy
* Recommendation
* Action
* Context Snapshot
* External Entity Reference
* Mapping Definition

Restaurant-specific Product entities remain within the Restaurant Domain Pack.

This document does not redefine canonical knowledge or external-system mapping.

---

# 4. PRODUCT PRINCIPLE

A Product represents **what the restaurant offers as a sellable or serviceable business concept**.

The platform shall distinguish between:

```text
Product
Menu Item
Recipe
Ingredient
Price
Promotion
Inventory Item
Availability
Recommendation
```

These concepts shall never be collapsed into one entity.

---

# 5. PRODUCT

A `Product` represents a canonical restaurant offering.

Typical attributes include:

* Product ID
* Name
* Internal name
* Description
* Product type
* Category
* Brand
* Restaurant scope
* Status
* Unit of sale
* Default portion
* Preparation requirement
* Recipe reference
* Tax classification reference
* Dietary attributes
* Allergen attributes
* Service eligibility
* Channel eligibility
* Images
* Tags
* Version
* Effective dates

---

# 6. PRODUCT STATUS

Suggested states:

```text
DRAFT
ACTIVE
SUSPENDED
DISCONTINUED
ARCHIVED
```

Status represents lifecycle.

Status is not the same as current availability.

An active product may still be temporarily unavailable.

---

# 7. PRODUCT TYPES

Examples include:

* Prepared Food
* Beverage
* Alcoholic Beverage
* Dessert
* Ingredient-Based Add-On
* Side Dish
* Modifier
* Combo
* Package
* Buffet Offering
* Catering Item
* Banquet Package
* Service Chargeable Item
* Retail Product
* Gift Card
* Membership Product

Additional types may be introduced when needed.

---

# 8. PRODUCT CATEGORY

A `ProductCategory` classifies products.

Examples:

* Appetizers
* Soups
* Salads
* Seafood
* Beef
* Poultry
* Pasta
* Pizza
* Desserts
* Coffee
* Wine
* Beer
* Cocktails
* Soft Drinks

Categories may be hierarchical.

---

# 9. CATEGORY HIERARCHY

Example:

```text
Beverages

├── Non-Alcoholic
│   ├── Coffee
│   ├── Tea
│   ├── Juice
│   └── Soft Drinks
│
└── Alcoholic
    ├── Wine
    ├── Beer
    └── Cocktails
```

Category hierarchy supports:

* Search.
* Analytics.
* Menu organization.
* Recommendation.
* Reporting.

---

# 10. PRODUCT VARIANT

A `ProductVariant` represents a commercial variation of a Product.

Examples:

```text
Pizza
    ├── Small
    ├── Medium
    └── Large
```

or:

```text
Coffee
    ├── Hot
    └── Iced
```

Typical attributes:

* Variant ID
* Product ID
* Variant name
* SKU
* Size
* Presentation
* Recipe adjustment
* Price reference
* Status

---

# 11. SIZE

A `ProductSize` represents a size option.

Examples:

* Small
* Medium
* Large
* Individual
* Family
* 250 ml
* 500 ml
* 1 liter

Size may influence:

* Recipe quantity.
* Price.
* Inventory consumption.
* Packaging.
* Nutrition.

---

# 12. PRESENTATION

A `ProductPresentation` represents how a Product is served or sold.

Examples:

* Plate
* Bowl
* Glass
* Bottle
* Cup
* Box
* Slice
* Piece
* Tray
* Family Pack

Presentation is distinct from Product identity.

---

# 13. SKU

A Product or Product Variant may have a SKU.

Typical attributes:

* SKU
* Barcode
* Internal code
* External POS code
* Supplier code

Canonical Product ID remains authoritative inside ECIP.

External codes are mappings.

---

# 14. PRODUCT DESCRIPTION

A Product may have multiple descriptions:

* Internal description
* Customer-facing description
* Operational description
* Marketing description

These may differ while referencing the same Product.

---

# 15. LOCALIZED PRODUCT CONTENT

Product content may support:

* Multiple languages
* Regional descriptions
* Local terminology
* Measurement units

Localization shall not create duplicate products unnecessarily.

---

# 16. PRODUCT IMAGE

A Product may reference one or more images.

Typical metadata:

* Image ID
* Asset reference
* Purpose
* Language or locale
* Channel
* Display order
* Status
* Alt text
* Rights

Images are presentation assets.

---

# 17. PRODUCT TAG

Product tags may support classification or discovery.

Examples:

* Popular
* Seasonal
* Chef Recommended
* New
* Premium
* Spicy
* Vegetarian
* Vegan
* Gluten-Free

Tags implying safety or dietary characteristics shall be governed by authoritative Product and Recipe knowledge.

---

# 18. PRODUCT ATTRIBUTE

A `ProductAttribute` represents a structured characteristic.

Examples:

* Spice level
* Serving temperature
* Preparation style
* Cuisine
* Portion size
* Flavor profile
* Alcohol content
* Cooking method

Attributes support semantic search and recommendations.

---

# 19. FLAVOR PROFILE

Product flavor profile may include dimensions such as:

* Sweet
* Savory
* Spicy
* Smoky
* Sour
* Bitter
* Rich
* Light
* Creamy
* Fresh

Flavor profiles may support preference matching.

---

# 20. DIETARY ATTRIBUTE

Examples:

* Vegetarian
* Vegan
* Pescatarian
* Gluten-free according to defined policy
* Dairy-free
* Low sodium

Dietary claims shall have authoritative evidence.

---

# 21. ALLERGEN ATTRIBUTE

A Product may expose known allergen information derived from:

* Recipe
* Ingredient
* Preparation environment
* Supplier declarations

Examples:

* Contains peanuts
* Contains milk
* Contains egg
* Contains shellfish
* May contain nuts

The Recipe and Ingredient domains remain primary sources of composition.

---

# 22. PRODUCT RECIPE REFERENCE

A Product may reference one or more Recipes.

Example:

```text
Product:
Grilled Salmon

Recipe:
Grilled Salmon Standard Recipe
```

Different variants may reference different recipe versions.

---

# 23. PRODUCT WITHOUT RECIPE

Not every Product requires a restaurant recipe.

Examples:

* Bottled water
* Packaged soda
* Retail merchandise
* Gift card

The model shall support both prepared and non-prepared products.

---

# 24. MODIFIER

A `Modifier` represents an allowed customization.

Examples:

* No onion
* Extra cheese
* Sauce on the side
* Medium rare
* Add avocado
* Substitute salad for fries

A Modifier may affect:

* Price.
* Recipe.
* Inventory.
* Preparation time.
* Nutrition.
* Allergens.

---

# 25. MODIFIER GROUP

A `ModifierGroup` organizes related choices.

Examples:

```text
Steak Doneness
    ├── Rare
    ├── Medium Rare
    ├── Medium
    ├── Medium Well
    └── Well Done
```

or:

```text
Choose Side
    ├── Fries
    ├── Salad
    ├── Vegetables
    └── Mashed Potatoes
```

---

# 26. MODIFIER GROUP RULES

Typical rules include:

* Required or optional
* Minimum selections
* Maximum selections
* Exactly one selection
* Multiple selections
* Default option
* Additional price
* Incompatible selections

---

# 27. PRODUCT-MODIFIER RELATIONSHIP

A Product may expose:

* Global modifiers.
* Product-specific modifiers.
* Variant-specific modifiers.
* Menu-context-specific modifiers.

The Product Catalog owns logical modifier eligibility.

The Menu may restrict which modifiers are exposed in a given context.

---

# 28. ADD-ON

An `AddOn` represents an optional additional sellable component.

Examples:

* Extra cheese
* Bacon
* Avocado
* Side salad
* Extra sauce

An Add-On may itself map to a Product.

This enables consistent pricing, inventory and reporting.

---

# 29. SUBSTITUTION

A `ProductSubstitutionOption` defines allowed substitutions.

Examples:

```text
Fries
    → Salad

Regular milk
    → Oat milk
```

Substitutions may affect:

* Price.
* Allergens.
* Recipe.
* Inventory.
* Customer preference compatibility.

---

# 30. PRODUCT BUNDLE

A `ProductBundle` represents a structured combination of products sold together.

Examples:

* Burger + fries + beverage
* Family meal
* Lunch combo

Typical attributes:

* Bundle ID
* Name
* Components
* Selection rules
* Quantity rules
* Pricing reference
* Effective period
* Status

---

# 31. BUNDLE COMPONENT

A `BundleComponent` represents one part of a Product Bundle.

Examples:

```text
Lunch Combo

Component 1:
Choose one main course

Component 2:
Choose one beverage

Component 3:
Choose one dessert
```

Each component may define:

* Allowed products.
* Quantity.
* Required or optional.
* Upgrade rules.

---

# 32. PACKAGE

A `Package` represents a broader commercial offering that may combine:

* Products
* Services
* Capacity
* Reservations
* Event resources

Examples:

* Birthday package
* Banquet package
* Corporate lunch package

Packages may extend beyond simple Product Bundles.

---

# 33. PRODUCT SERVICE TYPE ELIGIBILITY

A Product may be eligible for:

* Dine In
* Take Away
* Delivery
* Drive Through
* Catering
* Banquet
* Buffet

Eligibility shall be explicit.

---

# 34. PRODUCT CHANNEL ELIGIBILITY

A Product may be exposed through:

* Telephone
* Web Chat
* Mobile App
* Kiosk
* Delivery platform
* Employee POS

Channel eligibility is separate from Product existence.

---

# 35. PRODUCT BRANCH ELIGIBILITY

A Product may be:

* Available across all branches.
* Available only in selected branches.
* Exclusive to a location.
* Exclusive to a region.

The Product Catalog shall preserve branch applicability.

---

# 36. PRODUCT BRAND SCOPE

In multi-brand operations, a Product may belong to:

* One brand.
* Multiple brands.
* Shared internal catalog.

Brand ownership shall remain explicit.

---

# 37. PRODUCT AVAILABILITY

Current availability is not owned solely by Product Catalog.

Availability may depend on:

* Inventory
* Recipe
* Equipment
* Kitchen
* Schedule
* Branch
* Channel
* Service type

The Product Catalog exposes eligibility and structure.

Operational domains determine real-time feasibility.

---

# 38. PRODUCT OFFERABILITY

A Product may be active but not offerable.

Example:

```text
Product:
Pizza Margherita

Status:
ACTIVE

Branch:
Downtown

Required equipment:
Pizza oven

Pizza oven:
OUT OF SERVICE

Result:
TEMPORARILY_UNAVAILABLE
```

This shall be resolved through Operational Context.

---

# 39. PRODUCT PRICE

Price is defined in:

`12_Pricing_and_Promotions.md`

The Product Catalog may reference pricing entities.

It shall not make price the core identity of Product.

---

# 40. PRODUCT PROMOTION

A Product may participate in:

* Discounts
* Promotions
* Bundles
* Loyalty rewards
* Seasonal campaigns

Promotion rules are owned by the Pricing and Promotions domain.

---

# 41. PRODUCT COST

Product cost may be derived from:

* Recipe ingredients
* Supplier cost
* Packaging
* Labor
* Allocated overhead

The Product Catalog may reference cost intelligence.

It shall not duplicate accounting logic.

---

# 42. PRODUCT MARGIN

Margin is an analytical result.

It may support:

* Sales recommendations.
* Menu engineering.
* Executive Intelligence.

Customer recommendations shall not be based on margin alone.

---

# 43. PRODUCT NUTRITION

Where available, nutritional information may include:

* Calories
* Protein
* Carbohydrates
* Fat
* Sodium
* Sugar

Nutritional information shall preserve source and validity.

---

# 44. PRODUCT PREPARATION TIME

A Product may have an expected baseline preparation time.

Actual preparation time depends on:

* Kitchen workload.
* Current queue.
* Equipment.
* Staffing.
* Modifiers.

Therefore baseline preparation time is not a real-time promise.

---

# 45. PRODUCT COMPLEXITY

Products may carry operational complexity indicators.

Examples:

* Low
* Medium
* High

Complexity may help predict kitchen workload.

---

# 46. PRODUCT PACKAGING

Products intended for Take Away or Delivery may require packaging.

Examples:

* Container type
* Beverage carrier
* Insulated packaging
* Tamper seal

Packaging may affect:

* Cost.
* Inventory.
* Delivery suitability.

---

# 47. DELIVERY SUITABILITY

A Product may define delivery suitability.

Examples:

```text
SUITABLE
CONDITIONALLY_SUITABLE
NOT_RECOMMENDED
NOT_ALLOWED
```

Factors may include:

* Product stability.
* Temperature sensitivity.
* Packaging.
* Travel time.

---

# 48. TAKE AWAY SUITABILITY

Take Away suitability may differ from Delivery suitability.

A Product may travel well for 5 minutes but poorly for 45 minutes.

The model shall support this distinction.

---

# 49. PRODUCT QUALITY WINDOW

A Product may define a recommended time window between completion and consumption.

This may support delivery routing and ETA decisions.

---

# 50. PRODUCT AGE RESTRICTION

Some Products may require age-related restrictions according to applicable laws or restaurant policy.

Examples:

* Alcoholic beverages

The Action and Policy layers shall enforce relevant requirements.

---

# 51. PRODUCT SALES RESTRICTION

Possible restrictions:

* Time-based
* Location-based
* Age-based
* Event-based
* Membership-based
* Quantity-based

Restrictions shall be policy-driven.

---

# 52. PRODUCT COMPATIBILITY

Products may have commercial relationships.

Examples:

```text
Steak
    PAIRS_WITH Red Wine

Coffee
    PAIRS_WITH Cheesecake
```

These relationships may support recommendation intelligence.

---

# 53. PRODUCT AFFINITY

Product affinity is derived from historical behavior.

Example:

```text
Customers who order Product A
frequently also order Product B.
```

Affinity is analytical.

It shall not be stored as intrinsic Product truth.

---

# 54. PRODUCT COMPLEMENT

A `ProductComplementRelationship` may represent curated business knowledge.

Examples:

* Burger complements fries.
* Espresso complements tiramisu.

This differs from statistical affinity.

---

# 55. PRODUCT SUBSTITUTE

A `ProductSubstituteRelationship` defines alternative products.

Examples:

```text
Product unavailable:
Grilled Salmon

Possible alternatives:
Sea Bass
Tuna Steak
```

Substitution may consider:

* Category.
* Flavor.
* Price.
* Dietary compatibility.
* Customer preference.

---

# 56. PRODUCT UPGRADE

An `UpgradeRelationship` may identify a premium alternative.

Example:

```text
House Wine
    → Reserve Wine
```

This may support upselling.

The customer must receive clear pricing and choice.

---

# 57. PRODUCT DOWNGRADE OR LOWER-COST ALTERNATIVE

The model should also support lower-cost or simpler alternatives.

Sales Intelligence shall not assume that every recommendation should increase ticket value.

---

# 58. PRODUCT CROSS-SELL RELATIONSHIP

Curated cross-sell examples:

* Main course → beverage
* Main course → dessert
* Pizza → appetizer
* Coffee → pastry

These may coexist with analytical affinity models.

---

# 59. PRODUCT CUSTOMER HISTORY

Customer History may expose:

* Previously purchased products
* Purchase frequency
* Last purchase
* Typical modifiers
* Product complaints
* Product compliments

The Product Catalog remains authoritative for current Product identity.

---

# 60. PRODUCT CUSTOMER PREFERENCE MATCH

Customer Preferences may be matched against:

* Category
* Ingredient
* Flavor profile
* Dietary attributes
* Product history

This supports personalized recommendations.

---

# 61. PRODUCT ALLERGY COMPATIBILITY

Known allergies shall constrain recommendations.

The platform shall determine compatibility using authoritative recipe and ingredient data.

Product name alone is insufficient.

---

# 62. PRODUCT SAFETY

Safety-related product information may include:

* Allergens
* Alcohol content
* Preparation restrictions
* Cross-contact warnings
* Temperature requirements

Safety rules override commercial optimization.

---

# 63. PRODUCT KNOWLEDGE

Products shall be represented as enterprise knowledge capable of answering questions such as:

* What is it?
* What does it contain?
* How is it prepared?
* What sizes exist?
* What can be modified?
* Is it suitable for delivery?
* What allergens may be present?
* What does it pair with?
* Is it currently offerable?

---

# 64. PRODUCT SEARCH

Conversational queries may include:

```text
"What chicken dishes do you have?"

"Do you have anything without dairy?"

"What comes in a family size?"

"What can I order that's under 20 minutes?"

"Which desserts have fruit?"
```

Product search shall combine catalog knowledge with operational context.

---

# 65. PRODUCT RECOMMENDATION

A Product recommendation may consider:

```text
Customer Preference
+
Customer History
+
Current Intent
+
Product Knowledge
+
Price
+
Promotion
+
Availability
+
Kitchen Capacity
+
Business Objective
```

No single dimension should independently determine the recommendation.

---

# 66. PRODUCT VERSIONING

Product definitions may change.

Examples:

* Recipe changed.
* Name changed.
* Portion changed.
* Packaging changed.
* Dietary attribute changed.
* Product discontinued.

Product history shall preserve sufficient version information.

---

# 67. PRODUCT HISTORICAL IDENTITY

A historical order shall retain the Product or Product Version that existed at transaction time.

Current Product changes shall not rewrite historical sales.

---

# 68. PRODUCT DEPRECATION

A Product may be discontinued while remaining historically referenced.

Suggested lifecycle:

```text
ACTIVE
→ SUSPENDED
→ DISCONTINUED
→ ARCHIVED
```

Archived products remain queryable for historical evidence.

---

# 69. PRODUCT REPLACEMENT

A discontinued Product may reference a successor.

Example:

```text
Old Product:
Classic Burger

Replaced By:
Signature Burger
```

Replacement does not rewrite historical identity.

---

# 70. EXTERNAL PRODUCT MAPPING

External systems may use different identifiers.

Example:

```text
ECIP Product:
PRD-001

POS A:
ITEM-882

Delivery Platform:
SKU-5544
```

Mappings shall use canonical external-reference mechanisms.

---

# 71. PRODUCT IMPORT

Product catalogs may originate from:

* POS
* ERP
* Spreadsheet
* Existing catalog database
* External platform

Import shall preserve:

* Source
* External identifier
* Import batch
* Mapping quality
* Validation status

---

# 72. PRODUCT SYNCHRONIZATION

Synchronization may update:

* Product status
* Names
* Categories
* External mappings
* Eligibility
* Menu relationships

Authoritative ownership shall be configured explicitly.

---

# 73. PRODUCT CONFLICT

Possible conflicts include:

* Different names across systems
* Different active statuses
* Different category mappings
* Different variant structures

Conflicts shall be visible and governed.

---

# 74. PRODUCT SOURCE OF TRUTH

Source authority may vary.

Example:

```text
POS:
Sellable product activation

ERP:
Tax classification

Recipe system:
Composition

ECIP:
Canonical semantic representation
```

Ownership shall remain explicit.

---

# 75. PRODUCT EVENTS

Initial domain events include:

```text
ProductCreated
ProductUpdated
ProductActivated
ProductSuspended
ProductDiscontinued
ProductArchived

ProductVariantCreated
ProductVariantUpdated
ProductVariantDeactivated

ProductCategoryCreated
ProductCategoryUpdated

ModifierCreated
ModifierUpdated
ModifierAssignedToProduct
ModifierRemovedFromProduct

ProductBundleCreated
ProductBundleUpdated

ProductEligibilityChanged
ProductChannelEligibilityChanged
ProductBranchEligibilityChanged

ProductRecipeChanged
ProductDietaryAttributeChanged
ProductAllergenAttributeChanged

ProductReplacementDefined

ProductImported
ProductSynchronizationStarted
ProductSynchronizationCompleted
ProductSynchronizationFailed
ProductConflictDetected
ProductConflictResolved
```

---

# 76. RELATIONSHIPS

```text
Restaurant
    HAS Product

Brand
    OWNS Product

Product
    BELONGS_TO ProductCategory

Product
    HAS ProductVariant

Product
    MAY_HAVE ProductSize

Product
    MAY_HAVE ProductPresentation

Product
    MAY_REFERENCE Recipe

Product
    HAS ProductAttribute

Product
    MAY_HAVE DietaryAttribute

Product
    MAY_HAVE AllergenAttribute

Product
    HAS ModifierGroup

ModifierGroup
    CONTAINS Modifier

ProductBundle
    CONTAINS BundleComponent

BundleComponent
    REFERENCES Product

MenuItem
    REFERENCES Product

Product
    MAY_HAVE SubstituteProduct

Product
    MAY_HAVE ComplementProduct

Product
    MAY_HAVE UpgradeProduct

Product
    MAY_MAP_TO ExternalEntityReference
```

---

# 77. BUSINESS RULES

The following rules apply:

1. A Product has one canonical identity within its domain scope.

2. Product identity shall remain independent of Menu placement.

3. Current Price shall not define Product identity.

4. Product availability shall not define Product lifecycle status.

5. A Product may appear in multiple Menus.

6. A Product may have multiple Variants.

7. Modifiers shall preserve explicit eligibility and selection rules.

8. Recipe references shall remain authoritative for composition.

9. Dietary and allergen claims shall be evidence-based.

10. Current Product changes shall not rewrite historical transactions.

11. External system identifiers shall not replace canonical Product IDs.

12. Product recommendations shall consider current operational feasibility.

13. Known safety constraints shall override commercial optimization.

14. Product lifecycle changes shall preserve audit history.

15. Products may remain historically referenced after discontinuation.

16. Provider-specific catalog structures shall remain behind integration mappings.

---

# 78. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Product

ProductCategory

ProductVariant

ProductSize

ProductPresentation

ProductAttribute

ModifierGroup

Modifier

ProductModifierEligibility

ProductServiceTypeEligibility

ProductChannelEligibility

ProductBranchEligibility

ProductRecipeReference

DietaryAttribute

AllergenAttribute

ExternalProductMapping
```

Introduce later when commercially required:

```text
Advanced Product Affinity

Advanced Substitute Ranking

Autonomous Bundle Generation

Product Similarity Models

Advanced Delivery Suitability Prediction

Advanced Semantic Product Graph
```

---

# 79. IMPLEMENTATION PRINCIPLE

This document defines the logical Product Catalog Model.

It does not prescribe:

* Database schema.
* POS schema.
* Product UI.
* Inventory implementation.
* Pricing engine.
* Recommendation algorithm.
* Recipe engine.
* Search engine.
* Machine learning model.

Implementation shall preserve the semantic distinction between:

```text
PRODUCT

PRODUCT VARIANT

MENU ITEM

RECIPE

INGREDIENT

PRICE

PROMOTION

AVAILABILITY

RECOMMENDATION
```

---

# 80. FINAL RULE

Before ECIP can reason correctly about a restaurant Product, it shall be able to answer:

> What is the canonical Product?

> Which category and variant does it belong to?

> What recipe or composition defines it?

> Which modifiers are valid?

> Which service types, branches and channels support it?

> What dietary and allergen information is authoritative?

> Is it currently available and operationally feasible?

> Which Menu exposes it?

> What current Price and Promotion apply?

> Is it appropriate for this customer and this context?

Only after these dimensions are resolved may ECIP reliably describe, recommend, sell or execute actions involving the Product.

