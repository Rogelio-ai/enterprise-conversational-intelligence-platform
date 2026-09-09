# WS-33-A — Production Readiness & Pilot Discovery

## Status and decision

**Discovery status:** COMPLETE  
**Pilot decision:** **NO-GO today.** The certified restaurant workflows are not yet wrapped in a production deployment, recovery, and operating boundary. A tightly controlled, cash-only, screen-based pilot can become the first GO target after the P0 gates in this document close. Electronic payments, real CFDI, and physical printing must remain disabled until their separate P1 capability gates pass.

This is a repository-evidence assessment as of 2026-09-09. It performs no deployment, provider provisioning, printer operation, production-code change, or migration.

Baseline evidence:

- Branch: `feat/ws-00-01-runtime-reuse-baseline`.
- Certified integration baseline present: `5baa352 feat(integration): complete restaurant end-to-end wiring`.
- The working tree was clean and `git diff --check` passed before discovery.
- Repository sources inspected include `compose.yaml`, both web applications, the API Dockerfile/settings/runtime, Alembic history through `0040_staff_location_authorization_scope`, bootstrap, payment and fiscal adapters, health/metrics/logging, and `connectors/restaurant_local_connector/`.

## Pilot Topology

The smallest production-like topology supported by the architecture is:

```text
Restaurant / diner browsers
          |
          | HTTPS 443, one public origin
          v
  DNS + TLS reverse proxy / static host             optional staged services
     |                     |                         +-----------------------+
     | /diner, /staff      | /api                    | Conekta JS tokenization|
     v                     v                         | browser -> provider    |
 Diner Web + Staff Web   ECIP API ------------------>| Conekta API (HTTPS)   |
                           |  \---------------------->| FINKOK SOAP (HTTPS)   |
                           |
                           | private DB network
                           v
                       MySQL 8.4 + encrypted backups
                           ^
                           |
Restaurant Connector host | outbound HTTPS 443 only
  Local Connector --------+
        |
        +-- LAN TCP/9100 -> ESC/POS printer(s), or
        +-- local USB device / CUPS queue -> printer(s)
```

Core cash-only operation requires the web clients, API, and MySQL. It does **not** require Redis, a cache, or object storage. Fiscal artifact storage becomes required only when CFDI is enabled. No inbound Internet access to the connector or printers is required. The repository does not currently contain the reverse proxy/static hosting, production Compose/orchestration, backup service, or observability backend shown as required boundaries.

Environment recommendation:

| Environment | Need | Minimum form |
| --- | --- | --- |
| Development | Existing | Current Compose and Vite development servers. |
| Pre-pilot validation | Required, may be short-lived | Production images/config/topology with synthetic data; provider demo/sandbox only; no live restaurant traffic. A separate permanent staging estate is unnecessary for one pilot. |
| Pilot/production | Required | Isolated pilot data, durable MySQL, HTTPS public origin, controlled secrets, backups, monitoring, and rollback path. |

## Readiness Summary

| Domain | Classification | Repository-grounded finding |
| --- | --- | --- |
| Restaurant application workflows | READY | WS-30/31/32 software baseline covers diner, staff, Order -> Preparation, Kitchen, cash, settlement, paid-check dispatch, and Manager. |
| Application deployment | BLOCKED | Compose is development-only; production web hosting, ingress/TLS, release procedure, and CI/CD are absent. |
| Runtime configuration and secrets | PARTIAL | Typed API settings and ignored `.env` files exist, but no production secret provider/injection/rotation mechanism or complete production template exists. |
| Database and storage | BLOCKED | MySQL 8.4, migrations, pooling, and readiness exist; TLS, controlled migration, backup/restore, and restore proof do not. |
| Bootstrap and master data | BLOCKED | Admin bootstrap and many CRUD APIs exist; staff identity/RBAC/location-grant provisioning and a complete repeatable pilot seed/import process do not. Real pilot inputs are missing. |
| Diner and staff clients | PARTIAL | Applications build and consume `/api`; no production images/static server, URLs, browser/device evidence, or deployed same-origin route exists. |
| Cash and settlement | PARTIAL | Software is ready; pilot cash register, activation, cash session, staff grants, opening/control process, and acceptance evidence remain. |
| Electronic payment | BLOCKED | Conekta execution/recovery software exists, but real secret resolution, merchant inputs, location configuration, and production evidence do not. Exclude initially. |
| Fiscal/FINKOK | BLOCKED | CFDI 4.0 mapping/stamping/recovery exists, but real credentials, artifact storage, issuer/provider setup, and production evidence do not. Exclude initially. |
| Local Print Connector software | READY | Polling, enrollment, scope binding, durable SQLite ledger, adapters, heartbeat, recovery, Docker, and Debian/systemd packaging exist. |
| Physical printing | BLOCKED | No printer inventory, host, mappings, LAN/USB evidence, or physical certification exists. Exclude initially. |
| Network/DNS/TLS | BLOCKED | Application supports HTTPS-oriented use, but no public hostnames, DNS/TLS ownership, ingress, firewall policy, or origin policy is provisioned. |
| Observability | PARTIAL | JSON logs, correlation IDs, health/readiness, Prometheus metrics, payment metrics, and connector heartbeat exist; collection, dashboards, alerts, retention, and ownership do not. |
| Backup/restore | BLOCKED | No database/config/artifact backup or restore procedure and no restore verification exist. |
| Security operations | PARTIAL | Argon2, signed scoped tokens, permission/location enforcement, secret redaction patterns, and connector credential rotation/revocation exist; production perimeter, secrets, identity lifecycle, and response procedures do not. |
| Operational runbooks | BLOCKED | Connector README is useful but the required platform and incident runbooks are absent. |
| Billing invoice printing | NOT REQUIRED FOR PILOT | No connector-authoritative invoice representation exists. Electronic CFDI can be staged without physical invoice printing, subject to operator/compliance confirmation. |

## Deployment Readiness

### Existing and production-usable foundations

- `apps/api/Dockerfile` has a non-root Python 3.12 `runtime` target and includes Alembic assets.
- `/health` provides liveness; `/ready` verifies MySQL; `/metrics` exposes Prometheus-format metrics.
- Both React/Vite clients have deterministic build commands and use `/api` by default, which suits same-origin routing.
- The Local Connector has a runtime image and Debian/systemd packaging with a restricted service account and automatic restart.

