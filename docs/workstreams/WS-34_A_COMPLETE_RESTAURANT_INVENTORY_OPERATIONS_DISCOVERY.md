# WS-34-A — Complete Restaurant Inventory Operations Discovery

## Status and decision

**STATUS: CLOSED — DISCOVERY COMPLETE**

The existing inventory foundation is semantically correct and remains the only stock foundation.
WS-34 must extend it into operational authorities; it must not build a second inventory ledger.

The smallest useful Carnitas Muñoz pilot adds a single default warehouse, practical item-specific
UOM conversions, direct receiving with supplier and immutable cost evidence, immutable recipe
versions, dedicated waste, physical counts, reconciled actual consumption/variance, an explicit
negative-stock policy, standard-cost valuation, and the corresponding Staff Web workflows. Full
purchase-order workflow, prepared-component batches/yield, transfers, replenishment automation,
weighted-average costing, and lot/expiry enforcement can follow without weakening the P0 ledger.

No restaurant fact is inferred by this document. In particular, on-site raw-pork transformation,
multiple storage areas, supplier practices, and lot/expiry requirements need operator confirmation.

## Baseline and evidence

- Repository: `/home/rogelio/proyectos/pryecip`
- Branch: `feat/ws-00-01-runtime-reuse-baseline`
- Starting worktree: clean
- WS-33 predecessor: `35f7f43 feat(pilot): establish real restaurant configuration discovery`
- `git diff --check`: clean before discovery
- Inventory foundation commits: `6df055c` and `7ce2d1c`
- Primary pilot database contract: MySQL 8.4; current MariaDB portability remains required.

Sources verified:

- `apps/api/app/models/inventory.py`
- `apps/api/app/restaurant/inventory/{service,order_consumption,contracts,units,errors}.py`
- `apps/api/app/api/routes/{inventory,restaurant_orders}.py`
- `apps/api/alembic/versions/0035_inventory_recipe_stock_foundation.py`
- `apps/api/alembic/versions/0036_restaurant_order_consumption.py`
- `apps/api/tests/test_inventory_recipe_stock_foundation.py`
- `apps/api/tests/test_restaurant_order_inventory_consumption.py`
- `docs/domains/DOMAIN_APPLICATION_CAPABILITY_MAP.md`
- `docs/enterprise-core/ENTERPRISE_CORE_BOUNDARY_RULES.md`
- `CANONICAL_ENTERPRISE_INTELLIGENCE_MODEL.md`
- `docs/workstreams/WS-31_A_RESTAURANT_STAFF_OPERATIONAL_EXPERIENCE_DISCOVERY.md`

The documentation assigns Ingredient, Recipe, and Inventory Item semantics to the Restaurant
Domain. The executable code, rather than the conceptual examples, is current implementation
authority.

## D1 — Current foundation map

### Existing authority disposition

| Existing contract | Decision | Preserved authority | Required evolution |
|---|---|---|---|
| `InventoryItem` | EXTEND | Location-scoped stocked-item ID, code, base UOM, standard cost, currency, lifecycle, optimistic version | Add default warehouse relationship/policy projections, optional organization catalog identity, conversions and cost-revision evidence without changing existing IDs. |
| `ProductConsumptionDefinition` | EXTEND | One product/location consumption definition; DERIVABLE/NON_DERIVABLE coverage | Become stable recipe header with immutable versions/effective dating. Preserve current header IDs and current projection. |
| `ProductConsumptionComponent` | EXTEND | Inventory item and normalized base quantity in a product definition | Bind each row to an immutable recipe version and retain entered UOM plus conversion snapshot. Preserve existing component IDs during initial-version backfill. |
| `StockMovement` | EXTEND | Immutable quantity ledger, signs, idempotency, reversal, actor/reason/reference and sale-consumption evidence | Add warehouse, semantic source operation, entered/base UOM evidence, cost authority, and optional lot. Keep all existing movement IDs and meanings. |
| `RestaurantOrderConsumption` | PRESERVE | Exactly-once accepted-order materialization, COMPLETE/PARTIAL evidence, fingerprint and unresolved coverage | No replacement. New movements resolve recipe-version, warehouse, UOM and cost references while preserving the header contract. |

No current contract is deprecated or superseded. Existing API responses remain compatible; new
fields must be additive or exposed through versioned projections.

### Executable foundation

| Capability | Present authority |
|---|---|
| Items | Create, update with expected version, activate/inactivate, list by authorized Location |
| UOM | Exact Decimal quantities; KG/G, L/ML and identity UNIT/PORTION conversion |
| Recipes | Location-specific replace-all definition with optimistic version and normalized components |
| Stock ledger | OPENING_BALANCE, MANUAL_IN, MANUAL_OUT, ADJUSTMENT, REVERSAL, CONSUMPTION |
| Stock | Sum of immutable movements by Location and item; negative quantity allowed |
| Cost | Mutable item standard cost; current theoretical product cost; mixed currency made explicit |
| Sales consumption | Accepted order deterministically creates one header and negative movements, including combo/choice components |
| History | Recipe version number and cost/UOM/name snapshots on sale-consumption movements |
| Security | Tenant filtering, Location scope validation, `inventory.read`/`inventory.manage` |

Known properties to preserve:

- Manual movement idempotency and request fingerprints.
- One opening balance per item and one direct reversal per movement.
- Authorization before inventory disclosure.
- Missing/NON_DERIVABLE/currency-mismatch coverage never fabricates cost or blocks a sale.
- Accepted-order replay never consumes twice.
- Inventory failure rolls back order acceptance transactionally.
- Negative balances are currently valid and must remain ALLOW until an explicit policy transition.

Concrete executable evidence:

| Layer | Existing implementation |
|---|---|
| Models/tables | `InventoryItem`/`inventory_items`, `ProductConsumptionDefinition`/`product_consumption_definitions`, `ProductConsumptionComponent`/`product_consumption_components`, `RestaurantOrderConsumption`/`restaurant_order_consumptions`, and `StockMovement`/`stock_movements` in `apps/api/app/models/inventory.py` |
| Services | Item create/update/list, consumption-definition get/replace, movement create/reverse, stock/movement queries, and theoretical-cost resolution in `apps/api/app/restaurant/inventory/service.py`; accepted-order materialization and consumption lookup in `order_consumption.py` |
| APIs | `POST/PATCH/GET /inventory-items`; `GET/PUT /products/{product_id}/consumption-definition`; `POST/GET /inventory/stock-movements`; `GET /inventory/stock`; `POST /products/{product_id}/theoretical-cost:resolve`; `GET /restaurant-orders/{order_id}/theoretical-consumption` |
| Migrations | `0035_inventory_recipe_stock_foundation.py` creates items, consumption definitions/components and movements; `0036_restaurant_order_consumption.py` adds accepted-order consumption authority and movement linkage |
| Tests | `test_inventory_recipe_stock_foundation.py` certifies exact UOM, scope/permissions, optimistic item/recipe changes, cost/mixed currency, idempotency, reversal and stock sums; `test_restaurant_order_inventory_consumption.py` certifies exactly-once materialization, frozen cost, negative stock, combo selection, incomplete coverage and transactional rollback |

## D2 — Gap matrix

| Capability | Current status | Exact gap to target authority | Pilot |
|---|---|---|---|
| Raw material/ingredient identity | PARTIAL | No shared identity or behavior-driving roles | P2 taxonomy; relational roles are sufficient P0 |
| Inventory item | IMPLEMENTED | Location identity cannot unify the same item across Locations | P0 preserve; shared catalog P2 |
| UOM/conversion | PARTIAL | No box/case/bottle/bag conversion or conversion evidence | P0 item conversions |
| Warehouse/storage | MISSING | Stock is only Location-scoped | P0 one default warehouse; multiple warehouses P1 |
| Stock authority | IMPLEMENTED | No warehouse dimension/policy lock projection | P0 extend |
| Negative-stock policy | MISSING | Always ALLOW, with no warning evidence | P0 WARN policy after explicit activation |
| Supplier | MISSING | No identity, availability or offering | P0 minimum supplier |
| Purchasing | MISSING | No PO aggregate/lifecycle | P1 |
| Receiving | MISSING | MANUAL_IN is not receipt authority | P0 direct and PO-ready receipt |
| Purchase cost history | MISSING | Only mutable standard cost | P0 immutable receipt/cost evidence |
| Recipe version/effectivity | PARTIAL | Components are replaced; prior definition graph is not retained | P0 |
| Prepared component/yield | MISSING | No transformation recipe or batch input/output | P1 unless operator makes it P0 |
| Waste/loss | PARTIAL | Free-text MANUAL_OUT lacks typed loss authority/cost/approval | P0 |
| Actual consumption | MISSING | No measured or reconciled authority | P0 count-to-count reconciliation; batch actual P1 |
| Physical count | PARTIAL | ADJUSTMENT exists, but no count/approval/posting authority | P0 |
| Theoretical/actual variance | MISSING | No closed period/equation/value evidence | P0 |
| Valuation | MISSING | Stock and cost exist separately; no as-of projection | P0 STANDARD live; snapshots P1 |
| Transfer | MISSING | Independent manual movements cannot form an atomic transfer | P2 for one-warehouse pilot |
| Reorder/par | MISSING | No threshold or recommendation authority | P1 |
| Lot/batch/expiry | MISSING | No perishable traceability | P1, subject to operator/regulatory need |
| Return to supplier | MISSING | No linked compensating authority | P1 |
| Advanced traceability | PARTIAL | Strong actor/order snapshots; no receipt/supplier/lot/warehouse chain | P0 receipt/warehouse chain; lot chain P1 |
| Cost visibility security | PARTIAL | Broad inventory.read exposes costs | P0 split permission |
| Staff workflow | MISSING | Backend API exists; no Staff Web inventory workflow found | P0 bounded workflows |

## D3 — Target inventory domain model

### Identity and classification decision

`InventoryItem` remains the Location stocking identity for compatibility. A future
`InventoryCatalogItem` provides optional Organization-level identity across Locations. Existing
items can be linked without changing their IDs.

Ingredient, raw material, purchased item, and prepared component are not mutually exclusive
entities or a single enum:

- **Ingredient**: an InventoryItem used by a recipe component.
- **Purchased item**: an InventoryItem with a supplier offering or receipt line.
- **Prepared component**: an InventoryItem produced by a preparation recipe/batch.
- **Raw material**: a purchased item consumed as preparation input.
- **Packaging/supply/resale**: optional reporting categories, introduced only if they drive policy.

This relational-role model avoids false taxonomy. An item can be both purchased and used as an
ingredient, or both produced and purchased.

### Aggregate/entity model

