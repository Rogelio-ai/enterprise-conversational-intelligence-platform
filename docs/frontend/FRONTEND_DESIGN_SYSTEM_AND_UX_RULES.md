# FRONTEND DESIGN SYSTEM AND UX RULES

**Project:** Restaurant Intelligence Platform
**Document Type:** Authoritative Frontend Design, UX, Interaction, Experience, Boundary and Change-Control Rules
**Status:** ACTIVE — AUTHORITATIVE
**Initial Scope:** Diner Experience
**Future Scope:** Diner, Host, Waiter, Kitchen, Cashier, Manager and future operational interfaces
**Applies To:** Frontend architecture, frontend functionality, frontend design, frontend/backend boundaries, UX implementation and Codex-assisted frontend changes

---

# 1. PURPOSE

This document defines the authoritative frontend design and user-experience rules for the Restaurant Intelligence Platform.

Its purpose is to ensure that every frontend surface is:

* consistent,
* intuitive,
* fast,
* accessible,
* responsive,
* reusable,
* maintainable,
* restaurant-brandable,
* channel-compatible,
* visually excellent,
* emotionally impressive,
* functionally correct,
* safely evolvable,
* and strictly separated from backend business authority.

This document also establishes the authoritative boundaries between:

```text
FUNCTIONALITY
and
DESIGN
```

```text
BACKEND
and
FRONTEND
```

and:

```text
FRONTEND FUNCTIONALITY
and
BACKEND FUNCTIONALITY
```

It additionally governs how frontend-related changes may be delegated to Codex.

This document governs frontend implementation unless a later explicit architectural decision supersedes a rule.

It is intentionally practical.

It MUST NOT evolve into a large design-governance project that delays production.

---

# 2. PRIMARY PRODUCT EXPERIENCE PRINCIPLE

The frontend exists to make the Restaurant Intelligence Platform easy and enjoyable to use.

The frontend MUST NOT become a second business-rules engine.

Canonical principle:

```text
USER
  ↓
FRONTEND
  ↓
AUTHORITATIVE API
  ↓
DOMAIN SERVICES
  ↓
AUTHORITATIVE RESULT
  ↓
FRONTEND PRESENTATION
```

Never:

```text
USER
  ↓
FRONTEND
  ↓
REIMPLEMENTED BUSINESS LOGIC
  ↓
BACKEND
```

---

# 3. EXPERIENCE OBJECTIVE

The user should normally understand:

1. where they are,
2. what they can do,
3. what just happened,
4. whether an action succeeded,
5. whether something requires attention,
6. what they should do next,

without understanding the internal architecture of the platform.

The UI MUST translate domain state into understandable interaction without changing domain truth.

---

# 4. USER EXPERIENCE PRIORITIES

Prioritize in this order:

1. Correctness
2. Clarity
3. Speed
4. Low interaction friction
5. Accessibility
6. Consistency
7. Responsive behavior
8. Visual excellence
9. Perceived intelligence
10. Brand quality
11. Delight
12. Decorative sophistication

Visual effects MUST NEVER make the system harder or slower to operate.

---

# 5. FRONTEND EXPERIENCE MODES

The platform supports three conceptual interaction modes:

```text
MANUAL UI
    │
    ├── buttons
    ├── menus
    ├── forms
    └── direct manipulation

CONVERSATIONAL UI
    │
    └── Digital Waiter

VOICE
    │
    └── future speech transport
```

They MUST converge on the same authoritative backend capabilities.

Conceptually:

```text
MANUAL UI ───────────────┐
                         │
CHAT → ORCHESTRATION ────┼──→ DOMAIN CAPABILITIES
                         │
VOICE → ORCHESTRATION ───┘
```

Business semantics MUST NOT depend on the interaction channel.

---

# 6. MANUAL UI MUST ALWAYS EXIST

Any important diner action available conversationally SHOULD also have an equivalent manual UI path.

Examples:

```text
"Quiero ver el menú"
        ↕
MENÚ button
```

```text
"Quiero ver mi pedido"
        ↕
MI PEDIDO
```

```text
"Quiero pagar"
        ↕
CUENTA / PAGAR
```

Conversation is an enhancement.

It MUST NOT make basic restaurant operation dependent on natural-language understanding.

---

# 7. MOBILE-FIRST DINER EXPERIENCE

The diner frontend MUST be designed mobile-first.

Primary expected devices:

```text
smartphone
    ↓
small tablet
    ↓
tablet
    ↓
desktop
```

Desktop behavior MUST remain correct, but diner UX decisions MUST primarily optimize for smartphone usage.

---

# 8. STAFF EXPERIENCE

Staff interfaces have different priorities.

Primary expected devices may include:

```text
tablet
POS terminal
desktop
kitchen display
mobile device
```

The same design system SHOULD be reused.

However:

```text
DINER UX ≠ STAFF UX
```

Diner experience prioritizes simplicity and guidance.

Staff experience prioritizes operational speed, information density and rapid repeated actions.

Do not force one identical layout onto every role.

---

# 9. RESPONSIVE DESIGN

The frontend MUST adapt fluidly rather than depend on a fixed screen resolution.

Use logical responsive ranges such as:

```text
SMALL
MEDIUM
LARGE
EXTRA LARGE
```

Exact implementation breakpoints may follow the selected frontend framework.

Avoid business logic based on breakpoints.

---

# 10. TOUCH-FIRST INTERACTION

Diner interfaces MUST be comfortable for touch.

Interactive targets SHOULD normally provide approximately:

```text
44 × 44 CSS px minimum effective touch area
```

Avoid tiny:

* icons,
* checkboxes,
* quantity controls,
* close buttons,
* links.

Critical actions MUST NOT depend on hover.

---

# 11. INFORMATION ARCHITECTURE

The diner should have a small number of persistent conceptual destinations.

Initial model:

```text
INICIO
MENÚ
MI PEDIDO
CUENTA
AYUDA
```

The exact visual implementation may use:

* bottom navigation,
* contextual header,
* drawers,
* tabs,
* contextual actions.

Do not create deep navigation trees.

---

# 12. PRIMARY DINER NAVIGATION

For mobile diner experience, prefer persistent access to the most important destinations.

Recommended conceptual navigation:

```text
┌─────────────────────────────────┐
│ Restaurant / Context            │
├─────────────────────────────────┤
│                                 │
│        CURRENT CONTENT          │
│                                 │
├─────────────────────────────────┤
│ Inicio | Menú | Pedido | Cuenta │
└─────────────────────────────────┘
```

Help/Digital Waiter may be exposed through a persistent contextual action rather than consuming permanent navigation space.

Final implementation may adapt this model based on usability.

---

# 13. NAVIGATION STATE

Navigation MUST NOT accidentally discard:

* OrderDraft,
* product configuration,
* payment state,
* continuation state,
* conversation context.

Changing screens is a presentation operation.

It MUST NOT implicitly cancel authoritative backend state.

---

# 14. BROWSER NAVIGATION

Where applicable:

* browser Back SHOULD behave predictably,
* refresh SHOULD recover authoritative state,
* deep links SHOULD fail safely,
* frontend-only state MUST NOT be the sole source of business truth.

After refresh, the frontend SHOULD reconstruct important state from backend APIs.

---

# 15. DINER SESSION CONTEXT

The frontend MUST understand the current authenticated diner context.

Conceptually:

```text
Restaurant
Location
RestaurantServiceSession
DinerSession
Conversation
```

The UI MUST NOT allow the diner to arbitrarily change authoritative tenant/location/session identifiers.

---

# 16. CLOSED SESSION

When backend reports:

```text
SESSION_CLOSED
```

the UI MUST clearly indicate that the previous restaurant session has ended.

It MUST NOT:

* revive the session,
* reuse the old access lifecycle,
* silently create another session,
* continue submitting commands against the closed session.

Provide an appropriate exit/re-entry experience.

---

# 17. DESIGN TOKENS

Visual values MUST be represented through reusable design tokens.

At minimum define tokens for:

```text
colors
typography
spacing
radius
borders
shadows
motion
z-index/elevation
```

Components SHOULD consume semantic tokens instead of scattered literal values.

---

# 18. SEMANTIC COLOR TOKENS

Prefer semantic names:

```text
background
surface
surface-elevated
text-primary
text-secondary
text-disabled
border
primary
primary-contrast
success
warning
danger
info
focus
```

Avoid components depending directly on arbitrary literal colors.

Bad:

```text
#16A34A
```

inside dozens of components.

Better:

```text
success
```

resolved by the active theme.

---

# 19. THEMING

The design architecture MUST support themes.

Initial platform themes:

```text
LIGHT
DARK
SYSTEM
```

The architecture SHOULD allow future restaurant branding without component rewrites.

Potential future branding:

```text
restaurant logo
primary brand color
secondary/accent color
selected typography
limited visual personality
```

Branding MUST operate through controlled theme tokens.

---

# 20. RESTAURANT BRANDING BOUNDARY

Restaurant customization MUST NOT permit arbitrary styling that breaks usability.

Restaurants may eventually customize selected identity properties.

They MUST NOT be able to override critical semantic meaning such as:

```text
danger
success
disabled
focus
payment uncertainty
critical alerts
```

in a way that destroys accessibility or consistency.

---

# 21. DARK MODE

Dark mode MUST be a real semantic theme.

Do not implement it by simply inverting colors.

Verify:

* contrast,
* elevated surfaces,
* borders,
* disabled states,
* error states,
* product imagery,
* dialogs,
* forms,
* payment interfaces.

---

# 22. TYPOGRAPHY

Use a small typography hierarchy.

Conceptual roles:

```text
display
heading-1
heading-2
heading-3
body
body-small
label
caption
price
```

Avoid excessive font sizes or arbitrary per-component typography.

---

# 23. READABILITY

Diner interfaces MUST prioritize readability.

Avoid:

* tiny text,
* low contrast,
* excessive uppercase,
* long centered paragraphs,
* dense administrative terminology.

Prices and important totals MUST be visually easy to identify.

---

# 24. SPACING

Use a consistent spacing scale.

Example conceptual scale:

```text
xs
sm
md
lg
xl
2xl
```

Do not introduce arbitrary margins and paddings unless necessary.

Whitespace is part of information hierarchy.

---

# 25. SHAPE AND RADIUS

Use consistent shape tokens for:

```text
buttons
cards
inputs
dialogs
chips
product images
drawers
```

Avoid each component inventing its own border radius.

---

# 26. ICONOGRAPHY

Use one consistent icon family where possible.

Icons MUST reinforce meaning.

Icons MUST NOT be the only representation of unfamiliar or critical actions.

Use labels, tooltips or context where appropriate.

---

# 27. IMAGES

Product imagery is optional for the initial pilot unless authoritative product image data exists.

The UI MUST work correctly without images.

If no image exists:

use a consistent neutral placeholder or image-free layout.

Do NOT fabricate product images.

---

# 28. COMPONENT ARCHITECTURE

Prefer reusable components over page-specific duplication.

Initial component families may include:

```text
AppShell
TopBar
BottomNavigation
PageHeader

Button
IconButton
TextInput
Select
Checkbox
Radio
QuantitySelector

Card
ProductCard
ProductList
ProductDetail
ChoiceGroup
ChoiceOption

DraftItem
DraftSummary
PriceSummary

OrderCard
OrderStatus

AccountSummary
PaymentMethodSelector
PaymentStatus

AssistanceRequestStatus
ContinuationPrompt

Dialog
Drawer
Toast
Alert
EmptyState
LoadingState
ErrorState
```

This is guidance, not a requirement to create every component before it is needed.

---

# 29. NO PREMATURE COMPONENT LIBRARY

Do NOT build a massive design system before building actual screens.

Rule:

```text
BUILD WHEN NEEDED
      ↓
REUSE WHEN REPEATED
      ↓
GENERALIZE WHEN PATTERN IS PROVEN
```

Not:

```text
DESIGN EVERY POSSIBLE COMPONENT
      ↓
months later
      ↓
build product
```