### Development-only or incomplete

- `compose.yaml` builds the API's `development` target, exposes Uvicorn directly, includes test dependencies, defaults `APP_ENV` to development, and starts with `alembic upgrade head` inside every API start.
- Its API health check calls `/health`, so a container can be healthy while MySQL is unavailable; production orchestration must use `/ready` for readiness.
- Compose contains only MySQL and API. It has no Diner Web, Staff Web, reverse proxy, static host, TLS, backup job, log/metric collector, or connector deployment.
- The web apps have no production Dockerfiles/static-server configuration. Their Vite proxy is development-only.
- FastAPI has no CORS middleware. The recommended minimum is a single HTTPS origin with proxy routing, avoiding a cross-origin dependency. If separate origins are chosen, an explicit allowlist is required.
- No CI/CD or release/deployment scripts were found. There is no immutable image/version promotion, controlled migration job, or rollback automation.
- `.env.example` is explicitly development-oriented and omits FINKOK configuration and all production provider/storage resolver settings. No tracked pilot/production environment template exists.

### Minimum production deployment boundary

Create immutable API and web images, one HTTPS ingress/static host, a private MySQL network, durable volumes, readiness-based rollout, and explicit release identity. Run Alembic once as a controlled pre-deploy job after backup and compatibility review—not concurrently in each API replica. Keep development and pilot secrets/data isolated. Validate the complete artifact in the pre-pilot environment before promotion.

## Runtime Configuration and Secrets

| Category | Examples (names/categories only) | Class | Current injection | Production finding |
| --- | --- | --- | --- | --- |
| API runtime | app environment, bind host/port, log level | required/non-secret | Environment/`.env` | Typed; production template missing. |
| MySQL connection | host, port, database, user | required/pilot-specific | Environment | Supported; topology values unknown. |
| MySQL passwords | application and administrative/root credentials | secret | Compose environment | No production secret store/injection or rotation procedure. Root credential should not be injected into API. |
| Authentication | JWT signing secret, algorithm, token TTL | secret/required | Environment | Minimum secret length enforced; rotation would invalidate tokens and has no documented procedure. |
| Diner access | independent restaurant access-code secret and diner TTL | secret/required | Environment | Independent secret enforced; rotation/access-code replacement procedure missing. |
| Connector auth | enrollment/access/credential TTLs; one-time client secret | secret/pilot-specific | API env plus local `0600` JSON file | Rotation/revocation APIs exist; issuance and host procedure required. |
| Payment | Conekta public key, private merchant credential, credential binding | provider credential | Public key in DB/client config; private key through resolver interface | No production `MerchantCredentialResolver`; real payments blocked. |
| Fiscal | FINKOK environment/endpoint/timeouts, account credential, credential binding | provider credential | Settings plus resolver interface | Settings exist but are absent from example/Compose; no production credential resolver. |
| Fiscal artifacts | storage endpoint/bucket/key, encryption credential | secret/provider-specific | Storage port interface | No implementation/config; real CFDI blocked. |
| TLS | certificate/private key or managed-certificate authority | secret/external | None | Ownership and provisioning missing. |
| Bootstrap | tenant/admin identity and temporary password | secret/pilot-specific | Environment only when CLI is run | Idempotent CLI exists; values must be removed after use and password rotated. |
| Connector targets | API URL, ledger/config paths, queues/IPs/device paths/encoding | pilot-specific | Local TOML | Supported; real values and protected configuration backup missing. |

Source-control exposure finding: no tracked production credential or certificate was found. `.env` and `.env.*` are ignored, while `.env.example` contains development placeholders. This is not a P0 leak. Before deployment, scan the release artifact/history with an approved secret scanner and use a production secret manager or protected orchestrator secrets—not repository files or image layers.

## Database / Storage

- Actual database: MySQL 8.4 in Compose. `compose.mariadb.yaml` is an alternative/test override, not the selected pilot baseline.
- Alembic is a single linear chain through head `0040_staff_location_authorization_scope`.
- SQLAlchemy uses async `aiomysql`, `pool_pre_ping`, 300-second recycle, and configurable pool size/overflow. Alembic uses the synchronous PyMySQL URL.
- Database URL construction has no TLS parameters. If MySQL crosses a host/network trust boundary, verified DB TLS is required; even when co-located on a private host, encryption-at-rest, firewall isolation, least privilege, and backup encryption remain required.
- The named volume provides persistence, not backup. There is no dump/snapshot schedule, off-host destination, retention, encryption, restore script, point-in-time strategy, or tested recovery-time/recovery-point objective.
- Core operation requires no Redis or object store. Enabling CFDI requires a durable implementation of `FiscalArtifactStoragePort`; the DB stores immutable artifact metadata/reference/hash, not the stamped XML bytes.

Required safe sequence: verify target/version and capacity; take and validate an encrypted backup; run a single controlled `alembic upgrade head`; verify Alembic head, `/ready`, and critical read paths; deploy compatible application images; preserve the prior application artifact; roll back application traffic if validation fails. Database downgrade is not an assumed rollback. A fresh-install rehearsal and an upgrade rehearsal from a representative prior copy are required in pre-pilot.

Minimum backup policy to finalize in WS-33-B:

| Asset | Minimum recommendation | Owner/evidence |
| --- | --- | --- |
| MySQL | Automated encrypted daily full backup plus a transaction-log/PITR mechanism where the selected platform supports it; off-host copy; at least 30 days retention, subject to business/legal confirmation | Operator; job success alert and quarterly restore drill, with a restore before pilot GO. |
| Fiscal artifacts (when enabled) | Versioned/encrypted storage and backup aligned with required retention; hash verification | Operator/compliance; retrieval and hash match proof. |
| Deployment/config | Versioned non-secret manifests; encrypted backup of secret references and operator-owned recovery data | Operator; rebuild rehearsal without copying plaintext secrets. |
| Connector | Protect TOML mappings and the host/state volume; keep credentials separately recoverable through re-enrollment | Restaurant/operator; replacement-host rehearsal when printing is enabled. |

RPO/RTO and retention are external business decisions and must be approved before policy implementation.

## Bootstrap / Master Data

