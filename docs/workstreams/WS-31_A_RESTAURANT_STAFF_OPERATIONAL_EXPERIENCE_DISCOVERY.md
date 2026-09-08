# WS-31-A — Restaurant Staff Operational Experience Discovery

## 1. Document status

**Workstream:** WS-31-A — Restaurant Staff Operational Experience Discovery
**Status:** COMPLETE — DISCOVERY ONLY
**Discovery decision:** PROCEED WITH REQUIRED BACKEND ENABLEMENT
**Certified baseline:** WS-30, commit `347df6d`
**Branch inspected:** `feat/ws-00-01-runtime-reuse-baseline`
**Inspection date:** 2026-09-07

This document records repository evidence and the minimum implementation sequence for the
first staff-facing pilot. It does not authorize a frontend implementation by itself and it
does not change restaurant-domain authority.

## 2. Executive decision

The recommended topology is one new `apps/staff-web` React application with a shared staff
shell and capability-aware workspaces for Host, Waiter, Kitchen, Cashier and Manager.
Separate applications per role are not justified by current backend contracts.

The backend already has substantial command authority for service sessions, preparation,
Checks, Payments, cash, billing, fiscal issuance and paid-check printing. It is not yet
sufficient for an end-to-end staff pilot because several domains expose commands or
identifier-based reads without the location-scoped discovery surfaces required by a real
operator.

The decisive gaps are:

1. `DinerOperationalRequest` has the correct types and lifecycle in persistence, but has no
   staff list, detail or status-transition API.
2. Cashier and Manager cannot reliably discover current cash sessions, Checks, Payments,
   billing work or paid-print dispatches after navigation/reload.
3. Fiscal profiles required to create a billing document have no API for staff capture,
   verification or selection.
4. Accepted orders are not automatically routed to preparation. The routing and execution
   APIs exist; automatic Order-to-Preparation wiring remains WS-32 scope.
5. Authentication and permission enforcement exist, but production staff provisioning,
   standard role grants and location-specific membership scope do not.

Therefore WS-31 must not be treated as frontend-only. The smallest backend enablement slices
must precede the dependent staff screens. No new business engine is required.

## 3. Evidence and inspection boundary

The discovery inspected only the relevant routes, dependencies, models, services, tests,
bootstrap, diner frontend and authoritative frontend rules:

- `apps/api/app/api/deps.py`
- `apps/api/app/api/routes/auth.py`
- `apps/api/app/bootstrap_admin.py`
- organization, location, resource and restaurant-service routes/models/services
- diner operational-request route/model/service
- order, preparation and preparation-delivery routes/models/services
- Check, Payment, cash, billing, fiscal-issuance and paid-print routes/models/services
- focused backend tests for those domains
- `apps/diner-web`
- `docs/frontend/FRONTEND_DESIGN_SYSTEM_AND_UX_RULES.md`

No production code, frontend file or migration was created or modified during discovery.

## 4. Authentication, authorization and location

### Current login

Staff can log in through `POST /auth/login` with email, password and optional `tenant_id`.
If the user has exactly one active tenant membership, the tenant is inferred. Multiple
active memberships require an explicit tenant selection. The response is a bearer JWT with
user, tenant and membership evidence. `GET /auth/me` revalidates active user, membership and
tenant state on every authenticated request and returns current roles and permissions.

There is no server logout or refresh endpoint. For the pilot, logout is removal of the local
token and query cache; expiration returns the user to login. Staff authentication must not
reuse diner join/access-code semantics.

### Permission enforcement

Backend routes enforce permission codes through `require_permission(...)`. Roles are
tenant-owned, many-to-many collections of permissions, and a membership may have multiple
roles. The frontend should therefore drive navigation and actions from permissions returned
by `/auth/me`, using role names only as labels. Hidden controls are not authorization.

The model can represent `HOST`, `WAITER`, `KITCHEN`, `CASHIER` and `MANAGER`, but the only
role created by `bootstrap_admin.py` is `TENANT_ADMIN`. There are no user, membership, role
or grant management routes. Pilot staff identities and grants currently require controlled
out-of-band provisioning.