---

# 30. BUTTON HIERARCHY

Use a small action hierarchy.

Conceptually:

```text
PRIMARY
SECONDARY
TERTIARY
DESTRUCTIVE
```

A screen SHOULD normally have one visually dominant primary action.

Avoid multiple competing primary buttons.

---

# 31. DESTRUCTIVE ACTIONS

Destructive or difficult-to-reverse operations require clear wording.

Examples:

```text
Eliminar producto
Cancelar solicitud
Salir
```

Confirmation SHOULD be proportional to risk.

Do not require confirmation for every harmless action.

---

# 32. FORM DESIGN

Forms SHOULD:

* request only necessary information,
* provide clear labels,
* preserve entered information after recoverable errors,
* identify invalid fields near the field,
* avoid unnecessary modal chains.

Placeholder text MUST NOT replace field labels when persistent context is important.

---

# 33. VALIDATION OWNERSHIP

Frontend may perform presentation-level validation such as:

```text
required field empty
invalid local formatting
obviously malformed input
```

Backend remains authoritative for:

```text
business validity
ownership
availability
price
promotion
product configuration
payment rules
check rules
billing rules
session rules
```

Frontend validation improves UX.

It does NOT replace backend validation.

---

# 34. LOADING STATES

Any asynchronous action MUST provide feedback.

Avoid an apparently frozen interface.

Use context-appropriate:

```text
spinner
skeleton
progress indicator
disabled submitting state
```

Do not display a full-screen loader for small background operations unless necessary.

---

# 35. DOUBLE SUBMISSION

While an authoritative mutation is being submitted, UI SHOULD prevent accidental duplicate interaction where appropriate.

However, backend idempotency remains authoritative.

Frontend disabling alone MUST NEVER be considered sufficient idempotency protection.

---

# 36. OPTIMISTIC UI

Use optimistic UI only when failure is cheap and authoritative reconciliation is straightforward.

Do NOT optimistically claim success for critical operations such as:

```text
order confirmation
payment
settlement
invoice issuance
session closure
```

Wait for authoritative backend result.

---

# 37. ERROR EXPERIENCE

Users MUST NOT normally see:

```text
stack traces
SQL errors
HTTP internals
Python exception names
internal IDs without purpose
```

Translate controlled backend states into understandable UI.

Keep technical diagnostics in observability/logging channels.

---

# 38. ERROR LEVELS

Conceptual UX levels:

```text
INLINE
NOTICE
WARNING
BLOCKING ERROR
CRITICAL STATE
```

Use the least disruptive presentation appropriate to the situation.

Do not use modal dialogs for every error.

---

# 39. EXPERIENCE STATE MAPPING

The frontend MUST explicitly support the authoritative diner experience states.

Current known states include:

```text
OK
CLARIFICATION_REQUIRED
PRODUCT_UNAVAILABLE
CONFIGURATION_REQUIRED
ACTION_BLOCKED
STAFF_ASSISTANCE_REQUIRED
CONTINUATION_REQUIRED
PAYMENT_UNCERTAIN
SESSION_CLOSED
```

Frontend MUST NOT reinterpret these states into contradictory business meanings.

---

# 40. OK

`OK` means the requested operation or read completed successfully according to backend truth.

Show the relevant result.

Avoid unnecessary success dialogs for routine operations.

---

# 41. CLARIFICATION_REQUIRED

When:

```text
CLARIFICATION_REQUIRED
```

the frontend MUST present the authoritative alternatives or required information.

Never silently choose.

The UI SHOULD prefer selectable options when available rather than forcing additional typing.

---

# 42. CONFIGURATION_REQUIRED

When:

```text
CONFIGURATION_REQUIRED
```

show the missing required configuration.

Examples:

```text
Elige una guarnición
Elige el término
Selecciona una bebida
```

Only show choices allowed by authoritative backend data.

---

# 43. PRODUCT_UNAVAILABLE

Do not silently substitute another product.

Clearly indicate that the requested product is unavailable.

Alternative recommendations may be introduced later only through an explicit recommendation capability.

---

# 44. ACTION_BLOCKED

When:

```text
ACTION_BLOCKED
```

explain the reason at a user-appropriate level and show the valid next action if one exists.

Do not expose internal locking terminology unnecessarily.

---

# 45. STAFF_ASSISTANCE_REQUIRED

When:

```text
STAFF_ASSISTANCE_REQUIRED
```

show that the request was sent or that staff assistance is required according to durable backend evidence.

If request status is available, display it.

Do not claim that a staff member is coming unless the backend actually provides such evidence.

---

# 46. PAYMENT_UNCERTAIN

`PAYMENT_UNCERTAIN` is a special high-importance state.

The UI MUST NOT say:

```text
Pago rechazado
```

or:

```text
Pago realizado
```

unless authoritative state supports that conclusion.

The UI SHOULD clearly communicate:

```text
Estamos verificando el estado de su pago.
No vuelva a pagar por el momento.
```

Provide a status refresh/recovery path through existing backend capability.

Never encourage blind retry.

---

# 47. CONTINUATION_REQUIRED

When:

```text
CONTINUATION_REQUIRED
```

the diner experience MUST explicitly present the continuation decision.

Canonical conceptual UX:

```text
¿Desean algo más?

[ Sí, continuar ]

[ No, terminar ]
```

Do not infer NO from inactivity.

Do not automatically close after payment.

---

# 48. SESSION_CLOSED

When:

```text
SESSION_CLOSED
```

show a final session-ended experience.

Do not keep normal ordering navigation active.

Provide only actions appropriate for a closed session.

---

# 49. MENU EXPERIENCE

The menu MUST prioritize discovery.

Support navigation conceptually through:

```text
Agrupadores
    ↓
Familias
    ↓
Productos
```

and conversational discovery where available.

Do not require the diner to understand the internal catalog model.

---

# 50. MENU SEARCH AND FILTERING

If implemented, menu search/filtering MUST operate over authoritative available diner catalog data.

Do not create frontend-only availability truth.

---

# 51. PRODUCT CARD

A ProductCard SHOULD prioritize:

```text
product name
short description when useful
price
availability/orderability
configuration indicator
image when available
```

Avoid excessive metadata on menu cards.

Detailed information belongs in ProductDetail.

---

# 52. PRODUCT DETAIL

ProductDetail may show:

```text
name
description
principal ingredients when authoritative
price
included components
configurable choices
availability
additional relevant information
image when available
```

Do not display fabricated or inferred ingredients.

---

# 53. PRODUCT CONFIGURATION

Configuration UI MUST be generated from authoritative configuration contracts.

Support patterns such as:

```text
required single choice
optional single choice
required multiple choice
optional multiple choice
minimum selections
maximum selections
included components
```

The UI MUST visually distinguish required from optional choices.

---

# 54. COMPLEX COMMERCIAL PRODUCTS

The UX architecture MUST remain capable of representing:

```text
simple products
packages
combos
breakfasts
fixed meals
buffet-related products
configurable combinations
```

without assuming every menu item is a simple independent product.

Do not build speculative UI for structures not yet exposed by authoritative backend contracts.

---

# 55. ORDER DRAFT EXPERIENCE

The diner MUST always be able to understand what is currently in their draft.

Show:

```text
product
configuration
quantity
commercial amount
editable state
```

when authoritative data exists.

---

# 56. DRAFT IS NOT ACCEPTED ORDER

The UI MUST visually distinguish:

```text
DRAFT
```

from:

```text
CONFIRMED / ACCEPTED ORDER
```

Do not imply that food is being prepared before RestaurantOrder acceptance succeeds.

---

# 57. CONFIRM ORDER

Order confirmation is a significant action.

Before confirmation, show an understandable authoritative preview.

After confirmation succeeds, clearly communicate that the order was accepted.

If confirmation fails:

do not show success.

---

# 58. MULTIPLE ORDER ROUNDS

The diner experience MUST support multiple ordering rounds during one RestaurantServiceSession.

Do not assume one diner session equals one RestaurantOrder.

---

# 59. VIEW ORDER

The order experience SHOULD distinguish current draft from accepted orders.

Conceptually:

```text
MI PEDIDO

Por confirmar
...

Pedidos enviados
...
```

Use actual backend states.

---

# 60. ACCOUNT PREVIEW

Account preview is informational.

ABSOLUTE RULE:

```text
VIEW ACCOUNT
    ≠
CREATE CHECK
```

Opening the account screen MUST NOT itself:

* create a Check,
* freeze consumption,
* reserve payment exposure,
* block ordering.

---

# 61. ACCOUNT PRESENTATION

The diner SHOULD be able to understand:

```text
consumption
quantities
line amounts
totals
relevant payment state
```

according to authoritative projection.

Do not independently reconstruct financial truth from unrelated frontend state.

---

# 62. CHECK EXPERIENCE

When payment/check creation requires scope selection, present only valid backend-supported scopes.

Examples may include:

```text
Mi consumo
Toda la mesa
Personas seleccionadas
```

Do not assume a default when scope is ambiguous and financially significant.

---

# 63. PAYMENT EXPERIENCE

Payment UI MUST distinguish:

```text
payment method
payment provider/executor
payment status
```

without exposing unnecessary infrastructure terminology to diners.

---

# 64. CASH PAYMENT

Diner frontend MUST NOT operate CashSession.

Cash payment from diner experience means:

```text
request cash assistance
    ↓
staff/cashier handles physical cash
```

The UI should make this clear.

---

# 65. PAYMENT SUCCESS

Only show successful payment when authoritative backend state confirms it.

Do not infer payment success from:

```text
browser redirect
button click
provider window closing
frontend timeout
```

---

# 66. PAYMENT FAILURE

If backend confirms failure:

show a clear recoverable state when appropriate.

Do not confuse:

```text
FAILED
```

with:

```text
UNCERTAIN
```

---

# 67. POST-SETTLEMENT EXPERIENCE

After confirmed full settlement, preserve canonical sequence.

Conceptually:

```text
PAYMENT CONFIRMED
      ↓
Invoice option
      ↓
Printed paid account option
      ↓
Continuation decision
```

Slow invoice/printing operations MUST NOT unnecessarily block continuation once durable request/dispatch semantics permit progress.

---

# 68. INVOICE EXPERIENCE

For the initial diner pilot, invoice may route through staff assistance according to existing backend contracts.

Do not create frontend fiscal authority that does not exist in backend.

---

# 69. PAID CHECK PRINTING

Printing is explicit.

Do NOT automatically print after payment.

Diner request:

```text
Quiero mi cuenta impresa
```

routes through the existing operational-request boundary.

Staff remains responsible for authorized paid-print dispatch where current backend rules require it.

---

# 70. HUMAN ASSISTANCE

Human assistance MUST remain easily reachable.

The Digital Waiter must never trap the diner.

A diner should have a clear path to request staff help.

---

# 71. DIGITAL WAITER EXPERIENCE

The Digital Waiter SHOULD feel integrated into the restaurant experience rather than like a generic chatbot.

It should understand the current context through backend orchestration.

Examples:

```text
show menu
show products
add item
configure item
review order
confirm
view account
request payment
request assistance
continuation
```

The frontend MUST NOT implement natural-language business interpretation itself.

---

# 72. DIGITAL WAITER PRESENTATION

Conversational responses SHOULD combine structured UI with conversation.

Instead of only:

```text
Tenemos Coca-Cola, Sprite y Fanta.
```

prefer:

```text
Digital Waiter message

[ Coca-Cola card ]
[ Sprite card ]
[ Fanta card ]
```

when structured product data is available.

Conversation and direct manipulation SHOULD complement each other.

---

# 73. CONVERSATION DOES NOT REPLACE UI

The diner should not have to type complex commands when a direct control is easier.

Use conversation where it reduces friction.

Use direct controls where they are faster.

---

# 74. CONVERSATIONAL CLARIFICATION

When backend returns structured clarification:

render it as interactive options where possible.

Example:

```text
¿Cuál desea?

[ Coca-Cola 355 ml ]
[ Coca-Cola 600 ml ]
```

