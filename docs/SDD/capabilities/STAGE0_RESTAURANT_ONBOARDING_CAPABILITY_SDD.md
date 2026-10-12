# RESTAURANT INTELLIGENCE PLATFORM
# STAGE 0 RESTAURANT ONBOARDING CAPABILITY SOFTWARE DESIGN DOCUMENT

**Capability:** Stage 0 Restaurant Onboarding
**Document:** `STAGE0_RESTAURANT_ONBOARDING_CAPABILITY_SDD.md`
**Template:** `CAPABILITY_SDD_TEMPLATE.md`
**Status:** APPROVED
**Version:** 0.1.0
**Owner:** Restaurant Onboarding Domain
**Last Updated:** 2026-10-11

---

# 1. PURPOSE

Define the technical design that makes the approved Stage 0 workbook the capture authority while
reusing the existing WS-35 analyze, coverage, planning, confirmation, provisioning, replay, and
evidence implementation. The capability converts confirmed workbook capture into authorized,
Tenant-safe calls to existing owning capabilities; it does not make the workbook an independent
source of domain truth or persistence ownership.

---

# 2. AUTHORITY

## 2.1 Governing Sources

```text
Product Authority:
  - Project Operator acting as Product Owner, explicit APPROVED decision dated 2026-10-11:
    docs/operations/templates/ECIP_Stage0_Restaurant_Onboarding.xlsx is the official Stage 0
    capture format, contract identifier restaurant-onboarding/v1.
Domain Authority:
  - domain-packs/restaurant/RESTAURANT_DOMAIN_MODEL.md
  - applicable domain-pack modules 01-04, 09-12, 20, 23-24 and 26-28
  - domain-packs/restaurant/39_Restaurant_Business_Rules.md
Global Architectural Authority:
  - AGENTS.md
  - docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
Global SDD:
  - docs/SDD/GLOBAL_SDD.md (APPROVED, version 0.2.0)
Applicable ADRs: None found
Security Baseline: docs/SDD/GLOBAL_SDD.md Section 18
Reuse Policy: docs/SDD/GLOBAL_SDD.md Section 32
Related Capability SDDs:
  - docs/SDD/capabilities/IDENTITY_AUTHORIZATION_CAPABILITY_SDD.md version 0.2.0
  - docs/SDD/capabilities/ORGANIZATION_LOCATION_PROVISIONING_CAPABILITY_SDD.md version 0.1.0
Executable/repository contracts:
  - apps/api/app/onboarding/
  - apps/api/app/api/routes/onboarding.py
  - apps/api/app/models/onboarding.py
  - apps/api/alembic/versions/0052_onboarding_import_evidence.py
  - onboarding binding migrations 0053-0055 and Staff continuation migrations 0056-0057
```

The Product Owner approval fixes the workbook capture format. It does not approve this SDD, a
particular implementation, automatic role policy, or persistence semantics not resolved here.

## 2.2 Authority of This SDD

After explicit approval, this document is authoritative for Stage 0 onboarding technical design.
It does not redefine the workbook's product fields, Restaurant domain behavior, or state owned by
P01, P02, or another Restaurant capability.

## 2.3 Approval Record

```text
Document path: docs/SDD/capabilities/STAGE0_RESTAURANT_ONBOARDING_CAPABILITY_SDD.md
Document version: 0.1.0
Approving authority/role: Architecture Authority; Product Owner additionally required only for
  changes to the approved workbook/product decision
Explicit decision: APPROVED — implementation authorized for Phases A-C only; Phase D excluded
Decision date: 2026-10-11
Approval evidence/reference: Explicit operator decision in "P04 — APPROVAL REGISTRATION +
  STAGE 0 IMPORTER ALIGNMENT — PHASES A–C — IMPLEMENTATION & CERTIFICATION — FINAL"
Open conditions: NONE for Phases A-C; Phase D remains excluded and requires separate authority
```

## 2.4 Approved Workbook Decision Record

```text
Artifact: docs/operations/templates/ECIP_Stage0_Restaurant_Onboarding.xlsx
Contract identifier: restaurant-onboarding/v1
Approving authority/role: Project Operator acting as Product Owner
Explicit decision: APPROVED
Decision date: 2026-10-11
Approved scope: Official Stage 0 Restaurant capture format
SHA-256 evidence: 52036dd971c570b52448ddc33c0554329616adcc4e661417f3c98f1a2e3b4fff
Implementation approval: NOT IMPLIED
```

---

# 3. CAPABILITY BOUNDARY

## Owns

- Recognition and interpretation of the approved 35-sheet workbook profile.
- Capture normalization, validation, cross-sheet reference resolution, coverage, and deterministic
  import planning.
- Authorized orchestration of existing owning application services.
- Dataset fingerprinting, replay decisions, import result/evidence, and honest partial status.
- Mapping workbook-local references to authoritative persisted identities without inventing
  business data.

## Does Not Own

- Workbook product fields or business meaning; Product/Domain Authority owns those.
- Tenant, Organization, Location, headquarters, Identity, roles, grants, catalog, inventory,
  preparation, payment, cash, or fiscal state.
- Automatic permission or administrative-role creation.
- Credential capture, payment-provider secrets, opening stock, operational transactions, or real
  Restaurant data outside an authorized confirmation.
- A frontend workflow or a new preview endpoint.

---

# 4. SCOPE, NON-GOALS AND DEFERRED

## 4.1 In Scope

- Official workbook identity, Metadata, all 32 capture sheets, controlled values, and references.
- Progressive capture/import coverage independent of workbook completeness.
- P01/P02-compatible Organization, Location, Staff, and Location-role binding.
- Existing WS-35 analysis, planning, persistence authority adapters, replay, and evidence.

## 4.2 Non-Goals / Out of Scope

- Modifying or regenerating the approved workbook.
- Importing worksheets whose owning persistence/service contract is unavailable.
- Creating new domain models merely to mirror workbook columns.
- Staff credentials, payment execution, cash sessions, stock movements, receipts, lots, losses,
  batches, transfers, or valuation history.
- New public endpoints, frontend, infrastructure, or broad Restaurant redesign.

## 4.3 Deferred

| ID | Requirement | Reason | Dependency | Blocking |
|---|---|---|---|---|
| D-001 | Full import for offers, buffets, fixed meals, modifiers, promotions, recipes, devices, and cash-register policy | Current executable authority is absent or incomplete for the official schema | Approved owning-capability contract and implementation | NO for Phase A-C; YES for claiming that worksheet imported |
| D-002 | Payment-method activation/executor configuration | Operational/credential workflow, not catalog import | Approved Payment capability workflow | NO; capture remains reportable |
| D-003 | Full combined `Fiscal_Tax` interpretation | Official sheet does not carry all current separate tax/product-classification inputs | Approved fiscal mapping or workbook product decision | NO for capture; YES for full import |

---