Kitchen uses the same staff JWT and permission mechanism as other staff. Its relevant
permissions are `preparation.read`, `preparation.execute` and, where appropriate,
`preparation.dispatch`. Connector machines use a separate connector credential boundary and
must not be treated as kitchen users.

Recommended navigation gates follow capabilities, not hard-coded role names:

| Workspace | Minimum capability gates |
|---|---|
| Host | `location.read`, `resource.read`, `restaurant_service.read`; actions require `restaurant_service.manage`. |
| Waiter | `restaurant_service.read`, `restaurant_order.read`, `restaurant_check.read`, plus new operational-request read/manage permissions. |
| Kitchen | `preparation.read`; actions require `preparation.execute`; reprint requires `preparation.dispatch`. |
| Cashier | `cash_management.read`, `restaurant_check.read`, `restaurant_payment.read`, plus new operational-request read; each action uses its existing manage/recover permission. |
| Manager | The union of granted read capabilities; mutations appear only for the specific existing manage/recover permission. |

A person may legitimately see multiple workspaces when their permission union allows it.

### Location resolution

The JWT establishes tenant scope, not organization or location scope. A staff client with
`location.read` can call `GET /locations`, optionally filtered by organization, and select a
location as UI context. Operational APIs then take a location directly or derive it from an
authoritative resource/entity.

There is no membership-to-location grant and no server-side “current location”. Consequently:

- a one-location pilot can select the sole active location after login;
- a multi-location tenant can expose all tenant locations to any membership with the broad
  permission;
- switching location can be a client context change, but it is not a security boundary.

This is acceptable only for a deliberately single-location pilot. Location-specific access
is a real pre-rollout gap, not a reason to invent a cross-location dashboard in WS-31.

## 5. Recommended staff shell and frontend reuse

Create one staff application, conceptually:

```text
apps/staff-web
  shared authenticated shell
    organization/location context
    capability-aware navigation
    session/logout
    global network/auth/conflict handling
  workspaces
    host
    waiter
    kitchen
    cashier
    manager
```

Reuse the existing stack unless a later implementation proves a blocker: React 19,
TypeScript, Vite, React Router, TanStack Query, Vitest and React Testing Library.

Reuse from `apps/diner-web` at the design and engineering-pattern level:

- semantic token names and the warm product identity;
- light/dark/system theme behavior;
- QueryClient and server-state ownership conventions;
- centralized typed HTTP/error handling;
- accessible state, loading, focus and responsive patterns;
- exact money/date formatting approaches.

Do not import or copy diner session storage, diner auth context, diner route guards, diner API
contracts or consumer page semantics. Current reusable code is located inside the diner app,
not a shared package. Start the staff app with the minimum local primitives; extract a shared
package only after repeated source-level reuse is proven.

The staff visual mode should preserve the same brand while favoring denser lists, persistent
context, keyboard efficiency on desktop and approximately 44px touch targets on handheld
screens. “WOW” means rapid recognition, safe action and excellent exception handling.

## 6. Authoritative capability inventory

### Host and service

Existing staff contracts:

| Capability | Contract | Finding |
|---|---|---|
| Select location | `GET /locations` | Tenant-scoped list; client selects context. |
| List tables | `GET /resources?location_id=...&resource_type=TABLE&status=ACTIVE` | Resource lifecycle only; occupancy is not a Resource status. |
| Determine occupancy | `GET /resources/{id}/service-sessions/current` | `200` returns OPEN session and active diner count; `404` means no current session. |
| Open table | `POST /resources/{id}/service-sessions` | Accepts party size; returns join key and plaintext access code once. |
| Change party size | `PUT /restaurant-service-sessions/{id}/party-size` | Cannot reduce below active diner count. |
| Recover access | `POST .../access-code/regenerate` | Generates a new code; current-session read intentionally does not expose plaintext. |
| Close/release | `POST /restaurant-service-sessions/{id}/close` | Enforces financial/continuation closure eligibility, ends active diners and conversations, and releases the table. |