Selection should route through the same orchestration/business capability.

---

# 75. VOICE READINESS

Frontend components SHOULD be designed so future voice interaction can trigger the same actions.

Do not couple components to keyboard/mouse-only assumptions.

Voice transport is NOT required for initial frontend implementation unless separately authorized.

---

# 76. ACCESSIBILITY

Accessibility is part of the product.

At minimum support:

* sufficient contrast,
* semantic HTML,
* keyboard navigation where applicable,
* visible focus,
* accessible labels,
* screen-reader-friendly controls,
* meaningful status announcements,
* appropriate touch target sizes.

---

# 77. COLOR MUST NOT BE THE ONLY SIGNAL

Never communicate critical state exclusively through color.

Bad:

```text
red = failed
green = success
```

Better:

```text
✓ Pago confirmado
⚠ Pago pendiente de verificación
```

with accessible text and semantics.

---

# 78. FOCUS MANAGEMENT

Dialogs, drawers and important state transitions MUST manage focus appropriately.

Keyboard users must not become trapped or lose navigation context.

---

# 79. MOTION

Motion should communicate:

* relationship,
* transition,
* feedback.

Avoid decorative animation that slows restaurant interaction.

Respect reduced-motion preferences where practical.

---

# 80. PERFORMANCE

Restaurant UX must feel fast.

Prioritize:

```text
fast initial render
small interaction latency
efficient API usage
reasonable bundle size
image optimization
lazy loading where useful
```

Do not sacrifice correctness for perceived speed.

---

# 81. NETWORK CONDITIONS

Restaurant networks may be imperfect.

Frontend MUST handle:

```text
slow request
temporary disconnect
timeout
retryable read
non-retryable mutation uncertainty
```

carefully.

Do not blindly retry financial or order mutations.

---

# 82. OFFLINE BOUNDARY

Do NOT invent full offline ordering for the initial pilot.

If network is unavailable:

show a clear state.

Offline mutation synchronization requires explicit future architecture.

---

# 83. API ERROR HANDLING

Centralize common API error handling where practical.

Use authoritative experience states first.

HTTP status alone SHOULD NOT determine diner business meaning when a structured backend state exists.

---

# 84. FRONTEND STATE OWNERSHIP

Separate:

```text
SERVER STATE
UI STATE
```

Server state includes:

```text
menu
product availability
OrderDraft
accepted orders
account
Check
Payment
continuation
operational requests
```

UI state includes:

```text
selected tab
open dialog
expanded section
temporary input
local display preference
```

Do not promote UI state into business truth.

---

# 85. SERVER STATE RECONCILIATION

After important mutations, reconcile with authoritative backend state.

Examples:

```text
confirm order
payment
continuation
assistance request
```

Do not rely indefinitely on locally predicted state.

---

# 86. CACHING

Caching may improve performance but MUST respect business freshness.

Be particularly careful with:

```text
price
promotion
availability
draft
account
payment status
continuation
```

Stale cache MUST NOT override authoritative responses.

---

# 87. INTERNATIONALIZATION

User-facing strings SHOULD be externalized from business components.

Initial language:

```text
Spanish
```

Architecture SHOULD permit future additional languages.

Do not implement a large translation-management system for the pilot.

---

# 88. LOCALE FORMATTING

Use locale-aware formatting for:

```text
currency
dates
times
numbers
```

Do not manually concatenate currency symbols throughout components.

---

# 89. MEXICO INITIAL CONTEXT

Initial restaurant deployment is expected to support Mexican operational context.

Frontend should correctly present:

```text
MXN
Mexican date/time conventions where appropriate
CFDI-related diner terminology where exposed
```

without hardcoding domain rules that belong to backend.

---

# 90. SECURITY

Never expose frontend secrets.

Frontend MUST NOT contain:

```text
merchant credentials
PAC credentials
database credentials
server secrets
private API keys
```

Only public client configuration explicitly intended for frontend use may be bundled.

---

# 91. AUTHENTICATION DATA

Store diner authentication/session material according to the existing security architecture.

Do not introduce alternative authentication mechanisms merely for frontend convenience.

---

# 92. CROSS-TENANT SAFETY

Frontend routing and state MUST NOT permit one restaurant/location/diner to access another's data.

Backend remains authoritative.

Frontend filters are never security boundaries.

---

# 93. PRIVACY

Only request and display diner information necessary for the experience.

Initial diner identity:

```text
Name
Email — optional but recommended
Access Code
```

Do not expand personal-data collection without product need.

---

# 94. EMPTY STATES

Every important collection screen SHOULD have a deliberate empty state.

Examples:

```text
No has agregado productos todavía.
```

```text
Aún no tienes pedidos enviados.
```

Empty state SHOULD explain the useful next action.

---

# 95. SUCCESS FEEDBACK

Routine successful operations should receive proportional feedback.

Examples:

```text
Producto agregado
Pedido enviado
Solicitud enviada
```

Avoid modal success dialogs for every action.

---

# 96. STATUS VISIBILITY

Longer-running operations need visible state.

Examples:

```text
payment verification
staff assistance request
invoice request
print request
```

Do not leave the user wondering whether the request was received.

---

# 97. CONFIRMATION POLICY

Require confirmation when an action:

* has meaningful financial consequences,
* is difficult to reverse,
* closes a session,
* removes significant user work.

Do not confirm harmless navigation.

---

# 98. ACCESS CODE EXPERIENCE

Diner entry SHOULD be simple.

Conceptually:

```text
Nombre

Email
(opcional)

Código de acceso

[ Entrar ]
```

Do not expose tenant/location IDs.

Access-code validation remains backend authoritative.

---

# 99. EMAIL EXPERIENCE

Email is optional but recommended.

Explain its value only when useful.

Do not block diner entry solely because optional email is absent unless future explicit policy changes.

---

# 100. RETURNING DINER PERSONALIZATION

Advanced returning-diner personalization is POST-PILOT unless explicitly promoted.

Do not block frontend completion on:

```text
recommendation engine
CRM profile
visit-history personalization
predictive suggestions
```

---

# 101. ANALYTICS

Frontend MAY emit product analytics events later.

Analytics MUST NOT:

* become business authority,
* block user actions,
* expose sensitive data unnecessarily.

Initial pilot should prioritize operational functionality over exhaustive analytics instrumentation.

---

# 102. OBSERVABILITY

Frontend errors that materially affect operation SHOULD be observable.

Capture enough diagnostic context to investigate failures without exposing sensitive information.

---

# 103. TESTING STRATEGY

Frontend tests should prioritize high-value behavior.

Focus on:

```text
critical components
navigation
business-state rendering
important user journeys
API integration boundaries
error states
payment uncertainty
continuation
```

Do not attempt exhaustive snapshot testing of every visual variation.

---

# 104. E2E PRIORITY

The highest-value frontend validation is the real diner journey.

Eventually certify:

```text
enter table
→ browse menu
→ configure product
→ create draft
→ confirm order
→ view accepted order
→ view account
→ pay
→ request invoice/print if desired
→ continuation
```

This belongs primarily to WS-32 End-to-End Integration rather than blocking every individual frontend component.

---

# 105. FRONTEND DEVELOPMENT RULE

Build vertical usable slices.

Preferred:

```text
Access
↓
Menu
↓
Product
↓
Draft
↓
Order
↓
Account
↓
Payment
↓
Post-payment
```

Avoid:

```text
build every button
build every card
build every modal
build every service
then attempt integration
```

---

# 106. FRONTEND IMPLEMENTATION SEQUENCE

Recommended WS-30-C sequence:

```text
C1 — Frontend Foundation + Diner Access
C2 — Menu + Product + Configuration
C3 — Draft + Order
C4 — Account + Payment
C5 — Assistance + Post-Settlement + Continuation
C6A — Digital Waiter Backend Completion
C6B — Digital Waiter UI Integration
C7 — Focused Diner Journey Validation
```

These are implementation slices, not mandatory independent architectural workstreams.

Merge slices only when their changes are genuinely dependent and cannot be safely implemented independently.

Do NOT automatically create separate review/certification workstreams for every slice.

---

# 107. FRONTEND FOUNDATION

Before feature screens, establish only the minimum foundation needed:

```text
frontend application
routing
API client
authentication/session integration
theme tokens
layout shell
common error handling
server-state strategy
basic reusable controls
```

Do not spend excessive time building infrastructure before the first functional screen.

---

# 108. TECHNOLOGY SELECTION

Before implementation, inspect the repository for an existing frontend stack.

Rule:

```text
REUSE EXISTING STACK FIRST
```

Do not introduce a second frontend framework without a concrete reason.

If no frontend exists, select the smallest production-suitable stack consistent with project requirements.

Technology selection MUST be explicit before implementation begins.

---

# 109. THIRD-PARTY UI LIBRARIES

A component library may be used when it accelerates development.

Avoid libraries that:

* impose difficult branding constraints,
* produce poor accessibility,
* dramatically increase bundle size,
* encourage business logic in components,
* make maintenance dependent on excessive abstraction.

Prefer proven, maintained tools.

---

# 110. DESIGN CONSISTENCY RULE

When two screens represent the same concept, they SHOULD use the same interaction pattern.

Examples:

```text
quantity selection
confirmation
error presentation
loading
empty state
price display
```

Consistency reduces learning cost.

---

# 111. DO NOT OVERDESIGN THE PILOT

Initial production-quality does NOT mean every screen needs:

```text
complex animations
custom illustrations
advanced personalization
dozens of themes
microinteraction choreography
```

Production quality means:

```text
correct
clear
fast
accessible
consistent
reliable
visually professional
visually memorable
```

---

# 112. DOMAIN AUTHORITY BOUNDARY

The frontend MUST NEVER independently determine:

```text
final product availability
authoritative price
promotion eligibility
commercial total
tax
Check liability
payment success
Settlement truth
cash expected amount
invoice validity
inventory consumption
session closure eligibility
```

Those remain backend responsibilities.

---

# 113. FRONTEND AUTHORITY

Frontend owns:

```text
visual presentation
navigation
interaction state
layout
responsive behavior
input affordances
display formatting
accessibility
theme selection
client-side convenience validation
visual polish
microinteractions
perceived quality
```

This boundary is mandatory.

---

# 114. FUTURE STAFF FRONTEND

The same design foundation will later support:

```text
HOST
WAITER
KITCHEN
CASHIER
MANAGER
```

But WS-30-C MUST NOT prematurely implement those interfaces.

---

# 115. FUTURE MANAGEMENT EXPERIENCE

Advanced dashboards and Intelligent Business Advisor experiences are explicitly outside WS-30-C.

Do not introduce:

```text
executive BI
predictive analytics
AI advisor
advanced alerts
business recommendations
```

into the diner frontend workstream.

---

# 116. PILOT COMPLETION CRITERION

The diner frontend is pilot-ready when a real diner can complete the intended journey without technical knowledge and without developers manually manipulating backend state.

The UI must allow the diner to understand what is happening at every critical point.

Functional correctness alone is not enough.

The essential journey must also feel production-quality.

---

# 117. ANTI-OVERENGINEERING RULE

No frontend capability enters the pilot critical path unless its absence:

1. prevents the diner from completing the essential journey,
2. creates incorrect business behavior,
3. creates a serious security or production risk,
4. creates unacceptable usability,
5. prevents an acceptable professional visual experience,
6. removes an essential Restaurant Intelligence Platform value proposition.

Otherwise:

```text
POST-PILOT
```

---

# 118. IMPLEMENTATION DECISION RULE

When choosing between:

```text
more abstraction
```

and:

```text
a small correct reusable implementation
```

prefer the smallest correct implementation that preserves future extensibility.

Do not optimize for hypothetical future complexity.

---

# 119. UX DECISION RULE

When choosing between:

```text
technically impressive
```

and:

```text
obvious to the diner
```

prefer:

```text
OBVIOUS TO THE DINER
```

When both can be achieved without unnecessary complexity:

```text
OBVIOUS
+
BEAUTIFUL
+
FAST
```

is the target.

---

# 120. CORE EXPERIENCE PRINCIPLE

The best frontend is not the one that exposes the sophistication of the Restaurant Intelligence Platform.

The best frontend is the one that hides that sophistication behind a simple, trustworthy and impressive experience.

Canonical objective:

```text
POWERFUL BACKEND
      +
SIMPLE EXPERIENCE
      +
PREMIUM PRESENTATION
      =
RESTAURANT INTELLIGENCE PLATFORM
```

The diner should feel:

```text
"I can easily get what I need."
```

The restaurant should receive:

```text
correct
controlled
auditable
authoritative
business operations
```

without forcing the diner to understand the complexity underneath.

---

# 121. WOW EXPERIENCE STANDARD

The Restaurant Intelligence Platform frontend MUST create a strong positive first impression and sustain that impression during real use.

The target reaction is not merely:

```text
"It works."
```

The target reactions are:

```text
FIRST IMPRESSION
"Wow, this looks impressive."

FIRST USE
"Wow, this is incredibly easy to use."

REAL OPERATION
"Wow, this does much more than I expected."

RESTAURANT OWNER
"Wow, this platform exceeds my expectations."
```

This is a strategic product requirement.

---

# 122. WOW MUST COME FROM QUALITY, NOT DECORATION

The platform MUST NOT attempt to create visual impact through excessive:

* animation,
* gradients,
* effects,
* visual noise,
* oversized graphics,
* unnecessary motion,
* decorative complexity.

The WOW effect should emerge from:

```text
beautiful visual design
+
exceptional clarity
+
fluid interaction
+
intelligent behavior
+
fast response
+
useful contextual information
+
attention to detail
```

The product should feel premium without feeling complicated.

---

# 123. VISUAL QUALITY STANDARD

Every principal screen SHOULD feel intentionally designed.

Avoid interfaces that look like:

```text
generic admin panel
developer tool
raw CRUD application
template-based SaaS
unfinished prototype
```

The Restaurant Intelligence Platform should have a recognizable product identity.

The visual language should communicate:

```text
modern
premium
trustworthy
intelligent
clean
professional
warm
restaurant-oriented
advanced
```

---

# 124. FIRST-IMPRESSION DESIGN

A first-time user should immediately understand that the platform is a high-quality product.

Important first-impression elements include:

```text
clear hierarchy
excellent typography
balanced whitespace
professional imagery where available
high-quality iconography
consistent component styling
polished transitions
clear restaurant identity
excellent mobile presentation
```

The first screen MUST NOT feel empty, generic or technically oriented.

---

# 125. PERCEIVED INTELLIGENCE

The frontend SHOULD make the intelligence of the platform visible through useful behavior rather than technical terminology.

Examples:

Instead of exposing:

```text
CONFIGURATION_REQUIRED
```

show the diner the exact missing choice.

Instead of exposing:

```text
CLARIFICATION_REQUIRED
```

present the relevant alternatives.

Instead of asking the diner to navigate multiple screens unnecessarily:

surface the obvious next action.

The user should feel:

```text
"The system understands what I am trying to do."
```

---

# 126. MICROINTERACTION QUALITY

Small interactions contribute strongly to perceived quality.

Examples include:

```text
adding a product
changing quantity
opening product detail
confirming an order
receiving assistance acknowledgement
payment confirmation
switching sections
```

These interactions SHOULD provide immediate, subtle and polished feedback.

Motion should be:

```text
short
smooth
purposeful
non-blocking
```

Never slow down restaurant operation for decoration.

---

# 127. DELIGHT WITHOUT FRICTION

The frontend MAY include moments of delight when they reinforce the experience.

Examples:

```text
subtle add-to-order animation
clean confirmation transition
context-aware welcome
restaurant-branded presentation
pleasant empty states
intelligent next-action suggestions
```

But delight MUST NEVER compete with:

```text
speed
clarity
accessibility
operational correctness
```

---

# 128. PREMIUM DINER EXPERIENCE

The diner frontend should feel closer to a premium consumer application than to a traditional restaurant POS.

The diner should not feel that they are interacting with administrative software.

The experience SHOULD feel:

```text
natural
visual
direct
personal
fast
guided
modern
```

Product discovery should be attractive enough to support commercial conversion without becoming visually overwhelming.

---

# 129. PRODUCT PRESENTATION QUALITY

Products are a central commercial element.

Where authoritative information exists, product presentation SHOULD use:

```text
strong product name
clear price
concise description
appealing image
important ingredients
configuration indicators
availability
```

Cards and product detail screens SHOULD make products desirable and easy to understand.

The menu is not merely a database listing.

It is part of the restaurant's sales experience.

---

# 130. OWNER WOW EXPERIENCE

The restaurant owner must perceive value beyond individual operational functions.

The owner experience should communicate:

```text
control
professionalism
visibility
automation
intelligence
consistency
operational maturity
technological leadership
```

Even before advanced Business Intelligence and Advisor capabilities are implemented, the operational frontend should make clear that the restaurant is running on an integrated intelligence platform.

The owner should feel:

```text
"This is much more than a POS."
```

and ideally:

```text
"This is more than I expected."
```

---

# 131. FUNCTIONAL WOW

The strongest WOW moments SHOULD come from functionality.

Examples:

```text
diner enters with a simple access code
menu immediately knows the active restaurant/location
product configuration is guided automatically
Digital Waiter understands what the diner wants
order and account are always synchronized
payment state is trustworthy
staff assistance is requested without leaving the experience
post-payment continuation is intelligently managed
```

A visually beautiful system with clumsy workflows does NOT satisfy the WOW standard.

---

# 132. ZERO-DEAD-END EXPERIENCE

The user SHOULD rarely encounter a screen where they do not know what to do next.

Whenever possible, present:

```text
current state
+
reason
+
valid next action
```

Not:

```text
Action blocked.
```

Prefer:

```text
Your account is currently being finalized.

[ View account ]
[ Ask for assistance ]
```

using authoritative available actions.

---

# 133. PROGRESSIVE DISCLOSURE

The interface MUST NOT expose all platform complexity at once.

Show users only what they need in the current context.

Conceptually:

```text
SIMPLE SURFACE
      ↓
POWERFUL CAPABILITY UNDERNEATH
```

This is essential to the WOW experience.

Users should discover sophistication progressively rather than confront it immediately.

---

# 134. RESPONSIVE WOW

The product MUST feel intentionally designed on every supported device.

Mobile must not look like a compressed desktop application.

Desktop must not look like a stretched mobile interface.

Each viewport should feel native to its form factor while sharing the same design system.

---

# 135. CONSISTENCY AS QUALITY

Inconsistent interfaces destroy perceived quality quickly.

The same concepts MUST behave consistently across the platform:

```text
buttons
navigation
status
confirmation
errors
loading
selection
totals
payment state
assistance
```

A user who learns one part of the platform should transfer that knowledge to another.

---

# 136. PERFORMANCE IS PART OF DESIGN

A beautiful interface that feels slow is not premium.

Perceived performance MUST be considered part of the visual experience.

Prioritize:

```text
immediate interaction feedback
skeleton states instead of blank screens
progressive data loading
optimized images
smooth navigation
minimal unnecessary requests
```

---

# 137. TRUST IS PART OF WOW

Financial and operational confidence is more important than visual spectacle.

The user must trust that:

```text
the order was received
the amount is correct
the payment state is real
the request for assistance exists
the session state is accurate
```

Trustworthy behavior reinforces the premium experience.

---

# 138. DESIGN REVIEW QUESTIONS

For every important screen or journey, ask:

```text
Is it correct?

Is it obvious?

Is it fast?

Is it visually excellent?

Does it feel polished?

Does it feel intelligent?

Would a first-time user be impressed?

Would a diner enjoy using it?

Would a restaurant owner proudly show it to someone else?

Does it feel like a finished commercial product rather than a developer interface?
```

If correctness is NO:

do not ship.

If usability is NO:

improve it.

If visual quality is clearly mediocre:

improve it before considering the experience production-ready.

---

# 139. WOW WITHOUT OVERENGINEERING

The WOW requirement MUST NOT become an excuse for endless frontend development.

Use the rule:

```text
WOW THROUGH HIGH-IMPACT DETAILS
NOT THROUGH MAXIMUM FEATURE COUNT
```

Prioritize the elements users notice most:

```text
first screen
navigation
menu
product presentation
ordering
account
payment
Digital Waiter
feedback
transitions
restaurant branding
```

Do not postpone production to perfect low-impact decorative details.

---

# 140. PILOT VISUAL READINESS

A frontend is not considered pilot-ready merely because all endpoints work.

Before pilot launch, the critical diner journey MUST satisfy both:

```text
FUNCTIONAL READINESS
+
EXPERIENCE READINESS
```

Experience readiness means the essential journey is:

```text
visually polished
consistent
responsive
clear
pleasant
trustworthy
professional
impressive
```

---

# 141. FINAL EXPERIENCE OBJECTIVE

The Restaurant Intelligence Platform should create three successive reactions:

```text
SEE IT
   ↓
"Wow."

USE IT
   ↓
"Wow, this is incredibly easy."

UNDERSTAND WHAT IT DOES
   ↓
"Wow, this is far more powerful than I expected."
```

For the restaurant owner:

```text
"This makes my restaurant feel more advanced,
more controlled,
more professional,
and more intelligent."

"This is more than I expected."
```

This experience standard applies initially to the diner frontend and later extends to staff and management interfaces.

---

# 142. DESIGN DIRECTION BEFORE SCREEN IMPLEMENTATION

Frontend implementation MUST NOT allow each screen to invent its own visual style.

Before substantial screen development, establish one coherent visual direction covering at least:

```text
visual personality
base palette
surface hierarchy
typography
spacing
radius
button language
card language
navigation model
iconography
motion behavior
light/dark behavior
restaurant-branding boundary
```

This direction should be implemented through the design tokens and reusable components defined in this document.

The purpose is not to delay implementation.

The purpose is to prevent inconsistent visual decisions during implementation.

---

# 143. VISUAL IDENTITY MUST FEEL ORIGINAL

The Restaurant Intelligence Platform SHOULD avoid looking like an unchanged third-party UI template.

Third-party components may accelerate implementation, but the final product should possess its own recognizable visual personality.

Avoid the impression:

```text
"this looks like another generic dashboard"
```

Target:

```text
"this looks like the Restaurant Intelligence Platform"
```

---

# 144. RESTAURANT EMOTIONAL CONTEXT

Restaurant interaction is not purely administrative.

The diner experience may involve:

```text
hunger
anticipation
choice
social interaction
celebration
urgency
payment
service expectations
```

The visual experience SHOULD therefore be warmer and more inviting than a traditional enterprise operations interface.

However:

```text
WARM
≠
CHILDISH

PREMIUM
≠
COLD

MODERN
≠
COMPLICATED
```

---

# 145. VISUAL HIERARCHY MUST GUIDE ACTION

Every screen SHOULD make visually obvious:

```text
where the user is
what matters most
what can be done
what the primary next action is
```

The user SHOULD NOT need to scan the entire screen to understand the next step.

Primary actions should emerge naturally from hierarchy rather than from excessive visual emphasis.

---

# 146. COMMERCIAL PRESENTATION

The diner frontend is also a commercial interface.

Good UX can increase:

```text
product discovery
confidence
conversion
average ticket
successful configuration
additional ordering rounds
```

without using manipulative dark patterns.

The system SHOULD help the diner discover relevant restaurant offerings clearly and attractively.

Do not manipulate users into unintended purchases.

---

# 147. DIGITAL WAITER AS A SIGNATURE EXPERIENCE

The Digital Waiter SHOULD become one of the signature experiences of the Restaurant Intelligence Platform.

Its visual integration should make it feel like a natural extension of the restaurant rather than a separate chat application.

It MAY appear through:

```text
contextual assistant surface
floating action
integrated conversation panel
contextual suggestions
structured conversational cards
```

