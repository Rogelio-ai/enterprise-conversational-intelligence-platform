# STATUS

PASS — OPERATOR DATASET REQUIRED

# DECISION

The certified local pre-pilot has a valid real Tenant/Organization/Location authority, but it is
not ready for restaurant operation. Only confirmed public restaurant facts were promoted. All
PREPILOT, TEST, synthetic staff/menu/resources, and workstation/printer records remain
certification authority only. No production payment or fiscal integration was enabled.

# BASELINE

- Branch: `feat/ws-00-01-runtime-reuse-baseline`.
- Starting worktree: clean; `git diff --check`: pass.
- Required preceding evidence is present in commits `1b60f37`, `51af435`, `a07f0d4`, and the
  current history, including C2A, C3A/C3B, C4, and C5.
- MySQL 8.4, API, and the local pre-pilot environment were healthy during the inventory.
- Conekta TEST was not rerun; the Connector was not reenrolled.

# PILOT AUTHORITY

- Tenant `1`: **Carnitas Muñoz y Cortes**, slug `carnitas-munoz-y-cortes`, ACTIVE.
- Organization `1`: **CMC — Carnitas Muñoz y Cortes**, ACTIVE.
- Location `1`: **SLP-CARNITAS-MUNOZ — Carnitas Muñoz**, ACTIVE,
  `America/Mexico_City`, San Luis Potosí, San Luis Potosí, `MX`.
- These records were reused, not recreated. Tenant and location isolation remain unchanged.

# CURRENT CONFIGURATION INVENTORY

| Area | Authoritative current records | Classification |
|---|---|---|
| Restaurant authority/profile | Tenant 1; Organization 1; Location 1; confirmed identity/geography | REAL |
| Optional location contact fields | Address/postal/phone/email null | NEEDS OPERATOR CONFIRMATION |
| Administrator | Rogelio/TENANT_ADMIN, granted Location 1 | NEEDS OPERATOR CONFIRMATION |
| Staff | Three PREPILOT users/roles, granted Location 1 | SYNTHETIC |
| Tables/resources | MESA-01 / Mesa 01 Pre-Pilot, ACTIVE | SYNTHETIC |
| Cash registers | CAJA-01 / Caja 01 Pre-Pilot, ACTIVE | SYNTHETIC |
| Preparation owner | PLATFORM | NEEDS OPERATOR CONFIRMATION |
| Preparation area/routes | COCINA; three active product routes | SYNTHETIC |
| Menu/catalog | Menú Local Pre-Pilot; one section/category; three products | SYNTHETIC |
| Prices | Taco 25, Quesadilla 45, Refresco 30; MXN | SYNTHETIC |
| Modifiers/options | No compositions, choice groups, or options | NEEDS OPERATOR CONFIRMATION |
| Combos/packages | No compositions/components | NEEDS OPERATOR CONFIRMATION |
| Buffets | No dedicated buffet or unlimited-service model | NEEDS OPERATOR CONFIRMATION |
| Fixed meals | No configured composition; structure/choices exist, schedules do not | NEEDS OPERATOR CONFIRMATION |
| Promotions | No promotions or product/location associations | NEEDS OPERATOR CONFIRMATION |
| Fiscal/tax | PREPILOT-IVA-16 rule; three PREPILOT product classifications; no issuer profile | DEVELOPMENT/CERTIFICATION ONLY |
| Payments | CASH path; Conekta TEST CARD/MXN executor; one successful CASH, one successful and one failed TEST CARD payment; production runtime disabled | DEVELOPMENT/CERTIFICATION ONLY |
| Print destinations | COCINA-HP-P1005 to `workstation_hp_p1005` | DEVELOPMENT/CERTIFICATION ONLY |
| Connector | WS-HP-P1005, one enrollment and credential; active/recently seen | DEVELOPMENT/CERTIFICATION ONLY |
| Certification operating state | Cash activated; one certification cash session and one service session remain OPEN | DEVELOPMENT/CERTIFICATION ONLY |