`python -m app.bootstrap_admin` idempotently creates one Tenant, one User, one Tenant Membership, `TENANT_ADMIN`, core permissions, and the membership-role assignment. It is not wired to deployment. It does not create Organization, Location, staff users/roles, location grants, operational resources, restaurant catalog, fiscal/payment configuration, or connector topology. CRUD APIs cover many business objects, but no production staff/user/RBAC provisioning API or complete seed/import tool was found; those records currently need an approved one-time administrative mechanism.

| Pilot object | Mechanism | Minimum collected/verified input |
| --- | --- | --- |
| Tenant + initial admin | Automated CLI, manually invoked | Tenant name/slug; named admin email/display name; temporary strong password. |
| Organization | Manual through authenticated API | Legal/operating name and organization identity used by restaurant. |
| Location | Manual through API | Location name/code, address/timezone/operating identity required by its fields. |
| Staff memberships, roles, permissions | Missing complete provisioning workflow | Named Host, Waiter, Kitchen, Cashier, Manager identities; least-privilege role mapping. |
| Membership location grants | Missing complete provisioning workflow | Explicit grant of each staff membership to the one pilot location. |
| `TABLE` resources | Manual through API | Limited table codes/names and physical mapping. |
| `CASH_REGISTER` | Manual through API | Register code/name and responsible cashier workflow. |
| Cash management activation/session | Manual operational action | Activation decision, opening float/control rules, assigned operator. |
| Preparation areas | Manual through API | Kitchen/bar/etc. areas actually used. |
| Product preparation routes | Manual through API | Product-to-area mapping; unmapped behavior decision. |
| Products/compositions/menu/prices/tax evidence | Manual through APIs; no bulk importer found | Approved pilot menu, modifiers/compositions, availability, MXN prices, fiscal product/unit/tax classification where required. |
| Payment executor configuration | Manual/data mechanism not exposed as obvious admin CRUD | Only needed for electronic payment: location executor, capability, public key, non-secret binding, status/priority. |
| Issuer fiscal profile | Manual through check-scoped fiscal API | Only for CFDI: verified legal name, RFC, regime, postal code. |
| Connector and destinations | Manual through APIs | Connector identity; each preparation-area destination and `local_target_key`. |
| Paid-check target | Manual per print request | Active `CASH_REGISTER`, connector, and validated `local_target_key`. |

Before GO, export a redacted manifest of IDs and relationships and have the restaurant owner verify it. Run the bootstrap CLI once under change control, rotate the initial admin password, remove bootstrap values from the runtime, and restrict future CLI execution. There is no bootstrap HTTP endpoint to disable.

## Diner / Staff

- Diner needs a public HTTPS URL, a supported modern browser with JavaScript/local storage, and a staff-opened service session whose short access code is communicated for the correct location/table. The app joins and restores a diner-scoped bearer session.
- Staff needs a separate HTTPS route, named credentials, correct permissions, and an explicit membership location grant. Host, Waiter, Kitchen, Cashier, and Manager workspaces exist; least-privilege pilot roles and account lifecycle still need provisioning.
- Minimum device evidence: one representative diner phone browser and each actual staff device/browser; responsive visibility, session restore/logout, clock/timezone, network interruption, and safe retry. A large compatibility matrix is unnecessary.
- Shared accounts are not acceptable. Kitchen may use a dedicated named/operator-managed account only if accountability and shift handoff are explicitly approved.

## Payments

### Software readiness

**READY as an application foundation, not real-money ready.** `ConektaPaymentExecutor` supports Conekta Direct API card orders in MXN, single-attempt submission, durable idempotency evidence, explicit `UNCERTAIN`, and read-only recovery by external order reference. Diner Web loads Conekta's hosted tokenizer script and receives only the configured public key. Payment metrics and staff retry/recover endpoints exist. Cash payment is staff-only and integrates with cash sessions when cash management is active.

No inbound Conekta webhook/callback route was found. The current design is synchronous execution plus API retrieval recovery; 3DS is explicitly separate. Provider requirements must be confirmed before claiming this topology sufficient. If production requires webhook/3DS handling, that is additional implementation and public callback/DNS/TLS scope.

### External readiness

**BLOCKED.** Merchant production activation, production public/private keys, contract/limits, accepted domain/origin, and support/escalation contacts are unknown. The default app injects no production `MerchantCredentialResolver`; the only concrete resolver is explicitly deterministic/in-memory for tests. Location executor/capability data and reconciliation evidence are absent.

### Real-money GO gate

All must pass: production merchant account enabled; protected private-key resolver and public client key provisioned; location CARD/MXN capability enabled only in the target location; production HTTPS/origin and any required callback/3DS path confirmed; idempotent execution and recovery exercised; provider dashboard/API totals reconciled to ECIP; `UNCERTAIN` freeze/recovery/escalation runbook rehearsed; alerts active; one controlled low-value real transaction, recovery check, settlement, and refund/void policy evidence approved. Until then, keep electronic executors inactive.

Recommended progression: test executor -> Conekta test/sandbox account -> controlled real transaction outside normal service -> explicit enablement decision. Provider-specific current requirements remain **NEEDS CONFIRMATION** with Conekta; no provider was contacted in this discovery.

## Fiscal / FINKOK

### Software readiness

**READY as an application foundation.** The default registry includes a FINKOK SOAP adapter with demo/production endpoints, bounded timeouts, CFDI 4.0 mapping/serialization, `sign_stamp`, authoritative response/UUID/XML verification, explicit uncertain results, and `stamped` recovery. Immutable issuance attempts/results and artifact metadata/hash are persisted. Issuer and recipient fiscal profiles are supported. No CFDI cancellation implementation was found.

The adapter expects the issuer CSD relationship to be registered externally; it consumes a FINKOK username/password credential, not certificate/key files. This provider-account assumption must be confirmed. On success FINKOK returns stamped XML bytes, and issuance cannot finish safely without a real `FiscalArtifactStoragePort`. The default app supplies neither a fiscal credential resolver nor artifact storage.

### External readiness

**Demo/test-provider readiness: BLOCKED by configuration and credentials. Real-CFDI readiness: BLOCKED.** Missing inputs include FINKOK demo/production accounts, verified issuer fiscal identity, provider-side CSD setup/certificate validity evidence if required, protected credentials, storage/retention choice, and operator/compliance acceptance.

### Real-CFDI GO gate