Exact implementation should favor simplicity and mobile usability.

---

# 148. STRUCTURED INTELLIGENCE OVER TEXT WALLS

Whenever backend orchestration provides structured information, the frontend SHOULD prefer visual interaction over long conversational paragraphs.

Examples:

```text
products → cards
choices → selectors
payment methods → actionable options
ambiguity → candidate buttons
account → structured financial summary
continuation → explicit decision controls
```

Digital Waiter text should explain and guide.

Structured UI should perform the interaction whenever it is more efficient.

---

# 149. UX SHOULD ANTICIPATE THE NEXT LIKELY ACTION

Where authoritative domain state makes the next step obvious, the UI SHOULD surface it.

Examples:

```text
draft ready
→ Review order

order accepted
→ View order / Continue ordering

account requested
→ Select payment scope if necessary

payment confirmed
→ Invoice / Printed account

post-settlement complete
→ ¿Desean algo más?
```

This should be deterministic from backend state.

Do not create speculative AI behavior merely to anticipate actions.

---

# 150. FRONTEND SUCCESS CRITERION

Frontend success is NOT:

```text
all screens implemented
```

Frontend success is:

```text
essential workflows complete
+
business truth preserved
+
excellent usability
+
strong visual identity
+
premium perceived quality
+
high user confidence
```

The implementation should make users want to continue using the product.

---

# 151. PRODUCT PRIDE STANDARD

The frontend SHOULD reach a quality level where:

```text
a diner would recommend the experience

staff would prefer using it over older systems

a restaurant owner would proudly demonstrate it

the product team would confidently show it to a prospective customer
```

This is not a requirement for decorative perfection.

It is a requirement for overall product quality.

---

# 152. FINAL AUTHORITATIVE EXPERIENCE RULE

Every frontend decision should contribute to at least one of:

```text
CORRECTNESS
CLARITY
SPEED
USABILITY
ACCESSIBILITY
CONSISTENCY
TRUST
VISUAL EXCELLENCE
PERCEIVED INTELLIGENCE
COMMERCIAL VALUE
```

If a frontend change contributes to none of these:

do not add it.

The final objective is:

```text
ENTERPRISE-GRADE POWER
        +
CONSUMER-GRADE SIMPLICITY
        +
PREMIUM VISUAL QUALITY
        +
INTELLIGENT EXPERIENCE
        =
RESTAURANT INTELLIGENCE PLATFORM
```

---

# 153. AUTHORITATIVE IMPLEMENTATION BOUNDARIES

From the beginning of frontend implementation, every requested change MUST respect explicit architectural boundaries.

At minimum distinguish:

```text
FUNCTIONALITY
        ↕
DESIGN
```

```text
BACKEND
        ↕
FRONTEND
```

```text
BACKEND FUNCTIONALITY
        ↕
FRONTEND FUNCTIONALITY
```

These boundaries exist to prevent:

```text
responsibility leakage
business-rule duplication
uncontrolled coupling
accidental redesign
unnecessary backend changes
unnecessary frontend changes
regressions
collateral damage
```

No implementation request should begin until the responsibility of the requested change is understood.

---

# 154. FUNCTIONALITY VS DESIGN BOUNDARY

Functionality answers:

```text
WHAT DOES THE SYSTEM DO?
```

Design answers:

```text
HOW DOES THE USER EXPERIENCE AND INTERACT WITH IT?
```

Examples of functionality:

```text
join diner session
retrieve menu
configure product
add product to draft
confirm order
retrieve account
initiate payment
request assistance
answer continuation decision
```

Examples of design:

```text
visual hierarchy
color
typography
spacing
layout
animation
component appearance
navigation presentation
responsive adaptation
interaction feedback
```

The two collaborate but MUST NOT be treated as the same responsibility.

---

# 155. DESIGN MUST NOT CHANGE BUSINESS SEMANTICS

A design change MUST NOT silently alter:

```text
business rules
API semantics
domain state
financial state
session ownership
order lifecycle
payment lifecycle
authorization
availability
price
promotion
settlement
billing
inventory
```

Example:

Changing:

```text
button position
```

MUST NOT cause:

```text
different backend action
different payment behavior
different business validation
```

unless the requested change explicitly includes that functional change.

---

# 156. FUNCTIONAL CHANGE MUST NOT TRIGGER UNRELATED REDESIGN

A functional change MUST NOT automatically authorize:

```text
visual redesign
navigation redesign
theme replacement
component-library replacement
CSS restructuring
unrelated UX changes
```

unless those changes are required by the requested functionality.

Canonical rule:

```text
FUNCTIONAL CHANGE
        ≠
DESIGN REDESIGN
```

---

# 157. DESIGN CHANGE MUST NOT TRIGGER UNRELATED FUNCTIONAL CHANGE

Likewise:

```text
DESIGN CHANGE
        ≠
FUNCTIONAL REDESIGN
```

A request to improve:

```text
visual appearance
spacing
typography
layout
responsive behavior
microinteraction
```

does not authorize changes to backend business behavior.

---

# 158. BACKEND VS FRONTEND BOUNDARY

The backend is authoritative for business truth.

The frontend is authoritative for presentation and interaction.

Canonical architecture:

```text
FRONTEND
    │
    │ user intention
    ↓
BACKEND
    │
    │ authoritative decision
    ↓
FRONTEND
    │
    │ understandable presentation
    ↓
USER
```

The frontend requests.

The backend decides.

The frontend presents.

---

# 159. BACKEND AUTHORITY

Backend owns authoritative decisions concerning:

```text
authentication
authorization
tenant ownership
organization ownership
location ownership
session validity
product availability
product configuration validity
pricing
promotions
commercial totals
order acceptance
Check state
financial liability
payment state
Settlement state
cash management
billing
fiscal evidence
inventory consumption
session closure eligibility
idempotency
concurrency
transactional invariants
```

Frontend MUST NOT independently reproduce these decisions.

---

# 160. FRONTEND FUNCTIONAL AUTHORITY

Frontend functionality owns client-side behavior necessary to let the user interact with backend capabilities.

Examples:

```text
screen navigation
form interaction
temporary form state
selected UI options
opening/closing dialogs
display filtering over already-authorized data
presentation sorting
loading state
visual feedback
local formatting
focus management
responsive interaction
theme preference
accessibility behavior
```

This functionality is legitimate frontend functionality because it does not establish business truth.

---

# 161. FRONTEND MUST NOT BECOME BUSINESS AUTHORITY

Frontend MUST NOT decide:

```text
whether a diner may order
whether a product is truly available
what a product ultimately costs
whether a promotion applies
whether an order is accepted
whether a Check can be created
whether payment succeeded
whether a Settlement exists
whether an invoice is valid
whether a diner or table may close
```

It may present these outcomes only after receiving authoritative evidence.

---

# 162. FRONTEND CONVENIENCE VALIDATION

Frontend MAY perform convenience validation to improve interaction.

Examples:

```text
required field empty
invalid email syntax
invalid local character count
obvious input-format problem
```

But:

```text
CLIENT VALIDATION
        ≠
BUSINESS VALIDATION
```

Backend MUST still validate authoritative requirements.

---

# 163. API CONTRACT BOUNDARY

The API contract is the formal boundary between frontend and backend.

Frontend SHOULD consume explicit API contracts rather than depend on:

```text
database structure
ORM models
backend implementation details
internal service classes
internal exceptions
private backend constants
```

Backend changes that preserve API semantics SHOULD normally remain invisible to frontend.

Frontend design changes SHOULD normally remain invisible to backend.

---

# 164. NO DATABASE ACCESS FROM FRONTEND

Frontend MUST NEVER access the platform database directly.

Canonical:

```text
FRONTEND
    ↓
API
    ↓
DOMAIN
    ↓
PERSISTENCE
```

Never:

```text
FRONTEND
    ↓
DATABASE
```

---

# 165. NO BACKEND WORKAROUNDS IN FRONTEND

If backend lacks an authoritative capability required for correct operation, frontend MUST NOT invent a substitute business implementation.

Instead:

```text
IDENTIFY GAP
    ↓
CLASSIFY AS BACKEND
    ↓
IMPLEMENT MINIMUM BACKEND CAPABILITY
    ↓
EXPOSE CONTRACT
    ↓
CONSUME FROM FRONTEND
```

This is particularly important for the Digital Waiter.

Frontend MUST NOT implement natural-language business interpretation merely because a backend orchestration endpoint is incomplete.

---

# 166. NO FRONTEND WORKAROUNDS IN BACKEND

Likewise, backend SHOULD NOT accumulate presentation-specific logic merely to avoid implementing correct frontend interaction.

Examples that normally belong to frontend:

```text
modal visibility
button layout
screen navigation
CSS theme
animation timing
responsive layout
local display formatting
```

Keep presentation responsibility in the presentation layer.

---

# 167. CHANGE CLASSIFICATION BEFORE IMPLEMENTATION

Every change SHOULD first be classified as one or more of:

```text
DESIGN
FRONTEND FUNCTIONALITY
BACKEND FUNCTIONALITY
API CONTRACT
CROSS-BOUNDARY
```

This classification determines permitted scope.

Example:

```text
CHANGE:
Make product cards more attractive

CLASSIFICATION:
DESIGN

PERMITTED:
frontend presentation

NOT PERMITTED:
backend product semantics
pricing
database
order logic
```

Another example:

```text
CHANGE:
Allow diner transcript recovery after refresh

CLASSIFICATION:
BACKEND FUNCTIONALITY + API CONTRACT + FRONTEND FUNCTIONALITY

PERMITTED:
minimum backend read capability
API contract
frontend transcript recovery

NOT PERMITTED:
conversation subsystem redesign
new chatbot architecture
unrelated UI redesign
```

---

# 168. CROSS-BOUNDARY CHANGE RULE

Some valid changes require both frontend and backend.

That does NOT eliminate the boundary.

Instead:

```text
BACKEND PORTION
        ↓
EXPLICIT CONTRACT
        ↓
FRONTEND PORTION
```

Each side MUST retain its own responsibility.

Cross-boundary change does not mean unrestricted cross-layer modification.

---

# 169. MINIMUM NECESSARY CHANGE

Every implementation MUST follow:

```text
REQUESTED OUTCOME
        ↓
IDENTIFY MINIMUM REQUIRED SCOPE
        ↓
CHANGE ONLY THAT SCOPE
        ↓
VERIFY DIRECT EFFECT
        ↓
VERIFY RELEVANT PRESERVATION
```

Do not expand scope because nearby code could also be improved.

---

# 170. ONE PROMPT PER INDEPENDENT CHANGE

Canonical Codex rule:

```text
ONE INDEPENDENT CHANGE
        =
ONE CODEX PROMPT
```

A prompt MUST have one clearly defined implementation objective.

Examples of independent changes:

```text
create frontend foundation
```

```text
implement diner access screen
```

```text
implement menu browsing
```

```text
implement product configuration
```

```text
correct one identified responsive defect
```

These SHOULD NOT automatically be combined into one giant prompt.

---

# 171. DEPENDENT CHANGE EXCEPTION

Two or more changes MAY be included in one Codex prompt only when they are genuinely dependent.

Dependency means:

```text
CHANGE B CANNOT BE CORRECTLY IMPLEMENTED
WITHOUT CHANGE A
```

or:

```text
SEPARATING THEM WOULD CREATE
A TEMPORARILY INVALID OR UNUSABLE IMPLEMENTATION
```

Then:

```text
DEPENDENT CHANGE A
        +
DEPENDENT CHANGE B
        =
ONE COHERENT PROMPT
```

---

# 172. PROXIMITY IS NOT DEPENDENCY

Changes are not dependent merely because:

```text
they affect the same screen
they affect nearby files
they belong to the same workstream
they are both frontend changes
they are both visually related
they are convenient to implement together
```

Dependency must be functional or architectural.

---

# 173. PROMPT ATOMICITY

Every Codex prompt SHOULD be atomic enough that its result can be answered clearly:

```text
DID THE REQUESTED CHANGE SUCCEED?
YES / NO
```

Avoid prompts whose success requires evaluating many unrelated objectives.

Atomic prompts improve:

```text
precision
reviewability
rollback
debugging
credit efficiency
regression attribution
```

---

# 174. PROMPT SCOPE MUST BE EXPLICIT

Every implementation prompt SHOULD explicitly state:

```text
OBJECTIVE
BOUNDARY
ALLOWED SCOPE
FORBIDDEN SCOPE
ACCEPTANCE CRITERIA
FOCUSED VERIFICATION
REPORT FORMAT
```

This prevents Codex from interpreting a local change as permission to redesign adjacent architecture.

---

# 175. NO UNRELATED MODIFICATIONS

Absolute rule:

```text
DO NOT TOUCH ANYTHING
THAT IS NOT REQUIRED
FOR THE REQUESTED CHANGE
```

Codex MUST preserve unrelated:

```text
files
modules
services
components
styles
tests
configuration
migrations
API contracts
domain behavior
documentation
```

unless modification is technically necessary for the requested change.

---

# 176. NO OPPORTUNISTIC REFACTORING

While implementing a requested change, Codex MUST NOT perform unrelated:

```text
cleanup
renaming
formatting sweeps
dependency upgrades
architecture restructuring
component migrations
service rewrites
test rewrites
directory reorganizations
```

merely because it identifies an opportunity.

Potential improvements may be reported separately.

They MUST NOT be silently included.

---

# 177. NO SCOPE EXPANSION BY CODEX

Codex is an implementation executor within the authorized scope.

It MUST NOT independently decide to enlarge the change.

If implementation reveals a required additional modification outside the authorized boundary:

```text
STOP
    ↓
REPORT BLOCKER
    ↓
EXPLAIN REQUIRED ADDITIONAL CHANGE
    ↓
WAIT FOR NEW DECISION
```

unless the additional modification is an inseparable technical dependency already covered by the prompt.

---

# 178. PRESERVE CERTIFIED BEHAVIOR

Previously implemented and certified behavior is presumed valid.

A new change MUST preserve it unless the new requirement explicitly supersedes it.

Canonical:

```text
NEW CHANGE
    +
PRESERVE EXISTING CERTIFIED BEHAVIOR
```

Not:

```text
NEW CHANGE
    →
REINTERPRET OLD SYSTEM
```

---

# 179. PRESERVE BACKEND AUTHORITY

Frontend implementation MUST NOT weaken backend authority for convenience.

Examples of prohibited shortcuts:

```text
hardcoded prices
frontend-computed settlement truth
frontend-generated availability
frontend-only authorization
frontend-only payment success
frontend-created session closure truth
```

---

# 180. PRESERVE FRONTEND DESIGN AUTHORITY

Backend changes MUST NOT unnecessarily dictate visual implementation.

An API SHOULD expose semantic state.

Frontend determines how that state is presented according to this document.

Example:

Backend:

```text
PAYMENT_UNCERTAIN
```

Frontend:

```text
appropriate warning surface
message
status affordance
visual hierarchy
```

Backend should not prescribe CSS/layout.

---

# 181. DIRECT DAMAGE DEFINITION

A direct damage is an unintended defect in the exact capability being changed.

Example:

```text
CHANGE:
Improve diner access form.

DIRECT DAMAGE:
The form no longer submits correctly.
```

Every change MUST verify absence of direct damage.

---

# 182. SECONDARY DAMAGE DEFINITION

A secondary damage is an unintended defect in a capability directly connected to the changed capability.

Example:

```text
CHANGE:
Modify diner authentication handling.

SECONDARY DAMAGE:
Authenticated menu requests stop working.
```

Relevant secondary effects MUST be verified.

---

# 183. COLLATERAL DAMAGE DEFINITION

A collateral damage is an unintended defect outside the primary change path caused by shared dependencies, shared components, configuration or infrastructure.

Example:

```text
CHANGE:
Modify global Button component.

COLLATERAL DAMAGE:
Payment confirmation button becomes visually or functionally broken.
```

Verification MUST consider plausible collateral impact.

---

# 184. REGRESSION DEFINITION

A regression exists when behavior that previously worked correctly stops working correctly because of the new change.

Regression may be:

```text
functional
visual
responsive
accessibility-related
contractual
security-related
performance-related
```

depending on the scope of the change.

---

# 185. CHANGE IMPACT RADIUS

Before verification, determine the plausible impact radius.

Conceptually:

```text
CHANGED CODE
    ↓
DIRECT DEPENDENCIES
    ↓
SHARED DEPENDENCIES
    ↓
RELEVANT USER JOURNEYS
```

Verification SHOULD cover this radius.

It MUST NOT automatically expand to the entire platform.

---

# 186. PROPORTIONAL REGRESSION VERIFICATION

After each Codex change:

```text
VERIFY ENOUGH
TO CERTIFY THE CHANGE
```

but:

```text
DO NOT RUN EVERYTHING
BY DEFAULT
```

Verification must be proportional to risk.

---

# 187. FOCUSED VERIFICATION FIRST

Codex SHOULD normally perform:

```text
1. changed capability test
2. directly affected integration test
3. relevant shared-component test if applicable
4. build/type/lint check when appropriate
```

This is preferable to automatically running the entire repository test suite.

---

# 188. FULL REGRESSION IS NOT A PER-PROMPT REQUIREMENT

A full platform regression MUST NOT automatically run after every small frontend change.

Full regression is appropriate when:

```text
closing a major integration stage
changing shared architecture
changing highly central infrastructure
preparing pilot/release
or when focused evidence reveals broader risk
```

This prevents verification from becoming more expensive than implementation.

---

# 189. CODEX MUST NOT SPEND TIME ON UNNECESSARY BROAD REGRESSION

Codex SHOULD NOT be used to wait for long, deterministic test suites when agent reasoning is unnecessary.

Canonical execution allocation:

```text
CODEX
=
bounded implementation
+
focused verification

CHATGPT
=
architecture
+
analysis
+
review

LOCAL TERMINAL
=
long deterministic regression suites
```

This rule is especially important for conserving Codex usage.

---

# 190. VERIFICATION MUST MATCH CHANGE TYPE

For a design-only change, verification may emphasize:

```text
build correctness
affected component rendering
responsive behavior
accessibility basics
visual consistency
absence of functional behavior change
```

For frontend-functional changes:

```text
interaction
API integration
state handling
error handling
affected journey
```

For backend-functional changes:

```text
domain behavior
transactional invariants
API contract
focused backend tests
```

For cross-boundary changes:

```text
backend contract
frontend consumption
integration between both
```

---

# 191. DESIGN REGRESSION

A frontend change can be functionally correct and still cause a design regression.

Examples:

```text
broken responsive layout
incorrect spacing
inconsistent typography
unreadable contrast
hidden action
overlapping component
broken dark mode
lost focus indication
```

Relevant design regressions MUST be considered part of certification.

---

# 192. FUNCTIONAL REGRESSION

A visual improvement MUST NOT break:

```text
navigation
submission
authentication
API calls
draft state
order actions
payment actions
continuation
assistance
```

Visual certification therefore includes preservation of affected functional behavior.

---

# 193. ACCESSIBILITY REGRESSION

Changes to shared interactive components MUST preserve:

```text
semantic element behavior
keyboard interaction
focus visibility
labels
touch target
screen-reader meaning
contrast where applicable
```

Accessibility is not optional collateral behavior.

---

# 194. RESPONSIVE REGRESSION

Changes to layout or shared visual components MUST consider supported responsive ranges.

A desktop-correct implementation is not certified if it breaks the primary mobile diner experience.

Likewise, mobile-first does not authorize obviously broken desktop behavior.

---

# 195. API CONTRACT REGRESSION

Frontend implementation MUST NOT silently rely on undocumented backend behavior.

Backend implementation MUST NOT silently break frontend-consumed contracts.

Any intentional API contract change must be explicit.

---

# 196. SECURITY REGRESSION

No frontend change may weaken:

```text
authentication
authorization
tenant isolation
session isolation
secret handling
PII protection
```

Frontend behavior must never be treated as a security boundary.

---

# 197. FINANCIAL REGRESSION

Changes affecting account/payment surfaces require special care.

The frontend MUST preserve authoritative distinctions between:

```text
preview
Check
Payment
Settlement
payment success
payment failure
payment uncertainty
```

No visual simplification may collapse these semantics.

---

# 198. CERTIFICATION AFTER CHANGE

Every Codex implementation prompt MUST end with a bounded certification step.

The certification should answer:

```text
REQUESTED CHANGE: PASS / FAIL

DIRECT DAMAGE: NONE / FOUND

SECONDARY DAMAGE: NONE / FOUND

COLLATERAL DAMAGE: NONE / FOUND

REGRESSION IN VERIFIED SCOPE: NONE / FOUND
```

This is evidence-based certification.

It is not permission to launch an unlimited audit.

---

# 199. CERTIFICATION SCOPE MUST BE STATED

Codex MUST state what it actually verified.

Example:

```text
VERIFIED:
- diner access component
- join API integration
- authenticated transition
- existing menu route accessibility
- frontend build

NOT RUN:
- full backend regression
- unrelated staff flows
```

Never imply that the entire platform was certified when only focused tests were performed.

---

# 200. NO FALSE CERTIFICATION

Codex MUST NOT state:

```text
NO REGRESSIONS
```

as an absolute platform-wide claim unless evidence actually supports it.

Preferred:

```text
No regression detected within the verified impact scope.
```

Certification must be precise.

---

# 201. STOP ON REAL REGRESSION

If verification discovers a real regression caused by the requested change:

```text
DO NOT IGNORE IT
DO NOT CERTIFY PASS
```

Codex should determine whether the correction is:

```text
directly part of the requested change
```

If yes, correct it within the same prompt.

If the correction requires unrelated architectural scope:

```text
STOP
REPORT
REQUEST DECISION
```

---

# 202. NO REVIEW-OF-REVIEW LOOP

After:

```text
IMPLEMENTATION
    ↓
FOCUSED VERIFICATION
    ↓
PASS
```

the change is complete.

Do NOT automatically create:

```text
review prompt
review-of-review prompt
second certification
third certification
```

unless new evidence reveals a real problem.

---

# 203. DEFECT REMEDIATION RULE

If verification identifies a genuine defect:

```text
DEFECT
    ↓
MINIMUM REMEDIATION
    ↓
RETEST AFFECTED SCOPE
    ↓
PASS
    ↓
CLOSE
```

Do not restart the entire implementation.

Do not repeat unrelated tests without reason.

---

# 204. PARTIAL WORK PRESERVATION

If Codex or VS Code is interrupted:

```text
DO NOT RESTART AUTOMATICALLY
```

First inspect:

```text
git status
git diff
```

Preserve legitimate partial work.

Continue from the existing state when safe.

This reduces:

```text
duplicate work
credit consumption
merge risk
accidental divergence
```

---

# 205. CHANGE TRACEABILITY

Each prompt SHOULD make it possible to identify:

```text
what changed
why it changed
which files changed
what was verified
what remains unchanged
```

Traceability should be concise.

It MUST NOT become bureaucratic documentation overhead.

---

# 206. CODEX REPORT FORMAT

Unless a specific change requires additional information, Codex reports SHOULD remain compact.

Preferred:

```text
STATUS
CHANGES
VERIFICATION
REGRESSION / DAMAGE CHECK
ISSUES
GIT
```

Avoid multi-thousand-line implementation reports.

---

# 207. STATUS

Codex should report:

```text
STATUS: COMPLETE
```

or:

```text
STATUS: BLOCKED
```

or:

```text
STATUS: FAILED
```

Do not hide incomplete implementation behind ambiguous wording.

---

# 208. CHANGES

`CHANGES` should describe only meaningful modifications.

Example:

```text
CHANGES
- Added diner frontend application shell.
- Added diner join form.
- Added authenticated session bootstrap.
```

Do not paste large code diffs unless specifically requested.

