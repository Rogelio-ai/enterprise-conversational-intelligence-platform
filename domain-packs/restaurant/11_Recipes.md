# 11_Recipes.md

**Document ID:** RDM-011
**Document Name:** Recipes
**Domain Pack:** Restaurant Intelligence Platform
**Product:** Enterprise Conversational Intelligence Platform (ECIP)
**Version:** 1.0.0
**Status:** ACTIVE
**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the Recipe Model for the Restaurant Intelligence Platform.

Its purpose is to represent how restaurant Products are prepared from Ingredients, Portions, Preparation Steps, Equipment, Production Rules and Operational Constraints.

The Recipe Model provides the authoritative restaurant-domain representation of product composition and preparation logic.

Recipes are critical to:

* Product composition.
* Ingredient consumption.
* Inventory deduction.
* Cost calculation.
* Allergen determination.
* Dietary classification.
* Kitchen execution.
* Preparation-time estimation.
* Substitution reasoning.
* Product availability.
* Quality control.
* Sales recommendations.
* Customer safety.

---

# 2. OBJECTIVES

The Recipe Model enables ECIP to:

* Understand what each prepared Product contains.
* Understand how each Product is prepared.
* Determine required Ingredients.
* Determine ingredient quantities.
* Determine preparation steps.
* Determine required equipment.
* Determine kitchen stations involved.
* Calculate theoretical ingredient consumption.
* Support inventory availability checks.
* Support recipe costing.
* Support allergen detection.
* Support dietary classification.
* Support ingredient substitutions.
* Support Product variants and sizes.
* Estimate preparation requirements.
* Support kitchen workload reasoning.
* Preserve recipe history.
* Support operational and conversational intelligence.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends and consumes the following canonical concepts:

* Knowledge Item
* Knowledge Fact
* Policy
* Procedure
* Context Snapshot
* Recommendation
* Action
* External Entity Reference

Restaurant-specific Recipe concepts remain within the Restaurant Domain Pack.

This document does not redefine canonical knowledge or procedural concepts.

---

# 4. RECIPE PRINCIPLE

A Recipe represents the governed definition of how a prepared Product is composed and produced.

The platform shall distinguish between:

```text
Product

Recipe

Ingredient

Inventory Item

Preparation Step

Production Execution

Cost

Availability
```

These concepts are related but not equivalent.

---

# 5. RECIPE

A `Recipe` represents a defined preparation specification.

Typical attributes include:

* Recipe ID
* Name
* Product reference
* Recipe type
* Version
* Yield
* Portion definition
* Preparation time
* Cook time
* Rest time
* Total expected time
* Required kitchen station
* Required equipment
* Instructions
* Status
* Effective dates
* Approval status

Suggested lifecycle:

```text
DRAFT
→ APPROVED
→ ACTIVE
→ SUSPENDED
→ RETIRED
→ ARCHIVED
```

---

# 6. RECIPE TYPES

Examples include:

* Standard Recipe
* Base Recipe
* Component Recipe
* Batch Recipe
* Assembly Recipe
* Beverage Recipe
* Cocktail Recipe
* Sauce Recipe
* Dough Recipe
* Dessert Recipe
* Catering Recipe
* Banquet Recipe
* Buffet Recipe

A Product may reference one or more Recipes.

---

# 7. STANDARD RECIPE

A Standard Recipe represents the normal preparation specification for a Product.

Example:

```text
Product:
Grilled Salmon

Recipe:
Standard Grilled Salmon

Yield:
1 portion
```

This Recipe may define:

* Ingredient quantities.
* Preparation sequence.
* Required station.
* Cooking method.
* Quality standards.

---

# 8. BASE RECIPE

A Base Recipe represents an intermediate preparation used by multiple Products.

Examples:

* Tomato sauce.
* Brown stock.
* Pizza dough.
* House dressing.
* Pastry cream.
* Salsa.

Base Recipes improve consistency and cost calculation.

---

# 9. COMPONENT RECIPE

A Product may contain components prepared independently.

Example:

```text
Product:
Chicken Pasta

Components:
- Pasta portion
- Alfredo sauce
- Grilled chicken
- Garnish
```

Each component may reference a separate Recipe.

---

# 10. BATCH RECIPE

A Batch Recipe produces multiple portions.

Examples:

* Soup.
* Sauce.
* Dough.
* Rice.
* Dessert base.

Typical attributes:

* Batch size.
* Expected yield.
* Yield unit.
* Portion conversion.
* Shelf life.
* Storage requirements.

---

# 11. RECIPE VERSION

A `RecipeVersion` represents an immutable definition valid during a specific period.

Recipe changes may include:

* Ingredient change.
* Quantity change.
* Preparation change.
* Equipment change.
* Yield change.
* Portion change.
* Allergen-impacting change.
* Cost-impacting change.

Historical transactions shall preserve the Recipe Version applicable at the time where required.

---

# 12. RECIPE VERSIONING PRINCIPLE

Current recipe changes shall not rewrite historical composition.

This is important for:

* Cost analysis.
* Allergen investigations.
* Customer disputes.
* Quality analysis.
* Historical inventory consumption.

---

# 13. RECIPE YIELD

Yield represents the amount produced by a Recipe.

Examples:

```text
1 plate

10 portions

5 liters

2 kilograms

24 pieces
```

Typical attributes:

* Yield quantity.
* Yield unit.
* Expected usable yield.
* Expected waste.

---

# 14. PORTION

A `RecipePortion` defines the quantity used to serve one commercial unit.

Examples:

```text
Batch:
5 liters soup

Serving portion:
300 ml

Expected portions:
16
```

Portion information is important for:

* Cost.
* Inventory.
* Nutrition.
* Production planning.

---

# 15. INGREDIENT

An `Ingredient` represents a food, beverage or consumable component used in preparation.

Typical attributes:

* Ingredient ID
* Name
* Ingredient category
* Unit
* Status
* Allergen information
* Dietary attributes
* Inventory reference
* Supplier references

Detailed lifecycle is further defined in `25_Ingredient_Lifecycle.md`.

---

# 16. RECIPE INGREDIENT

A `RecipeIngredient` represents the use of an Ingredient within a Recipe.

Typical attributes:

* Recipe.
* Ingredient.
* Quantity.
* Unit.
* Preparation note.
* Sequence.
* Required or optional.
* Waste factor.
* Yield factor.
* Substitution policy.

---

# 17. INGREDIENT QUANTITY

Quantities shall use explicit units.

Examples:

* grams
* kilograms
* milliliters
* liters
* pieces
* ounces
* cups

Unit normalization shall be consistent enough to support costing and inventory deduction.

---

# 18. UNIT CONVERSION

Recipe units may differ from inventory units.

Example:

```text
Inventory:
Olive oil purchased in liters.

Recipe:
Uses 20 ml.
```

The system shall support governed unit conversion.

Conversion shall not introduce silent precision errors.

---

# 19. INGREDIENT WASTE FACTOR

Some Ingredients lose usable quantity during preparation.

Examples:

* Vegetable trimming.
* Meat trimming.
* Peeling.
* Cooking shrinkage.

A waste factor may support more accurate costing and inventory planning.

---

# 20. YIELD FACTOR

Yield factor represents usable output after preparation.

Example:

```text
Raw beef:
1.0 kg

Usable cooked beef:
0.78 kg
```

Yield factors may vary by Ingredient and preparation method.

---

# 21. PREPARATION STEP

A `PreparationStep` represents one step in Recipe execution.

Typical attributes:

* Step number.
* Description.
* Station.
* Equipment.
* Expected duration.
* Temperature.
* Dependency.
* Quality checkpoint.

---

# 22. STEP SEQUENCE

Preparation steps may be:

* Sequential.
* Parallel.
* Conditional.

Example:

```text
1. Season salmon
2. Heat grill
3. Grill salmon
4. Prepare vegetables
5. Plate
```

Some steps may run concurrently.

---

# 23. PREPARATION DEPENDENCY

A step may depend on another step.

Example:

```text
Sauce preparation
must complete before plating.
```

Dependencies support production reasoning.

---

# 24. PREPARATION TIME

Recipe time may include:

* Setup time.
* Preparation time.
* Cook time.
* Rest time.
* Assembly time.

Baseline time is not the same as current ETA.

Current ETA also depends on:

* Kitchen queue.
* Equipment availability.
* Staffing.
* Batch state.
* Modifiers.

---

# 25. KITCHEN STATION

A Recipe may require one or more Kitchen Stations.

Examples:

* Grill.
* Fry.
* Cold Kitchen.
* Pizza.
* Dessert.
* Bar.
* Bakery.

Station requirements contribute to workload reasoning.

---

# 26. EQUIPMENT REQUIREMENT

Recipes may require Equipment.

