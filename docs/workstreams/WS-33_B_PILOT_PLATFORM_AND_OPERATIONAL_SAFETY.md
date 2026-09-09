# WS-33-B — Pilot Platform and Operational Safety

## Status and decision

**STATUS: PASS**  
**DECISION: APPROVED**  
**WS-33-B closed: YES**  
**Overall pilot: NO-GO — WS-33-C and WS-33-D remain.**

Baseline: clean `feat/ws-00-01-runtime-reuse-baseline` at `4adb372eec1683b9d9e553aa1c2ccf5488a6a535` (`WS-33-A`), with baseline `git diff --check` passing. No commit or push was performed.

## Deliverables

### D1 — Production Deployment & Artifact Distribution — COMPLETE

- Independent production images: `restaurant-api`, `restaurant-diner-web`, `restaurant-staff-web`, and `restaurant-local-connector`; versioned ingress image also supplied.
- Production Compose consumes image references only. No application source mounts, Vite/Uvicorn development mode, database publication, build context, or startup migration exists on a VPS.
- TLS ingress serves `/diner/`, `/staff/`, and same-origin `/api/`; both SPAs have deep-link fallback. API, static services, ingress, and migration job use least-privilege/read-only settings and health integration.
- `scripts/release-images.sh` derives `git-<full SHA>`, labels images with the revision, supports publish, and reports a digest after registry push. `latest` is not accepted as authoritative identity.
- External MySQL is configured by host/port/database/runtime and migration identities. The certification-only override adds local isolated MySQL without publishing a port.
- Private-registry workflow and separate build/push, VPS pull-only, and Connector pull-only credential boundaries are documented. Actual registry namespace and credentials remain operator values.

### D2 — Production Configuration & Secret Boundary — COMPLETE

- One authoritative non-secret contract covers image references, runtime, external MySQL, JWT/auth, diner secret, public origin/trusted hosts, logs, monitoring, provider settings, Connector TTLs, and explicit capability switches.
- Runtime, migration, TLS, registry, backup, provider, and Connector secrets remain protected backend/local files. Frontend build variables contain only public paths. MySQL root is absent from API and migration runtime.
- Secret-file injection is non-echoing; health/readiness are bounded; logs record metadata rather than request/provider payloads.
- Production Compose hard-disables electronic payments, CFDI, connector delivery, and external POS. Tests prove empty Conekta/FINKOK registries and fail-closed Connector/POS endpoints.
- Bounded tracked-secret/artifact and runtime-image filesystem checks passed.

### D3 — Controlled Database Migration — COMPLETE

- API `CMD` starts Uvicorn only. The profiled `migrate` service is the single production Alembic authority.
- Promotion flow requires a non-empty confirmed backup (checksum verified when present), executes `alembic upgrade head`, then verifies current revision. Failure exits nonzero and blocks deployment.
- Executed fresh isolated database migration: `base → 0040_staff_location_authorization_scope` PASS.
- Executed representative existing database migration: `0039_payment_executor_client_configuration → 0040_staff_location_authorization_scope` PASS; synthetic tenant row retained.
- No new business-schema migration was introduced. Database rollback policy is compatible application rollback or controlled restore, never automatic downgrade.

### D4 — Backup & Restore — COMPLETE

- `mysql-backup.sh` produces timestamped/release-named consistent MySQL dumps, checks non-empty dump and gzip integrity, optionally encrypts with AES-256/PBKDF2, emits SHA-256, supports a mounted/off-host destination and provider-neutral upload command, configurable retention, and Pushgateway success/failure metrics.
- A safe missing-database run returned failure and published failure state: PASS.
- Executed encrypted backup and checksum validation: PASS.
- Executed isolated restore into a new database: PASS.
- Restored database Alembic head, representative tenant, API connection, `/ready`, and authenticated `/tenants/current` read: PASS.
- RPO, RTO, retention, and destination remain operator inputs.

### D5 — Production Security Perimeter — COMPLETE

- TLS 1.2/1.3 integration, HSTS/CSP/frame/content/referrer/permissions headers, safe proxy header replacement, same-origin routing, trusted hosts, public entry rate limiting at edge and bounded per-process defense in depth are present.
- `/health` and `/ready` are public bounded probes; `/metrics`, docs, Redoc, and OpenAPI are denied publicly. Prometheus scrapes metrics privately. DB has no host port.
- Services drop capabilities, enable no-new-privileges, use read-only filesystems where applicable, and run non-root. VPS and Connector hosts need no repository credential.
- Executed outage cycle: DB up `/ready` 200; DB stopped `/health` 200 and `/ready` 503; DB restarted `/ready` recovered to 200.

### D6 — Observability & Alerting — COMPLETE

- Private Prometheus and Alertmanager deployment uses HTTP availability/latency/error metrics, readiness, bounded operational event counters, existing payment metrics, backup Pushgateway state, and structured stdout logs.
- Operational view and alerts cover API unavailable/error rate, DB readiness, Order → Preparation failure, backup failure/staleness, uncertain payments, fiscal failures, Connector offline, and print action-required backlog. Disabled-capability signals remain inactive.
- Prometheus successfully scraped API `/metrics` and collected `ecip_backup_success{job="ecip_backup"}=1`.
- Safe synthetic `ApiUnavailable` rule test: PASS. Recipient remains operator input.
- Sampled structured logs contained route/status/correlation metadata and no secret or payment/fiscal payload values.