---

# 209. VERIFICATION

`VERIFICATION` should contain:

```text
commands or checks performed
PASS/FAIL result
focused scope
```

It should not contain unnecessary raw test output.

---

# 210. REGRESSION / DAMAGE CHECK

Codex should explicitly report:

```text
DIRECT DAMAGE: NONE DETECTED
SECONDARY DAMAGE: NONE DETECTED
COLLATERAL DAMAGE: NONE DETECTED
REGRESSION: NONE DETECTED IN VERIFIED SCOPE
```

or identify the actual problem.

---

# 211. ISSUES

Only unresolved real issues belong in:

```text
ISSUES
```

Do not populate the section with speculative future enhancements.

---

# 212. GIT

Report concise Git state:

```text
branch
changed files
working-tree status
commit if explicitly requested
```

Do not automatically commit unless the prompt authorizes it.

---

# 213. PROMPT CREDIT EFFICIENCY

Prompt design MUST consider Codex usage efficiency.

Prefer:

```text
small prompt
clear target
known files where possible
bounded change
focused verification
short report
```

Avoid:

```text
large architectural rediscovery
+
implementation
+
full regression
+
audit
+
documentation rewrite
+
review
```

inside one prompt.

---

# 214. DO NOT MAKE CODEX REDISCOVER ESTABLISHED ARCHITECTURE

Once architecture has been established and documented, subsequent prompts SHOULD reference the authoritative rule rather than asking Codex to rediscover it.

Example:

```text
Follow:
docs/frontend/FRONTEND_DESIGN_SYSTEM_AND_UX_RULES.md
```

Then provide only the change-specific instructions.

---

# 215. ARCHITECTURE DECISIONS BELONG BEFORE IMPLEMENTATION

Codex SHOULD NOT be forced to make major architectural decisions while implementing a small change.

Preferred:

```text
CHATGPT / ARCHITECTURE DECISION
        ↓
BOUNDED CODEX PROMPT
        ↓
IMPLEMENTATION
```

This keeps implementation deterministic.

---

# 216. DESIGN DECISIONS MUST ALSO BE CONTROLLED

Codex MUST NOT invent a different visual language on each screen.

Once established:

```text
tokens
typography
spacing
radius
navigation
button hierarchy
surface hierarchy
motion
```

must be reused.

A new screen extends the design system.

It does not independently redefine it.

---

# 217. SHARED COMPONENT CHANGE RISK

Changes to shared components have larger collateral radius.

Examples:

```text
Button
Input
Dialog
AppShell
Navigation
Card
API client
session provider
theme tokens
```

Therefore a shared-component change SHOULD verify at least one representative dependent use when practical.

---

# 218. LOCAL COMPONENT CHANGE RISK

Changes isolated to a feature-local component normally require only local and directly connected verification.

Do not run platform-wide regression merely because one isolated visual component changed.

---

# 219. DEPENDENCY UPDATE RULE

Do not update dependencies incidentally.

Dependency changes require explicit need.

Before adding a dependency ask:

```text
Does existing stack already solve this?

Is this dependency necessary?

Does it materially reduce implementation complexity?

Is it maintained?

Does it introduce significant bundle/runtime/security cost?
```

Dependency upgrades unrelated to the requested change are prohibited.

---

# 220. FRONTEND INFRASTRUCTURE CHANGE RULE

Changes to:

```text
build system
router
API client
server-state layer
authentication bootstrap
theme foundation
test infrastructure
```

are higher-impact than ordinary screen changes.

They require focused verification of representative consumers.

They still do NOT automatically require full platform regression.

---

# 221. BACKEND CHANGE DURING FRONTEND IMPLEMENTATION

Frontend work may expose a genuine backend gap.

When this occurs:

```text
DO NOT PATCH AROUND IT IN FRONTEND
```

Classify the gap.

Then implement only the minimum backend capability required.

Example:

```text
Diner needs transcript after refresh
        ↓
backend lacks diner-authorized transcript read
        ↓
add bounded backend read contract
        ↓
consume from frontend
```

Do not redesign the entire Conversation domain.

---

# 222. FRONTEND CHANGE DURING BACKEND REMEDIATION

When a backend gap is remediated, frontend changes should consume the resulting contract.

Do not combine unrelated visual redesign merely because the frontend file is already being edited.

---

# 223. CHANGE DEPENDENCY GRAPH

For complex changes, think conceptually in terms of:

```text
A
↓
B
↓
C
```

If B requires A and C requires B, they may form one coherent change when splitting them would create invalid intermediate states.

But if:

```text
A    B    C
```

are independent, they should normally be separate prompts.

---

# 224. ONE PROMPT DOES NOT MEAN ONE FILE

A single change may legitimately require several files.

Example:

```text
Diner Access
```

may require:

```text
route
screen
form component
API call
session state
focused test
```

These belong in one prompt when together they implement one coherent change.

Atomicity is about the change objective, not file count.

---

# 225. ONE FILE DOES NOT MEAN ONE CHANGE

Conversely, two unrelated changes in one file remain two changes.

Do not combine them merely because Codex will edit the same file.

---

# 226. DEFINITION OF A CHANGE

A change is a coherent externally understandable outcome.

Good:

```text
Implement diner login using the existing join API.
```

Too broad:

```text
Build frontend.
```

Too implementation-fragmented:

```text
Create one input.
```

unless that input itself is the requested outcome.

---

# 227. CHANGE ACCEPTANCE CRITERIA

Every prompt SHOULD define observable completion.

Example:

```text
A diner can enter name, optional email and access code,
submit through the authoritative join endpoint,
receive authenticated diner context,
and reach the authenticated diner shell.
```

Acceptance criteria should describe behavior, not merely files created.

---

# 228. PRESERVATION CRITERIA

Prompts SHOULD also state what must remain unchanged.

Example:

```text
MUST PRESERVE:
- existing backend join semantics
- token format
- session lifecycle
- tenant/location authority
- existing API behavior
```

This makes non-regression part of implementation rather than an afterthought.

---

# 229. FORBIDDEN-SCOPE CRITERIA

Important prompts SHOULD explicitly state forbidden scope.

Example:

```text
DO NOT:
- redesign backend authentication
- add new diner identity fields
- add social login
- change database schema
- implement staff frontend
```

This materially reduces accidental scope expansion.

---

# 230. DESIGN ACCEPTANCE CRITERIA

Frontend prompts involving user-visible screens SHOULD include experience acceptance criteria.

At minimum where relevant:

```text
mobile-first
responsive
accessible
consistent with tokens
clear primary action
appropriate loading state
appropriate error state
premium visual quality
no generic CRUD appearance
```

---

# 231. WOW ACCEPTANCE WITHOUT SUBJECTIVE CHAOS

The WOW requirement does not authorize arbitrary redesign.

Evaluate it through concrete properties:

```text
strong hierarchy
balanced spacing
excellent typography
coherent surfaces
smooth interaction
clear feedback
responsive polish
restaurant warmth
visual consistency
fast perceived response
```

This makes visual excellence implementable and reviewable.

---

# 232. VISUAL CHANGE IS A REAL CHANGE

A design modification is not “just CSS” if it changes the user experience.

It must respect:

```text
scope
responsive behavior
accessibility
shared-component impact
design consistency
focused verification
```

But it does not require backend regression when backend behavior is untouched.

---

# 233. FUNCTIONAL CHANGE IS NOT AUTOMATIC VISUAL AUTHORIZATION

When implementing a new frontend capability, create only the visual presentation necessary to meet the established design standard.

Do not use the feature request as an excuse to redesign existing unrelated screens.

---

# 234. PRESERVE USER JOURNEY CONTINUITY

Changes must preserve the coherent diner journey:

```text
ACCESS
→ MENU
→ PRODUCT
→ CONFIGURATION
→ DRAFT
→ ORDER
→ ACCOUNT
→ PAYMENT
→ POST-PAYMENT
→ CONTINUATION
```

A local improvement must not create a dead end in adjacent journey steps.

---

# 235. PRESERVE REFRESH RECOVERY

Where authoritative backend state exists, frontend changes should preserve or improve the ability to recover state after browser refresh.

Do not make critical business continuity depend solely on ephemeral component state.

---

# 236. PRESERVE MANUAL / CONVERSATIONAL CONVERGENCE

Frontend changes MUST preserve:

```text
MANUAL UI
        ↓
SAME DOMAIN CAPABILITY
        ↑
DIGITAL WAITER
```

Do not create separate business semantics for the conversational interface.

---

# 237. PRESERVE FUTURE VOICE COMPATIBILITY

Frontend implementation should avoid coupling domain actions exclusively to mouse or keyboard events.

Future voice should be able to invoke the same backend actions without domain redesign.

This does not require implementing voice now.

---

# 238. PRESERVE MULTI-TENANT AUTHORITY

No frontend convenience may introduce arbitrary tenant or location selection for diners.

Context comes from the authenticated restaurant/session lifecycle.

Backend remains authoritative.

---

# 239. PRESERVE FINANCIAL TRUTH

No frontend change may derive financial truth by combining stale or unrelated local data.

Financial presentation must come from authoritative projections and responses.

---

# 240. PRESERVE PAYMENT UNCERTAINTY

Any payment-related frontend change MUST preserve the special meaning of:

```text
UNCERTAIN
```

Never transform uncertainty into:

```text
SUCCESS
```

or:

```text
FAILURE
```

without authoritative evidence.

---

# 241. PRESERVE CONTINUATION SEMANTICS

Payment completion does not automatically mean service-session closure.

Frontend must preserve:

```text
SETTLEMENT
    ↓
CONTINUATION_REQUIRED
    ↓
¿Desean algo más?
```

No frontend shortcut may silently infer NO.

---

# 242. PRESERVE ACCOUNT PREVIEW SEMANTICS

Frontend must preserve:

```text
VIEW ACCOUNT
≠
CREATE CHECK
```

Visual navigation to account information must remain informational unless the diner explicitly initiates the authoritative Check/payment flow.

---

# 243. PRESERVE CASH BOUNDARY

Diner frontend does not operate physical cash custody.

Cash interaction remains:

```text
DINER
→ REQUEST CASH ASSISTANCE
→ STAFF
→ CASH MANAGEMENT
```

Do not expose CashSession controls to diners.

---

# 244. PRESERVE BILLING BOUNDARY

Frontend may request or present billing workflow.

It does not become fiscal authority.

PAC credentials, signing, stamping, fiscal validation and issuance truth remain backend responsibilities.

---

# 245. PRESERVE INVENTORY BOUNDARY

Frontend may display product availability exposed by backend.

It does not calculate theoretical stock or recipe consumption to determine availability independently.

---

# 246. PRESERVE PREPARATION BOUNDARY

Frontend may display appropriate order/preparation status when exposed.

It must not fabricate kitchen state based on elapsed time or frontend assumptions.

---

# 247. PRESERVE OPERATIONAL REQUEST EVIDENCE

When requesting:

```text
human assistance
cash assistance
invoice assistance
paid print
```

frontend must only claim durable request success when backend confirms it.

---

# 248. CHANGE COMPLETION RULE

A change is complete when:

```text
requested behavior implemented
+
acceptance criteria satisfied
+
focused verification passed
+
relevant direct/secondary/collateral risk checked
+
no unresolved regression within impact scope
```

Then:

```text
CLOSE THE CHANGE
```

Do not create additional work without evidence.

---

# 249. WORKSTREAM COMPLETION RULE

A workstream is complete when all changes required for its objective are complete.

Do not keep a workstream open merely to perform repetitive verification.

Broader integration belongs at intentional integration boundaries.

---

# 250. PRODUCTION-PATH PRIORITY

When choosing between:

```text
another optional improvement
```

and:

```text
completing the next essential production-path capability
```

prefer the production-path capability.

The project objective is to finish the Restaurant Intelligence Platform.

The process exists to support that objective.

The objective does not exist to support the process.

---

# 251. CHANGE GOVERNANCE MUST REMAIN LIGHTWEIGHT