Certification history remains present: 6 orders, 6 checks, 3 payments, 6 preparation dispatches,
3 paid-check dispatches, 1 cash session and 1 cash movement. The inventory reports only these
counts for evidence tables and never prints their payloads or secrets.

# REAL VS SYNTHETIC MATRIX

| Capability | Current record/config | Classification | Required before pilot | Missing operator input | Recommended action |
|---|---|---|---|---|---|
| Tenant | Tenant 1 | REAL | NO | None | Reuse |
| Organization | Organization 1 / CMC | REAL | NO | None | Reuse |
| Location identity/geography | Location 1; name, timezone, city, state, country | REAL | NO | None | Reuse |
| Location contact/address | Street, postal, phone, email null | NEEDS OPERATOR CONFIRMATION | NO | Optional supported fields | Add only if supplied |
| Administrator | Rogelio, current email, TENANT_ADMIN, Location 1 | NEEDS OPERATOR CONFIRMATION | YES | Confirm this is the real pilot administrator | Retain or provision a confirmed administrator |
| Staff | PREPILOT_WAITER/KITCHEN/CASHIER users | SYNTHETIC | YES | Real roster, role, location | Create separate real users; retain synthetic history |
| Tables/resources | MESA-01 | SYNTHETIC | YES | Complete real resource list | Create/reuse by location+code; later deactivate MESA-01 |
| Cash register | CAJA-01 | SYNTHETIC | YES if CASH | Real register list | Create/reuse; close synthetic session before deactivation |
| Preparation owner | PLATFORM | NEEDS OPERATOR CONFIRMATION | YES | PLATFORM or EXTERNAL_POS | Confirm before routing real items |
| Preparation areas | COCINA | SYNTHETIC | YES if PLATFORM preparation | Real area list | Create/reuse; do not rename historical COCINA |
| Preparation routing | Two AREA routes; one NO_PREPARATION | SYNTHETIC | YES | Policy per real product and area when AREA | Create new active routes; old routes become inactive, never deleted |
| Categories/menu/sections | PREPILOT category, menu, and section | SYNTHETIC | YES | Real names, hierarchy/order, status | Create separate real graph |
| Products | Three certification products | SYNTHETIC | YES | Real catalog fields | Create separate real products |
| Prices | 25/45/30 MXN | SYNTHETIC | YES | Real amount/currency/location/status | Configure real product prices |
| Modifiers/options | None | NEEDS OPERATOR CONFIRMATION | YES | Applicability; composition/choice data if used | Configure only when confirmed |
| Combos/packages | None | NEEDS OPERATOR CONFIRMATION | YES | Applicability; components/choices if used | Configure as product compositions |
| Buffets | No supported buffet semantics | NEEDS OPERATOR CONFIRMATION | YES | Whether buffet operation is required | Mark not applicable, or treat required buffet semantics as a pilot gap |
| Fixed meals | None; generic composition support only | NEEDS OPERATOR CONFIRMATION | YES | Applicability and supported composition data | Configure supported structure; schedules are not modeled |
| Promotions | None | NEEDS OPERATOR CONFIRMATION | YES | Applicability and promotion fields | Configure only confirmed promotions |
| Tax rule | PREPILOT-IVA-16 | DEVELOPMENT/CERTIFICATION ONLY | YES | Accountant-approved real rule | Add real rule; then end/deactivate certification rule safely |
| Product fiscal classification | Three PREPILOT schemes/codes | DEVELOPMENT/CERTIFICATION ONLY | YES | Approved codes per real product | Add real classifications; preserve snapshots |
| Issuer fiscal profile | None | NEEDS OPERATOR CONFIRMATION | NO unless invoicing | Legal fiscal profile | Required only if invoice issuance enters pilot scope |
| CASH | Certified path and historical payment | NEEDS OPERATOR CONFIRMATION | YES | Enable decision and currency | Use only after real register/cashier setup |
| Conekta TEST CARD/MXN | Active TEST DB executor; electronic runtime disabled | DEVELOPMENT/CERTIFICATION ONLY | NO | None for C6 | Preserve; never treat as production |
| Production electronic payment | Disabled | NEEDS OPERATOR CONFIRMATION | NO if cash-only | Whether CARD/TRANSFER is in pilot scope and provider | Separate production enablement; never reuse TEST authority |
| Preparation print destination | COCINA-HP-P1005 | DEVELOPMENT/CERTIFICATION ONLY | YES if physical prep printing | Real destination and target mapping | Provision after final hardware data |
| Paid-check print target | WS-HP-P1005 / synthetic register | DEVELOPMENT/CERTIFICATION ONLY | YES if physical checks required | Real cashier target mapping | Provision after final hardware data |
| Local Connector | WS-HP-P1005 and workstation credential | DEVELOPMENT/CERTIFICATION ONLY | YES if printing | Final workstation/connector facts | Create/enroll a distinct final connector |
| Cash operating state | Certification CashSession OPEN | DEVELOPMENT/CERTIFICATION ONLY | YES | Actual closing count; variance reason only if different | Close through domain workflow; never delete |
| Service operating state | Certification service session OPEN | DEVELOPMENT/CERTIFICATION ONLY | YES | Authorized closure decision | Close through domain workflow; never delete |
| Host role | No dedicated host capability/role | NOT APPLICABLE | NO | None | Do not create a synthetic role |