| Name | Purpose and ownership | Identity and critical fields | Lifecycle/relationships | Authoritative invariant |
|---|---|---|---|---|
| `InventoryCatalogItem` | Optional shared Organization item identity | tenant, organization, stable code/name, optional reporting category, status | Linked by one or more InventoryItems | Never owns stock; no cross-Organization link |
| `InventoryItem` (extend) | Location stocking configuration | existing ID; optional catalog item; code/name/base UOM; standard-cost pointer; status/version | Belongs to one Location; used by positions, recipes, supplier offerings | Base UOM cannot change after material history without explicit conversion migration |
| `Warehouse` | Stock authority subdivision inside one Location | tenant/org/location, code, name, is_default, status | ACTIVE/INACTIVE; exactly one active default per Location while inventory operates | No movement may cross scope; inactive warehouse accepts only correction/reversal |
| `WarehouseInventoryPosition` | Lock/version and fast projection, not financial authority | warehouse+item, ledger version, projected on-hand, negative-policy override | Updated atomically with movement insertion | Rebuildable from StockMovement; ledger wins on mismatch |
| `ItemUomConversion` | Convert purchase/count/recipe/transfer UOM to item base UOM | item, from UOM, numerator/denominator, version, effective interval, status | Immutable version once referenced | Store entered quantity/UOM and conversion snapshot on every operation |
| `Supplier` | Restaurant purchasing counterparty, Organization-owned | code, legal/commercial name, status; optional contact/reference | Optional Location availability | Supplier identity is Restaurant Domain; credentials/payment data are out of scope |
| `SupplierLocation` | Makes a supplier selectable at a Location | supplier+location, status | Availability only | Does not duplicate supplier identity |
| `SupplierItemOffering` | Supplier SKU/package/cost expectation | supplier, item, supplier SKU, purchase UOM/conversion, optional quoted cost/currency/lead time, status | Versioned/effective | Quote is planning evidence, never receipt cost authority |
| `PurchaseOrder` | Commercial intent to buy | org/location/destination warehouse, supplier, currency, expected delivery, actor/idempotency/status/version | Owns immutable approved lines | Approval does not change stock |
| `PurchaseOrderLine` | Ordered item commitment | item, entered purchase UOM/qty, base qty snapshot, unit cost/tax evidence | Mutable only while DRAFT; received totals projected | Accepted receipts, not PO status, determine stock |
| `GoodsReceipt` | Independent receiving operation | location/warehouse/supplier, optional PO, received time, actor/idempotency/status | Owns receipt lines; supports direct receipt | Only ACCEPTED receipt posts stock, exactly once |
| `GoodsReceiptLine` | Accepted/rejected quantity and cost evidence | item, entered/base quantity, UOM conversion snapshot, unit/base cost, currency, optional lot | May reference PO line | Base quantity/cost are immutable after acceptance |
| `InventoryCostRevision` | Explicit standard-cost history | item, cost/currency, effective time, reason, actor, source receipt optional | Append-only; current revision projected | No silent mutation; historical as-of cost is reproducible |
| `ProductConsumptionDefinition` (extend) | Stable direct-sale recipe identity | existing ID/product/location; current-version pointer | ACTIVE/INACTIVE header | One current effective version per product/location |
| `ConsumptionDefinitionVersion` | Immutable recipe version | definition, version, effective interval, tracking mode, batch basis/output basis | Owns versioned components | Referenced versions never mutate |
| `ProductConsumptionComponent` (extend) | Ingredient requirement | existing ID where migrated; version, item, entered UOM/qty, normalized base qty/conversion snapshot | Child of one immutable version | Positive exact quantity; same item once per version unless grouping is explicit |
| `PreparationRecipe` | Transformation of raw inputs to a prepared InventoryItem | Location/output item; expected input/output/yield and batch basis | Immutable versions | Separate from direct-sale consumption because it creates stock |
| `PreparationBatch` | Actual practical preparation event | recipe version, warehouse(s), batch identity, actor/times/status | Inputs, outputs and losses post one atomic materialization | Input, output and loss movements balance one batch and never double-post |
| `InventoryLoss` | Dedicated waste/spoilage/breakage authority | warehouse/item, category, entered/base qty, reason, actor, cost snapshot, approval/idempotency/status | Posts one WASTE movement; reversible by compensation | Equipment failure may be a reason, never an inventory item loss itself |
| `PhysicalCount` | Count workflow for one warehouse | location/warehouse, cutoff, status, actors/timestamps/idempotency | Owns CountLines | Posting produces each line adjustment at most once |
| `PhysicalCountLine` | Observed item quantity | item, entered/count UOM, conversion snapshot, ledger cursor, expected, counted, variance | Submitted lines immutable | Post delta is based on captured cursor so later movements are preserved |
| `InventoryReconciliation` | Closed period theoretical/actual/variance evidence | period, location/warehouse/item, inputs by category, qty/value/status | Generated from ledger and count boundaries; snapshot on close | Each movement category participates once; no double counting waste/adjustments |
| `InventoryTransfer` | One logical source-to-destination operation | org, source/destination warehouse, status, actor/idempotency | Owns lines, shipment and receipt evidence | Transfer out/in are generated atomically from one transfer identity |
| `ReplenishmentPolicy` | Human-facing low-stock recommendation | item+warehouse, minimum/maximum/par/reorder qty/lead time, status | Produces alerts/projections | Never auto-creates a PO in current target |
| `InventoryLot` | Optional receipt/preparation traceability | item/warehouse, lot code, received/produced time, expiry, supplier lot, status | Referenced by movements | Lot quantity remains ledger-derived; expiry policy is explicit |
| `SupplierReturn` | Accepted stock return to supplier | supplier/warehouse, source receipt lines where known, quantities/cost, status/idempotency | Posts compensating outbound movements | Never edits the original receipt |
| `StockMovement` (extend) | Sole material ledger | existing ID plus warehouse, operation type/id, entered/base UOM, conversion, cost and optional lot snapshots | Append-only; direct reversal/compensation | Every posted material operation yields deterministic balanced ledger entries |
| `RestaurantOrderConsumption` | Accepted-sale evidence header | existing identity/fingerprint/coverage | Owns sale CONSUMPTION movements | Exactly once; missing coverage remains explicit and never fabricated |

### Warehouse decision and current-stock migration

- Every Location with inventory receives exactly one default Warehouse.
- P0 exposes the default warehouse but does not require bins or multiple stockrooms.
- New movements require warehouse scope.
- Existing Location-only InventoryItems retain IDs and are associated with the default Warehouse.
- Existing StockMovements are backfilled to that warehouse in a deterministic, auditable migration;
  quantities, timestamps, costs, references and IDs do not change.
- The sum by Location before migration must equal the sum of its default warehouse after migration.
- Additional warehouses and bins are activated only from real operator data.

## D4 — Authority, state and invariant specification

### Stock authority

`ON_HAND` is the exact sum of posted StockMovement base quantities for item+warehouse (+ lot when
enabled) at a ledger cursor/time. Opening balances, accepted receipts, issues, sale consumption,
waste, posted counts, transfers, preparation batches, returns and reversals all enter through this
ledger.