Production PAC account enabled; issuer RFC/legal name/regime/postal code verified; required CSD certificates/keys valid and registered through the approved provider process; production credential resolver active; encrypted durable artifact storage active; provider demo issuance/recovery passed; production HTTPS egress allowed; stamped XML stored, retrievable, and hash-verified; ambiguous/failure recovery and customer delivery process rehearsed; controlled real issuance reconciled; cancellation limitation and correction procedure explicitly accepted. Until then, fiscal issuance stays disabled.

## Billing Print Limitation

Billing still does not expose a connector-ready authoritative printable invoice representation. Paid-check printing is a different artifact and must not be represented as fiscal invoice printing.

Impact: **DEFERRED / NON-BLOCKING** for the recommended initial pilot because CFDI is disabled. A later electronically issued CFDI can operate without connector printing from a software-flow perspective, provided the operator/compliance owner approves the electronic delivery and retention method. Physical invoice printing remains out of scope until an authoritative representation is designed and certified.

## Local Connector

### Software readiness

**SOFTWARE OPERATIONAL: READY.** The Python 3.12 worker polls both Preparation and Paid Check job families over outbound HTTPS, uses one-time enrollment and short-lived access tokens, enforces tenant/organization/location binding, maps explicit logical target keys with no fallback printer, and records a versioned SQLite ledger. It provides heartbeat/status, bounded backoff, singleton behavior, fenced claims, safe restart, CUPS reconciliation, explicit raw ESC/POS uncertainty, intentional reprint semantics, structured logs, a non-root Docker runtime, and Debian/systemd packaging.

### Deployment and host requirements

- Always-on supported Linux host at the restaurant, correct time, outbound HTTPS/DNS, protected disk, operator access, and a restart/service owner.
- Root-owned config, credential JSON mode `0600`, writable persistent ledger directory, log collection, package/image release identifier, and backup/replacement procedure.
- Network ESC/POS requires LAN reachability to printer IP/port (normally TCP/9100). USB requires stable device path, OS permissions, and physical attachment. CUPS requires a configured queue and PyCUPS; Debian declares `python3-cups`, while the current connector Docker image does not install PyCUPS, so do not select CUPS-in-container without closing that packaging gap.
- Physical pilot status remains **BLOCKED** until every actual destination passes certification.

### Machine-loss recovery

Cloud dispatch rows remain authoritative for job state, but the local ledger is authoritative evidence about whether the physical submission boundary may have been crossed. Therefore cloud reconstruction alone is unsafe for ambiguous in-flight work. Preserve/encrypt the connector state volume where practical. On loss: stop/revoke the old credential; retain/recover its disk and ledger if available; install a replacement; restore verified mappings; re-enroll; reconcile every claimed/in-progress/uncertain dispatch with an operator; then resume cloud polling. Never restore a stale ledger blindly or automatically reprint uncertain work.

## Physical Printers

For every enabled logical destination, the restaurant must provide:

| Required input | Notes |
| --- | --- |
| Logical destination | Preparation area destination code/name, or paid-check cashier target. |
| Physical placement | Kitchen station, bar, cashier, etc. |
| Brand/model | Exact model and firmware if available. |
| Connection | Network ESC/POS, USB ESC/POS, or CUPS. |
| Address | Static/reserved IP and port for network; device path for USB; queue name for CUPS. |
| Compatibility | ESC/POS support or approved driver/queue. |
| Media | Paper width translated to supported 32/42/48 columns. |
| Features | Cutter availability/command behavior. |
| Text | Required accents/symbols and verified `cp437`, `cp850`, or `latin-1` code page. |
| Host/network | Connector host, VLAN/subnet/firewall path, USB permissions, responsible owner. |

Preparation printing requires an active connector plus one `PreparationDeliveryDestination` for each enabled preparation area, with matching `local_target_key`. Paid-check printing requires an active `CASH_REGISTER`, active connector, and a separately chosen valid local target key; it is not modeled as a preparation destination.

Later certification evidence for each destination must show: connector authenticated and correct location; job received; correct destination; frozen content, quantities, modifiers, characters, width and order identity correct; cutter behavior correct; accepted/success state reported; printer-offline and network interruption behavior; connector restart and claim recovery; retry and intentional reprint; no automatic retry after an uncertain boundary; and no uncontrolled duplicate. CUPS acceptance/raw socket acceptance proves submission—not paper—so the operator must also attest physical output.

## Network / DNS / TLS

| Flow | Required path | Inbound/public requirement |
| --- | --- | --- |
| Browser -> platform | HTTPS TCP/443 to public DNS name; static client and `/api` under one origin recommended | Public ingress and valid TLS certificate. |
| Connector -> cloud | DNS + outbound HTTPS TCP/443 with certificate verification | No inbound restaurant connection. |
| API -> MySQL | TCP/3306 on private restricted network; verified TLS if crossing a trust boundary | Never public. |
| Diner browser -> Conekta | Outbound HTTPS to hosted tokenizer when cards enabled | CSP/origin/provider requirements must be confirmed. |
| API -> Conekta | Outbound HTTPS TCP/443 when cards enabled | No callback exists today; confirm whether provider requires one. |
| API -> FINKOK | Outbound HTTPS TCP/443 to selected SOAP endpoint when CFDI enabled | No inbound callback indicated by current adapter. |
| Connector -> network printer | Restaurant LAN, normally TCP/9100 for raw ESC/POS | LAN only; no Internet exposure. |
| Connector -> USB/CUPS | Local device node or CUPS service/queue | Host-local/LAN only. |

Before deployment select hostnames, prove DNS ownership, provision/renew TLS, define ingress limits, and document the allowed outbound destinations. Apply a secure Content Security Policy that accounts for Conekta only when enabled. Because the API has no CORS/trusted-host configuration, the single-origin proxy is the safe initial design. If proxy forwarding is used, trust only the known proxy and define forwarded-header behavior. Restaurant LAN details and firewall changes are external inputs.

## Observability

Existing primitives are useful but not an operating system: structured JSON logs, correlation IDs, safe route-label HTTP counters/duration, liveness, DB readiness, payment outcome/recovery metrics, event logs across payment/fiscal/preparation/printing, and connector heartbeat/`last_seen_at`. Logs include tenant and often organization/location/entity context; request-completion logs include tenant but not a general location field.