The model guarantees only one open service session per resource. Opening and closing lock the
relevant records and return controlled conflicts. Table reuse is supported after successful
closure.

Minimum Host workspace:

- location and active-table list;
- derived “available / in service” presentation from current session existence;
- party size, elapsed time and active diner count;
- open-table action with prominent access-code handoff;
- explicit regenerate-code action when the code was lost;
- close action with a clear warning that active diner sessions end;
- authoritative closure-conflict details and refetch.

The current APIs do not list diner identities for staff and require one current-session call
per table. Identity detail is not required for the stated Host critical journey. A
location-scoped table/service-session projection is P1 for operational scale, not a P0 pilot
blocker.

### Waiter and operational requests

`DinerOperationalRequest` already persists:

- types `HUMAN_ASSISTANCE`, `CASH_PAYMENT_ASSISTANCE`, `INVOICE_ASSISTANCE` and
  `PAID_CHECK_PRINT`;
- statuses `PENDING`, `ACKNOWLEDGED`, `COMPLETED` and `CANCELLED`;
- tenant, organization, location, resource, service-session, diner-session and optional
  Check scope;
- creation time, update time and final resolver membership/time;
- an index explicitly shaped for a location/status staff queue.

Only diner endpoints exist: `POST /diner/operational-requests` and owner-scoped
`GET /diner/operational-requests/{id}`. No staff route can list, read, acknowledge, complete
or cancel a request. There is also no ownership/assignment field for the acknowledged state.

Minimum required backend gap:

- introduce dedicated read/manage permissions for operational requests;
- location-scoped list with status/type, stable ordering and bounded pagination;
- staff detail by id;
- idempotent, concurrency-safe transition from `PENDING` to `ACKNOWLEDGED`, then to
  `COMPLETED` or `CANCELLED`;
- retain actor membership and transition timestamps. If acknowledgement ownership is not
  persisted, present it as “acknowledged”, not “owned by waiter”.

Explicit waiter assignment/handoff remains deferred. The pilot inbox can be shared by all
authorized staff at a location.

Existing order read is `GET /restaurant-orders` and `GET /restaurant-orders/{id}`. The list
is unbounded, tenant-wide and its response omits location, resource, service-session and
diner context even though the model stores those fields. It is insufficient as an
operational active-table order feed. `GET /restaurant-service-sessions/{id}/outstanding-balance`
and Check-by-id are useful once context identifiers are known.

Minimum Waiter workspace after enablement:

- shared request inbox prioritized by age and type;
- table/service context and related Check link;
- acknowledge, complete and cancel only where the certified transition contract authorizes
  it; there is no invented escalation state;
- accepted-order context and table balance read-only drill-down;
- no waiter assignment, shift routing or workload balancing.

### Kitchen and preparation

Existing preparation authority is strong and directly usable:

- configuration and areas are location scoped;
- `GET /preparation-works` lists platform-owned work by location, area, derived execution
  state, order and cursor;
- default queue excludes completed work;
- work includes area, order time/channel, table resource and item details;
- item states are exactly `NEW`, `IN_PROGRESS`, `COMPLETED`;
- legal mutations are exactly `NEW -> IN_PROGRESS -> COMPLETED`;
- transitions require expected state, expected version and `Idempotency-Key`, lock the row
  and retain employee membership/correlation evidence;
- dispatches can be listed by location/state/destination/work/order;
- dispatch states are `PENDING`, `IN_PROGRESS`, `DESTINATION_SUBMISSION_ACCEPTED`,
  `RETRYABLE_FAILURE`, `UNCERTAIN`, `ACTION_REQUIRED`;
- human reprint creates a separate `REPRINT` dispatch and requires `preparation.dispatch`.