# REAL CONFIGURATION APPLIED

The explicit command `python -m app.configure_pilot_known_real` verified the exact IDs and names,
filled only Location `locality=San Luis Potosí` and `administrative_area=San Luis Potosí`, and
confirmed existing `country_code=MX`. Its first execution reported those two updates; its second
reported `already_configured`. No startup seeding, schema migration, production business-code
change, duplicate, or history mutation was introduced.

# RESTAURANT PROFILE

## known

Commercial identity Carnitas Muñoz y Cortes; pilot location Carnitas Muñoz; city/state San Luis
Potosí; country Mexico (`MX`); timezone `America/Mexico_City`.

## missing

Supported but optional: street address (`address_line1`, optionally `address_line2`), postal code,
phone, and business email. Business hours and operating policies are not modeled and are not part
of this dataset.

# STAFF

## current

Rogelio is active as TENANT_ADMIN at Location 1. Three active synthetic users cover waiter,
kitchen, and cashier certification paths.

## classification

Administrator: NEEDS OPERATOR CONFIRMATION. PREPILOT staff/users/roles: SYNTHETIC. Kitchen and
cashier roles are needed when platform preparation and CASH are enabled; waiter is needed when
staff-assisted table service is used. A separate manager is optional because TENANT_ADMIN can
currently cover management. Host is not a dedicated implemented role.

## required data

For each real employee: display name, unique email/login, role (WAITER, KITCHEN, CASHIER, or a
separately approved manager role/permission set), Location 1, and ACTIVE/INACTIVE. Do not submit
passwords in this template; credential setup must use the protected onboarding channel.

# TABLES / RESOURCES

## current

MESA-01 / Mesa 01 Pre-Pilot / TABLE / ACTIVE.

## classification

SYNTHETIC. It remains referenced by certification service, order, check, and print snapshots.

## required data

Every real service resource: unique code within Location 1, name, supported type (`TABLE` or other
implemented Resource type when truly needed), and ACTIVE/INACTIVE.

# CASH REGISTERS

CAJA-01 / Caja 01 Pre-Pilot / CASH_REGISTER / ACTIVE is SYNTHETIC and has a referenced OPEN
certification CashSession. If CASH is enabled, provide each real register's code, name, and status.
Create separate records; close the certification session via the cash workflow before later
deactivating CAJA-01. Do not edit or delete its financial history.

# PREPARATION

## areas

COCINA / Cocina / ACTIVE is SYNTHETIC. Supported real fields are location, optional linked
resource, code, name, and status.

## routing

The synthetic Taco and Quesadilla route to COCINA with `AREA`; Refresco uses `NO_PREPARATION`.
The supported real policies are `AREA`, `COMPONENTS`, and `NO_PREPARATION`; `AREA` requires an
active area, while the others require no area.

## required data

Confirm preparation owner (`PLATFORM` or `EXTERNAL_POS`); provide real areas; then, for every real
product, provide policy and the area when policy is AREA. Do not infer actual kitchen stations.