# 5. EXISTING SYSTEM / DISCOVERY BASELINE

```text
Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Commit: 62c4ebebcec36ec35aebab8218352c5f2158ed5e
Migration head: 0069_org_hq_provisioning

Relevant backend:
  apps/api/app/onboarding/{contract,xlsx,analyzer,importer,staff_provisioning}.py
  apps/api/app/api/routes/onboarding.py
Relevant frontend: N/A
Relevant domain modules: app.identity, app.organization_location, app.minimal_provisioning,
  app.restaurant catalog/menu/pricing/resource/preparation/inventory/tax/fiscal provisioning
Relevant tables: onboarding_imports, onboarding_staff_continuations, existing owned business tables,
  and existing catalog/menu binding tables
Relevant endpoints:
  GET /onboarding/stage0/coverage
  POST /onboarding/stage0/analyze
  POST /onboarding/stage0/confirm
Relevant integrations: internal owning capability services only
Relevant tests: test_stage0_onboarding_contract.py, test_stage0_onboarding_analysis.py,
  test_stage0_onboarding_confirmed_import.py, test_stage0_staff_provisioning.py
Relevant documentation: docs/operations/STAGE0_ONBOARDING_TEMPLATE.md and related SDDs
```

Existing WS-35 is `IMPLEMENTED_NOT_CERTIFIED` for its legacy generated schema. It classifies 21
legacy groups as importable, ten as deferred, and payment methods as operational-only. The
approved workbook is currently rejected before row parsing: its 32 capture sheets have different
names/schemas, Metadata has four columns, and the executable template identity expects the deleted
`ECIP_Stage0_Restaurant_Onboarding_v1.xlsx`. This is a legacy executable-contract discrepancy,
not authority to change the approved workbook.

---

# 6. REUSE ANALYSIS

| Component | Owner | Reuse | Required Change | Risk |
|---|---|---|---|---|
| Official workbook | Product Authority | Reuse as-is | None; bytes protected | Product drift if regenerated |
| `analyze_xlsx` / normalized analysis DTOs | Onboarding | Reuse with extension | Recognize official profile and Metadata | Structural false acceptance |
| `coverage` | Onboarding | Reuse with extension | Report official worksheets separately from importability | False readiness claims |
| `build_import_plan` / `confirm_import` | Onboarding | Reuse with adapter | Consume official normalized rows and preserve existing evidence semantics | Partial/replay drift |
| Existing provisioning modules | Owning capabilities | Reuse as-is where contract fits | Official-code adapters only | Ownership bypass |
| P02 Organization/Location/minimal provisioning | Enterprise Core | Reuse as-is/with bounded composition | Workbook orchestration calls P02; no parallel writes | Headquarters violation |
| P01 Staff invitations/access participant | Identity | Reuse as-is | Map confirmed Staff/role/location inputs | Privilege escalation |
| Onboarding/binding/evidence tables | Onboarding and owning capabilities | Reuse as-is where sufficient | Profile marker in evidence result; migration only if implementation proves necessary and receives authority | Legacy ambiguity |

No service, microservice, queue, alternate Organization/Location repository, or alternate Identity
provisioner is justified.

---

# 7. ACTORS AND DOMAIN CONCEPTS

## 7.1 Actors

| Actor | Responsibility | Relevant Authorization |
|---|---|---|
| Restaurant data capturer | Enters approved capture data; cannot import by workbook possession | No import authority implied |
| Restaurant confirmer | Confirms capture accuracy in workbook metadata | Product/business confirmation; not server authorization |
| Authorized Staff importer | Analyze and confirm within active Tenant/Location authority | Existing authenticated membership and per-owner permissions |
| Owning capability service | Validate/mutate its state | Existing P01/P02/Restaurant service contract |

## 7.2 Domain Concepts

| Concept | Meaning | Authoritative Source | Technical Representation |
|---|---|---|---|
| Official workbook | Approved Stage 0 capture format | Product decision, 2026-10-11 | 35-sheet XLSX profile |
| Capture row | Proposed Restaurant configuration with capture status | Official workbook | Normalized analyzed row |
| Import plan | Deterministic proposed owning-service operations | This SDD | Existing `ImportPlan` extended for official groups |
| Import evidence | Durable result/replay record | Existing WS-35 contract | `OnboardingImport` and result JSON |
| Headquarters | One current valid Location for operational Organization | P02 SDD | P02-owned Organization reference/history |
| Workbook-local reference | Stable source identity only within this workbook contract/profile | This SDD | Namespaced source key/binding, never invented business ID |

---

# 8. INVARIANTS

```text
S0-INV-001 — Official capture authority
Rule: The approved workbook profile is recognized without renaming, deleting, or silently changing
      its fields; incompatible schema is rejected explicitly.
Authority: Product approval; Global SDD GLOBAL-INV-007.
Enforcement: Exact required sheet/header profile and Metadata contract validation.
Failure behavior: INVALID analysis; no plan or business write.
Verification: C01-C03, C15.

S0-INV-002 — Tenant and ownership isolation
Rule: Workbook identifiers resolve only inside the authenticated Tenant and applicable
      Organization/Location; identical codes never establish cross-Tenant identity.
Authority: BR-CORE-001..004; Global SDD GLOBAL-INV-001.
Enforcement: Server context, scoped queries, owning services, relational constraints.
Failure behavior: Reject without mutation or cross-Tenant disclosure.
Verification: C04, C10.

S0-INV-003 — Ownership reuse
Rule: Onboarding orchestrates owning services and never directly creates competing P01/P02 or
      Restaurant-owned persistence behavior.
Authority: Global SDD Sections 4, 9, 32; P01/P02 SDDs.
Enforcement: Adapter/service dependency boundary.
Failure behavior: Unsupported coverage or implementation stop.
Verification: C08, C11-C14.

S0-INV-004 — Identifier integrity
Rule: Source identifiers are classified, normalized, scoped, and replayed deterministically;
      workbook-local references are not persisted as invented domain identifiers.
Authority: Product workbook rules; Global SDD Sections 9, 14.
Enforcement: Section 11 mapping and existing unique bindings/authorities.
Failure behavior: Duplicate/conflict/unresolved-reference error.
Verification: C04-C05, C09.

S0-INV-005 — Non-mutating analysis
Rule: Coverage and analysis perform no business or evidence writes.
Authority: Product workbook rules; Global SDD Sections 3, 12.
Enforcement: Parser/analyzer dependencies exclude persistence mutation.
Failure behavior: Any write is certification failure.
Verification: C06.

S0-INV-006 — Honest progressive coverage
Rule: Capture support, import support, partial support, unsupported status, and not-applicable
      status are distinct and never reported as one another.
Authority: Product approval.
Enforcement: Per-worksheet coverage contract and result summaries.
Failure behavior: Confirmation blocks unsafe content; no false imported count.
Verification: C07, C14.

S0-INV-007 — Valid partial state only
Rule: Each owning aggregate and the P02 core/Identity composition is atomic. A recoverable PARTIAL
      import may contain completed valid aggregates plus durable evidence, never invalid partial
      aggregates or falsely completed rows.
Authority: Global SDD Sections 12, 28; existing WS-35 PARTIAL contract.
Enforcement: Owning transactions, typed outcomes, replay evidence.
Failure behavior: Roll back affected unit and persist accurate recoverable result.
Verification: C08-C09, C16.
```