Examples:

* Grill.
* Oven.
* Fryer.
* Blender.
* Espresso machine.
* Mixer.

Equipment status may affect product offerability.

---

# 27. EQUIPMENT DEPENDENCY

Example:

```text
Product:
Wood-fired pizza

Required equipment:
Pizza oven

Pizza oven:
Out of service

Result:
Product may become unavailable
```

Recipe knowledge therefore contributes directly to Operational Context.

---

# 28. COOKING METHOD

Examples:

* Grilled.
* Fried.
* Baked.
* Roasted.
* Boiled.
* Steamed.
* Sous-vide.
* Raw.
* Blended.
* Shaken.
* Stirred.

Cooking method may affect:

* Preparation time.
* Flavor profile.
* Nutrition.
* Allergen cross-contact.
* Equipment requirements.

---

# 29. TEMPERATURE REQUIREMENT

Recipes may specify:

* Cooking temperature.
* Holding temperature.
* Serving temperature.
* Storage temperature.

These values may support Food Safety and Quality Control.

---

# 30. COOKING DONENESS

Some Products support customer-selected doneness.

Examples:

* Rare.
* Medium rare.
* Medium.
* Medium well.
* Well done.

Doneness may be represented as a Modifier affecting preparation.

---

# 31. MODIFIER IMPACT ON RECIPE

Modifiers may change Recipe execution.

Example:

```text
Modifier:
No cheese

Effect:
Remove cheese ingredient
```

or:

```text
Modifier:
Extra avocado

Effect:
Add ingredient quantity
```

Recipe execution shall resolve applicable modifier changes.

---

# 32. RECIPE OVERRIDE

Some Product Variants may use a Recipe override.

Example:

```text
Product:
Pizza

Small variant:
Recipe A

Large variant:
Recipe B
```

Variant-specific composition shall remain explicit.

---

# 33. SIZE SCALING

Recipe quantities may scale according to Product Size.

Scaling may be:

* Linear.
* Rule-based.
* Explicit per size.

The platform shall not assume linear scaling when business rules define otherwise.

---

# 34. SUBSTITUTION

A `RecipeSubstitution` defines an authorized replacement.

Examples:

```text
Regular milk
→ Oat milk

Fries
→ Salad
```

Substitution may affect:

* Cost.
* Allergens.
* Dietary classification.
* Inventory.
* Preparation time.
* Price.

---

# 35. SUBSTITUTION RULE

Substitution shall preserve:

* Original Ingredient.
* Replacement.
* Eligibility.
* Quantity conversion.
* Price impact.
* Allergen impact.
* Approval rule.

---

# 36. EMERGENCY SUBSTITUTION

Temporary substitutions may occur due to stock or supply problems.

These shall be explicitly controlled.

ECIP shall not invent substitutions simply because ingredients appear similar.

---

# 37. ALLERGEN DERIVATION

Recipe composition is a primary source for allergen reasoning.

Conceptually:

```text
Recipe
    ↓
Recipe Ingredients
    ↓
Ingredient Allergen Data
    ↓
Product Allergen Profile
```

Cross-contact risk may require additional rules.

---

# 38. CROSS-CONTACT

A Recipe may carry cross-contact considerations.

Examples:

* Shared fryer.
* Shared grill.
* Shared preparation surface.
* Shared utensils.

Cross-contact warnings shall not be derived solely from ingredient lists.

---

# 39. DIETARY CLASSIFICATION

Recipe composition may support classifications such as:

* Vegetarian.
* Vegan.
* Dairy-free.
* Gluten-free according to policy.

Claims shall be based on explicit rules and authoritative data.

---

# 40. RECIPE NUTRITION

Nutritional values may be derived from:

* Ingredient nutrition.
* Quantity.
* Yield.
* Cooking transformation.

Calculated values shall preserve methodology and confidence.

---

# 41. RECIPE COST

Recipe cost may derive from:

```text
Ingredient quantity
×
Current ingredient cost
+
Packaging
+
Other direct costs
```

Detailed financial accounting may exist elsewhere.

Recipe Cost primarily supports operational and commercial intelligence.

---

# 42. STANDARD COST VS ACTUAL COST

The model shall distinguish:

* Standard theoretical Recipe Cost.
* Actual realized cost.

Differences may arise from:

* Waste.
* Substitutions.
* Supplier price.
* Portion variance.

---

# 43. RECIPE MARGIN SUPPORT

Recipe cost may support Product Margin calculation.