`WarehouseInventoryPosition` may provide locking and a current projection, but it is rebuildable
and never replaces the ledger. P0 does not define RESERVED or AVAILABLE because no inventory
reservation requirement exists. If later justified, `AVAILABLE = ON_HAND - RESERVED` must be a
separate projection with explicit reservation authority.

### Negative stock

Policy values are ALLOW, WARN and BLOCK. Resolution order is item+warehouse override, warehouse,
Location, then Organization default. Migration initially sets ALLOW to preserve behavior; the
recommended pilot setting is WARN.

- WARN posts the movement and immutable warning evidence.
- BLOCK serializes on WarehouseInventoryPosition and rejects employee-initiated outbound,
  transfer-dispatch and waste commands that would cross below zero.
- Accepted-sale theoretical consumption is never discarded and never rolls back a valid sale; it
  posts with a policy violation even under BLOCK.
- Receipts, positive adjustments and compensating reversals are never blocked.
- Count posting is authoritative and may reveal a negative position; it posts with an exception.

### UOM precision

- Existing global dimensional conversions remain authoritative.
- Box/case/bottle/bag conversions are item-specific; supplier offering selects the applicable
  purchase conversion.
- Base, purchase, recipe, count and transfer UOM are recorded distinctly.
- Quantities use Decimal only, with six base decimals initially.
- The entered quantity, UOM, conversion version/factor, normalized base quantity and any explicit
  rounding residual are frozen on the command/line/movement.
- Nonrepresentable results use an explicit HALF_UP-to-six-decimals policy and retain the residual;
  no binary float is permitted.

### PurchaseOrder state machine

```text
DRAFT -> SUBMITTED -> APPROVED -> PARTIALLY_RECEIVED -> RECEIVED -> CLOSED
  |         |            |
  +------> CANCELLED <----+
```

- DRAFT lines are mutable under optimistic versioning.
- SUBMITTED is reviewable; return-to-DRAFT is an explicit actor action.
- APPROVED freezes commercial lines and destination.
- PARTIALLY_RECEIVED/RECEIVED are derived from accepted receipt quantities.
- Cancellation is allowed only before accepted receipt; after partial receipt, close remaining
  quantity with reason rather than rewriting history.
- CLOSED and CANCELLED are terminal. Amendment after approval creates a linked revision/change
  order, never an in-place mutation.

### GoodsReceipt state machine

```text
DRAFT -> ACCEPTED
  |
  +-> CANCELLED
ACCEPTED -> compensating ReceiptReversal or SupplierReturn
```

- A receipt may reference a PO or be direct if Location policy permits.
- Under/partial receipt is allowed. Over-receipt requires explicit policy/approval.
- Rejected quantity is evidence but never stock.
- ACCEPTED atomically posts receipt movements and immutable base quantity/cost evidence.
- Operation identity plus idempotency key and source document uniqueness prevent duplicate receipt.

### Cost and valuation

P0 costing method is **STANDARD** because it preserves the current contract, is deterministic,
works before sufficient purchase history exists, and avoids silently choosing FIFO or average.

- Standard-cost changes become append-only InventoryCostRevisions.
- Receipt actual cost, conversion and currency remain immutable receipt/movement evidence.
- Consumption, waste, transfer, adjustment and order-consumption movements freeze the selected
  cost authority and extended cost.
- Last purchase cost and purchase-price trend are projections from accepted receipts.
- WEIGHTED_AVERAGE is P1 after receiving evidence is certified; FIFO is P2 and requires lots/layers.
- Live STANDARD valuation is derived as-of a ledger cursor/date using on-hand and the effective
  standard cost. Period valuation snapshots are P1.
- Currency is never silently converted. Results group by currency or return CURRENCY_MISMATCH.
- Negative positions are shown separately with `NEGATIVE_STOCK`; they are not hidden by netting.

### Recipe and yield authority

Direct menu recipes continue to drive accepted-sale theoretical consumption. Each immutable
version has an effective interval, batch/output basis, entered and normalized component quantity,
tracking mode and status. An accepted order freezes the exact version and cost evidence.

Prepared-item transformation is a distinct PreparationRecipe/PreparationBatch authority because
it creates stock, whereas ProductConsumptionDefinition consumes stock. Expected yield belongs to
the recipe version; actual input/output and actual preparation loss belong to the batch.

Example semantics, without claiming restaurant facts:

```text
PreparationRecipe: expected raw input -> expected prepared output/yield
PreparationBatch: actual raw input -> actual prepared output + classified actual loss
Menu recipe: prepared InventoryItem -> sold Product consumption
```

Cost of prepared output equals frozen batch input cost plus explicitly supported attributable cost,
allocated across actual good output. Expected yield predicts; it never fabricates actual waste.
Whether Carnitas Muñoz needs prepared components/batches in P0 is operator-dependent; the default
roadmap places it in P1.

### Theoretical and actual consumption

- Accepted sale continues to create deterministic theoretical CONSUMPTION exactly once.
- Missing recipe coverage stays PARTIAL and never invents quantity/cost.
- Voids/cancellations, if an authoritative commercial lifecycle later supports them, create an
  exactly-once compensating movement linked to the original consumption; no original row changes.
- Practical P0 actual consumption is count-to-count reconciled consumption. Employees do not log
  every gram.
- P1 preparation batches provide direct actual inputs for high-value preparation processes.

For a count-bounded period, recorded receipts/transfers/returns/waste/batches/adjustments are each
classified once. The signed posted count adjustment is the residual between ledger expectation and
physical reality. For direct-sale items:

```text
reconciled_actual_consumption = theoretical_consumption - signed_count_adjustment
variance_quantity             = reconciled_actual_consumption - theoretical_consumption
```

Waste already recorded before the count is reported separately and is not added again to variance.
Preparation inputs are actual consumption in their own category. The reconciliation stores its
formula/schema version and source ledger cursors.

### Loss authority