These rules exist to reduce risk and waste.

They MUST NOT become a new bureaucratic layer.

The desired execution pattern is:

```text
UNDERSTAND
↓
CLASSIFY
↓
BOUND
↓
IMPLEMENT
↓
VERIFY
↓
CLOSE
```

Not:

```text
DISCOVER
↓
AUDIT
↓
REVIEW
↓
IMPLEMENT
↓
AUDIT
↓
REVIEW
↓
CERTIFY
↓
REVIEW CERTIFICATION
↓
REVIEW REVIEW
```

---

# 252. DEFAULT CODEX CHANGE TEMPLATE

Unless a particular change requires otherwise, frontend Codex prompts SHOULD conceptually follow:

```text
CHANGE
[one coherent change]

OBJECTIVE
[observable outcome]

CLASSIFICATION
[DESIGN / FRONTEND FUNCTIONALITY /
 BACKEND FUNCTIONALITY / API CONTRACT / CROSS-BOUNDARY]

BOUNDARY
[what layer owns the change]

ALLOWED SCOPE
[minimum files/capabilities necessary]

MUST PRESERVE
[relevant existing behavior]

DO NOT
[explicit forbidden scope]

IMPLEMENT
[bounded requirements]

VERIFY
[focused tests/checks proportional to impact]

CERTIFY
- requested change
- direct damage
- secondary damage
- collateral damage
- regression within verified scope

REPORT
STATUS
CHANGES
VERIFICATION
REGRESSION / DAMAGE CHECK
ISSUES
GIT
```

The actual prompt SHOULD remain as short as practical.

---

# 253. DEFAULT CERTIFICATION LANGUAGE

Preferred successful certification:

```text
STATUS: COMPLETE

REQUESTED CHANGE: PASS

DIRECT DAMAGE:
None detected.

SECONDARY DAMAGE:
None detected in the verified affected scope.

COLLATERAL DAMAGE:
None detected in the verified impact radius.

REGRESSION:
No regression detected within the verified scope.
```

This wording is intentionally bounded.

---

# 254. DESIGN-ONLY CHANGE TEMPLATE RULE

For a design-only change, Codex SHOULD explicitly preserve functionality.

Conceptually:

```text
CLASSIFICATION:
DESIGN

DO NOT CHANGE:
backend
API contract
business semantics
navigation semantics unless requested
domain state
financial behavior

VERIFY:
affected visual component
responsive behavior
accessibility basics
existing affected interaction
frontend build
```

Do not run backend full regression for a purely visual change unless there is concrete evidence that backend behavior could be affected.

---

# 255. FRONTEND-FUNCTIONAL CHANGE TEMPLATE RULE

For frontend-functional changes:

```text
CLASSIFICATION:
FRONTEND FUNCTIONALITY

PRESERVE:
backend authority
API semantics
business rules
design system

VERIFY:
interaction
state transitions
API integration
controlled errors
directly affected journey
build/type checks
```

---

# 256. BACKEND-FUNCTIONAL CHANGE TEMPLATE RULE

When frontend implementation exposes a required backend gap:

```text
CLASSIFICATION:
BACKEND FUNCTIONALITY
or
CROSS-BOUNDARY

IMPLEMENT:
minimum missing authoritative capability

PRESERVE:
existing domain architecture
existing business semantics
unrelated API contracts

VERIFY:
focused backend behavior
contract
direct frontend consumer when applicable
```

No broad backend redesign is authorized.

---

# 257. SHARED-DESIGN CHANGE TEMPLATE RULE

For shared tokens/components:

```text
CLASSIFICATION:
DESIGN / FRONTEND FOUNDATION

VERIFY:
changed primitive
representative consumers
light/dark where relevant
responsive behavior where relevant
accessibility where relevant
build
```

This recognizes the larger collateral radius without requiring exhaustive application-wide testing.

---

# 258. CHANGE FAILURE RULE

If the requested outcome cannot be safely implemented within the authorized boundary:

Codex MUST NOT improvise a large solution.

Report:

```text
STATUS: BLOCKED

BLOCKER:
[precise reason]

REQUIRED ADDITIONAL CHANGE:
[minimal additional scope]

NO UNRELATED CHANGES MADE
```

Then await architectural decision.

---

# 259. ARCHITECTURAL ESCALATION RULE

Escalate from implementation to architectural decision only when the requested change reveals:

```text
missing ownership boundary
contradictory contracts
missing authoritative backend capability
security conflict
financial invariant conflict
unavoidable cross-domain coupling
```

Do not escalate ordinary implementation details.

---

# 260. FRONTEND DEVELOPMENT OPERATING MODEL

The authoritative frontend operating model is:

```text
PRODUCT REQUIREMENT
        ↓
ARCHITECTURAL BOUNDARY
        ↓
ONE COHERENT CHANGE
        ↓
ONE BOUNDED CODEX PROMPT
        ↓
MINIMUM IMPLEMENTATION
        ↓
FOCUSED VERIFICATION
        ↓
DAMAGE / REGRESSION CERTIFICATION
        ↓
CLOSE
        ↓
NEXT CHANGE
```

Dependent changes may share a prompt.

Independent changes do not.

---

# 261. FINAL CHANGE-CONTROL PRINCIPLE

Every requested change MUST maximize:

```text
PRECISION
+
PRESERVATION
+
TRACEABILITY
+
VERIFIABILITY
+
PRODUCTION PROGRESS
```

while minimizing:

```text
SCOPE
+
UNRELATED MODIFICATION
+
REGRESSION RISK
+
CODEX CONSUMPTION
+
PROCESS OVERHEAD
```

---

# 262. FINAL FRONTEND/BACKEND PRINCIPLE

The architectural relationship is:

```text
BACKEND
=
AUTHORITATIVE BUSINESS INTELLIGENCE
+
DOMAIN TRUTH
+
SECURITY
+
TRANSACTIONAL CORRECTNESS

FRONTEND
=
USER EXPERIENCE
+
INTERACTION
+
PRESENTATION
+
ACCESSIBILITY
+
VISUAL QUALITY
+
PERCEIVED INTELLIGENCE
```

Together:

```text
AUTHORITATIVE BACKEND
        +
EXCEPTIONAL FRONTEND
        =
TRUSTWORTHY
INTELLIGENT
PREMIUM
RESTAURANT EXPERIENCE
```

Neither layer should absorb the other's responsibility merely for implementation convenience.

---

# 263. FINAL PRESERVATION PRINCIPLE

The default assumption for every new change is:

```text
EVERYTHING ALREADY WORKING
REMAINS WORKING
```

unless the requirement explicitly changes that behavior.

Therefore:

```text
CHANGE WHAT IS REQUESTED
PRESERVE WHAT IS NOT
VERIFY THE RELEVANT IMPACT
CLOSE WHEN EVIDENCE IS SUFFICIENT
```

---

# 264. FINAL ANTI-REGRESSION PRINCIPLE

Regression prevention does NOT mean testing everything after every change.

It means:

```text
UNDERSTAND THE CHANGE
        ↓
UNDERSTAND ITS IMPACT RADIUS
        ↓
VERIFY THAT RADIUS
        ↓
ESCALATE ONLY IF EVIDENCE JUSTIFIES IT
```

This produces stronger engineering evidence with less unnecessary work.

---

# 265. FINAL CODEX PRINCIPLE

Codex is not authorized to redesign the Restaurant Intelligence Platform every time it receives a prompt.

Codex is authorized to:

```text
IMPLEMENT
THE REQUESTED CHANGE
WITHIN
THE ESTABLISHED ARCHITECTURE
```

and then:

```text
VERIFY
THE RELEVANT IMPACT
```

Nothing more unless explicitly authorized.

---

# 266. FINAL PRODUCTION PRINCIPLE

The Restaurant Intelligence Platform is being built to reach production.

Therefore every process rule in this document is subordinate to the following objective:

```text
BUILD THE RIGHT THING
        ↓
BUILD IT CORRECTLY
        ↓
PRESERVE WHAT ALREADY WORKS
        ↓
VERIFY ENOUGH TO TRUST IT
        ↓
MOVE FORWARD
```

Do not sacrifice correctness for speed.

Do not sacrifice progress for unnecessary verification.

The desired balance is:

```text
CORRECTNESS
+
FOCUS
+
MINIMAL CHANGE
+
SUFFICIENT EVIDENCE
+
CONTINUOUS PRODUCTION PROGRESS
```

---

# 267. FINAL AUTHORITATIVE RULE

From this point forward, frontend development of the Restaurant Intelligence Platform SHALL follow all rules established in this document.

For every change:

```text
1. IDENTIFY THE REQUIREMENT.

2. CLASSIFY THE CHANGE:
   DESIGN
   FRONTEND FUNCTIONALITY
   BACKEND FUNCTIONALITY
   API CONTRACT
   CROSS-BOUNDARY.

3. ESTABLISH THE RESPONSIBILITY BOUNDARY.

4. DETERMINE WHETHER THE CHANGE IS
   INDEPENDENT OR DEPENDENT ON ANOTHER CHANGE.

5. USE ONE CODEX PROMPT PER INDEPENDENT CHANGE.

6. COMBINE CHANGES ONLY WHEN THEY ARE
   GENUINELY DEPENDENT.

7. IMPLEMENT THE MINIMUM NECESSARY CHANGE.

8. DO NOT MODIFY UNRELATED IMPLEMENTATION.

9. PRESERVE EXISTING CERTIFIED BEHAVIOR.

10. VERIFY THE DIRECT CHANGE.

11. VERIFY RELEVANT SECONDARY IMPACT.

12. VERIFY PLAUSIBLE COLLATERAL IMPACT.

13. CERTIFY ONLY THE SCOPE ACTUALLY VERIFIED.

14. REMEDIATE ONLY REAL DEFECTS.

15. DO NOT CREATE REVIEW-OF-REVIEW LOOPS.

16. CLOSE THE CHANGE WHEN SUFFICIENT
    EVIDENCE EXISTS.

17. MOVE TO THE NEXT PRODUCTION-PATH CHANGE.
```

Canonical summary:

```text
CLEAR BOUNDARIES
        +
ONE COHERENT CHANGE
        +
MINIMUM NECESSARY IMPLEMENTATION
        +
PRESERVATION OF EXISTING BEHAVIOR
        +
PROPORTIONAL VERIFICATION
        +
EXPLICIT DAMAGE/REGRESSION CERTIFICATION
        +
NO UNNECESSARY REVIEW LOOPS
        =
CONTROLLED FRONTEND DEVELOPMENT
```

And the final product objective remains:

```text
ENTERPRISE-GRADE BACKEND POWER
            +
CONSUMER-GRADE SIMPLICITY
            +
PREMIUM VISUAL QUALITY
            +
INTELLIGENT INTERACTION
            +
CONTROLLED CHANGE
            +
PRODUCTION RELIABILITY
            =
RESTAURANT INTELLIGENCE PLATFORM
```

---

# DOCUMENT STATUS

```text
DOCUMENT:
FRONTEND_DESIGN_SYSTEM_AND_UX_RULES.md

STATUS:
ACTIVE — AUTHORITATIVE

BASELINE:
Previous authoritative frontend design and UX rules preserved.

INTEGRATED GOVERNANCE:
Functionality vs Design boundary
Backend vs Frontend boundary
Frontend Functionality vs Backend Functionality boundary
One Prompt per Independent Change
Dependent Change Exception
Minimum Necessary Change
No Unrelated Modification
No Opportunistic Refactoring
Direct Damage Verification
Secondary Damage Verification
Collateral Damage Verification
Regression Verification
Proportional Certification
Codex Credit Efficiency
No Review-of-Review
Production-Path Priority

APPLIES FROM:
Beginning of Restaurant Intelligence Platform frontend implementation.

PRIMARY OBJECTIVE:
Build the Restaurant Intelligence Platform frontend rapidly,
safely and incrementally without sacrificing backend authority,
existing certified behavior, visual excellence or production quality.
```