Margin may inform:

* Menu engineering.
* Sales recommendations.
* Executive Intelligence.

Margin shall not override customer suitability or safety.

---

# 44. INVENTORY CONSUMPTION

Recipe completion may produce theoretical Ingredient consumption.

Example:

```text
Order:
2 grilled salmon

Recipe per portion:
220 g salmon

Expected consumption:
440 g salmon
```

Actual inventory behavior may include additional waste and variance.

---

# 45. THEORETICAL VS ACTUAL CONSUMPTION

The platform shall distinguish:

```text
Theoretical consumption
based on Recipe

Actual consumption
based on inventory movement
```

Variance is operational intelligence.

---

# 46. RECIPE AVAILABILITY

A Recipe may be executable only if required Ingredients and resources are available.

Conceptually:

```text
Ingredients available
+
Required station available
+
Required equipment operational
+
Business policy permits
=
Recipe potentially executable
```

---

# 47. PARTIAL AVAILABILITY

A Product may remain available with authorized substitutions.

Example:

```text
Regular side unavailable.

Allowed substitute:
Vegetables.

Result:
Product offerable with conditions.
```

---

# 48. RECIPE FEASIBILITY

`RecipeFeasibility` represents whether a Recipe can currently be executed.

Suggested states:

```text
FEASIBLE

FEASIBLE_WITH_SUBSTITUTION

FEASIBLE_WITH_DELAY

NOT_FEASIBLE
```

Feasibility is contextual.

---

# 49. BATCH PRODUCTION

Batch Recipes may be prepared before customer orders.

Examples:

* Soup.
* Sauce.
* Dough.
* Dessert.

The platform may track:

* Batch produced.
* Quantity remaining.
* Production time.
* Expiration.
* Quality status.

---

# 50. PREPARED COMPONENT INVENTORY

Prepared Recipe Components may act as semi-finished inventory.

Examples:

* Pizza dough.
* Pasta sauce.
* Cooked rice.
* Pre-portioned protein.

This enables more accurate availability reasoning.

---

# 51. RECIPE SHELF LIFE

Prepared Recipes or components may have:

* Production time.
* Expiration time.
* Holding time.
* Storage requirements.

Expired components shall not be considered available.

---

# 52. RECIPE PRODUCTION FORECAST

Historical demand may help forecast production needs.

Examples:

* Soup batches.
* Dough.
* Sauces.
* Desserts.

This belongs primarily to Production Intelligence but consumes Recipe information.

---

# 53. RECIPE QUALITY STANDARD

A Recipe may define quality expectations.

Examples:

* Portion weight.
* Appearance.
* Temperature.
* Texture.
* Plating.
* Presentation.

Quality Control may validate against these standards.

---

# 54. PLATING STANDARD

Prepared Products may define plating instructions.

Examples:

* Plate type.
* Garnish.
* Component position.
* Sauce presentation.

This may support consistency and future machine-vision quality controls.

---

# 55. RECIPE INSTRUCTIONS

Recipe instructions may have different audiences:

* Kitchen staff.
* Training.
* Customer-safe description.
* AI operational reasoning.

Sensitive proprietary recipe details should not automatically be exposed to customers.

---

# 56. RECIPE CONFIDENTIALITY

Some Recipes may represent proprietary intellectual property.

Access may therefore be restricted.

Examples:

```text
Customer:
May receive ingredient and allergen information.

Cook:
May receive preparation instructions.

Chef:
May receive full recipe specification.
```

Authorization shall be role-aware.

---

# 57. RECIPE KNOWLEDGE LEVELS

The platform should distinguish:

```text
Public Product Knowledge

Customer Safety Knowledge

Operational Preparation Knowledge

Confidential Recipe Knowledge
```

This prevents conversational AI from exposing confidential preparation details.

---

# 58. RECIPE SEARCH

Authorized users or agents may ask:

```text
"What ingredients are required?"

"Which dishes use shrimp?"

"Which recipes need the grill?"

"What can we still prepare without avocados?"

"Which products contain dairy?"
```

Results shall respect authorization.

---

# 59. RECIPE AND CUSTOMER QUESTIONS

Customers may ask:

```text
"Does this contain peanuts?"

"Can you make it without cheese?"

"Is this vegetarian?"

"Can I replace fries with salad?"
```

ECIP shall answer from governed Recipe and Product knowledge.

It shall not guess.

---

# 60. RECIPE AND CUSTOMER ALLERGIES

