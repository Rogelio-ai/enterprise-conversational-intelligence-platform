# SQLAlchemy ↔ Alembic ↔ MySQL schema consistency audit

**Audit date:** 2026-10-09

**Audit result:** COMPLETE — CONSISTENCY FAIL

**Clean rebuild certification:** PASS
**Rebuild readiness:** READY_WITH_REMEDIATION

## 1. Scope and authority

This report records a read-only audit of the canonical SQLAlchemy metadata, the complete
Alembic graph, the protected local MySQL `ecip` schema, and a disposable database rebuilt from
zero with `alembic upgrade head`.

Governing sources inspected:

- `AGENTS.md`;
- `docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md`;
- `docs/SDD/GLOBAL_SDD.md` version 0.2.0, APPROVED;
- `docs/SDD/capabilities/MYSQL_BACKUP_RECOVERY_CAPABILITY_SDD.md` version 0.1.1,
  APPROVED, for source-protection and isolation rules;
- `docs/operations/DATABASE_BACKUP_RESTORE_RUNBOOK.md`;
- `skills/repository-discover/SKILL.md` and
  `skills/capability-certification/SKILL.md`.

No additional Capability SDD was required. This run made no permanent design or product change;
the only database mutation was in uniquely owned disposable verification infrastructure. The
approved Global SDD migration, persistence, tenant-isolation, and security rules were sufficient.

## 2. Baseline

| Item | Actual evidence |
|---|---|
| Repository | `/home/rogelio/proyectos/pryecip` |
| Branch | `feat/ws-00-01-runtime-reuse-baseline` |
| HEAD | `ca878dcf5a25a57ae09596fd3fdc7def8abeb404` |
| Working tree | Dirty before audit; all pre-existing modified and untracked work preserved |
| Source database | `ecip`, MySQL 8.4.8 |
| Source container | `pryecip-mysql-1`; ID `e7e099b1e7a2ee1110b28d3e4292f6847c08767930f34e16a4d2399cdfae47d4` |
| Source volume | `pryecip_mysql-data`, mounted at `/var/lib/mysql` |
| Source Alembic current | `0067_internal_operational_message_foundation (head)` |
| Alembic heads | one: `0067_internal_operational_message_foundation` |

The dirty tree includes Staff Credential Administration, Staff Login remediation, governance
documents, and the approved MySQL Backup & Recovery SDD described by the operator. None was
modified by this audit.

## 3. Deterministic inventories

`app.models` was imported before reading `Base.metadata`; therefore the metadata inventory does
not rely on importing `Base` alone.

| Inventory | SQLAlchemy | Current `ecip` | Clean Alembic database |
|---|---:|---:|---:|
| Application tables | 151 | 151 | 151 |
| Infrastructure tables | 0 | 1 (`alembic_version`) | 1 (`alembic_version`) |
| Total physical tables | N/A | 152 | 152 |
| Application columns | 2,297 | 2,297 | 2,297 |
| Application primary keys | 151 | 151 | 151 |
| Foreign keys | 427 | 427 | 427 |
| Unique constraints | 305 | 305 | 305 |
| CHECK constraints | 453 | 453 | 453 |
| ORM-declared explicit indexes | 168 | N/A | N/A |
| Physical non-unique indexes | N/A | 515 | 516 |

Equal aggregate foreign-key counts do not imply equivalence: the source has extra redundant
foreign keys that numerically offset missing or incorrect required foreign keys.

All 151 application tables in both physical databases use InnoDB. In both databases, 147 tables
use `utf8mb4_unicode_ci` and four use the MySQL 8.4 server default
`utf8mb4_0900_ai_ci`; the four-table deviation is a confirmed clean-chain defect described below.

## 4. Alembic history

| Property | Result |
|---|---|
| Revision files / graph revisions | 67 / 67 |
| Base | `0001_runtime_baseline` |
| Head | `0067_internal_operational_message_foundation` |
| Branch points | none |
| Merge points | none |
| `depends_on` edges | none |
| Duplicate revision IDs | none |
| Missing/broken `down_revision` | none |
| Ordering | one linear graph established by Alembic, not filename-number assumptions |