Loss categories: WASTE, SPOILAGE, BREAKAGE, PREPARATION_LOSS, EXPIRY, OTHER. They may apply to food,
prepared items, packaging or supplies; equipment is not stock loss. Required evidence is item,
warehouse, entered/base quantity, UOM conversion, category, reason, actor/time, cost snapshot,
approval decision and idempotency key. Configurable quantity/value thresholds require a second
approver. Correction is a linked compensating reversal.

### PhysicalCount state machine

```text
DRAFT -> COUNTING -> SUBMITTED -> APPROVED -> POSTED
  |          |           |
  +------> CANCELLED <----+
```

- P0 does not freeze restaurant stock globally.
- Each submitted line freezes counted quantity/UOM/time and a ledger cursor with expected quantity.
- Movements after that cursor remain valid. Posting adds the captured delta to the then-current
  ledger, so later movements are preserved.
- Variance thresholds determine whether approval is required; self-approval is prohibited when
  separation-of-duty policy applies.
- POSTED is terminal and generates each COUNT_ADJUSTMENT once. Cancellation never posts stock.

### Transfer state machine

```text
DRAFT -> APPROVED -> DISPATCHED -> PARTIALLY_RECEIVED -> RECEIVED -> CLOSED
  |          |
  +------> CANCELLED
```

Same-Location transfers may atomically post OUT+IN without in-transit state when immediately
received. Cross-Location transfers use dispatch and receipt confirmation; partial/rejected receipt
remains linked to the same transfer. Source/destination entries share transfer and line identity.
After dispatch, correction uses receipt, return or linked reversal—not cancellation. P2 for the
one-default-warehouse pilot.

### PreparationBatch state machine

```text
DRAFT -> STARTED -> COMPLETED
  |          |
  +------> CANCELLED
```

Completion atomically posts actual inputs, prepared outputs and recorded loss. A completed batch is
immutable; correction is a linked compensating batch/reversal. This state machine is P1 unless real
operator evidence promotes prepared-component tracking to P0.

### Replenishment

ReplenishmentPolicy is item+warehouse scoped and may define minimum, maximum, par, reorder point,
reorder quantity and lead time. Low-stock is a query/recommendation with evidence time and stock
cursor. It never automatically creates or approves a PurchaseOrder.

### Lots, expiry and returns

- P0 records received time and receipt source.
- Lot, supplier lot, produced batch and expiry are P1 unless operator/regulatory input requires P0.
- Restaurant traceability is receipt/preparation-to-movement linkage, not pharmaceutical pedigree.
- Supplier returns reference accepted receipt/cost evidence and post outbound compensation.
- A customer refund/order reversal affects inventory only through an authoritative disposition
  decision; returned prepared food is not silently restocked.
- Unused transfer return is a linked reverse transfer, not unrelated manual movements.

### Audit, idempotency and concurrency

Every command carries tenant, organization, Location, warehouse where applicable, authenticated
actor, operation identity, idempotency key, correlation/time, reason/reference and source/reversal
relationships. Material and cost evidence is append-only after posting.

- Optimistic versioning: item configuration, recipes, supplier offerings, draft POs and policies.
- Pessimistic locking: warehouse-item position during negative-policy checks and ledger post;
  receipt acceptance, count posting, transfer dispatch/receipt, batch completion and reversal.
- Lock multiple positions in deterministic `(tenant, location, warehouse, item, lot)` order.
- Duplicate command with same fingerprint returns the original result; same key/different
  fingerprint conflicts.
- Posted-operation reversal is at most once and must balance the original base quantity/cost scope.

### Security ownership

All domain rows retain tenant and Organization scope. Warehouse belongs to exactly one authorized
Location. Cross-Location commands require grants to every participating Location; cross-tenant and
cross-Organization relationships are rejected at database and service boundaries. Authorization
precedes existence disclosure.

Target permissions replace the broad operational use of `inventory.manage` incrementally:

| Permission | Authority |
|---|---|
| `inventory.stock.read` | Items and quantities, without costs |
| `inventory.cost.read` | Unit costs, valuation and margin inputs |
| `inventory.item.manage` | Item/UOM/replenishment configuration |
| `inventory.recipe.manage` | Recipe versions |
| `inventory.movement.manage` | Exceptional manual movement/reversal |
| `inventory.receipt.manage` | Draft/accept receipt |
| `inventory.purchase.manage` / `.approve` | PO authoring / approval |
| `inventory.waste.manage` / `.approve` | Loss recording / threshold approval |
| `inventory.count.manage` / `.approve` | Count execution / approval and post |
| `inventory.transfer.manage` / `.approve` | Transfer execution / approval |

Existing `inventory.read` and `inventory.manage` remain compatibility/admin permissions during
migration. Cost visibility is never implied by ordinary stock access.

### API and service boundaries

Existing item, recipe, stock, movement, cost and order-consumption APIs remain. New boundaries use
command services for mutation and projection services for reads.

Commands:

- Configure warehouse, negative policy, item conversion and standard-cost revision.
- Create/update/submit/approve/close/cancel PurchaseOrder.
- Draft/accept/cancel/reverse GoodsReceipt; create SupplierReturn.
- Publish a recipe version; start/complete/reverse PreparationBatch.
- Record/approve/reverse InventoryLoss.
- Open/count/submit/approve/post/cancel PhysicalCount.
- Draft/approve/dispatch/receive/close/reverse InventoryTransfer.
- Configure replenishment policy.

Queries:

- Item/catalog/supplier/offering and active recipe projections.
- On-hand by Location/warehouse/item/lot and ledger history.
- Open purchasing/receiving exceptions.
- Current and as-of standard cost/valuation.
- Count progress and exceptions.
- Theoretical consumption, reconciled actual consumption, waste and variance.
- Low-stock/replenishment and purchase-price trends.

## Operator experience and intelligence outputs

### Staff Web responsibility