# MENU / PRICING

## synthetic current

Menú Local Pre-Pilot; category Menú Pre-Pilot; section Platillos Pre-Pilot; Taco de carnitas
25.0000 MXN, Quesadilla 45.0000 MXN, Refresco 30.0000 MXN; all ACTIVE.

## real current

None.

## required data

Menu name/status/location; sections with name/order/status; categories with optional parent,
name/order/status; products with category, name, optional description and status; membership in
menu section with order/status; price amount, currency, location and status; preparation policy
and area when applicable. Scheduled availability is not supported; only lifecycle status is.

# COMPLEX COMMERCIAL STRUCTURES

- Modifiers/options — **NEEDS OPERATOR DATA**. Supported through a product composition, choice
  group name, minimum/maximum selections, order/status, and option product, quantity/order/status.
  There is no direct per-option surcharge field; pricing authority is the option ProductPrice.
- Combos/packages — **NEEDS OPERATOR DATA**. Supported as a parent product composition with fixed
  component products/quantities and optional choice groups.
- Buffets — **NEEDS OPERATOR DATA**. Confirm whether required. Unlimited offerings and service
  periods have no current authoritative model; if required, this is a pilot capability gap.
- Fixed meals — **NEEDS OPERATOR DATA**. Components and course choices can use compositions, but
  schedule/service-period availability is not modeled.
- Promotions — **NEEDS OPERATOR DATA**. Percentage and fixed-amount discounts, product scope,
  location scope, UTC validity interval, combinability, priority, lifecycle, and source are
  supported.

# FISCAL / TAX

## PREPILOT status

PREPILOT-IVA-16, MX-PREPILOT, and all PREPILOT product/unit classification schemes and codes are
DEVELOPMENT/CERTIFICATION ONLY. They remain active solely to preserve certified order evidence;
they are not real tax authority.

## real authority status

No real tax rule, real product fiscal classification, or issuer fiscal profile exists. CFDI
issuance is disabled.

## required data

For the real tax rule: scope (organization or Location 1), tax classification code, jurisdiction
code, tax category, treatment, effect (TRANSFERRED/WITHHELD), rate, calculation policy, rounding
policy, effective-from, optional effective-to, and status. For each product: fiscal jurisdiction,
product classification scheme/code, unit classification scheme/code, effective dates, and status.
If invoicing is in pilot scope, also legal name, tax identifier, tax regime, fiscal postal code,
and status for the issuer. All values require accounting/fiscal approval.

# PAYMENTS

- CASH — implemented and certified, but real use needs operator confirmation, MXN confirmation,
  a real cashier, and a real cash register.
- Conekta TEST — certified CARD/MXN configuration is preserved; it is certification-only.
- Production status — electronic payments and Conekta production remain disabled. TEST authority
  must never be promoted or reused as production authority.
- Required decisions — enabled methods among CASH/CARD/TRANSFER, currency, and provider for each
  non-cash method. If CARD/TRANSFER is selected, production provisioning is a separate controlled
  step; no credentials belong in this report.

# PRINT / CONNECTOR

- Workstation certification — WS-HP-P1005, COCINA-HP-P1005, and
  `workstation_hp_p1005` are DEVELOPMENT/CERTIFICATION ONLY; enrollment and credential history is
  preserved.
- Final hardware status — not provisioned. Pilot readiness is DEFERRED TO FINAL HARDWARE.
- Required hardware data — purpose (preparation area or paid account), area when applicable,
  brand/model, physical/network connection, CUPS queue or TCP host/port or USB device path,
  paper width mapped to supported columns (32/42/48), ESC/POS compatibility, cutter compatibility,
  and encoding (`cp437`, `cp850`, or `latin-1` for direct ESC/POS). Brand/model, physical paper
  width, and cutter capability are compatibility facts; current persisted target fields are
  adapter, queue/host/port/device path, columns, and encoding. Direct ESC/POS currently sends a
  cut command, so do not select it for hardware that cannot safely support that command.

# OPERATING CONFIGURATION