Static operation inventory across upgrade and downgrade functions:

| Operation | Call sites |
|---|---:|
| `create_table` | 150 (one looped call site creates multiple final tables) |
| `drop_table` | 128 |
| `add_column` / `drop_column` / `alter_column` | 94 / 73 / 8 |
| `create_index` / `drop_index` | 167 / 56 |
| `create_foreign_key` | 34 |
| `create_unique_constraint` | 40 |
| `create_check_constraint` | 69 |
| `drop_constraint` | 114 |
| raw `op.execute` | 14 |

Raw SQL/data-transform call sites occur in revisions `0003`, `0016`, `0023`, `0041`, `0042`,
`0043`, and `0064`. No migration contains `CREATE TRIGGER`, `CREATE VIEW`,
`CREATE PROCEDURE`, `CREATE FUNCTION`, or `CREATE EVENT`. No downgrade was executed.

## 5. Isolated clean rebuild

Owned temporary resources:

- container: `pryecip-schema-audit-mysql-20261009`;
- volume: `pryecip-schema-audit-data-20261009`;
- network: `pryecip-schema-audit-net-20261009`.

Before migration, Docker inspection proved that the temporary MySQL container:

- was attached only to `pryecip-schema-audit-net-20261009`;
- mounted only `pryecip-schema-audit-data-20261009` at `/var/lib/mysql`;
- published no host port (`3306/tcp` and `33060/tcp` were `null`);
- resolved the Alembic runner target as host
  `pryecip-schema-audit-mysql-20261009`, port `3306`, database `ecip_audit`, and user
  `audit_user`.

The current repository source was mounted read-only into the runner. `alembic upgrade head`
completed with exit code 0. The resulting database reported:

```text
current: 0067_internal_operational_message_foundation
heads:   0067_internal_operational_message_foundation
tables:  151 application + alembic_version
MySQL:   8.4.8
```

The first failing revision is **NONE**. All three temporary resources were removed individually
after evidence collection; no audit resource remains.

## 6. Structural comparison

### 6.1 Result matrix

| Comparison | Raw result | Normalized semantic result |
|---|---|---|
| SQLAlchemy vs clean Alembic | FAIL | FAIL — 9 confirmed differences |
| Clean Alembic vs current MySQL | FAIL | FAIL — 5 confirmed differences |
| SQLAlchemy vs current MySQL | FAIL | FAIL — 14 confirmed differences |

Normalization treated the following as equivalent where semantics match:

- `NUMERIC` and MySQL `DECIMAL`;
- SQLAlchemy `Boolean` and MySQL `TINYINT(1)`;
- `CURRENT_TIMESTAMP`, `CURRENT_TIMESTAMP()`, and MySQL-reflected `now()`;
- numeric defaults such as `0`, `0.0000`, and quoted equivalents;
- identifier quoting and constraint-name-only differences;
- MySQL implicit foreign-key indexes;
- MySQL's `_ascii` versus `_utf8mb4` introducer on the same ASCII-only REGEXP literal;
- column ordinal differences when names, types, nullability, defaults, and constraints match.

Normalization did not suppress ownership columns, referenced columns, referential actions,
required constraints, material defaults, collations, or explicit application indexes.

### 6.2 Confirmed SQLAlchemy vs clean-Alembic differences (Type A)

