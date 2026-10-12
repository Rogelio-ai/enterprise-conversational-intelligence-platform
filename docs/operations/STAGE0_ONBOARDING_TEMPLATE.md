# Stage 0 restaurant onboarding workbook

Contract version: `restaurant-onboarding/v1`

The Product-approved workbook is
`docs/operations/templates/ECIP_Stage0_Restaurant_Onboarding.xlsx`.

It is an immutable 35-sheet capture artifact: `Instructions`, `Metadata`, `_Lists`, and 32
capture sheets. Do not regenerate, rename, reformat, or replace it through the legacy template
generator. Its approved pristine SHA-256 is
`52036dd971c570b52448ddc33c0554329616adcc4e661417f3c98f1a2e3b4fff`.

Metadata uses the exact four-column header `field,value,required,notes`. Complete every field
marked `YES`, retain `contract_version=restaurant-onboarding/v1` and
`dataset_kind=REAL_PREPILOT`, and set the dataset plus applicable rows to `CONFIRMADO` only after
Restaurant review. Use `NO APLICA` for an intentional exclusion. A confirmed operational
Organization must identify exactly one confirmed active headquarters Location.

The analyze and coverage endpoints recognize this official profile without changing it. Coverage
separates capture recognition from actual import support; a recognized worksheet is not proof that
its rows can be persisted. The certified incremental confirmation boundary is:

- bind one confirmed Organization and one confirmed headquarters Location to the exact existing,
  authorized server scope; this path does not create or replace either record;
- import confirmed Categories, Menus, Menu Sections, and Menu Items through their existing owners;
- import the core confirmed Product while reporting `PARTIAL` because `sale_uom` has no current
  Product owner field; and
- import confirmed undated MXN Prices while deferring any row with `valid_from` or `valid_to`.

All other populated official rows remain explicitly deferred. `NO APLICA` rows are intentionally
excluded. Confirmation fails closed on scope, permission, owner-plan, and reference conflicts.

Do not enter passwords, hashes, tokens, access codes, provider credentials, generated database
IDs, stock movements, lots, receipts, losses, preparation batches, transfers, valuation history,
or payment-provider secrets. Workbook identifiers are business-supplied or workbook-local as
defined by the approved Stage 0 Capability SDD; they never authorize cross-Tenant resolution or
invent a domain identifier.

The historical generator and its in-memory workbook remain only as legacy executable-contract
regression evidence. They are not the official operator workbook and must not recreate the deleted
`ECIP_Stage0_Restaurant_Onboarding_v1.xlsx` artifact.