---

# 9. LIFECYCLE AND KEY FLOWS

## 9.1 State Model

```text
CAPTURED XLSX
    ↓ analyze (no writes)
VALID | INVALID
    ↓ coverage + deterministic plan (no writes)
CONFIRMABLE | BLOCKED_BY_COVERAGE_OR_VALIDATION
    ↓ authorized explicit confirmation
SUCCESS | PARTIAL | FAILED
    ↓ exact replay
UNCHANGED / RESUMED ACCORDING TO EXISTING EVIDENCE
```

`PENDIENTE`, `CAPTURADO`, and `POR CONFIRMAR` rows are never import candidates.
`CONFIRMADO` makes a populated row an import candidate subject to validation and coverage.
`NO APLICA` records an intentional capture exclusion and is never imported. Workbook confirmation
does not substitute for server authorization.

## 9.2 Key Use Cases

```text
UC-001 — ANALYZE OFFICIAL WORKBOOK
Actor: Authenticated Staff user.
Preconditions: XLSX boundary valid.
Trigger: POST /onboarding/stage0/analyze.
Main flow: Recognize profile; validate Metadata, sheets, headers, controlled values, rows,
           duplicates and references; normalize deterministically; return coverage inputs.
Postconditions: No database mutation.
Failure cases: Explicit workbook/sheet/row/field errors.

UC-002 — CONFIRM SUPPORTED PLAN
Actor: Authorized Staff importer.
Preconditions: Valid analysis, matching fingerprint, explicit confirmation and sufficient scope.
Trigger: POST /onboarding/stage0/confirm.
Main flow: Build complete plan; block unsafe dependencies; invoke owning services in dependency
           order; record exact outcomes and replay evidence.
Postconditions: Only authorized supported records persist; summaries match actual outcomes.
Failure cases: Atomic unit rollback and FAILED/PARTIAL evidence according to Section 21.

UC-003 — SAFE REPLAY
Actor: Same authorized class of caller.
Preconditions: Same normalized dataset, profile, scope and fingerprint.
Trigger: Repeated confirmation.
Main flow: Return/resume existing evidence; do not duplicate business entities or side effects.
Postconditions: Existing identities and history preserved.
```

---

# 10. OWNERSHIP

| Entity / State | Owner | Scope | Cross-Owner Access |
|---|---|---|---|
| Workbook format/fields | Product Authority | Stage 0 product contract | Onboarding interprets only |
| Normalized analysis/plan | Onboarding | Request + authenticated scope | Owning services consume planned inputs |
| Import/replay evidence | Onboarding | Tenant + Organization + Location + actor | Read through authorized onboarding behavior |
| Tenant/Organization/Location/headquarters | Enterprise Core/P02 | Tenant/Organization | Onboarding calls P02 |
| User/membership/role/grant/invitation | Identity/P01 | Tenant/Location | Onboarding calls P01 |
| Restaurant records | Respective capability | Organization/Location/aggregate | Onboarding calls public/application contract |
| Payment credentials/effects | Payment capability | Tenant/Location/provider | Never captured or imported here |

---

# 11. DATA MODEL AND INTEGRITY

## 11.1 Official Workbook Contract

The pristine approved template has SHA-256
`52036dd971c570b52448ddc33c0554329616adcc4e661417f3c98f1a2e3b4fff`, 35 worksheets,
and contract identifier `restaurant-onboarding/v1`. The checksum identifies approved template
bytes; populated workbooks are recognized by contract/profile structure, not by equal checksum.

All 267 capture headers use the same dark-blue structural style. This means every header/column is
part of the required schema; it does not mean every cell is non-null. Cell requiredness comes from
explicit Metadata `required`, identifier/reference needs, capture status, and the target owning
service contract. `notes`, explicitly optional fields such as `email_optional`, and fields the
owning contract permits to be absent remain optional. Unknown or reordered contract columns are
rejected unless a future approved contract version defines compatibility.

Controlled values are exactly the workbook lists: `ACTIVE/INACTIVE`, `YES/NO`, capture states,
resource types, payment categories, UOM values, preparation modes, optionality, promotion types,
executor kinds, tax modes, date-control values, and Staff role examples. A list example does not
create a Role, permission, payment executor, or domain enum absent from its owner.

## 11.2 Worksheet Inventory and Progressive Coverage

Current coverage means executable support for the approved workbook itself. Every capture sheet is
currently `IMPORT_UNSUPPORTED` because the legacy analyzer rejects the profile before row parsing.
Target capture support for all rows begins in Phase A; target import status remains bounded by the
listed owner.