| ID | Object | Metadata | Clean Alembic result | Severity | Remediation |
|---|---|---|---|---|---|
| A-01 | table collation: `billing_fiscal_results` | `utf8mb4_unicode_ci` through canonical Base | `utf8mb4_0900_ai_ci` | MEDIUM | Forward migration to canonical collation; add table options to the historical pattern only through a new forward correction, never rewrite history |
| A-02 | table collation: `billing_fiscal_artifacts` | `utf8mb4_unicode_ci` | `utf8mb4_0900_ai_ci` | MEDIUM | Same as A-01 |
| A-03 | table collation: `membership_location_roles` | `utf8mb4_unicode_ci` | `utf8mb4_0900_ai_ci` | MEDIUM | Same as A-01 |
| A-04 | table collation: `staff_auth_sessions` | `utf8mb4_unicode_ci` | `utf8mb4_0900_ai_ci` | MEDIUM | Same as A-01 |
| A-05 | `ix_goods_receipts_purchase_order` | absent from ORM | `(tenant_id,purchase_order_id,status,id)` | LOW | Declare the existing migration-owned index in the ORM model |
| A-06 | `ix_goods_receipt_lines_purchase_order_line` | absent from ORM | `(tenant_id,purchase_order_line_id,goods_receipt_id)` | LOW | Declare the existing migration-owned index in the ORM model |
| A-07 | `ix_preparation_dispatches_connector_eligibility` | absent from ORM | `(tenant_id,connector_id_snapshot,state,available_at,id)` | LOW | Declare the existing migration-owned index in the ORM model |
| A-08 | `pos_order_submission_attempts.result` server default | none | `'IN_PROGRESS'` | MEDIUM | Add the existing server default to ORM metadata, or obtain authority to remove it in a forward migration |
| A-09 | `staff_auth_sessions.status` server default | none | `'ACTIVE'` | MEDIUM | Add the existing server default to ORM metadata, or obtain authority to remove it in a forward migration |

The clean schema otherwise matches ORM table/column membership, normalized types, nullability,
primary keys, foreign keys including actions, unique constraints, named CHECK constraints, and all
ORM-declared indexes. Alembic autogenerate emitted 97 raw differences: 94 default comparisons and
three migration-only indexes. Ninety-two default comparisons normalize to equivalent MySQL
representations; A-08 and A-09 remain semantic differences.

### 6.3 Confirmed clean-Alembic vs current-MySQL differences (Type B)

| ID | Object | Clean Alembic | Current MySQL | Severity / impact | Data remediation |
|---|---|---|---|---|---|
| B-01 | `fk_membership_location_grants_membership_tenant` | `(membership_id,tenant_id) → tenant_memberships(id,tenant_id) ON DELETE CASCADE` | missing | CRITICAL — grants can pair a membership from one tenant with another tenant/location | Not currently; orphan count 0 |
| B-02 | `fk_membership_location_roles_grant` | `(membership_id,location_id,tenant_id) → membership_location_grants(membership_id,location_id,tenant_id) ON DELETE CASCADE` | only `(membership_id,location_id) → ...` | CRITICAL — the known `0064` tenant column is omitted | Not currently; three-column orphan count 0 |
| B-03 | `fk_purchase_orders_availability_scope` | `(supplier_id,tenant_id,organization_id,location_id) → supplier_locations(...) ON DELETE RESTRICT` | missing | HIGH — supplier/location availability is not enforced | **YES**: all 35 current purchase orders lack a matching `supplier_locations` row |
| B-04 | `fk_goods_receipts_purchase_order` | absent | extra narrow `purchase_order_id → purchase_orders.id ON DELETE RESTRICT` | LOW — redundant with the expected six-column scope FK | No rows currently |
| B-05 | `fk_goods_receipt_lines_purchase_order_line` | absent | extra narrow `purchase_order_line_id → purchase_order_lines.id ON DELETE RESTRICT` | LOW — redundant with the expected eight-column scope FK | No rows currently |

Migration `0048_purchase_order_operations` explains B-03: on an existing database it counts
availability orphans and creates the FK only when that count is zero. It permits the revision to be
stamped successfully when the FK is skipped. This is a confirmed existing-data migration-path gap,
not a clean-install failure.

Raw source/clean comparison also found:

- a different physical order for eight `purchase_orders` columns; normalized as non-semantic;
- an ASCII versus UTF-8 literal introducer in `ck_purchase_order_lines_currency`; the pattern is
  ASCII-only and normalized as equivalent;
- supporting-index names/additions caused by the missing or differently shaped FKs; normalized as
  MySQL implicit-index consequences, not independent defects.

### 6.4 SQLAlchemy vs current MySQL (Type C)

Type C is the union of A-01 through A-09 and B-01 through B-05: 14 confirmed material
object-level differences. No table or application column is missing or unexpected.

### 6.5 MySQL-specific/physical-only objects (Type D)