| Workflow | Priority | Functional responsibility |
|---|---|---|
| Inventory overview/current stock | P0 | Location/warehouse filter, stock state, negative warnings, freshness cursor |
| Inventory item/UOM | P0 | Maintain item, base/purchase/count units and conversions with version conflicts |
| Recipe | P0 | Review/publish effective recipe versions and coverage gaps |
| Direct receiving | P0 | Select supplier/item/UOM, enter accepted/rejected quantity/cost, confirm once |
| Waste | P0 | Record typed loss, reason and approval state |
| Physical count | P0 | Open, count, submit, approve and post without hidden adjustment |
| Variance | P0 | Show theoretical, count-reconciled actual, recorded waste and residual separately |
| Cost/margin | P0 restricted | Standard cost, recipe cost and theoretical margin only to authorized roles |
| Low stock | P1 | Human replenishment recommendations |
| Purchase order | P1 | Draft/review/approve/receive/close |
| Preparation batch/yield | P1 | Record practical batch inputs/output/loss for selected processes |
| Lot/expiry | P1 | Receive/consume/count by lot where enabled |
| Transfer | P2 | Dispatch/receive and exception handling |

No visual design is specified. Every UI success state must be backed by the authoritative command
result; warnings and concurrency conflicts remain visible.

### Intelligence outputs

| Output | Priority | Authority |
|---|---|---|
| Stock on hand | P0 | Ledger sum as-of cursor |
| Theoretical consumption | P0 | Accepted-order recipe snapshots |
| Reconciled actual consumption | P0 | Closed physical-count periods |
| Variance quantity/value/percent | P0 | Versioned reconciliation formula and count boundaries |
| Waste by category/cost | P0 | Approved loss operations |
| Recipe/product theoretical cost | P0 | Effective recipe and standard-cost revisions |
| Gross-margin inputs | P0 restricted | Accepted commercial amount and historical theoretical cost |
| Purchase-price trend | P1 | Accepted receipt-line costs |
| Inventory valuation | P0 live STANDARD; P1 snapshots | Ledger plus effective cost authority |
| Low-stock/replenishment | P1 | On-hand and ReplenishmentPolicy |
| Yield/preparation variance | P1 | PreparationBatch actual versus recipe expectation |
| FIFO/lot exposure | P2 | Lot/layer ledger |

## D5 — Carnitas Muñoz pilot boundary

This is the default smallest useful inventory pilot. Conditional promotion requires actual operator
evidence, not inference from the restaurant name.

| Capability | Priority | Decision |
|---|---|---|
| Existing items/stock ledger/theoretical consumption | P0 — REQUIRED BEFORE PILOT | Preserve and certify |
| Inventory item classification | P2 — POST-PILOT | Roles are derived; taxonomy is not required for authority |
| One default warehouse | P0 — REQUIRED BEFORE PILOT | Required compatibility scope with minimal operator burden |
| Multiple warehouses/bins | P1 — DESIRABLE DURING PILOT | Promote only if real storage areas need separate stock |
| UOM conversions | P0 — REQUIRED BEFORE PILOT | Item-specific purchase/count conversions plus existing metric units |
| Suppliers | P0 — REQUIRED BEFORE PILOT | Minimum identity for trustworthy direct receipts |
| Full purchasing/approval | P1 — DESIRABLE DURING PILOT | Direct receipt is sufficient P0 |
| Receiving | P0 — REQUIRED BEFORE PILOT | Stock enters only on accepted receipt/opening/count/other explicit authority |
| Purchase-cost history | P0 — REQUIRED BEFORE PILOT | Freeze actual receipt evidence; preserve standard cost |
| Recipe versioning/effectivity | P0 — REQUIRED BEFORE PILOT | Sales evidence must resolve an immutable recipe |
| Prepared components and yield | P1 — DESIRABLE DURING PILOT | Promote to P0 only if on-site transformation must be measured |
| Actual consumption | P0 — REQUIRED BEFORE PILOT | Count-to-count reconciliation; no gram-by-gram entry |
| Dedicated waste | P0 — REQUIRED BEFORE PILOT | Typed, costed, reversible loss evidence |
| Physical counts | P0 — REQUIRED BEFORE PILOT | Required to anchor real stock and actual usage |
| Theoretical/actual variance | P0 — REQUIRED BEFORE PILOT | Core useful Restaurant Intelligence output |
| Standard-cost valuation | P0 — REQUIRED BEFORE PILOT | Live, by currency, negative stock explicit |
| Weighted-average/snapshot valuation | P1 — DESIRABLE DURING PILOT | Requires certified receipts |
| FIFO | P2 — POST-PILOT | No current justification |
| Transfers | P2 — POST-PILOT | Not needed with one Location/default warehouse |
| Reorder/par | P1 — DESIRABLE DURING PILOT | Recommendation only |
| Lot/expiry | P1 — DESIRABLE DURING PILOT | Promote to P0 if operator/regulatory evidence requires it |
| Return to supplier | P1 — DESIRABLE DURING PILOT | Manual correction is not final long-term authority |
| Negative-stock policy | P0 — REQUIRED BEFORE PILOT | Explicit WARN; never silently change legacy ALLOW |
| Staff Web P0 workflows | P0 — REQUIRED BEFORE PILOT | Overview, item/UOM, recipe, receipt, waste, count, variance, restricted cost |

### Pilot dataset impact

Collect only these real facts after the target contracts exist.

P0:

- Default warehouse: code, name, active status.
- Each inventory item: location, code, name, base UOM, active status.
- Each non-base operational unit: unit code/name, exact conversion to base, intended use
  (purchase/count/recipe), effective date.
- Negative-stock policy confirmation: WARN recommendation or explicit alternative.
- Suppliers used for P0 receipts: code, name, active status, Location availability.
- Supplier offering when used: item, supplier SKU optional, purchase UOM/conversion.
- Opening stock: warehouse, item, observed quantity/UOM, observation time, actor/reference.
- Standard cost: item, base-unit cost, currency, effective time, source/reason.
- Direct receipt: supplier, warehouse, received time, item, accepted/rejected quantity/UOM,
  unit cost/currency, source reference.
- Each direct-sale recipe: product, Location, effective time, tracking mode, output/batch basis,
  component item, quantity/UOM, status.