| Worksheet | Owner; key fields; references | Existing authority / target import | Priority |
|---|---|---|---|
| Organizations | P02; `organization_code`; none | P02 services / `IMPORT_SUPPORTED` | B |
| Locations | P02; `organization_code`,`location_code`,`is_headquarters`; Organizations | P02 services / `IMPORT_SUPPORTED` | B |
| Staff | P01; `staff_username`; none | Existing identity or email invitation; blank-email new identity unsupported / `IMPORT_PARTIAL` | B |
| Staff_Location_Roles | P01; staff, location, `role_key`; Staff, Locations | Identity participant / `IMPORT_SUPPORTED` | B |
| Resources | Resource; location/resource codes | Existing provisioner / `IMPORT_SUPPORTED` | C |
| Cash_Registers | Resource/Cash; register/resource codes | Resource identity exists; cash policy incomplete / `IMPORT_PARTIAL` | D |
| Prep_Areas | Preparation; location/area/printer codes | Area provisioner; printer linkage incomplete / `IMPORT_PARTIAL` | C |
| Printers_Devices | Resource/Preparation integration; device/location | Resource identity only / `IMPORT_PARTIAL` | D |
| Categories | Catalog; category/parent codes | Existing namespaced binding / `IMPORT_SUPPORTED` | C |
| Products | Catalog; product/category codes | Existing namespaced binding / `IMPORT_SUPPORTED` | C |
| Menus | Menu; location/menu codes | Existing namespaced binding / `IMPORT_SUPPORTED` | C |
| Menu_Sections | Menu; menu/section codes | Existing namespaced binding / `IMPORT_SUPPORTED` | C |
| Menu_Items | Menu; menu/section/item/product codes | Existing provisioner; item code is source-only / `IMPORT_SUPPORTED` | C |
| Prices | Pricing; location/item/amount/dates | Existing price authority / `IMPORT_PARTIAL` pending exact date mapping | C |
| Modifier_Groups | Product structure; group code | Models exist; onboarding authority absent / `IMPORT_UNSUPPORTED` | D |
| Modifier_Options | Product structure; group/option/product | Models exist; onboarding authority absent / `IMPORT_UNSUPPORTED` | D |
| Packages_Combos | Product/offers; offer/component codes | No complete official-schema authority / `IMPORT_UNSUPPORTED` | D |
| Buffets | Offers; buffet code | Required persistence authority unavailable / `IMPORT_UNSUPPORTED` | D |
| Buffet_Items | Offers; buffet/product/group/area | Required persistence authority unavailable / `IMPORT_UNSUPPORTED` | D |
| Fixed_Meals | Offers; offer/course fields | Required persistence authority unavailable / `IMPORT_UNSUPPORTED` | D |
| Promotions | Pricing; promotion code/dates/scope | Model exists; onboarding authority incomplete / `IMPORT_UNSUPPORTED` | D |
| Warehouses | Inventory; location/warehouse codes | Existing provisioner / `IMPORT_SUPPORTED` | C |
| Inventory_Items | Inventory; inventory/warehouse codes | Existing service / `IMPORT_SUPPORTED` | C |
| UOM_Conversions | Inventory; inventory/from/to UOM | Existing service / `IMPORT_SUPPORTED` | C |
| Suppliers | Purchasing; supplier code | Existing receiving authority / `IMPORT_SUPPORTED` | C |
| Supplier_Offerings | Purchasing; supplier/inventory codes | Existing receiving authority when inventory resolves one Location / `IMPORT_PARTIAL` | C |
| Consumption_Definitions | Inventory; product/consumption codes | Existing aggregate provisioner only with one unambiguous Location / `IMPORT_PARTIAL` | C |
| Consumption_Components | Inventory; consumption/inventory codes | Inherit definition scope; ambiguous Location unsupported / `IMPORT_PARTIAL` | C |
| Recipes | Inventory/Preparation; product/recipe/component | Existing models but official mapping incomplete / `IMPORT_PARTIAL` | D |
| Preparation_Routing | Preparation; location/product-or-component/area/printer | Product-area route supported; component/printer incomplete / `IMPORT_PARTIAL` | C/D |
| Payment_Methods | Payment; location/method/executor | Operational workflow, not catalog import / `NOT_APPLICABLE` | D |
| Fiscal_Tax | Tax/Fiscal; location/tax/classification | Existing separate authorities; combined mapping incomplete / `IMPORT_PARTIAL` | C/D |

Auxiliary worksheets are `CAPTURE_SUPPORTED` in Phase A and `NOT_APPLICABLE` for business-row
import: `Instructions`, `Metadata`, and `_Lists`.

## 11.3 Identifier Classification and Mapping

Normalization trims outer whitespace and applies Unicode NFC while preserving case. Resolution is
exact after normalization and scoped to authenticated Tenant plus the owning Organization/Location.
Any collision introduced by normalization is an error.

| Source fields | Class | Target / rule | Uniqueness and replay |
|---|---|---|---|
| `organization_code`, `location_code` | A — BUSINESS_SUPPLIED | P02 `Organization.code`, `Location.code` | Existing P02 Tenant/Organization scopes; same value converges, drift conflicts |
| `staff_username` | A — BUSINESS_SUPPLIED | P01 canonical `User.username` | Existing Identity uniqueness; no credential overwrite |
| `resource_code`, `register_code`, `device_code`, `area_code`, `warehouse_code`, `inventory_code`, `supplier_code` | A when owning model exposes code; otherwise C | Existing owner code/provisioning contract; aliases only through explicit adapter | Owner scope and constraints; replay resolves same entity |
| `category_code`, `product_code`, `menu_code`, `section_code` | C — WORKBOOK_LOCAL_REFERENCE | Existing namespaced external/onboarding mappings; official code becomes source key, not an invented model field | Namespace includes official profile and Tenant/Organization scope; immutable binding conflicts on drift |
| `item_code` | C — WORKBOOK_LOCAL_REFERENCE | Resolves official Prices and dependent rows to the authoritative MenuItem composite; not persisted as a domain code without owner authority | Unique within menu/location capture scope; replay resolves same MenuItem |
| `role_key` | C — WORKBOOK_LOCAL_REFERENCE | Exact selector for an already-existing Tenant Role name; examples do not create roles or grants | Tenant-scoped; missing/ambiguous role rejects |
| modifier/option/offer/buffet/promotion/consumption/recipe/method/tax codes | C until owner exposes an approved business code | Workbook cross-sheet identity and, where an existing binding exists, namespaced source mapping | Workbook/owner scope; unsupported persistence never claimed |
| Legacy internal `*_key` adapter values | B — PLATFORM_GENERATED technical input | Deterministically equal to the normalized official source code inside the official-profile namespace; never accepted as extra workbook columns | Stable for same profile/scope/source; collision rejects |
| Dataset fingerprint, import UUID, binding namespace | B — PLATFORM_GENERATED | Canonical normalized payload/profile/scope or platform UUID as applicable | Durable replay identity; excludes mutable XLSX metadata |
| Database primary/foreign keys | D — PERSISTED_INTERNAL_ID | Generated/resolved only by owning persistence | Never accepted from workbook; preserved on replay/update |

Business-supplied values are never synthesized. A source code whose target lacks an approved code
field remains workbook-local; changing it into a new domain identifier requires owner design and,
where business meaning changes, Product/Domain approval.

## 11.4 Scope Derivation Rules

Scope may be derived only through an exact, already validated reference path:

- Organization-scoped rows without `organization_code` inherit the single Metadata/Organizations
  identity. Multiple confirmed Organizations or disagreement with Metadata is invalid under v1.
- A row with `location_code` resolves that exact confirmed Location in the authenticated Tenant and
  Organization.
- `Inventory_Items` inherits Location from its uniquely resolved `warehouse_code`.
- `Supplier_Offerings` inherits Location from its uniquely resolved `inventory_code`; it is blocked
  if that inventory identity is missing or ambiguous. Suppliers themselves remain Organization-owned.
- Consumption Definitions and Components contain no Location reference. They may be imported by
  the existing Location-scoped authority only when the confirmed workbook has exactly one Location;
  otherwise they remain capture-supported/`IMPORT_PARTIAL` and confirmation reports the ambiguity.
- Menu Sections inherit scope from Menu; Menu Items inherit Menu, Section, Product, and Location;
  Prices resolve `item_code` plus explicit `location_code` to one MenuItem/Product.
- No scope is inferred from row order, lowest database ID, matching code in another Tenant, or an
  arbitrary headquarters.

## 11.5 Metadata Contract

The official four-column header is exactly `field,value,required,notes`. Required keys are
`contract_version`, `dataset_kind`, `restaurant_name`, `organization_code`, `capture_status`,
`captured_by`, `confirmed_by`, and `confirmed_at`; `notes` is optional. Requiredness comes from the
Metadata `required` column, which must contain `YES` or `NO` consistently with this contract.