No Prometheus/Grafana/log backend, scrape policy, dashboards, alert routing, retention, on-call ownership, or synthetic checks are deployed. `/metrics` is unauthenticated and must be network-restricted. `/docs`/OpenAPI use FastAPI defaults and should be disabled or access-restricted at the production edge. Provider/storage-specific readiness is not included in `/ready`.

Minimum pilot alerting:

| Priority | Signal | Required response |
| --- | --- | --- |
| P0 | Public API/synthetic journey down; DB not ready; backup failure; accepted Order lacks Preparation beyond threshold; tenant/location authorization incident | Page technical operator; stop new traffic if integrity is at risk. |
| P0 when capability enabled | Any payment or fiscal `UNCERTAIN`; financial duplication; incorrect fiscal identity/artifact | Freeze repeat action and invoke recovery procedure. |
| P1 | Elevated payment provider failures; fiscal rejection/failure; connector offline; printer/action-required backlog; Preparation latency/backlog | Notify operational owner with entity/location context. |

One compact pilot dashboard should show API availability/latency/error rate, DB readiness/connections/capacity, Order -> Preparation lag/failures, open checks/uncertain payments, fiscal outcomes if enabled, connector heartbeat/backlog/failures if enabled, and last successful backup/restore proof. Alert messages must contain correlation and scoped entity IDs, never credentials or raw sensitive provider payloads.

## Backup / Restore

Classification: **BLOCKED**. No safe pilot deploy/migrate/backup/restore/verify sequence exists today.

Before GO, choose an encrypted off-host backup destination and owner, approve RPO/RTO/retention, automate database backups, alert on failures, document restore into an isolated target, and demonstrate application-level verification after restore. Verification must include Alembic head, counts/scoped samples, login, menu/read paths, an accepted-order/Preparation consistency check using non-production evidence, and artifact retrieval/hash where applicable.

Connector configuration and ledger handling follow the machine-loss procedure above. The ledger should be preserved as recovery evidence, but it is not a substitute for the cloud database backup and should not be used to reconstruct business truth. Provider credentials should be restored by secret-manager recovery or rotation/re-enrollment, not copied from plaintext backups.

## Security Operations

Existing controls: Argon2 password hashes; signed time-limited JWTs; separate diner audience/token and secret-derived access-code handling; tenant-aware foreign keys/queries; permission and location-grant checks; connector one-time enrollment, hashed credentials, short access token, rotation/revocation, and location binding; ephemeral provider credential contracts; no tracked production secret observed.

Pilot gaps: no production TLS/edge controls, rate limiting, explicit allowed hosts/origins, security headers/CSP, secret backend, secret rotation calendar, identity provisioning/deprovisioning workflow, audit/incident runbook, deployed vulnerability/secret scanning, or access review. Public liveness is acceptable if minimal; readiness, metrics, docs, and administrative routes need edge/network policy. Logs/backup access and retention require least privilege.

Initial identities must be named. Use bootstrap only for the initial administrator under change control; remove bootstrap environment variables, rotate the temporary password, review the administrator role, create least-privilege staff roles, grant only the pilot location, and test that cross-location access is denied. Terminated/lost-device accounts and connector/provider credentials need immediate revoke/rotate procedures.

## Runbook Status

| Runbook | Status | Required before |
| --- | --- | --- |
| Connector install/config/status | PARTIAL | Physical printing; README/systemd material exists but no site-specific checklist. |
| Start/stop platform | MISSING | Pilot GO. |
| Deploy/release verification | MISSING | Pilot GO. |
| Upgrade + controlled DB migration | MISSING | Pilot GO. |
| Application rollback/traffic stop | MISSING | Pilot GO. |
| Database backup | MISSING | Pilot GO. |
| Database restore + verification | MISSING | Pilot GO. |
| Incident response/security escalation | MISSING | Pilot GO. |
| Restaurant manual fallback/pilot shutdown | MISSING | Pilot GO. |
| Connector restart/re-enrollment/machine loss | PARTIAL | Physical printing. |
| Printer offline/uncertain/reprint | PARTIAL | Physical printing. |
| Payment `UNCERTAIN` recovery/reconciliation | MISSING | Electronic payment. |
| Fiscal failure/uncertain/artifact recovery | MISSING | CFDI. |

WS-33-B must produce the pilot-critical platform runbooks. Capability-specific runbooks can wait until the capability is enabled.

## External Input Register

No secret values belong in this register.

| Input | Required For | Owner/Source | Secret? | Repository Can Determine? | Status |
| --- | --- | --- | ---: | ---: | --- |
| Pilot restaurant, tenant and organization identity | Deployment/bootstrap | Restaurant owner | No | No | MISSING |
| Pilot location identity, address/timezone, hours | Bootstrap/GO | Restaurant owner | No | No | MISSING |
| Limited table/resource inventory | Core pilot | Restaurant manager | No | No | MISSING |
| `CASH_REGISTER`, cash controls and opening float policy | Cash pilot | Restaurant finance/manager | Partly | No | MISSING |
| Pilot menu, compositions/modifiers, prices, availability | Core pilot | Restaurant/menu owner | No | No | MISSING |
| Product fiscal classifications and tax treatment | Correct commercial/fiscal evidence | Restaurant accountant/catalog owner | No | No | MISSING |
| Preparation areas and product routes | Order -> Preparation | Kitchen manager | No | No | MISSING |
| Named Host/Waiter/Kitchen/Cashier/Manager identities | Staff operations | Restaurant manager | Initial password | No | MISSING |
| Least-privilege role and location-grant approval | Staff operations | Restaurant manager/security owner | No | Partly | NEEDS CONFIRMATION |
| Public Diner/Staff hostname(s) and DNS ownership | Deployment | User/domain owner | No | No | MISSING |
| TLS provisioning/renewal owner | Deployment | User/platform operator | Private key | No | MISSING |
| Hosting region/platform, capacity and network boundary | Deployment | Platform owner | No | No | MISSING |
| Backup destination, RPO/RTO, retention and restore owner | Safe GO | Business/platform owner | Storage credential | No | MISSING |
| Technical on-call and restaurant escalation contacts | Safe GO | User/restaurant | Contact data | No | MISSING |
| Pilot window, transaction limits and manual fallback | Safe GO | Restaurant/operator | No | No | MISSING |
| Conekta account/environment/merchant activation | Real payments | Merchant/Conekta | Account data | No | MISSING |
| Conekta public/private production credentials | Real payments | Merchant/Conekta | Yes (private) | No | MISSING |
| Conekta origin, webhook, 3DS and reconciliation requirements | Real payments | Conekta/merchant | No | No | NEEDS CONFIRMATION |
| FINKOK demo and production account | Test/real CFDI | Issuer/FINKOK | Yes | No | MISSING |
| Verified issuer legal name, RFC, regime, postal code | Real CFDI | Issuer/accountant | Sensitive | No | MISSING |
| CSD certificate/key validity and provider registration evidence | Real CFDI | Issuer/FINKOK | Yes | No | NEEDS CONFIRMATION |
| Fiscal artifact retention/delivery/compliance policy | Real CFDI | Accountant/compliance | No | No | MISSING |
| Physical printer inventory and logical mapping | Physical printing | Restaurant | No | No | MISSING |
| Connector host and administrator | Physical printing | Restaurant/IT | Access credential | No | MISSING |
| Restaurant LAN, IP/port/VLAN/USB/CUPS facts | Physical printing | Restaurant/IT | Partly | No | MISSING |
| Physical invoice print requirement | Billing printing | Restaurant/accountant | No | No | NEEDS CONFIRMATION |
| Redis/cache | Initial pilot | N/A | No | Yes | NOT REQUIRED |
| External POS integration | Recommended initial pilot | Restaurant/product owner | Varies | Partly | NOT REQUIRED |