The minimum Kitchen workspace is a location/area queue, item detail, Start and Complete
actions, completed-history filter, delivery exception visibility and authorized reprint.
There is no additional kitchen state to invent.

Order confirmation currently materializes inventory consumption but does not call preparation
routing. `POST /restaurant-orders/{id}/preparation-routing` exists and is idempotent, but the
tests invoke it separately. Automatic accepted Order-to-Preparation routing remains WS-32
integration scope. A kitchen UI can be implemented against existing queue APIs, but an
end-to-end incoming queue is only complete after WS-32.

### Cashier, Check, Payment and cash

Existing authoritative commands include:

- create/read/mutate/freeze/cancel Check by identifier with expected version and idempotency;
- read table outstanding balance;
- initiate staff Payment, including cash with cash-session id, exact tender and authoritative
  change due;
- read settlement (including all Payments), retry definite `FAILED` Payment and recover
  `UNCERTAIN` Payment;
- list available electronic executors by organization/location/method/currency;
- open a cash session on a `CASH_REGISTER`, record opening float/manual movements, count,
  close with selected count and variance reason, and read a session by id.

Financial authority is correctly separated: diner creates `CASH_PAYMENT_ASSISTANCE`; an
authorized employee initiates the cash Payment; the Payment service records tender/change
movements in the open CashSession and applies canonical settlement. The UI must never compute
authoritative change, balance, settlement or variance.

The current operational-read gaps are substantial:

- no location/status list or “current for register/cashier” CashSession endpoint;
- no CashSession movement/count history endpoint;
- no Check list by location/service-session/status;
- no staff Payment get/list by location/state; staff can only discover Payments through a
  known Check settlement;
- no staff operational-request inbox to receive cash assistance.

Without stable identifiers retained in the current page, a cashier cannot resume an open cash
session after reload, discover the next Check, or find uncertain Payments. Minimum enablement
must add location-scoped query APIs over existing truth; it must not create another payment or
cash engine.

Cashier electronic-payment presentation must distinguish:

- `IN_PROGRESS`: active processing, bounded polling, no duplicate initiation;
- `SUCCEEDED`: confirmed and reflected by settlement;
- `REJECTED`: definite provider rejection and safe corrective path;
- `FAILED`: definite failure, explicit retry only where backend permits;
- `UNCERTAIN`: unknown money outcome, prominent exposure and recovery action only;
- `RESERVED` and `CANCELLED`: retain their canonical meaning where returned.

### Billing / CFDI

Existing staff authority supports:

- create a billing document from a settled Check and active issuer/recipient fiscal-profile
  identifiers;
- read a known billing document and frozen fiscal evidence;
- initiate fiscal issuance through the provider boundary;
- read a known issuance;
- recover uncertain issuance and retry only when service invariants permit it.

Billing document status is currently `DRAFT`. Fiscal issuance states are `PENDING`,
`IN_PROGRESS`, `SUCCEEDED`, `FAILED`, `REJECTED`, `UNCERTAIN`.

The staff workflow is incomplete because there is no route to create, update, verify, list or
select `IssuerFiscalProfile` or `CustomerFiscalProfile`; tests seed these directly. There is
also no location/status list for billing documents or issuances, and invoice assistance cannot
be consumed by staff because of the operational-request gap.

Minimum backend enablement:

- expose scoped fiscal-profile read/write contracts sufficient to capture and validate the
  existing canonical fields; do not redesign CFDI;
- allow an invoice-assistance handler to locate the customer/check and active profiles;
- add location/status list/read linkage for billing documents and issuances;
- preserve FINKOK/PAC credential resolution and issuance/recovery as backend-only authority.

### Paid-check printing

Existing staff APIs can explicitly request paid printing for a settled Check and read a known
dispatch. The request binds cashier resource, connector and local target; connector delivery
claims/results remain machine-authorized. Dispatch states are `PENDING`, `IN_PROGRESS`,
`DESTINATION_SUBMISSION_ACCEPTED`, `RETRYABLE_FAILURE`, `UNCERTAIN`, `ACTION_REQUIRED`.