| Object | Source | Clean | Classification |
|---|---:|---:|---|
| Views | 0 | 0 | none |
| Triggers | 0 | 0 | none |
| Procedures | 0 | 0 | none |
| Functions | 0 | 0 | none |
| Events | 0 | 0 | none |
| `alembic_version` | 1 | 1 | expected migration infrastructure |
| Implicit/supporting indexes | present | present | expected MySQL physical implementation when semantically compatible |

## 7. Tenant-isolation certification

The expected `0064` contract is:

```text
FOREIGN KEY (membership_id, location_id, tenant_id)
REFERENCES membership_location_grants (membership_id, location_id, tenant_id)
ON DELETE CASCADE
```

Evidence by layer:

| Layer | Observed contract |
|---|---|
| SQLAlchemy model | expected three-column FK |
| Migration `0064` | expected three-column FK |
| Clean Alembic MySQL | expected three-column FK |
| Current MySQL | incorrect two-column `(membership_id,location_id)` FK |

Rollback-only clean-database probes:

| Scenario | Result | Evidence |
|---|---|---|
| Same-tenant grant and location-role assignment accepted | PASS | both inserts succeeded |
| Duplicate grant rejected | PASS | MySQL 1062 |
| Cross-tenant membership/location grant rejected | PASS | MySQL 1452 |
| Cross-tenant role assignment rejected by grant scope | PASS | MySQL 1452 |
| Orphan location-role assignment rejected | PASS | MySQL 1452 |
| Probe cleanup | PASS | outer transaction rollback; zero residual audit tenants |

Conclusion: `0064`, the ORM, and a clean rebuild agree. The known defect is current-database drift,
not a clean migration-chain defect and not a test-assumption defect. The current drift remains a
CRITICAL tenant-isolation defect even though current rows happen to satisfy the missing constraints.

## 8. Bootstrap and application readiness

Against the clean database:

- application construction: PASS;
- database connectivity/readiness primitive: PASS;
- capability permissions seeded by migrations: 74;
- tenants and roles after migrations: 0 and 0;
- bootstrap required: YES;
- core permissions added/ensured by bootstrap rather than migrations:
  `tenant.read`, `tenant.manage`, `user.read`, `user.manage`,
  `staff_credentials.manage`, `role.read`, `role.manage`,
  `operational_request.read`, and `operational_request.manage`.

This is an operational bootstrap dependency, not a schema-rebuild failure. The audit did not run
bootstrap provisioning or the full application E2E lifecycle.

## 9. Rebuild readiness and exact remediation

**Classification: READY_WITH_REMEDIATION.**

A new MySQL 8.4 database can be reproducibly constructed to Alembic head, the API can connect, and
clean-database tenant integrity passes. It is not fully schema-consistent with canonical metadata,
and an existing database cannot be assumed equivalent merely because it reports HEAD.

Required corrections, in order:

1. Obtain approval for a new forward-only remediation migration; do not rewrite revisions
   `0001`–`0067`.
2. Before the migration, classify and repair the 35 `purchase_orders` records that lack an
   authoritative `supplier_locations` relationship. The correct supplier/location business
   mapping is a domain/operator decision; this audit does not invent or insert it.
3. In the forward migration, add B-01, replace B-02 with the three-column FK, add B-03 only after
   orphan revalidation, and remove B-04/B-05 if the canonical composite constraints remain the
   approved design.
4. Reconcile the four table collations to `utf8mb4_unicode_ci` through the forward migration,
   with preflight checks for existing indexed text and an operational backup according to the
   controlled-migration runbook.
5. Align ORM metadata with the three existing explicit indexes and the two existing server
   defaults, unless an approved design decision instead removes those physical contracts.
6. Add a migration-path test proving that `0048`-style existing-data upgrades cannot reach HEAD
   while a required availability FK is silently absent. Preserve existing migration history.
7. Rebuild an empty database again, upgrade a representative existing database copy, rerun the
   structural comparison and tenant probes, then re-certify.
8. For a new development environment, run the existing bootstrap-admin workflow with operator
   inputs after migrations; it owns initial tenant/admin-role/core-permission provisioning.