Grouped dependency order:

- **Before deployment:** restaurant/location identity, host/platform boundary, DNS/TLS ownership, named admin, backup destination/RPO/RTO, and operational contacts.
- **Before core pilot GO:** complete limited master data, named staff and grants, cash controls, pilot window/limits/manual fallback, production-like acceptance evidence.
- **Before real payments:** merchant activation, credentials, provider topology requirements, secret resolver, reconciliation/operator evidence.
- **Before real CFDI:** PAC accounts, fiscal identity/CSD evidence, credentials, artifact retention/storage, operator/compliance approval.
- **Before physical printing:** printer/host/LAN inventory, logical mappings, connector enrollment, and per-destination physical evidence.
- **Optional/deferred:** external POS, electronic payment, CFDI, physical/billing printing for day-one cash/screen pilot.

## Pilot Capability Matrix

| Capability | Software Ready | External Inputs Ready | Physical Evidence Needed | Pilot Status |
| --- | ---: | ---: | ---: | --- |
| Diner access/join/menu | Yes | No | Representative phone/browser | PARTIAL |
| Staff login and location-scoped operations | Yes | No | Actual staff device/browser | PARTIAL |
| Host service session/table access | Yes | No | Operational rehearsal | PARTIAL |
| Diner order -> accepted Order | Yes | No | End-to-end rehearsal | PARTIAL |
| Automatic Order -> Preparation | Yes | No | Timing/failure rehearsal | PARTIAL |
| Kitchen screen execution | Yes | No | Kitchen device/restart rehearsal | PARTIAL |
| Waiter operational requests | Yes | No | Staff rehearsal | PARTIAL |
| Cash register/session/payment | Yes | No | Drawer/control rehearsal | PARTIAL |
| Check settlement | Yes | No | Controlled cash transaction | PARTIAL |
| Electronic CARD payment | Yes (foundation) | No | Controlled real transaction/reconciliation | NOT IN INITIAL PILOT |
| Billing document/CFDI | Yes (foundation) | No | Provider/artifact evidence | NOT IN INITIAL PILOT |
| Kitchen physical printing | Yes (software) | No | Per-printer certification | NOT IN INITIAL PILOT |
| Paid-check physical printing | Yes (software) | No | Per-printer certification | NOT IN INITIAL PILOT |
| Physical fiscal invoice print | No authoritative payload | No | Design/certification | NOT IN INITIAL PILOT |
| Manager overview | Yes | No | Manager device/data rehearsal | PARTIAL |
| Backup/restore | No | No | Restore drill | BLOCKED |
| Observability/incident response | Partial | No | Alert/runbook drill | BLOCKED |

## P0/P1/P2 Gap Register

| ID | Domain | Current state -> required state | Severity/type | Owner | Recommended slice |
| --- | --- | --- | --- | --- | --- |
| P0-DEP-01 | Deployment | Dev Compose/direct Uvicorn/no web host -> immutable production images, HTTPS same-origin ingress, readiness rollout and release/rollback procedure | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-CFG-01 | Secrets | Environment placeholders/no production backend -> protected injection, access policy, rotation/recovery and release secret scan | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-DATA-01 | Database | Persistent volume only -> automated encrypted off-host backup, alert, isolated restore and verified recovery | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-MIG-01 | Migration | `upgrade head` on every API start -> single controlled backed-up migration/fresh-install/upgrade procedure | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-SEC-01 | Perimeter/security | No TLS/host/origin/rate/metrics-docs policy -> production edge, endpoint exposure policy, least privilege and identity lifecycle | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-OPS-01 | Observability | Primitives only -> collected logs/metrics, synthetic/readiness checks, P0 alerts, owners and retention | P0 PLATFORM BLOCKER | Codex + operator | WS-33-B |
| P0-RUN-01 | Operations | Required platform/incident/manual-fallback runbooks absent -> rehearsed concise runbooks and rollback authority | P0 PLATFORM BLOCKER | Codex + operator/restaurant | WS-33-B/D |
| P0-PILOT-01 | Pilot data | No real restaurant/master/staff data -> verified one-location manifest, named accounts/roles/grants, menu/routes/resources/cash configuration | P0 PLATFORM BLOCKER | Restaurant + Codex | WS-33-C |
| P0-ACC-01 | Acceptance | No production-like or restaurant rehearsal -> staged E2E, restart, backup/restore, alert and manual-fallback evidence | P0 PLATFORM BLOCKER | Operator + restaurant | WS-33-D |
| P1-PAY-01 | Payment | Conekta foundation but no production resolver/account/config -> protected credential resolution and all real-money gates | P1 CAPABILITY BLOCKER | Codex + merchant/Conekta | WS-33-C |
| P1-FIS-01 | Fiscal | FINKOK foundation but no resolver/storage/accounts -> credential resolver, artifact store and real-CFDI gates | P1 CAPABILITY BLOCKER | Codex + issuer/FINKOK | WS-33-C |
| P1-FIS-02 | Fiscal cancellation | No cancellation flow -> explicitly accepted correction/manual process or later implementation | P1 CAPABILITY BLOCKER if CFDI enabled | Product + accountant + Codex | WS-33-C |
| P1-PRN-01 | Printing | Connector ready; hardware/site unknown -> host, mappings and per-destination physical certification | P1 CAPABILITY BLOCKER | Restaurant IT + Codex | WS-33-C |
| P1-PRN-02 | CUPS packaging | Debian supports PyCUPS; Docker runtime does not -> select Debian/raw ESC/POS or add/test CUPS image support | P1 CAPABILITY BLOCKER only if CUPS container selected | Codex | WS-33-C |
| P2-DEP-01 | Health | Compose probes `/health` -> production readiness probe uses `/ready` | P2 improvement captured within P0 deployment work | Codex | WS-33-B |
| P2-CICD-01 | Delivery | No CI/CD -> add reproducible checks/image promotion; manual controlled releases may suffice for limited pilot | P2 improvement | Codex/operator | WS-33-B |
| P2-BIL-01 | Billing print | No authoritative connector invoice payload -> defer; never substitute paid check for CFDI | P2 PILOT-SCOPE EXCLUSION | Product/Codex | Future |
| P2-POS-01 | External POS | No real POS selected/certified -> use native path for initial pilot | P2 PILOT-SCOPE EXCLUSION | Restaurant/product | Future |