Location ACTIVE and geography are real. `preparation_owner=PLATFORM`, menu/resource/preparation
availability, cash activation, and current OPEN sessions arose from certification and cannot be
promoted without confirmation. Before go-live, load and validate the real active graph, close the
synthetic OPEN cash/service sessions through domain workflows, and then deactivate synthetic
active records when references and current-slot rules permit. Hours, shifts, service periods, and
general operating policies have no current configuration model and are not requested.

# SAFE TRANSITION PLAN

1. Validate operator data against Tenant 1 / Organization 1 / Location 1 and supported enums.
2. Create or reuse real records using existing natural uniqueness boundaries (location+code,
   organization/category name, product/location price, menu/location, connector target, and
   product current route). Reject conflicting matches; reruns must resolve to the same IDs.
3. Build real staff grants, resources, preparation areas, menu graph, prices, routes, fiscal
   authority, payment selection, and final print mapping while synthetic records remain available.
4. Run focused read-only readiness validation. Do not rerun Conekta TEST or reenroll WS-HP-P1005.
5. Close synthetic OPEN cash/service sessions through their domain commands using real observed
   closure facts; preserve settlements, snapshots, dispatches, reprints, attempts, and audit data.
6. Switch active configuration to real records, then set unneeded synthetic records INACTIVE.
   Product preparation route replacement already preserves old routes as inactive records.
7. Never hard-delete referenced history and never auto-seed restaurant data at startup.

# OPERATOR DATASET REQUIRED

## REQUIRED BEFORE PILOT

1. Confirm whether the current Rogelio account/email is the real pilot administrator.
2. Real staff roster: display name, unique email/login, role, Location 1, status; at minimum the
   roles needed by selected workflows (KITCHEN for platform preparation, CASHIER for CASH, WAITER
   for staff-assisted service).
3. Complete real tables/service resources: code, name, supported type, status.
4. Payment-method decision (CASH/CARD/TRANSFER), currency, and provider for non-cash methods.
5. Real cash registers (code/name/status) if CASH is enabled.
6. Preparation owner; real areas; routing policy and area, when applicable, for every real product.
7. Real menu graph, products, exact prices/currency/status, and menu/preparation availability.
8. YES/NO applicability for modifiers/options, combos/packages, buffets, fixed meals, and
   promotions; supported configuration fields for every YES answer.
9. Accountant-approved real tax rule and per-product fiscal classifications.
10. Final printer/connector data when physical preparation or paid-check printing is required.
11. Actual closing cash count for the certification CashSession, plus a variance reason only if
    the count differs, and authorization to close the certification service session.

## OPTIONAL BEFORE PILOT

1. Street address and optional second line, postal code, phone, and business email.
2. Separate manager identity/permission assignment if TENANT_ADMIN will not perform management.
3. Issuer fiscal profile only if invoice issuance is included in pilot scope.
4. Description and display order fields where the models allow defaults.

# OPERATOR DATA-ENTRY TEMPLATE

## RESTAURANT PROFILE

Street address (`address_line1`):
Address line 2 (`address_line2`, optional):
Postal code:
Phone:
Business email:

## TABLES / RESOURCES

`Code | Name | Type (TABLE/AREA/WORKSTATION/EQUIPMENT/VEHICLE/DEVICE/CASH_REGISTER) | ACTIVE/INACTIVE`

## STAFF

`Display name | Email/Login | Role | Location | ACTIVE/INACTIVE`

Current administrator account is real: `YES / NO`
No passwords in this document.

## CASH REGISTERS

`Code | Name | ACTIVE/INACTIVE`

## PREPARATION AREAS

Preparation owner: `PLATFORM / EXTERNAL_POS`
`Code | Name | Optional Resource code | ACTIVE/INACTIVE`

## MENU

Menu: `Name | ACTIVE/INACTIVE`
Section: `Menu | Name | Display order | ACTIVE/INACTIVE`
Category: `Parent category (optional) | Category | Display order | ACTIVE/INACTIVE`
Product: `Category (optional) | Product | Description (optional) | Price | Currency | Preparation policy (AREA/COMPONENTS/NO_PREPARATION) | Area (AREA only) | ACTIVE/INACTIVE`
Menu item: `Menu | Section | Product | Display order | ACTIVE/INACTIVE`