Logical data remediation is required only for B-03 based on current evidence. Collation correction
may physically rebuild tables but does not require inventing business values.

## 10. Source preservation and cleanup evidence

| Protected item | Result | Evidence |
|---|---|---|
| Original container | UNCHANGED | same ID; remained running |
| Original volume | UNCHANGED | same `pryecip_mysql-data` identity/mount |
| Original schema | UNCHANGED | before/after deterministic inventory SHA-256 `849ecd58277fb5bb87e464be4a189b8042416d020bbd3f036bfd6ff2d45eb68a` |
| Original Alembic revision | UNCHANGED | `0067_internal_operational_message_foundation (head)` before and after |
| Relevant source counts | UNCHANGED | grants 20; location roles 20; purchase orders 35; goods receipts 0; goods receipt lines 0 |
| Historical volumes | UNTOUCHED | no audit command targeted them; protected named volumes remain present |
| Temporary container | REMOVED | exact name absent after cleanup |
| Temporary volume | REMOVED | exact name absent after cleanup |
| Temporary network | REMOVED | exact name absent after cleanup |

No source migration, stamp, DDL, DML, restore, truncation, database recreation, volume removal, or
container restart was performed.

## 11. Verification commands

Secrets are intentionally represented by protected environment variables/placeholders. These are
the command forms used to reproduce the evidence; they must target a newly named isolated resource
set, never `pryecip_mysql-data`.

```bash
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all
git diff --check
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api alembic heads

PYTHONPATH=apps/api python3 /tmp/schema_audit_inventory.py metadata \
  --out /tmp/schema_audit_metadata.json

docker network create pryecip-schema-audit-net-20261009
docker volume create pryecip-schema-audit-data-20261009
AUDIT_API_IMAGE=sha256:931084dd44924b52ea98b0f0f1ecf65763b9b45c1e456ab19bbc2ff5f66844d0
docker run -d --name pryecip-schema-audit-mysql-20261009 \
  --network pryecip-schema-audit-net-20261009 \
  --mount source=pryecip-schema-audit-data-20261009,target=/var/lib/mysql \
  -e MYSQL_DATABASE=ecip_audit -e MYSQL_USER=audit_user \
  -e MYSQL_PASSWORD="$AUDIT_MYSQL_PASSWORD" \
  -e MYSQL_ROOT_PASSWORD="$AUDIT_MYSQL_ROOT_PASSWORD" mysql:8.4

# Verify: only audit network/volume and no published port, then run with current source read-only.
docker inspect pryecip-schema-audit-mysql-20261009
docker run --rm --read-only --tmpfs /tmp \
  --network pryecip-schema-audit-net-20261009 \
  -e MYSQL_HOST=pryecip-schema-audit-mysql-20261009 \
  -e MYSQL_PORT=3306 -e MYSQL_DATABASE=ecip_audit -e MYSQL_USER=audit_user \
  -e MYSQL_PASSWORD="$AUDIT_MYSQL_PASSWORD" \
  -e AUTH_JWT_SECRET="$AUDIT_JWT_SECRET" \
  -e RESTAURANT_ACCESS_CODE_SECRET="$AUDIT_ACCESS_SECRET" \
  -v /home/rogelio/proyectos/pryecip/apps/api:/app:ro \
  --entrypoint alembic "$AUDIT_API_IMAGE" upgrade head

# Inventory, Alembic autogenerate comparison, and rollback-only integrity probes.
python3 /tmp/schema_audit_migrations.py
docker run --rm --user 0 --read-only --tmpfs /tmp \
  --network pryecip-schema-audit-net-20261009 \
  -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \
  -e MYSQL_HOST=pryecip-schema-audit-mysql-20261009 \
  -e MYSQL_PORT=3306 -e MYSQL_DATABASE=ecip_audit -e MYSQL_USER=audit_user \
  -e MYSQL_PASSWORD="$AUDIT_MYSQL_PASSWORD" \
  -e AUTH_JWT_SECRET="$AUDIT_JWT_SECRET" \
  -e RESTAURANT_ACCESS_CODE_SECRET="$AUDIT_ACCESS_SECRET" \
  -v /home/rogelio/proyectos/pryecip/apps/api:/app:ro \
  -v /tmp/schema_audit_inventory.py:/audit.py:ro \
  -v /tmp/pryecip-schema-audit-evidence:/evidence \
  --entrypoint python "$AUDIT_API_IMAGE" \
  /audit.py db --out /evidence/clean.json
docker run --rm --user 0 --read-only --tmpfs /tmp \
  --network pryecip-schema-audit-net-20261009 \
  -e PYTHONPATH=/app -e MYSQL_HOST=pryecip-schema-audit-mysql-20261009 \
  -e MYSQL_PORT=3306 -e MYSQL_DATABASE=ecip_audit -e MYSQL_USER=audit_user \
  -e MYSQL_PASSWORD="$AUDIT_MYSQL_PASSWORD" \
  -e AUDIT_OUT=/evidence/compare-clean.json \
  -v /home/rogelio/proyectos/pryecip/apps/api:/app:ro \
  -v /tmp/schema_audit_alembic_compare.py:/compare.py:ro \
  -v /tmp/pryecip-schema-audit-evidence:/evidence \
  --entrypoint python "$AUDIT_API_IMAGE" /compare.py
docker run --rm --user 0 --read-only --tmpfs /tmp \
  --network pryecip-schema-audit-net-20261009 \
  -e PYTHONPATH=/app -e MYSQL_HOST=pryecip-schema-audit-mysql-20261009 \
  -e MYSQL_PORT=3306 -e MYSQL_DATABASE=ecip_audit -e MYSQL_USER=audit_user \
  -e MYSQL_PASSWORD="$AUDIT_MYSQL_PASSWORD" \
  -e AUDIT_OUT=/evidence/tenant-probes.json \
  -v /home/rogelio/proyectos/pryecip/apps/api:/app:ro \
  -v /tmp/schema_audit_tenant_probe.py:/probe.py:ro \
  -v /tmp/pryecip-schema-audit-evidence:/evidence \
  --entrypoint python "$AUDIT_API_IMAGE" /probe.py

# Exact owned cleanup only.
docker stop pryecip-schema-audit-mysql-20261009
docker rm pryecip-schema-audit-mysql-20261009
docker volume rm pryecip-schema-audit-data-20261009
docker network rm pryecip-schema-audit-net-20261009
```