P1 items do not delay the recommended pilot when the associated feature is explicitly disabled. P2 items must not delay it unless the chosen topology promotes one into an enabled-capability dependency.

## Minimum Pilot Scope

Use one Tenant, one Organization, one Location, a limited set of tables, a small approved menu, explicit preparation routes, one active cash register, named Host/Waiter/Kitchen/Cashier/Manager users with only the pilot location grant, and a technical operator present during controlled service.

Day-one capabilities:

- Enable: Diner access, native menu/order, automatic Preparation, Kitchen screen, waiter requests, Check, cash payment/cash session, Settlement, and Manager overview.
- Disable: Conekta/card/transfer executors, FINKOK/CFDI issuance, all connector destinations and paid-check printing, physical invoice printing, and external POS submission.
- Keep the restaurant's prior/manual order, kitchen, cash receipt, and accounting processes ready as rollback. Limit hours/tables/menu/transaction value and do not begin during peak service.

This scope is real—the application handles live diner/order/cash data—but avoids moving money through an uncertified provider, issuing fiscal documents, or crossing an uncertified physical printer boundary.

## Staged Enablement

1. **Stage 0 — production-like rehearsal:** synthetic data, full deployment/restart/restore/alerts/manual fallback.
2. **Stage 1 — controlled cash/screen pilot:** minimum scope above, technical operator present, low traffic.
3. **Stage 2 — physical printing:** only after connector host and each destination pass the physical print gate.
4. **Stage 3 — electronic payment:** sandbox, then controlled real payment and reconciliation; enable CARD per location only after GO.
5. **Stage 4 — CFDI:** demo issuance/recovery/artifact proof, then controlled real issuance and compliance sign-off.

Stages 2-4 are independent after Stage 1; business priority can reorder them, but none may inherit another stage's GO evidence.

## Pilot Success, Rollback, and GO / NO-GO Prerequisites

### Measurable success evidence

- Representative diner joins the correct service/table, sees the approved menu/configuration, confirms an order once, and receives authoritative status.
- Every accepted Order produces the correct Preparation work within the agreed threshold; Kitchen sees quantities/modifiers and completes it; no accepted Order is lost.
- Waiter requests are acknowledged/completed, Check liability matches the order, cash tender/change and cash-session movements reconcile, Settlement occurs once, and Manager totals/queues match authoritative records.
- API/DB/clients survive planned restart; session recovery behavior is understood; backup completes; isolated restore passes verification; alerts reach the named operator.
- If printing is enabled later: both Preparation and Paid Check evidence passes every configured destination, including offline/restart/reprint/duplicate-safety cases.
- If card is enabled later: controlled payment, `UNCERTAIN` recovery drill, settlement, and provider reconciliation pass.
- If CFDI is enabled later: controlled stamping, artifact retrieval/hash, recovery drill, customer delivery, and provider/accounting reconciliation pass.

### Pilot GO gate

- All P0 gaps are closed with evidence and owners.
- Every pilot-enabled P1 capability is certified; all other P1 capabilities are technically/configurationally disabled.
- Backup restore, deployment rollback/manual fallback, security/tenant-location isolation, Order -> Preparation, and cash reconciliation drills pass.
- Named technical and restaurant decision-makers sign the scope/window/limits and can stop the pilot.

### NO-GO / rollback triggers

Immediate stop for tenant/location data leakage, unsafe secret exposure, financial duplication, unrecoverable payment uncertainty, incorrect fiscal issuance, an accepted Order lost before Preparation, unrecoverable/corrupt database state, uncontrolled duplicate print, or inability to return to the manual process. Also pause on sustained API/DB outage, alerting blindness, backup failure beyond approved RPO, or repeated workflow divergence.

Rollback sequence: stop new diner traffic at ingress; announce manual mode; restrict staff mutations if integrity is uncertain; disable all electronic executor/fiscal configuration; stop connector service/claims when print integrity is uncertain; preserve database, logs, correlation/entity IDs, provider evidence, and connector ledger; restore prior application release only if data-compatible; do not downgrade the database casually; reconcile open orders/checks/payments/prints; return the restaurant to its prior process under the designated authority.

### Separate capability gates

- **Real money:** merchant production account and credentials; protected resolver; TLS/origin and any webhook/3DS requirement; idempotency/recovery; `UNCERTAIN` procedure; controlled real transaction; provider reconciliation.
- **Real CFDI:** production PAC account; correct issuer/CSD setup; protected resolver; artifact persistence; successful demo and controlled production issuance; recovery/delivery/operator procedure; cancellation limitation accepted.
- **Physical print:** installed/enrolled correct-location connector; destinations mapped; real printers and network/USB path; test print; offline, interruption, restart, retry, reprint, cutter/text and duplicate-safety evidence.

Current decision remains **NO-GO** until the core pilot P0 gate closes.

## User Action Checklist