The financial state is independent of printer failure and no automatic print occurs. The
staff UI must preserve both rules.

The remaining gaps are the shared operational-request inbox and a location/status list for
paid-print dispatches. After those exist, Cashier can verify settlement, explicitly request
print and monitor delivery/recovery states. Printer failure must never reopen or alter a
settled Check.

### Manager and inventory

Manager can compose an overview from authoritative read APIs only after the missing discovery
queries exist. Today, resources and preparation work/dispatches have useful location lists;
orders are tenant-wide and context-poor; service sessions require per-resource lookup; Checks,
Payments, cash, billing, paid print and operational requests lack adequate lists.

Inventory already exposes location-scoped item, stock and movement reads under
`inventory.read`. It may be a drill-down after core operational control, but inventory editing,
advanced BI, forecasting and owner advice are not required for this pilot.

Minimum Manager workspace:

- count/list active tables and diners;
- recent accepted orders and preparation backlog/exceptions;
- open/frozen Checks and outstanding/uncertain exposure;
- Payment exceptions, especially `UNCERTAIN`;
- open cash sessions and variance/closure exceptions;
- pending operational requests;
- billing/issuance and paid-print exceptions.

Manager actions must use the same existing permissions and commands. There are no invented
override, forced settlement, lock bypass or forced cash-close actions.

## 7. Shared operational status language

Staff presentation must map, not replace, canonical states:

| Domain | Canonical backend states | Safe staff presentation rule |
|---|---|---|
| Resource/service | Resource `ACTIVE/INACTIVE`; session `OPEN/CLOSED` | “Available” may be derived only from active TABLE plus absence of current OPEN session; “In service” from OPEN. |
| Order | `ACCEPTED` only | Call it accepted, never queued/preparing until preparation evidence exists. |
| Preparation routing | `PENDING/ROUTED/EXTERNAL_POS_OWNED/ACTION_REQUIRED` | Separate routing/configuration problems from item execution. |
| Preparation item | `NEW/IN_PROGRESS/COMPLETED` | Incoming / Preparing / Completed labels may map one-to-one. |
| Check | `OPEN/FROZEN/SETTLED/CANCELLED` | Show continuation decision separately: `NONE/PENDING/YES/NO`. |
| Payment | `RESERVED/IN_PROGRESS/SUCCEEDED/FAILED/REJECTED/UNCERTAIN/CANCELLED` | Never collapse UNCERTAIN into failed or paid. |
| Cash | session `OPEN/CLOSED`; movements and counts are evidence | Show expected, counted and frozen variance separately. |
| Operational request | `PENDING/ACKNOWLEDGED/COMPLETED/CANCELLED` | Do not imply staff ownership without persisted evidence. |
| Billing | document `DRAFT`; issuance `PENDING/IN_PROGRESS/SUCCEEDED/FAILED/REJECTED/UNCERTAIN` | Separate document readiness from provider issuance. |
| Print dispatch | `PENDING/IN_PROGRESS/DESTINATION_SUBMISSION_ACCEPTED/RETRYABLE_FAILURE/UNCERTAIN/ACTION_REQUIRED` | “Submitted to destination” is not proof a human received paper. |

Controlled errors must retain domain meaning: Payment/fiscal/print uncertainty, printer
delivery failure, cash variance, stale versions and session-closure conflicts are distinct
operational states, not a generic error banner.

## 8. Audit, concurrency and frontend authority

Existing actor evidence is generally adequate:

- service opening/closing stores membership ids;
- preparation transitions store employee membership, sequence and correlation id;
- Check commands and versions retain actor evidence;
- Payment attempts and settlement retain actor evidence;
- cash sessions, movements and counts retain actor/authorizer evidence;
- billing/issuance retains actor scope and attempts;
- paid-print dispatch retains creator membership and delivery attempts.

Operational requests already have final resolver membership/time but need the missing staff
transition service. Party-size changes and access-code regeneration do not persist a dedicated
actor history; this is not a pilot blocker and does not justify an audit subsystem.