The focused migration tests in `test_database_portability.py` were inspected but not executed,
because the relevant cases intentionally perform migration downgrades and this audit expressly
prohibited all downgrades. Direct clean-build and rollback-only integrity evidence replaced those
mutating test paths.

## 12. Final certification statement

```text
SQLALCHEMY ↔ ALEMBIC ↔ MYSQL
SCHEMA CONSISTENCY AUDIT: FAIL

CLEAN DATABASE REBUILD CERTIFICATION: PASS
FIRST FAILING REVISION: NONE
SINGLE HEAD: PASS

REBUILD READINESS: READY_WITH_REMEDIATION
MATERIAL DIFFERENCES: 14
```

No product code, model, migration, test, approved SDD, source database, or production source was
modified. No commit or push was performed.

---

## 13. Remediation record — 2026-10-09

This section preserves the original audit above and records the separately authorized remediation
of its nine SQLAlchemy-versus-clean-Alembic differences. The governing contract remains Global
SDD 0.2.0 Sections 10, 11, and 33: canonical relational options must be explicit, ORM and Alembic
must remain coherent, and migration history must not be rewritten.

### 13.1 Classification and disposition

| ID | Object | Primary classification | Severity | Existing authority approves target correction? | Disposition |
|---|---|---|---|---|---|
| D-01 | `billing_fiscal_results` table collation | `ALEMBIC_MIGRATION_DEFECT` | MEDIUM | YES | BLOCKED — requires a new forward migration; no historical revision changed |
| D-02 | `billing_fiscal_artifacts` table collation | `ALEMBIC_MIGRATION_DEFECT` | MEDIUM | YES | BLOCKED — requires a new forward migration; no historical revision changed |
| D-03 | `membership_location_roles` table collation | `ALEMBIC_MIGRATION_DEFECT` | MEDIUM | YES | BLOCKED — requires a new forward migration; no historical revision changed |
| D-04 | `staff_auth_sessions` table collation | `ALEMBIC_MIGRATION_DEFECT` | MEDIUM | YES | BLOCKED — requires a new forward migration; no historical revision changed |
| D-05 | `ix_goods_receipts_purchase_order` absent from ORM | `SQLALCHEMY_MODEL_DEFECT` | LOW | YES | REMEDIATED — declared with migration-owned name and column order |
| D-06 | `ix_goods_receipt_lines_purchase_order_line` absent from ORM | `SQLALCHEMY_MODEL_DEFECT` | LOW | YES | REMEDIATED — declared with migration-owned name and column order |
| D-07 | `ix_preparation_dispatches_connector_eligibility` absent from ORM | `SQLALCHEMY_MODEL_DEFECT` | LOW | YES | REMEDIATED — declared with migration-owned name and column order |
| D-08 | `pos_order_submission_attempts.result` server default absent from ORM | `SQLALCHEMY_MODEL_DEFECT` | MEDIUM | YES | REMEDIATED — ORM now declares `'IN_PROGRESS'` |
| D-09 | `staff_auth_sessions.status` server default absent from ORM | `SQLALCHEMY_MODEL_DEFECT` | MEDIUM | YES | REMEDIATED — ORM now declares `'ACTIVE'` |