- Waste: item, warehouse, category, quantity/UOM, reason, time.
- Physical count: warehouse, counted items, quantity/UOM, counted time and responsible actors.

P1 only when activated:

- Multiple warehouses: code/name/default/status and real stock allocation.
- Purchase orders: supplier, destination, lines/UOM/quantity/cost/currency, expected delivery.
- Prepared process: output item, expected input/output/yield, batch basis, actual batch inputs,
  output and classified loss.
- Replenishment: minimum/maximum/par/reorder quantity and lead time per item+warehouse.
- Lots: internal/supplier lot, receipt/production date, expiry date and required enforcement.

Do not collect employee passwords, payment data, invented conversions, guessed yields, fabricated
opening balances, or assumed expiry dates.

## D6 — Compatibility and conceptual migration strategy

1. Add Warehouse and one deterministic default Warehouse per inventory-enabled Location. Existing
   state remains ALLOW during migration.
2. Add nullable warehouse references and new evidence columns. Backfill every existing movement and
   item/definition association to its Location default Warehouse; validate pre/post sums before
   making required references non-null for new writes.
3. Introduce stable recipe-version rows. For every existing definition create version equal to its
   current version number, attach existing components without changing their IDs, and mark it
   current/effective. Do not fabricate prior versions.
4. Retain existing `InventoryItem.standard_unit_cost` as compatibility projection. Seed one cost
   revision from the current value with provenance `LEGACY_STANDARD_COST`; do not rewrite historical
   consumption snapshots.
5. Preserve all existing movement IDs, quantities, signs, timestamps, actor/reference,
   idempotency fingerprints, reversals and consumption relationships.
6. Existing OPENING_BALANCE/MANUAL/ADJUSTMENT/REVERSAL/CONSUMPTION meanings remain valid. New
   semantic operations add source-operation identity; legacy rows remain explicitly LEGACY.
7. Keep current API representations while services dual-read/additively project new fields. Switch
   command paths to new authorities only after equivalence tests pass; remove no old contract in
   WS-34 implementation slices.
8. Existing RestaurantOrderConsumption and frozen cost/recipe evidence remain untouched.
9. No destructive backfill of warehouse allocation is allowed when a Location already needs more
   than one real warehouse; operator-approved allocation or default legacy warehouse is required.
10. Each migration must be retry-safe on MySQL 8.4 and MariaDB, with upgrade/downgrade/re-upgrade,
    seeded-permission, FK-scope, and data-preservation certification.

## D7 — Implementation workstream plan

| Slice | Objective | Dependencies | Models/contracts and migration | Required tests | Acceptance gate | Pilot dependency |
|---|---|---|---|---|---|---|
| 1. Warehouse ledger compatibility | Add default Warehouse, movement warehouse scope, lock projection and explicit negative policy without changing balances | Current foundation | Extend InventoryItem/StockMovement; Warehouse, Position, policy; additive/backfill migration | Scope isolation, sum equivalence, ALLOW compatibility, WARN evidence, BLOCK races, reversal | Existing IDs/history preserved and stock identical; new posts warehouse-scoped | P0 |
| 2. Operational UOM and cost evidence | Add item conversions and append-only standard-cost revisions | Slice 1 | ItemUomConversion, InventoryCostRevision; movement evidence fields | Exact conversion/rounding, version snapshots, base-UOM immutability, currency mismatch, cost as-of | Every quantity/cost is reproducible without float | P0 |
| 3. Immutable recipe versions | Preserve recipe APIs while publishing immutable effective versions | Slice 2 | Extend definition/components; add version header and current pointer | Migration of existing definitions, optimistic publish, effectivity overlap, combo choices, missing coverage | Accepted order resolves exactly one frozen recipe version | P0 |
| 4. Supplier and direct receiving | Create supplier/offerings and receipt acceptance as stock authority | Slices 1–2 | Supplier, availability/offering, GoodsReceipt/Line; receipt movement source | Receipt once, partial/rejected quantities, direct policy, cost snapshot, duplicate concurrency, reversal, isolation | ACCEPTED receipt posts exact stock/cost once; draft/PO never does | P0 |
| 5. Dedicated loss | Replace new free-text waste practice with typed reversible loss operations | Slices 1–2 | InventoryLoss and approval policy; linked WASTE movement | Category/UOM/cost, threshold approval, once/reversal, inactive item/warehouse, permission | Approved loss is traceable and counted exactly once | P0 |
| 6. Physical count and reconciliation | Anchor actual stock and theoretical/actual variance | Slices 1–3, 5 | PhysicalCount/Line, Reconciliation; count adjustment source | No-freeze cursor correctness, posting once, concurrent later movements, approvals, formulas, no double-count waste | Posted count preserves later movements; closed reconciliation is reproducible | P0 |
| 7. P0 Staff Web and intelligence projections | Make certified P0 operations usable without direct API/DB work | Slices 1–6 | No new authority; command/query clients and permission split | Role/location/cost visibility, workflow conflicts, warning/error recovery, end-to-end pilot journey | Operator can receive, waste, count and explain variance through Staff Web | P0 |
| 8. Purchase-order operations | Add intent/approval/partial-receipt lifecycle without changing receipt authority | Slice 4 | PurchaseOrder/Line and receipt links | State machine, amendments, approvals, partial/over receipt, cancellation/close, cost privacy | PO and stock never conflate; receipt remains sole inbound authority | P1 |
| 9. Prepared components and yield | Add transformation recipe/batch with actual input/output/loss | Slices 2–3, 5 | PreparationRecipe versions, Batch/Input/Output | Yield math, atomic completion, cost allocation, cancellation/reversal, double-post prevention | Batch material/cost balance is reproducible | P1 conditional |
| 10. Replenishment, lots and valuation snapshots | Add human low-stock policy, optional perishable traceability and period valuation | Slices 4, 6; Slice 9 for produced lots | ReplenishmentPolicy, InventoryLot, valuation snapshot | As-of correctness, expiry/lot isolation, purchase trend, no auto-PO, negative/currency states | Outputs are evidence-backed and policy-bounded | P1 |
| 11. Atomic transfers and advanced costing | Multiwarehouse/location transfer; evaluate weighted average, then FIFO only if justified | Slices 1, 4, 10 | Transfer aggregate/lines; optional cost layers | Lock ordering, atomic out/in, partial receive, rejection/return, races, cost conservation | One transfer identity balances both sides; selected cost method reproducible | P2 |