1. Confirm the one restaurant/organization/location, pilot window, traffic/transaction limits, manual fallback, and named business/technical stop authorities.
2. Provide the limited tables/resources, menu/prices/modifiers, preparation areas/routes, cash-register controls, and named staff/role/location-grant approvals.
3. Choose the pilot hosting/network boundary, public hostname/DNS/TLS owner, and production secret-management method.
4. Choose the encrypted off-host backup destination and approve RPO, RTO, retention, restore owner, monitoring/on-call, and escalation contacts.
5. Decide whether day-one remains cash-only, screen-only, no-CFDI as recommended; keep each excluded capability disabled.
6. If physical printing is prioritized later, provide the connector host, printer inventory, logical mappings, LAN/USB/CUPS facts, and onsite test operator.
7. If cards are prioritized later, confirm the Conekta environment/account, provider requirements, and arrange credentials through the secret channel.
8. If CFDI is prioritized later, confirm FINKOK accounts, verified issuer/CSD setup, retention/delivery policy, and credentials through the secret channel.

## Recommended WS-33 Execution Slices

Three slices are sufficient; optional capabilities are gated within one configuration/certification slice rather than forcing day-one enablement.

### WS-33-B — Pilot Platform and Operational Safety

- **Objective:** build the production application boundary and close deployment, security, observability, migration, backup/restore, and platform-runbook P0s.
- **External inputs:** hosting boundary, DNS/TLS owner, secret method, backup destination/RPO/RTO/retention, on-call contacts.
- **Expected repository changes:** production API/web/ingress manifests/images, complete environment template without values, controlled migration/backup/restore/release scripts, monitoring/alert rules, and concise runbooks. No business-schema migration is expected unless implementation evidence proves one unavoidable.
- **Real-world actions:** provision pilot infrastructure/secrets/DNS/TLS/backup target and alert recipients; run pre-pilot restore/restart/rollback drills.
- **Verification:** immutable build; HTTPS/same-origin/API readiness; secret and exposure checks; fresh/upgrade migration rehearsal; backup/restore; alert delivery; rollback/manual-fallback rehearsal.
- **Exit:** platform P0-DEP/CFG/DATA/MIG/SEC/OPS/RUN closed.
- **Dependency:** WS-33-A and user inputs 1, 3, 4.

### WS-33-C — Restaurant Configuration and Capability Certification

- **Objective:** provision and verify the one-location master/staff/cash configuration; certify only the optional providers/printers the user elects to enable.
- **External inputs:** restaurant/menu/staff/cash data; and, only for selected capabilities, merchant/PAC credentials and requirements or printer/host/LAN inventory.
- **Expected repository changes:** repeatable redacted bootstrap/configuration tooling and acceptance fixtures; production secret-resolver/artifact-storage adapters only if payment/CFDI is selected; connector packaging/config changes only if the selected hardware demands them; capability runbooks.
- **Real-world actions:** named account setup, restaurant data approval, cash rehearsal; provider sandbox/controlled transaction or onsite printer tests only for selected capabilities.
- **Verification:** scope/RBAC denial tests; data manifest approval; core workflow and cash reconciliation; each selected real-money/CFDI/print gate independently.
- **Exit:** P0-PILOT closed; every enabled P1 certified and every excluded P1 demonstrably inactive.
- **Dependency:** WS-33-B environment available and user inputs 2, 5; inputs 6-8 only as applicable.

### WS-33-D — Pilot Acceptance and GO / NO-GO

- **Objective:** run production-like acceptance, execute final operational drills, and record the formal launch decision without silently expanding scope.
- **External inputs:** pilot window, restaurant participants, decision authorities, approved limits/manual fallback.
- **Expected repository changes:** acceptance evidence and final operator checklist; only defect fixes proven necessary by acceptance, reviewed separately.
- **Real-world actions:** representative-device journeys, restart/restore/alert/fallback drill, controlled service rehearsal, and signed GO/NO-GO.
- **Verification:** measurable success list, unresolved-gap review, rollback triggers, restore evidence, and capability configuration audit.
- **Exit:** no enabled P0, enabled P1 certified, owners present, formal GO; otherwise NO-GO with gaps retained.
- **Dependency:** WS-33-B and core portions of WS-33-C complete.

## Human vs Codex Responsibility

| Responsibility class | Remaining work |
| --- | --- |
| CODEX CAN IMPLEMENT | Production images/manifests/edge configuration; secret-provider interfaces/adapters against a user-selected backend; controlled deploy/migration/backup tooling; monitoring rules; bootstrap/config tooling; provider/storage integration code; runbooks and automated evidence. |
| USER / OPERATOR MUST PROVIDE | Restaurant/location/menu/preparation/staff/cash facts; hosting/DNS/TLS/backup choices; RPO/RTO/retention; contacts; approved scope/limits; merchant/PAC accounts and credentials through a secure channel; printer/host/LAN facts. |
| USER / OPERATOR MUST EXECUTE | Infrastructure and secret provisioning, DNS delegation, credential rotation, restore and rollback drills, account approval, restaurant training/rehearsal, physical checks, formal GO/NO-GO and pilot stop. Codex may guide/automate authorized steps. |
| EXTERNAL PROVIDER MUST ENABLE | Conekta merchant production capability and applicable origin/3DS/webhook requirements; FINKOK demo/production account and issuer/CSD relationship; provider support/escalation paths. |
| PHYSICAL HARDWARE REQUIRED | Actual diner/staff devices for representative validation; connector host; printers, cabling/LAN/USB/CUPS; paper/cutter/encoding tests. |

Codex cannot fabricate merchant/PAC credentials, DNS ownership, fiscal identity, provider activation, restaurant network facts, or physical print evidence.

## Discovery Verification and Issues

Completion checklist:

- Pilot topology, all readiness domains, configuration categories, database/storage, bootstrap/master data, provider readiness, connector/hardware/network, secrets, observability, recovery/security/runbooks: assessed.
- External Input Register, Pilot Capability Matrix, complete P0/P1/P2 register, minimum scope, staged gates, checklist, responsibilities, success/rollback, and three execution slices: defined.
- Production code changes: **NONE**.
- Migration: **NONE**.
- Broad WS-30/31/32 suites: not rerun by policy; certified baseline reused.
- Open issues are the gap register, not discovery omissions. Provider-current requirements, legal retention/delivery, RPO/RTO, infrastructure, restaurant data, and physical hardware remain external and must not be inferred.