D-01 through D-04 have an authorized target contract but not authorization in this task to create
or run the required forward migration. The required operator decision is whether to authorize the
next forward migration to convert those four tables to `utf8mb4_unicode_ci`, including the normal
backup, preflight, and rollout controls. No SDD amendment is required by current evidence, and no
`0068` revision was created.

The required forward DDL is limited to each table's default character-set/collation contract; it
must not replace explicit per-column binary collations:

```sql
ALTER TABLE billing_fiscal_results DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE billing_fiscal_artifacts DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE membership_location_roles DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE staff_auth_sessions DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Existing databases require the same forward DDL. Fresh installations require it after the
historical chain, because history may not be rewritten. No logical data migration is required;
normal MySQL metadata-lock/preflight and controlled rollout checks still apply.

### 13.2 Implemented minimal changes

- Added the three existing migration-owned indexes to ORM table metadata.
- Added the two existing physical server defaults to ORM column metadata while retaining their
  client-side defaults.
- Added one focused metadata regression test covering exact index names, index column order, and
  both server defaults.
- Made no migration, schema, seed, bootstrap, API, authorization, or source-database change.

### 13.3 Isolated re-certification evidence

The current repository source was mounted read-only into a new, no-port MySQL 8.4.8 environment.
The first attempt was externally interrupted and its disposable non-transactional DDL state was
discarded in full. A new empty volume was then rebuilt by a detached Alembic runner, which exited
zero at `0067_internal_operational_message_foundation (head)`.

| Check | Result |
|---|---|
| Clean migration rebuild from zero | PASS — 151 application tables plus `alembic_version` |
| Single migration head/current | PASS — `0067_internal_operational_message_foundation` |
| D-05 through D-07 metadata/physical index equality | PASS |
| D-08 and D-09 metadata/physical default equality | PASS after semantic quote normalization |
| Alembic autogenerate raw notices | 92, all `modify_default` MySQL rendering equivalents already normalized by the original audit |
| Remaining semantic SQLAlchemy-versus-clean differences | 4 — D-01 through D-04 only |
| Tenant/location rollback probes | PASS — same-tenant acceptance, duplicate rejection, three invalid-scope/orphan rejections, zero residual rows |
| Application construction and database connection | PASS |
| Focused remediation regression test | PASS — 1 passed |
| Existing portable-table-options test | FAILED independently — stale hard-coded table inventory; not caused by this remediation and not changed |
| Previously documented permission-seed drift | UNCHANGED — remains a readiness remediation outside this task |

Rebuild readiness remains `READY_WITH_REMEDIATION`: the five model defects are closed, while the
four migration-owned collation defects and previously documented permission-seed drift remain.

### 13.4 Source preservation and cleanup

The protected source container retained ID
`e7e099b1e7a2ee1110b28d3e4292f6847c08767930f34e16a4d2399cdfae47d4`, remained running with
`pryecip_mysql-data:/var/lib/mysql`, and remained at revision
`0067_internal_operational_message_foundation (head)`. No source DDL, DML, migration, stamp,
bootstrap, restore, truncation, restart, or volume operation was performed. The exact temporary
runner, MySQL container, volume, and network were removed after evidence collection.

---

## 14. Migration 0068 implementation and isolated certification — 2026-10-09

The project operator explicitly authorized one forward-only migration limited to D-01 through
D-04. Migration `0068_schema_collation_alignment` now follows
`0067_internal_operational_message_foundation` and changes only the four approved table defaults:

```sql
ALTER TABLE `billing_fiscal_results` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE `billing_fiscal_artifacts` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE `membership_location_roles` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE `staff_auth_sessions` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The migration does not use `CONVERT TO CHARACTER SET`; existing column definitions, including
explicit `ascii_bin` and `utf8mb4_bin` collations, are not converted. It performs no logical data
transformation. Its downgrade is intentionally blocked because the prior inherited table default
is environment-specific and cannot be reconstructed safely.