Each slice is independently deployable only after its migration and focused API/domain tests pass.
Do not combine P1/P2 breadth into a P0 prompt.

## Test and certification strategy

MySQL 8.4 is the primary pilot certification target. Current MariaDB portability tests remain a
release gate. Each slice requires unit tests for pure UOM/formula/state logic, integration tests for
database invariants and API authorization, and concurrency tests against a real database.

Mandatory cross-slice certification:

- Cross-tenant, cross-Organization, cross-Location and cross-warehouse FK/service rejection.
- Authorization-before-disclosure and independent cost visibility.
- Idempotent replay versus same-key/different-payload conflict.
- Deterministic lock ordering and concurrent negative-policy enforcement.
- Ledger sum, position rebuild and migration balance equivalence.
- Receipt acceptance exactly once; draft/PO/rejected quantity never changes stock.
- Transfer source/destination atomicity and cost conservation.
- Count posting exactly once with movements after the captured cursor preserved.
- At-most-one reversal and exact compensating quantity/cost evidence.
- Recipe version/effectivity correctness and accepted-order frozen evidence.
- Decimal precision, item/global conversion compatibility and rounding residual.
- Historical standard/receipt/batch/consumption/waste cost reproducibility.
- ALLOW/WARN/BLOCK behavior, including sale consumption under BLOCK.
- Variance equations with waste, receipts, adjustments and preparation inputs counted once.
- Upgrade, downgrade and re-upgrade from existing 0035/0036 data without ID/history loss.

## Architectural decision register

| Risk area | Status | Decision / required input |
|---|---|---|
| Inventory identity | DECIDED | Preserve Location InventoryItem; optional Organization catalog identity; ingredient/purchased/prepared are relational roles |
| Explicit item taxonomy | DEFERRED | Add only behavior-driving reporting/traceability categories |
| Warehouse authority | DECIDED | One default P0 Warehouse per Location; every new movement warehouse-scoped; bins deferred |
| Multiple real storage areas | NEEDS OPERATOR DOMAIN INPUT | Determines whether multiple warehouses move from P1 to P0 |
| UOM model | DECIDED | Existing metric globals plus immutable item-specific conversions and frozen evidence |
| Stock ledger authority | DECIDED | Immutable StockMovement remains sole material authority; Position is a lock/projection |
| Reservations/available stock | DEFERRED | No P0 requirement; expose ON_HAND only |
| Purchase/receipt separation | DECIDED | PO is intent; only ACCEPTED receipt creates stock |
| Direct receipts | DECIDED | Allowed P0 under Location policy with supplier/source evidence |
| Pilot costing | DECIDED | STANDARD with append-only revisions; actual receipt costs frozen separately |
| Weighted average/FIFO | DEFERRED | Weighted average P1 evaluation; FIFO P2 only with demonstrated need |
| Valuation | DECIDED | Live as-of STANDARD P0; period snapshots P1; currency/negative states explicit |
| Recipe versioning | DECIDED | Stable existing header plus immutable effective versions/components |
| Prepared recipes/batches | DEFERRED | P1 by default |
| On-site transformation/yield | NEEDS OPERATOR DOMAIN INPUT | Promote batch/yield to P0 only if actual restaurant process requires it |
| Actual consumption authority | DECIDED | P0 count-to-count reconciliation; P1 batch inputs for selected processes |
| Waste taxonomy | DECIDED | Dedicated typed, costed, approved, reversible loss authority |
| Physical-count behavior | DECIDED | No global freeze; line ledger cursor and delta posting preserve later movements |
| Variance calculation | DECIDED | Closed count-bounded reconciliation with versioned formula and exclusive categories |
| Transfer atomicity | DECIDED | One aggregate creates linked out/in; no unrelated manual pair |
| Pilot transfer need | DEFERRED | P2 with one default warehouse |
| Negative stock | DECIDED | Migration preserves ALLOW; pilot explicitly activates WARN; BLOCK is concurrency-safe and excludes loss of sale evidence |
| Lot/expiry | NEEDS OPERATOR DOMAIN INPUT | P1 default; regulatory/perishable process may promote it |
| Supplier commercial terms | DEFERRED | Only identity, availability, offering/UOM/lead-time needed initially |
| Automatic purchase creation | DEFERRED | Replenishment recommends only |
| Pilot minimum | DECIDED | Warehouse/UOM/supplier/receipt/cost/recipe/waste/count/variance/policy/UI P0; broader roadmap staged |

## Acceptance gates and deliverables

| Gate | Result | Evidence |
|---|---|---|
| G1 Current foundation | PASS | Existing five authorities, APIs, migrations, tests and gaps verified |
| G2 Target domain | PASS | Entities, ownership, identity, lifecycle, relationships and invariants explicit |
| G3 Operational authority | PASS | Stock, purchasing, receiving, counts, waste, consumption, variance and transfers defined |
| G4 Cost/recipe authority | PASS | UOM, STANDARD P0 cost/valuation, recipe versioning, prepared yield boundary explicit |
| G5 Pilot boundary | PASS | Major capabilities classified P0/P1/P2 with conditional operator inputs visible |
| G6 Compatibility/implementation | PASS | Non-destructive migration and independently certifiable slices defined |
| G7 Governance | PASS | Security, audit, concurrency, idempotency, testing and decision register explicit |

- D1 Current foundation map: PASS
- D2 Gap matrix: PASS
- D3 Target inventory domain model: PASS
- D4 Authority/state/invariant specification: PASS
- D5 Carnitas Muñoz P0/P1/P2 matrix: PASS
- D6 Compatibility/migration strategy: PASS
- D7 Implementation workstream plan: PASS