Concurrency protections to surface through the UI:

- table/session: row locks plus unique open resource slot;
- preparation: expected state/version, row lock and idempotency key;
- Check/continuation: expected version/fingerprint, table locks and idempotent commands;
- Payment: Check evidence, idempotency, fenced claims and explicit retry/recovery rules;
- cash: unique open register session, row locks, movement versions and idempotency;
- print/fiscal: claim fencing and explicit recovery semantics.

On a controlled `409`, the frontend should retain safe user input where appropriate, refetch
authoritative server state and explain the conflict. It must not invent optimistic ownership
or keep authoritative local copies of any operational/financial state.

## 9. Refresh strategy

No existing WebSocket, SSE or generic event platform is required. Bounded polling plus
mutation invalidation and explicit refresh is adequate for the first pilot:

| View | Initial strategy |
|---|---|
| Host table state | 10–15 seconds; immediate refetch after open/close/party/code actions. |
| Waiter request inbox | About 5 seconds while visible; refetch after every transition. |
| Kitchen active queue | 3–5 seconds while visible; refetch after item transition. |
| Payment in progress | About 2 seconds for the known Payment/settlement; stop on terminal state; UNCERTAIN requires explicit recovery. |
| Fiscal/print active work | 3–5 seconds only for nonterminal known work. |
| Manager overview | 10–15 seconds with per-panel manual retry. |

Intervals are UX defaults, not domain rules. Polling must pause or back off when the view is
hidden/offline and must not replay mutations.

## 10. Device priorities

- **Host — tablet/desktop:** glanceable table grid/list, large open/close controls, access code
  readable at handoff distance.
- **Waiter — phone/tablet:** age/type prioritized inbox, one-hand acknowledgement and clear
  table identity.
- **Kitchen — tablet/display/desktop:** maximum queue legibility, large item targets, area
  filtering and minimal navigation.
- **Cashier — POS/desktop:** keyboard-efficient money entry, tabular numerals, explicit
  confirmation and persistent exception context.
- **Manager — desktop/tablet:** dense overview with drill-down, not a decorative dashboard.

No native mobile application is needed.

## 11. Critical-journey classification

### Host — COVERED

`/auth/login` -> `/locations` -> `/resources` -> per-table current session -> open service
session -> access code -> existing diner join is implementable now. The N+1 table lookup and
absence of diner identity list are P1 usability/scale issues, not blockers for the stated
journey.

### Waiter — BLOCKED

Login, active-table derivation, accepted-order reads and table balance exist. The critical
request step is impossible: staff cannot discover, acknowledge or complete a
`DinerOperationalRequest`. The current order list also lacks operational table/location
context.

### Kitchen — PARTIAL

The complete queue, item transition and reprint UI contract exists. Accepted orders do not
automatically invoke preparation routing, so incoming work is not guaranteed end-to-end.
That integration remains WS-32 scope.

### Cashier — BLOCKED

Cash, Check, Payment, settlement, fiscal issuance and paid-print commands exist. The cashier
cannot consume assistance requests, resume/discover current cash work, discover Checks or
Payment exceptions, or capture/select fiscal profiles through APIs.

### Manager — BLOCKED

Some source reads exist, especially resources and preparation. There is no coherent way to
discover the required location-scoped Check, Payment, cash, request, billing and print
exceptions. Advanced BI is not needed to resolve this; bounded operational queries are.

## 12. Prioritized gaps

### P0 — blocks a required real-world pilot operation

1. **Staff operational-request consumption:** add list/detail and concurrency-safe lifecycle
   mutations with permissions and actor evidence. This unblocks Waiter, cash assistance,
   invoice assistance and paid-print requests.
2. **Cashier resumable financial work:** add current/list CashSession plus location/service
   scoped Check and Payment discovery sufficient to receive cash safely and recover uncertain
   Payments after reload.