### 14.1 Operational behavior

- Each MySQL `ALTER TABLE` can acquire a metadata lock and implicitly commits; transactional
  rollback is not claimed.
- Existing data, keys, constraints, indexes, and column collations are compatible and unchanged.
- If execution fails after some statements, inspect `information_schema.TABLES.TABLE_COLLATION`
  for all four targets, resolve the operational failure, and rerun `alembic upgrade head`. The
  statements are idempotent and Alembic advances the revision only after the complete upgrade
  function succeeds.
- Reversal requires a separately approved forward migration with an explicit target default; do
  not use `alembic downgrade` to guess an environment's former default.

### 14.2 Certification evidence

Certification used MySQL 8.4.8 with a dedicated container, volume, network, no published MySQL
port, and no source or historical-volume mount. Repository source was mounted read-only into the
migration and test runners.

| Check | Result |
|---|---|
| Repository migration heads | PASS — one: `0068_schema_collation_alignment` |
| Clean installation `0001` through `0068` | PASS |
| Clean application-table count | PASS — 151 |
| Clean table defaults | PASS — all four `utf8mb4_unicode_ci` |
| Focused upgrade `0067` through `0068` | PASS |
| Upgrade fixture defaults before | all four `latin1_swedish_ci`, inherited from the deliberately noncanonical test database |
| Upgrade fixture defaults after | all four `utf8mb4_unicode_ci` |
| Existing target-column definitions | PASS — unchanged byte-for-byte through information-schema projection |
| Non-target table metadata | PASS — unchanged |
| SQLAlchemy versus clean Alembic | PASS — zero material differences; 92 raw MySQL default-rendering equivalents remain normalized |
| Composite membership/location/Tenant FK | PASS — three columns, `ON DELETE CASCADE` |
| Same-Tenant relationship | PASS |
| Cross-Tenant relationship | PASS — rejected with MySQL 1452 |
| Orphan relationship | PASS — rejected with MySQL 1452 |
| Focused tests | PASS — 3 passed, 0 failed, 0 skipped |

The focused tests comprise two metadata portability tests and the isolated 0067-to-0068 upgrade
test. The stale model-table inventory used by the portability test was corrected from 128 to the
current 151 registered application tables without weakening its equality assertion.

### 14.3 Source preservation and cleanup

The protected `ecip` database was not migrated. After certification it still reported
`0067_internal_operational_message_foundation`; all four source table defaults remained
`utf8mb4_0900_ai_ci`. Source container ID
`e7e099b1e7a2ee1110b28d3e4292f6847c08767930f34e16a4d2399cdfae47d4` remained running with
`pryecip_mysql-data:/var/lib/mysql`. No source or historical volume was changed, recreated, or
removed. The temporary runners, MySQL container, volume, network, and evidence directory were
removed individually after collection.

Current result for the original nine SQLAlchemy-versus-clean-Alembic differences: **PASS — zero
material differences remain**.