- `contract_version` must equal `restaurant-onboarding/v1`.
- `dataset_kind` must equal `REAL_PREPILOT` for an operator workbook; automated tests use synthetic
  fixtures without real Restaurant information.
- Metadata `capture_status` must be `CONFIRMADO` before confirmation.
- `organization_code` must equal the single confirmed Organizations identity being bound.
- Tenant identity is never taken from the workbook; it comes exclusively from authenticated server
  context.
- Location binding comes from confirmed Locations rows and must remain inside that Organization.
- `restaurant_name`, capturer/confirmer fields, timestamp, and notes are capture provenance; they do
  not overwrite authoritative entity identity by themselves.
- Duplicate, unknown required, malformed, or conflicting Metadata is rejected. Unknown optional
  metadata is reported and rejected under v1 rather than silently ignored.

## 11.6 P02 Headquarters and Staff Convergence

For each confirmed Organization, confirmed Locations are planned through P02 in workbook order
only after identifiers and references are validated; row order never selects headquarters.

- An operational Organization must have exactly one confirmed ACTIVE Location with
  `is_headquarters=YES`. Zero or multiple YES values reject the Organization plan.
- For a new/configuration-incomplete Organization, P02 creates the first Location under its normal
  first-Location rule. If the workbook-designated headquarters is a later Location, the same
  authorized P02 composition explicitly replaces headquarters after every Location exists.
- For an existing Organization, a matching designation converges unchanged. A different YES value
  is an explicit authorized P02 replacement shown in the plan; it is never a silent overwrite.
- `is_headquarters=NO` never clears the current headquarters by itself. Inactive or cross-scope
  headquarters candidates are rejected. Existing Location identities are preserved.

Staff convergence preserves P01 behavior:

- `staff_username` first resolves an existing same-Tenant identity. Existing identity/access may be
  converged only through the P01 participant and without credential overwrite.
- A new Staff identity may use the existing invitation flow only when `email_optional` contains a
  valid deliverable address. A blank-email new identity remains `IMPORT_PARTIAL`; onboarding does
  not invent an email, password, token, or alternate activation workflow.
- `Staff_Location_Roles` executes only after identity resolution and exact existing `role_key`
  resolution. It creates no Role or permission and cannot delegate authority absent from the actor.

## 11.7 Relationships and Integrity

```text
Authenticated Tenant
  └─ Organization code
       ├─ Location codes / one P02 headquarters
       │    ├─ Staff Location roles
       │    ├─ Resources, registers, devices, preparation areas, warehouses
       │    └─ Menus, prices, inventory, routing, payment/fiscal capture
       ├─ Catalog → Products → Menus → Sections → Items
       └─ Suppliers / promotions / recipes / offers as supported
```

The analyzer validates sheet presence, exact headers, row completeness, controlled values,
duplicates, reference cardinality, reference scope, and dependency cycles before planning.
Database constraints and owning services remain authoritative for persisted integrity.

## 11.8 Persistence and Migration

```text
Current migration head: 0069_org_hq_provisioning
Migration required: NO for SDD authoring; implementation must first prove existing evidence and
  binding structures insufficient before proposing a migration
Affected tables: Existing onboarding evidence/bindings and owning business tables only
Data migration required: NO by this design
Destructive change: NO
Backward compatibility: Preserve every existing ID and historical import/evidence row
Production considerations: Never reinterpret legacy evidence as official-35-sheet evidence
```

New official-profile evidence includes a stable profile marker in `result_json` and normalized
fingerprint input. Existing legacy evidence remains readable and immutable. A schema change, if
later proven unavoidable, requires a separately authorized forward migration.

---

# 12. APPLICATION / SERVICE DESIGN

| Component | Responsibility | Inputs / Outputs | Dependencies |
|---|---|---|---|
| Official profile contract | Sheet/header/Metadata/control inventory | Workbook profile definition | Approved XLSX |
| Analyzer adapter | Normalize official rows and validate references/status | XLSX → `AnalysisResult` | Existing analyzer primitives |
| Coverage adapter | Per-official-sheet capture/import classification | Coverage DTO | Section 11.2 registry |
| Plan adapter | Translate supported official rows to existing authority commands | Analysis + server context → `ImportPlan` | Existing planners/provisioners |
| P02 orchestration adapter | Organization/Location/headquarters plus Identity participation | Confirmed Phase B rows → P02 result | P02/P01 services |
| Confirmation coordinator | Explicit authorized execution and evidence | Plan/fingerprint/context → result | Existing `confirm_import` behavior |

Analysis and coverage own no transaction. Confirmation coordinates transactions but each owning
service retains its approved mutation semantics. No adapter may directly write around an owner.

---

# 13. TRANSACTIONS, CONCURRENCY AND IDEMPOTENCY

## 13.1 Transaction Boundaries

```text
Operation: P02 Organization/Location/Staff binding
Reads/locks: Existing Tenant, Organization, Locations, actor, roles and Identity prerequisites in
             P02/P01 order
Writes: P02-owned core/headquarters/evidence plus P01-owned participant writes
Commit point: One P02 caller-owned outer commit
Rollback behavior: Total rollback on any failure
External side effects: Staff invitation delivery follows existing continuation contract

Operation: Restaurant aggregate import
Reads/locks: Owner-defined scope and natural/binding keys
Writes: One owner aggregate plus onboarding outcome evidence
Commit point: Owner-approved boundary; onboarding never splits an atomic aggregate
Rollback behavior: Affected aggregate rolls back; prior valid completed aggregates may remain and
                   are represented as PARTIAL for deterministic resume
External side effects: None unless separately owned/approved; payment effects prohibited
```

## 13.2 Concurrency

P02 lock order and headquarters revalidation remain unchanged. Other rows use existing owner lock
orders and unique constraints. Binding creation races converge only when the winning mapping is
equivalent; otherwise they return a scoped conflict. Onboarding adds no global lock.

## 13.3 Idempotency

```text
Operation: Official workbook confirmation
Required: YES
Idempotency mechanism: Official profile + contract version + authenticated scope + deterministic
                       normalized dataset fingerprint and existing unique replay identity
Persisted evidence: OnboardingImport plus owner bindings and Staff continuations
Replay behavior: Return/resume recorded result; never recreate completed equivalent entities
Duplicate side-effect prevention: Existing unique bindings, P02 operation behavior, invitation
                                   continuation, owner constraints, and evidence lookup
```

Reuse of a source identifier for non-equivalent authoritative content is a conflict, not an update
unless the owning service explicitly supports that field update.

---

# 14. API AND DTO CONTRACTS

## 14.1 API