3. **Fiscal-data workflow API:** expose existing issuer/customer fiscal-profile capture/read
   and linkage so staff can create the billing document required before issuance.
4. **Order-to-Preparation invocation:** complete under WS-32 so accepted pilot orders appear in
   the kitchen queue without a manual technical routing call.

### P1 — required before pilot quality/certification, but not a new domain foundation

1. Location-scoped table/service-session projection to avoid per-table lookup and support a
   coherent Host/Manager surface.
2. Operational order list filters and projection containing location/resource/service/diner
   context plus bounded pagination.
3. Cash movement/count history and location/status exception reads.
4. Location/status list/linkage for billing documents, fiscal issuances and paid-print
   dispatches.
5. Controlled staff identity/role provisioning with pilot grants. Existing login/RBAC works,
   so this is not a new auth design.
6. Enforce or explicitly constrain location access before any multi-location pilot; the
   current permission scope is tenant-wide.

## 13. Smallest ordered implementation slices

Each item is one logical prompt; dependent frontend slices start only after their backend
contract is certified.

1. **WS-31-B0A — Staff Operational Request Consumption**
   Add permissions, location-scoped queue/detail and idempotent lifecycle transitions over the
   existing model. No waiter assignment.
2. **WS-31-B0B — Staff Operational Read Projections**
   Add the minimum bounded location-scoped table/session, order, Check, Payment and cash reads
   needed to discover and resume work. Reuse current services and invariants.
3. **WS-31-B0C — Staff Fiscal Profile and Billing Discovery**
   Expose existing fiscal-profile capture/read plus billing/issuance/paid-print lists. No CFDI
   or printer redesign.
4. **WS-31-B1 — Staff Frontend Foundation and Authentication**
   Create `apps/staff-web`, staff JWT login/restoration/logout, location context, capability
   navigation, theme/tokens, typed API client and controlled errors.
5. **WS-31-B2 — Host Table Operations**
   Implement the table/service-session workspace and access-code handoff against certified
   APIs.
6. **WS-31-B3 — Waiter Operational Inbox**
   Implement shared request handling with table/order/Check context; no assignment engine.
7. **WS-31-B4 — Kitchen Operations**
   Implement area queue, item execution, dispatch exceptions and authorized reprint. Certify
   its dependency on WS-32 automatic routing.
8. **WS-31-B5 — Cashier Check, Payment and Cash Operations**
   Implement register session, opening float/movements, Check settlement, cash tender/change,
   electronic status/recovery and count/close.
9. **WS-31-B6 — Billing and Paid-Print Operations**
   Implement fiscal-data review, billing/issuance/recovery, explicit paid print and dispatch
   status.
10. **WS-31-B7 — Manager Operational Overview**
    Compose existing certified reads into an exception-first location overview; no BI or
    override engine.
11. **WS-31-C — Focused Staff Journey Validation**
    Certify role/capability denial, responsive device priorities, refresh/reload recovery,
    concurrent conflicts and the five critical journeys.

Before B1, deployment must have a controlled way to provision the five pilot identities and
permission grants. This may be a bounded bootstrap/administrative slice; it must not be solved
with shared credentials or frontend role simulation.

## 14. Explicitly deferred

- explicit waiter assignment and handoff records;
- shift routing and automatic workload balancing;
- advanced floor-plan editor and reservations;
- workforce scheduling;
- native mobile applications;
- advanced BI, predictive analytics and owner advisor;
- ERP expansion;
- generic notification platform;
- WebSocket, SSE or event-platform redesign;
- privileged Manager overrides that bypass financial/session invariants.

## 15. Final acceptance boundary

The staff pilot is ready only when each role can complete its classified journey using
authenticated, permission-enforced and location-safe backend authority; reload and concurrent
actors reconcile to server truth; and uncertainty remains explicit.

The frontend may improve recognition, prioritization and speed. It may never become authority
for table occupancy, preparation truth, Check liability, Payment outcome, cash balance,
billing issuance or printer delivery.