### D7 — Operational Runbooks & Rollback — COMPLETE

- Reproducible runbooks cover build/publish/pull/deploy, start/stop, release verification, controlled migration, backup, restore, traffic stop, application rollback, incident response, manual restaurant fallback, and Connector update/rollback.
- Executed representative operations: stack start, release verification, ingress traffic stop/start, immutable API image-ID selection/redeployment/readiness, encrypted backup/restore, DB incident cycle, and recovery verification.
- Connector current-tag and immutable-image-ID starts both passed while the Compose contract retained identical external config, credential, and named ledger mounts. Existing Connector suite passed. No physical printer was used.

## Production artifact strategy

Private source repository → controlled clean-commit build → private registry → immutable tag/digest → authenticated runtime pull. Source on VPS: **NO**. Source on Connector host: **NO by default**. Docker is packaging, not cryptographic source protection; no obfuscation was added.

Local MySQL is for development, rehearsal, destructive restore, and synthetic validation. External MySQL is the one authoritative real-pilot database. Continuous synchronization: **NO**.

## Excluded capabilities

| Capability | WS-33-B production state | Proof |
| --- | --- | --- |
| Electronic payment | disabled | Conekta is not registered when `ELECTRONIC_PAYMENTS_ENABLED=false` |
| CFDI | disabled | FINKOK is not registered when `CFDI_ISSUANCE_ENABLED=false` |
| Physical printing | disabled | `/connector/v1/*` fails closed when Connector delivery is disabled |
| External POS | disabled | `*pos-submission*` fails closed when external POS is disabled |

Certified underlying software remains present. Enabling any excluded capability requires later independent certification.

## Acceptance gates

| Gate | Result | Evidence summary |
| --- | --- | --- |
| G1 Deployment | PASS | all images built; Compose resolved/started; HTTPS Diner/Staff/API and SPA fallback passed; external DB supported/private |
| G2 Config/secrets | PASS | complete contract; separation and hard disables; bounded repo/image scans passed |
| G3 Migration | PASS | startup migration absent; explicit fresh and representative upgrade paths reached head |
| G4 Backup/restore | PASS | encrypted backup, checksum, isolated restore, head/data/readiness/authenticated read passed |
| G5 Security | PASS | TLS/headers/origin/proxy/endpoint/rate/private DB boundaries and outage cycle passed |
| G6 Observability | PASS | API/DB/backup/operations view, private metric scrape, structured logs, synthetic alert passed |
| G7 Operations/recovery | PASS | runbooks plus start/stop, traffic stop, digest rollback, migration, restore, fallback and Connector rehearsals passed |

## P0 closure matrix

| P0 | Deliverable | Gate | Result |
| --- | --- | --- | --- |
| P0-DEP-01 | D1 | G1 | PASS |
| P0-CFG-01 | D2 | G2 | PASS |
| P0-MIG-01 | D3 | G3 | PASS |
| P0-DATA-01 | D4 | G4 | PASS |
| P0-SEC-01 | D5 | G5 | PASS |
| P0-OPS-01 | D6 | G6 | PASS |
| P0-RUN-01 | D7 | G7 | PASS |

## Verification record

- Images: API `sha256:160610b9…`, Diner `sha256:a9f3ec9f…`, Staff `sha256:961a17af…`, Connector `sha256:def1c374…`, ingress `sha256:f4c95feb…`; local certification identities only. Registry digests become available after operator-authenticated push.
- Frontend production builds: PASS. Focused Diner 8 tests and Staff 16 tests: PASS.
- API config/health/production safety: 9 tests PASS; directly affected default-provider compatibility tests PASS. Connector: 23 tests PASS.
- Production Compose resolution and image-only startup: PASS.
- HTTPS ingress routing/SPA/security headers: PASS. Public metrics/docs/OpenAPI denied by policy.
- Fresh and representative upgrade migration: PASS. Backup failure detection: PASS. Encrypted backup/restore/head/data/API read: PASS.
- Prometheus private scrape, backup success signal, synthetic alert: PASS.
- Traffic stop/start, immutable API redeployment, Connector selection/reselection: PASS.
- Bounded secret/artifact scan, image-content checks, shell syntax, and `git diff --check`: PASS.

Direct regression: production runtime/configuration/security tests PASS.  
Secondary regression: focused Diner/Staff route-shell tests and production builds PASS.  
Collateral regression: existing Connector test target PASS; business behavior reused from WS-30/31/32 evidence because no business logic/schema changed.

## Operator inputs still required

Final DNS/domain, real TLS certificate/private key, hosting/IP, private registry namespace/account, build-push credential, distinct VPS/Connector pull credentials, external MySQL endpoint/runtime/migration/backup credentials, backup destination/encryption/storage credential, RPO/RTO/retention, alert recipient, and later restaurant/provider/printer inputs. These are **OPERATOR VALUE PENDING**, not implementation missing.

## Closure

- Deliverables complete: **YES**
- Gates passed: **YES**
- Platform P0s closed: **YES**
- Registry-ready artifacts: **YES**
- Source-free VPS deployment: **YES**
- Business-schema migration: **NONE**
- Architectural blockers: **NONE**
- WS-33-B closed: **YES**
- Pilot GO: **NO — WS-33-C/D remain**
- Next: **WS-33-C — Restaurant Configuration and Capability Certification**