```text
GET /onboarding/stage0/coverage
Purpose: Report every official worksheet and separate capture/import status.
Authorization: Existing authenticated context.
Response: Official profile, worksheet classification, owner, dependencies and reason.
Side effects: None.

POST /onboarding/stage0/analyze
Purpose: Analyze the official XLSX and return fingerprint, normalized summaries and explicit
         workbook/sheet/row/field issues.
Authorization: Existing authenticated context.
Request: XLSX body and optional filename; filename is diagnostic, not identity authority.
Response: Existing analysis envelope extended for official groups/profile.
Side effects: None.

POST /onboarding/stage0/confirm
Purpose: Explicitly confirm the exact analyzed dataset in authorized server scope.
Authorization: Existing authenticated context plus all permissions required by planned owners.
Request: XLSX, location/scope selection where applicable, exact dataset fingerprint, and existing
         explicit-confirmation header.
Response: Existing SUCCESS/PARTIAL/FAILED result and per-sheet actual outcomes.
Success status: Existing 201 first execution / 200 replay behavior.
Errors: 403 authorization/scope; 409 fingerprint, binding, stale or coverage conflict; 422 invalid
        analysis/Metadata/reference.
Audit effect: Existing onboarding evidence; P02/P01 and owner evidence as applicable.
```

No standalone preview endpoint is introduced. `build_import_plan` remains the internal
non-mutating preview/plan contract.

## 14.2 DTOs / Schemas

The official normalized row DTO retains worksheet, source row, capture status, normalized fields,
business/source key, resolved references, coverage class, and issues. Plan items retain owner,
operation, existing identity/version where relevant, and blocking reason. Network compatibility is
additive; legacy response fields remain until an approved version transition removes them.

---

# 15. AUTHENTICATION AND AUTHORIZATION

## 15.1 Authentication

Inherits Global SDD and P01 without exception. Workbook provenance fields are not credentials or
authentication evidence.

## 15.2 Authorization

| Operation | Required Capability | Scope | Additional Rule |
|---|---|---|---|
| Coverage/analyze | Existing authenticated membership | Active Tenant | No business writes |
| Organization/Location confirmation | Existing P02 permissions | Tenant/Organization/current and target Locations | P02 lifecycle/headquarters checks |
| Staff/role confirmation | Existing P01 access-provisioning combination | Tenant and each Location | Existing role only; actor cannot delegate absent authority |
| Restaurant worksheet confirmation | Existing owner permission(s) | Owner-defined Organization/Location | Complete plan checks every required permission before writes |

No permission, administrative role, Tenant, initial administrator, provider credential, or grant
is inferred merely from a workbook row.

---

# 16. AUDIT

| Operation | Actor | Evidence | Before/After Required |
|---|---|---|---|
| Analyze/coverage | Authenticated requester | Non-sensitive request/result logs only | No business before/after |
| Confirmation | Authorized membership | OnboardingImport result, profile/fingerprint/scope | Planned and actual per-sheet counts/outcomes |
| P02 headquarters/core change | Authorized actor | P02 evidence | P02-defined prior/new headquarters and provisioning result |
| Staff invitation/access | Authorized actor | P01 invitation/continuation/access evidence | No credential values |

Historical evidence is append-preserving and never rewritten to look like the new official profile.

---

# 17. INTEGRATIONS AND CROSS-CAPABILITY DEPENDENCIES

## 17.1 External Integrations

N/A — Stage 0 import performs no provider, POS, payment, printing, or messaging effect. Any future
external effect requires its owning approved contract.

## 17.2 Internal Capability Dependencies

| Capability | Dependency | Direction | Contract | Failure Impact |
|---|---|---|---|---|
| P01 Identity & Authorization | Staff invitation, existing Role, Location grants | Onboarding → P01 | Certified SDD/service | P02 unit rolls back or Staff continuation reports exact state |
| P02 Organization/Location | Organization, Location, headquarters, minimal provisioning | Onboarding → P02 | Certified SDD/service | Core unit rolls back; no parallel state |
| Catalog/Menu/Pricing | Category/Product/Menu/Section/Item/Price | Onboarding → owners | Existing provisioners/bindings | Aggregate fails/partial evidence |
| Resources/Preparation | Resources, areas, routes | Onboarding → owners | Existing provisioners | Aggregate fails/partial evidence |
| Inventory/Purchasing | Warehouses/items/UOM/suppliers/consumption | Onboarding → owners | Existing services | Aggregate fails/partial evidence |
| Tax/Fiscal/Payment | Capture or bounded supported configuration | Onboarding → owners | Existing separate authorities | Unsupported/partial rows block false import |

## 17.3 Events / Async Processing

N/A — existing synchronous orchestration and Staff continuation are sufficient. No queue or event
is introduced.

---

# 18. FRONTEND AND UX

## 18.1 Frontend Responsibility

N/A — this design adds no frontend. Existing API consumers may render returned coverage and issues.

## 18.2 Frontend / Backend Boundary

Backend analysis, authorization, validation, planning, and persistence remain authoritative.

## 18.3 UX Requirements

Errors identify worksheet, row, field, code, and safe value where applicable. Coverage makes
unsupported content visible before confirmation. Confirmation remains explicit.

## 18.4 Validation

Spreadsheet validation improves capture usability but does not replace server validation.

---

# 19. INTERNATIONALIZATION AND GENERATED OUTPUTS

Workbook labels/instructions may be Spanish; contract sheet names, headers, codes, controlled
values, identifiers, and monetary values are invariant. Analyzer errors follow existing API
localization policy. No printed/generated business output is introduced.

---

# 20. SECURITY AND PRIVACY

```text
Security concerns: malicious XLSX, Tenant confusion, privilege escalation, credential/provider
  secret capture, replay, formula/macro content, sensitive error/log disclosure.
Required controls: existing size/archive/member limits; no macros/formulas; exact schema;
  authenticated Tenant binding; server authorization; scoped reference resolution; explicit
  confirmation; deterministic fingerprint; secret-field rejection.
Personal data: Staff username/display name/optional email and capture provenance.
Visibility: Restricted to authenticated/authorized Tenant context.
Logging restrictions: Never log passwords, hashes, tokens, invitation acceptance tokens, provider
  credentials, full personal datasets, or workbook bytes.
```

---

# 21. FAILURE AND RECOVERY

| Failure | Persisted State | User/System Result | Recovery |
|---|---|---|---|
| Invalid workbook/profile/Metadata | Unchanged | INVALID with provenance | Correct capture under approved contract |
| Unsupported confirmed row/dependency | Unchanged before confirmation | Coverage/plan conflict | Implement approved owner support or mark genuinely not applicable |
| Unauthorized/cross-Tenant reference | Unchanged | Scoped denial | Use authorized correct scope |
| P02/P01 composed failure | Entire composed unit rolled back | FAILED/PARTIAL evidence as applicable | Correct cause and exact replay |
| Owner aggregate failure | That aggregate rolled back; prior valid units retained only when existing PARTIAL contract permits | Accurate PARTIAL/FAILED result | Resume from durable evidence |
| Process interruption after in-progress evidence | No blind re-execution | RECOVERY_REQUIRED or deterministic resume | Operator/replay path inspects evidence |
| Exact replay | No duplicate mutation | Prior/resumed result | None |
| Conflicting source binding | Existing identity unchanged | Explicit conflict | Reconcile authoritative identity; never overwrite blindly |