## MODIFIERS / OPTIONS

Applicable: `YES / NO`
`Parent product | Group | Option product | Option ProductPrice | Min selections | Max selections | Option quantity | Display order | ACTIVE/INACTIVE`
(`Min selections=0` means optional; `>=1` means required. No direct additional-price field exists.)

## COMBOS / PACKAGES

Applicable: `YES / NO`
`Parent product | Fixed component products | Quantities | Choice groups/options | Parent ProductPrice | ACTIVE/INACTIVE`

## BUFFETS

Required by the restaurant: `YES / NO`
No fillable buffet fields exist in the current repository. A YES answer identifies a capability gap.

## FIXED MEALS

Applicable: `YES / NO`
`Parent product | Fixed course products/quantities | Choice groups/options | Parent ProductPrice | ACTIVE/INACTIVE`
Time/service-period availability is unsupported.

## PROMOTIONS

Applicable: `YES / NO`
`Name | Description | PERCENTAGE_DISCOUNT/FIXED_AMOUNT_DISCOUNT | Benefit value | Currency (fixed only) | Starts at (timezone-aware) | Ends at (timezone-aware) | All locations YES/NO | Product scope | Location scope | Combinable YES/NO | Priority | ACTIVE/INACTIVE`

## FISCAL

Tax rule: `Scope | Tax classification code | Jurisdiction code | Tax category | Treatment | TRANSFERRED/WITHHELD | Rate | Calculation policy | Rounding policy | Effective from | Effective to (optional) | ACTIVE/INACTIVE`
Per product: `Product | Fiscal jurisdiction | Product classification scheme | Product classification code | Unit classification scheme | Unit classification code | Effective from | Effective to (optional) | ACTIVE/INACTIVE`
Issuer, only if invoicing: `Legal name | Tax identifier | Tax regime | Fiscal postal code | ACTIVE/INACTIVE`

## PAYMENTS

`Method (CASH/CARD/TRANSFER) | Enabled YES/NO | Currency | Provider (non-cash only)`

## PRINTERS

`Purpose (preparation/paid account) | Area (preparation only) | Brand/model | Adapter (cups/escpos_network/escpos_usb) | CUPS queue or TCP host:port or USB device path | Columns (32/42/48) | Encoding | Paper width | ESC/POS YES/NO | Cutter compatible YES/NO`

## CERTIFICATION SESSION CLOSURE

CashSession 1 actual closing count (MXN):
Variance reason (only if different):
Authorize closure of certification service session 1: `YES / NO`

# PILOT READINESS MATRIX

| Capability | Status |
|---|---|
| Tenant | READY |
| Organization | READY |
| Location | READY |
| Administrator | NEEDS OPERATOR DATA |
| Staff | NEEDS OPERATOR DATA |
| Tables/resources | NEEDS OPERATOR DATA |
| Cash register | NEEDS OPERATOR DATA |
| Preparation areas | NEEDS OPERATOR DATA |
| Preparation routing | NEEDS OPERATOR DATA |
| Menu | NEEDS OPERATOR DATA |
| Prices | NEEDS OPERATOR DATA |
| Modifiers/options | NEEDS OPERATOR DATA |
| Combos/packages | NEEDS OPERATOR DATA |
| Buffets | NEEDS OPERATOR DATA |
| Fixed meals | NEEDS OPERATOR DATA |
| Promotions | NEEDS OPERATOR DATA |
| Fiscal/tax | NEEDS OPERATOR DATA |
| Payment methods | NEEDS OPERATOR DATA |
| Conekta TEST | READY |
| Print destinations | DEFERRED TO FINAL HARDWARE |
| Local Connector | DEFERRED TO FINAL HARDWARE |
| Operating configuration | NEEDS OPERATOR DATA |

# DELIVERABLES

- D1 PASS
- D2 PASS
- D3 PASS
- D4 PASS
- D5 PASS
- D6 PASS
- D7 PASS