Example:

```text
Customer:
Peanut allergy

Product:
Dessert

Recipe:
Contains peanut ingredient
```

Result:

```text
Product shall not be recommended as compatible.
```

If data is insufficient, ECIP shall explicitly indicate uncertainty and escalate where appropriate.

---

# 61. RECIPE AND CUSTOMER PREFERENCES

Preferences may match:

* Ingredients.
* Preparation style.
* Flavor.
* Modifiers.
* Substitutions.

Example:

```text
Customer:
Prefers low-spice food

Recipe:
High spice level

Result:
Lower recommendation relevance
```

---

# 62. RECIPE AND MENU

Menu Items reference Products.

Products reference Recipes.

Conceptually:

```text
MenuItem
    ↓
Product
    ↓
Recipe
```

Menu presentation shall not duplicate Recipe composition unnecessarily.

---

# 63. RECIPE AND PRODUCT CATALOG

`10_Product_Catalog.md` owns Product identity.

This document owns Product preparation composition.

A Product may exist without a Recipe.

A Recipe shall not replace Product identity.

---

# 64. RECIPE AND INVENTORY

Inventory provides current Ingredient availability.

Recipe provides required Ingredient quantities.

Together they support Product availability.

---

# 65. RECIPE AND PURCHASING

Purchasing may use Recipe demand to estimate Ingredient requirements.

Example:

```text
Forecast:
300 pasta dishes

Recipe consumption:
120 g pasta each

Expected requirement:
36 kg pasta
```

---

# 66. RECIPE AND PRODUCTION

Production consumes Recipe instructions for:

* Preparation sequence.
* Station routing.
* Batch production.
* Workload estimation.

Detailed runtime execution belongs to `21_Production.md`.

---

# 67. RECIPE AND KITCHEN

Kitchen structure provides:

* Stations.
* Staff.
* Equipment.
* Current workload.

Recipe defines required resources.

Together they support ETA estimation.

---

# 68. RECIPE AND QUALITY CONTROL

Quality Control may compare produced items against Recipe standards.

Examples:

* Portion.
* Temperature.
* Presentation.
* Ingredient conformity.

---

# 69. RECIPE AND SALES INTELLIGENCE

Sales Intelligence may use Recipe knowledge to avoid inappropriate recommendations.

Examples:

* Allergy incompatibility.
* Long preparation time.
* Unavailable ingredient.
* High kitchen load.

---

# 70. RECIPE AND OPERATIONAL INTELLIGENCE

Recipe data supports detection of:

* Ingredient bottlenecks.
* Equipment dependencies.
* High-complexity Products.
* Production capacity constraints.
* Waste opportunities.

---

# 71. RECIPE AND EXECUTIVE INTELLIGENCE

Aggregated Recipe data may support:

* Food cost analysis.
* Menu engineering.
* Waste analysis.
* Margin analysis.
* Ingredient concentration risk.
* Equipment dependency risk.

---

# 72. RECIPE CHANGE CONTROL

Changes with significant impact should be governed.

Examples:

* Allergen change.
* Ingredient substitution.
* Portion size change.
* Recipe cost change.
* Preparation equipment change.

Changes shall preserve:

* Actor.
* Reason.
* Effective date.
* Previous version.
* Approval where required.

---

# 73. RECIPE APPROVAL

Depending on restaurant policy, Recipe approval may require:

* Chef.
* Food safety authority.
* Operations manager.
* Cost control.
* Corporate brand authority.

The Domain Model supports approval without prescribing a specific workflow.

---

# 74. RECIPE IMPORT

Recipes may originate from:

* POS.
* Recipe management system.
* ERP.
* Spreadsheet.
* Existing kitchen database.

Imported Recipes shall be normalized into the Restaurant Domain Model.

---

# 75. RECIPE SYNCHRONIZATION

Where an external source is authoritative, ECIP may synchronize:

* Recipe definitions.
* Ingredient quantities.
* Product mappings.
* Version status.

Sync conflicts shall be visible.

---

# 76. EXTERNAL RECIPE MAPPING

Example:

```text
ECIP Recipe:
RCP-001

POS:
REC-347

ERP:
FORMULA-991
```

External IDs shall not replace canonical Recipe identity.

---

# 77. RECIPE EVENTS

Initial events include:

```text
RecipeCreated

RecipeUpdated

RecipeApproved

RecipeActivated

RecipeSuspended

RecipeRetired

RecipeVersionCreated

RecipeIngredientAdded

RecipeIngredientUpdated

RecipeIngredientRemoved

RecipeSubstitutionAdded

RecipeSubstitutionRemoved

PreparationStepAdded

PreparationStepUpdated

RecipeYieldChanged

RecipePortionChanged

RecipeAllergenProfileChanged

RecipeDietaryProfileChanged

RecipeCostChanged

RecipeFeasibilityChanged

RecipeImported

RecipeSynchronizationStarted

RecipeSynchronizationCompleted

RecipeSynchronizationFailed

RecipeConflictDetected

RecipeConflictResolved
```

---

# 78. RELATIONSHIPS

```text
Product
    MAY_HAVE Recipe

Recipe
    HAS RecipeVersion

Recipe
    CONTAINS RecipeIngredient

RecipeIngredient
    REFERENCES Ingredient

Recipe
    HAS PreparationStep

PreparationStep
    MAY_REQUIRE KitchenStation

PreparationStep
    MAY_REQUIRE Equipment

Recipe
    HAS Yield

Recipe
    MAY_HAVE RecipeSubstitution

Recipe
    MAY_PRODUCE PreparedComponent

Recipe
    CONTRIBUTES_TO ProductAllergenProfile

Recipe
    CONTRIBUTES_TO ProductDietaryProfile

Recipe
    CONTRIBUTES_TO ProductCost

Recipe
    CONTRIBUTES_TO ProductAvailability
```

---

# 79. BUSINESS RULES

The following rules apply:

1. Recipe identity is separate from Product identity.

2. A Product may have zero, one or multiple Recipes.

3. Every Recipe shall define an explicit yield.

4. Recipe Ingredients shall use governed units.

5. Recipe version history shall remain traceable.

6. Current Recipe changes shall not rewrite historical composition.

7. Ingredient substitutions shall be explicitly authorized.

8. ECIP shall not invent substitutions.

9. Allergen information shall derive from authoritative composition and cross-contact rules.

10. Dietary claims shall be evidence-based.

11. Recipe availability shall consider required Ingredients, Equipment and Kitchen resources.

12. Recipe cost and actual cost are separate concepts.

13. Theoretical consumption and actual Inventory movement are separate concepts.

14. Confidential Recipe details shall respect authorization.

15. Recipe changes affecting safety shall require appropriate governance.

16. External Recipe identifiers shall remain integration mappings.

17. Recipe feasibility shall be evaluated using current Operational Context.

---

# 80. MVP PRIORITY

For the first production-oriented implementation, prioritize:

```text
Recipe

RecipeVersion

RecipeIngredient

IngredientReference

RecipeYield

RecipePortion

PreparationStep

KitchenStationRequirement

EquipmentRequirement

RecipeModifierEffect

RecipeSubstitution

RecipeAllergenDerivation

RecipeDietaryClassification

RecipeFeasibility

ExternalRecipeMapping
```

Defer unless required by the first commercial implementation:

```text
Advanced Recipe Optimization

Automated Recipe Generation

Computer-Vision Plating Validation

Advanced Nutrition Modeling

Advanced Yield Prediction

Autonomous Ingredient Substitution

Recipe Simulation Engine
```

---

# 81. IMPLEMENTATION PRINCIPLE

This document defines the logical Recipe Model.

It does not prescribe:

* Database schema.
* Recipe management application.
* Kitchen Display System.
* Inventory implementation.
* Cost accounting implementation.
* Production scheduler.
* Recommendation algorithm.
* AI model.

Implementation shall preserve the semantic distinction between:

```text
PRODUCT

RECIPE

RECIPE VERSION

INGREDIENT

INVENTORY ITEM

PREPARATION STEP

PRODUCTION EXECUTION

COST

AVAILABILITY
```

---

# 82. FINAL RULE

Before ECIP can reason reliably about the composition or preparation of a Product, it shall be able to determine:

> Which Recipe applies?

> Which Recipe Version is valid?

> What Ingredients and quantities are required?

> Which substitutions are explicitly permitted?

> Which Kitchen Stations and Equipment are required?

> What preparation steps and expected times apply?

> What allergen and dietary implications exist?

> Are all required Ingredients and resources currently available?

> Is the Recipe operationally feasible now?

> What level of Recipe information is the current actor authorized to access?

Only after these conditions are resolved may ECIP safely answer composition questions, calculate feasibility, recommend substitutions or support Product execution.