---

# 22. COMPATIBILITY AND LEGACY

- Existing WS-35 evidence, bindings, Staff continuations, database identities, and valid Restaurant
  data are preserved.
- The deleted `ECIP_Stage0_Restaurant_Onboarding_v1.xlsx` schema is legacy and unavailable; this
  design does not restore it or claim it as an upload contract.
- Existing legacy evidence remains readable and immutable. It is distinguished from new official
  profile evidence by the profile marker and fingerprint inputs.
- The public endpoint paths and existing result status vocabulary remain compatible.
- P01 permission catalog/grants/login and P02 lifecycle/minimal provisioning remain unchanged.
- A populated legacy workbook that does not match the official profile is rejected explicitly;
  historical import success is not retroactively invalidated or re-executed.

---

# 23. PERFORMANCE AND SCALABILITY

```text
Expected load: One bounded Stage 0 workbook; current template provides rows 2-61 per capture sheet
Latency-sensitive operations: None; operator-controlled workflow
Expected list/data size: 32 capture sheets, bounded rows
Concurrency considerations: Duplicate confirmation and owner binding races
Polling/batch constraints: No polling; process deterministically in dependency order
Known scale threshold: Reject workbook beyond established XLSX and row limits
```

No new cache, worker, queue, or distributed service is justified.

---

# 24. IMPLEMENTATION BOUNDARIES

## Allowed After Approval

- Extend the existing onboarding contract/analyzer/coverage/planner for the approved profile.
- Add bounded adapters to P02/P01 and existing Restaurant provisioning authorities.
- Add focused tests and minimal operator documentation reconciliation.
- Add profile information to existing result evidence without rewriting history.

## Conditionally Allowed

- New owner provisioning behavior only under that owner's approved design.
- A forward migration only if existing evidence/binding persistence is proven insufficient and
  separate migration authority is obtained.
- Full Phase D support only after its persistence and business semantics are approved.

## Prohibited

- Workbook changes, legacy workbook restoration, direct cross-owner table writes, new permission
  semantics, implicit administrative grants, credential/payment effects, invented Restaurant
  identifiers, unrelated refactoring, frontend/infrastructure changes, or historical evidence edits.

```text
Backend: YES
Frontend: NO
Database: NO by default; conditional only with separate authority
API: Existing endpoints only; additive response detail allowed
Infrastructure: NO
External integration: NO
```

---

# 25. IMPLEMENTATION SEQUENCE

```text
PHASE A — Official profile recognition
Objective: Metadata, exact sheets/headers, normalization, reference validation and honest coverage.
Exit: C01-C07, C14-C15 pass; no persistence path enabled by capture support alone.

PHASE B — Enterprise Core and Staff binding
Objective: Reuse P02 for Organization/Location/headquarters and P01 for Staff/Location roles.
Depends on: Phase A and approved SDD.
Exit: C08-C13 pass for Phase B rows.

PHASE C — Existing supported Restaurant authorities
Objective: Adapt official codes/references to existing WS-35 provisioners in dependency order.
Depends on: Required Organization/Location/catalog bindings.
Exit: Applicable C03-C10, C14, C16 pass for each enabled worksheet.

PHASE D — Remaining worksheets
Objective: Enable only worksheets with separately approved owner persistence and semantics.
Depends on: Section 4.3 dependencies.
Exit: Focused certification for each newly supported boundary; unimplemented rows remain honest.
```

Dependency order is: Organization → Location → Location-scoped state; Staff → Staff Location
roles; Categories → Products; Products and Menus → Menu Sections → Menu Items → Prices/dependent
offers; Warehouses/Inventory Items → UOM/consumption/recipes; Suppliers → Offerings; Resources,
devices and preparation areas → routing; tax/payment capture only through their owners.

---

# 26. TEST STRATEGY

| Requirement / Invariant | Test Level | Required Verification |
|---|---|---|
| Workbook identity/Metadata/headers | Unit + analyzer | Exact official fixture and controlled corruptions |
| Required fields/controls/references | Analyzer | Worksheet/row/field errors and dependency cases |
| Coverage truth | Contract/API | Every official sheet exactly once with actual classification |
| Non-mutation | Persistence snapshot | Analyze/coverage before/after equality |
| Identifier mapping/replay | Service + MySQL | Scoped bindings, conflict, exact replay |
| P01/P02 compatibility | Service/API + MySQL | Authorization, headquarters, outer transaction rollback |
| Supported owner imports | Focused integration | Exact created/updated/unchanged counts and state |
| Partial/unsupported behavior | Integration | No false import and no silent discard |
| Historical evidence | Persistence | Existing evidence unchanged/readable |

Use one task-owned isolated MySQL 8.4 instance at repository head. Do not use protected databases
or real Restaurant data. No full repository suite is required.

---

# 27. REGRESSION SCOPE

## Direct

```text
Affected: Stage 0 contract, analyzer, coverage, planner, confirmation, evidence and focused tests
Risk: Wrong profile, silent data loss, duplicate import, false coverage
Verification: C01-C10, C14-C16
```

## Secondary

```text
Affected: P01 invitations/access; P02 Organization/Location/headquarters/minimal provisioning;
          reused Restaurant provisioners and bindings
Dependency: Onboarding orchestration inputs and transaction participation
Verification: C08-C13 plus owner-focused regression
```

## Collateral

```text
Affected: Existing legacy evidence reads and API consumers
Shared dependency: Existing onboarding endpoints/models/status vocabulary
Verification: C16 and additive response compatibility; no broad suite unless shared code expands
```

---

# 28. CERTIFICATION SCENARIOS

All scenarios use synthetic task-owned data and isolated MySQL 8.4 where persistence applies.

| ID | Scenario | Expected evidence |
|---|---|---|
| C01 | Official workbook identity recognized | Profile/version/sheet count/hash-template evidence |
| C02 | All official headers recognized | 35 sheets accepted; exact extra/missing/reordered header failures |
| C03 | Required fields validated | Metadata and confirmed-row omissions identify sheet/row/field |
| C04 | Invalid references rejected | Missing, ambiguous, cyclic, and cross-scope references fail |
| C05 | Technical identifiers resolved | Correct A/B/C/D mapping, scoped bindings, collision rejection |
| C06 | Analyze non-mutating | Business/evidence snapshots unchanged |
| C07 | Coverage accurate | Every sheet reports capture/import status and owner truthfully |
| C08 | Authorized confirmation | Supported records equal confirmed plan and owner state |
| C09 | Replay | Second execution creates no duplicate or repeated side effect |
| C10 | Cross-Tenant rejection | Identical/mismatched codes cannot cross Tenant |
| C11 | P01 preserved | 83 permissions, grants/login unchanged; delegation enforced |
| C12 | P02 headquarters preserved | First/replacement/same-scope/operational invariant holds |
| C13 | Minimal provisioning compatible | No duplicate Organization/Location; caller-owned transaction atomic |
| C14 | Unsupported never false-imported | Explicit coverage/block/defer; zero imported count/state |
| C15 | Metadata contract | Four-column schema, required flags/version/status/binding validated |
| C16 | Historical evidence preserved | Legacy rows unchanged/readable and not misclassified/replayed |

---

# 29. ACCEPTANCE AND PASS / FAIL

```text
AC-001 — Official capture compatibility
Requirement: Approved workbook profile is recognized exactly and analyzed without workbook change.
Verification: C01-C04, C15.
PASS: Valid official fixture reaches normalized coverage/plan; invalid structure is explicit.
FAIL: Official profile rejected, silently altered, or ambiguously accepted.

AC-002 — Identifier/ownership integrity
Requirement: Every imported reference resolves deterministically through its owner and scope.
Verification: C04-C05, C09-C13.
PASS: Stable scoped identity and replay with no invented/cross-Tenant record.
FAIL: Collision, duplicate, direct owner bypass, or unauthorized mapping.

AC-003 — Honest progressive import
Requirement: Supported, partial, unsupported, and N/A coverage match actual behavior.
Verification: C07-C08, C14.
PASS: Only supported confirmed rows produce matching outcomes.
FAIL: Silent discard or false imported/supported claim.

AC-004 — Compatibility and recovery
Requirement: P01/P02 and historical evidence remain conformant; failures remain determinate.
Verification: C06, C09-C13, C16.
PASS: Required regressions pass with valid atomic/PARTIAL recovery behavior.
FAIL: Privilege/headquarters/history regression or invalid partial state.
```

Overall PASS requires every applicable enabled-phase scenario to pass, no unauthorized deviation,
and no blocking security issue. Unimplemented later phases remain excluded and cannot be reported
as certified.

---

# 30. STOP CONDITIONS

Implementation stops when workbook bytes/schema differ from the approved profile without Product
Authority; a source identifier cannot be mapped under Section 11.3; an owner service/persistence
contract is absent; P01/P02 would be bypassed; Tenant isolation or headquarters cannot be
preserved; partial behavior would silently lose confirmed data; a migration or new domain rule is
needed without approval; or isolated certification cannot be guaranteed.

---

# 31. OPEN QUESTIONS, RISKS AND DEFERRED ITEMS

## Open Questions

| Question | Impact | Blocking | Required Authority |
|---|---|---|---|
| None for Phase A-C design | The design uses existing owner semantics and leaves unavailable Phase D persistence unsupported | NO | N/A |

Phase D enablement is deferred implementation scope, not permission to invent the missing owner
contracts.

## Risks

| Risk | Impact | Mitigation | Residual Risk |
|---|---|---|---|
| Same `v1` identifier names two historical schemas | Wrong parser/replay | Official profile marker and exact schema; immutable legacy evidence | Low after Phase A |
| Codes look like business IDs where models expose no code | Invented domain identity | Section 11.3 classification and namespaced bindings | Low |
| Workbook confirmation mistaken for authorization | Privilege escalation | Server context and owner permission checks | Low |
| Partial import hides unsupported data | Lost configuration | Per-sheet coverage, blocking dependencies, exact outcomes | Low |
| P02 duplicated by direct writes | Invalid headquarters/core state | Mandatory P02 orchestration | Low |

## Deferred Items

See Section 4.3.

---

# 32. TRACEABILITY

| Requirement / Rule | Authority | SDD Section | Implementation | Verification |
|---|---|---|---|---|
| Official workbook unchanged/drives importer | Product approval | 2, 8, 11, 22 | Official profile adapter | C01-C03, C15 |
| Tenant isolation | BR-CORE-001..004; Global SDD | 8, 10, 15, 20 | Existing context/owners | C04, C10 |
| Identifier safety | Product workbook rules; Global SDD | 8, 11, 13 | Binding/plan adapters | C05, C09 |
| P01 compatibility | Identity SDD | 10, 13, 15, 17 | Existing invitation/access service | C11, C13 |
| P02 headquarters/minimal provisioning | P02 SDD | 8-10, 13, 17 | Existing P02 services | C12-C13 |
| Honest partial coverage | Product approval | 8-9, 11, 21 | Coverage/plan/result | C07, C14 |
| Historical integrity | Global SDD GLOBAL-INV-005 | 11, 16, 22 | Existing evidence + profile marker | C16 |

---

# 33. CERTIFICATION EVIDENCE

```text
SDD version: 0.1.0 — APPROVED FOR PHASES A-C; NOT YET IMPLEMENTED

Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Commit: 62c4ebebcec36ec35aebab8218352c5f2158ed5e
Working tree: Existing protected untracked files plus this documentation change
Migration head: 0069_org_hq_provisioning

Backend targeted tests: NOT RUN — design authoring only
Backend regression: NOT RUN
Frontend tests: NOT APPLICABLE
E2E: NOT RUN
Typecheck: NOT RUN
Build: NOT RUN
Migration verification: NOT RUN

Certification scenarios: C01-C16 NOT RUN
Known deviations: Official workbook versus legacy executable contract, documented in Section 5
Approved exceptions: NONE
Result: NOT CERTIFIED
Certification date: N/A
```

---

# 34. DEFINITION OF READY

```text
[x] Authority is identified
[x] Capability boundary is explicit
[x] Scope is bounded
[x] Existing implementation was inspected
[x] Reuse was evaluated
[x] Critical domain concepts are known
[x] Critical invariants are explicit
[x] Ownership is unambiguous
[x] Persistence is sufficiently designed for progressive phases
[x] API contracts are sufficiently designed
[x] Transactions/concurrency are defined where relevant
[x] Authorization/security requirements are known
[x] Implementation boundaries are explicit
[x] Verification and certification criteria are defined
[x] No blocking design question remains for Phase A-C
```

Gap review result: `PASS — READY_FOR_APPROVAL` on 2026-10-11. Section 2.3 records the subsequent
explicit approval for Phases A-C. This is not implementation or certification. Phase D worksheets
remain explicitly unsupported until their owning capability contracts are approved and available.

---

# 35. DEFINITION OF DONE

The capability is done only when this exact SDD version is explicitly approved; enabled phases are
implemented through existing owners; executable contracts conform; applicable C01-C16 scenarios
and focused regression pass in isolated MySQL 8.4; P01/P02 and historical evidence remain intact;
unsupported worksheets remain honest; no blocking security defect remains; and this SDD is
reconciled to the certified as-built boundary without claiming unimplemented phases.
