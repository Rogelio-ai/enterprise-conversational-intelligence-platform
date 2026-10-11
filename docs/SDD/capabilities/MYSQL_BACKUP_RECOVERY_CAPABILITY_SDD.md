# RESTAURANT INTELLIGENCE PLATFORM
# MYSQL BACKUP & RECOVERY CAPABILITY SOFTWARE DESIGN DOCUMENT

**Capability:** MySQL Backup & Recovery
**Document:** `MYSQL_BACKUP_RECOVERY_CAPABILITY_SDD.md`
**Template:** `CAPABILITY_SDD_TEMPLATE.md`
**Status:** CERTIFIED
**Version:** 0.1.1
**Last Updated:** 2026-10-10

---

# 1. PURPOSE

Define the authoritative technical design for the reusable MySQL Backup & Recovery capability.

The capability creates consistent, integrity-verifiable MySQL backups; manages operator-configured
retention; schedules daily execution; restores a selected backup into an isolated MySQL instance;
and records evidence sufficient to certify that the backup is recoverable without mutating the
source database.

This is infrastructure design. It does not define Restaurant domain behavior.

---

# 2. AUTHORITY

## 2.1 Governing Sources

```text
Product Authority: N/A — no product behavior is introduced
Domain Authority: N/A — no Restaurant domain rule is introduced
Global Architectural Authority:
  - AGENTS.md
  - docs/SDD/DOCUMENT_AUTHORITY_HIERARCHY.md
Global SDD: docs/SDD/GLOBAL_SDD.md (APPROVED, version 0.2.0)
Applicable ADRs: None found for this capability
Security Baseline: docs/SDD/GLOBAL_SDD.md Section 18
Reuse Policy: docs/SDD/GLOBAL_SDD.md Section 32
Other:
  - docs/workstreams/WS-33_B_PILOT_PLATFORM_AND_OPERATIONAL_SAFETY.md
  - docs/operations/DATABASE_BACKUP_RESTORE_RUNBOOK.md
  - docs/operations/LOCAL_PREPILOT.md
  - scripts/mysql-backup.sh
  - scripts/mysql-restore.sh
  - compose.pilot-local.yaml
```

WS-33-B is approved historical design and certification evidence for the existing pilot backup and
restore foundation. It remains authoritative for its certified boundary. This SDD preserves that
behavior, adds the target contracts required for reusable local automation, and does not rewrite
historical evidence.

The schedule and configurable retention defaults are capability authority under this approved
version. Material changes require review and reapproval under the governance model.

## 2.2 Authority of This SDD

This approved document is authoritative for the technical design of MySQL Backup & Recovery.
It inherits applicable approved higher authority. Prompts, conversations, implementation reports,
and tests do not independently redefine it.

This document is `CERTIFIED`: the approved design has been implemented and independently verified
for the local backup, retention, prepared-automation, and isolated-restore boundary recorded in
Section 33. Certification does not mean host automation is installed or active.

## 2.3 Approval Record

```text
Document path: docs/SDD/capabilities/MYSQL_BACKUP_RECOVERY_CAPABILITY_SDD.md
Document version: 0.1.1
Approving authority/role: Project operator acting as Architecture Authority under the approved governance model
Explicit decision: APPROVED
Decision date: 2026-10-08
Approval evidence/reference: Explicit operator authorization in “SDD FORMAL APPROVAL REGISTRATION — GLOBAL SDD + MYSQL BACKUP RECOVERY — FINAL”, received 2026-10-08
Open conditions: NONE
```

---

# 3. CAPABILITY BOUNDARY

## Owns

- Consistent logical backup orchestration for an explicitly selected MySQL database.
- Backup artifact naming, compression, integrity verification, checksum, metadata, and publication.
- Capability-owned operational evidence and failure reporting.
- Safe, configurable retention within explicitly authorized backup directories.
- Host-level daily scheduling definitions and activation evidence.
- Isolated restore-test orchestration and recovery certification evidence.
- Protection rules that prevent certification writes from reaching the source database.

## Does Not Own

- Restaurant domain data or its business meaning.
- MySQL application schema, Alembic migrations, or business tables.
- Production recovery authorization or automatic restoration into an authoritative database.
- API endpoints, frontend screens, or application authentication/authorization.
- Docker volume lifecycle outside uniquely created restore-test resources.
- External storage-provider selection, cloud credentials, or organization-wide legal retention.
- Database migration execution, except reading the current Alembic revision as evidence.

---

# 4. SCOPE, NON-GOALS AND DEFERRED

## 4.1 In Scope

- MySQL 8.4-compatible logical backups containing schema and data.
- `--single-transaction`, `--quick`, triggers, routines, and events.
- Gzip compression, SHA-256 checksums, metadata, safe permissions, and atomic publication.
- Overlap prevention and duplicate scheduled-run suppression.
- Daily systemd service/timer execution at 03:00 in `America/Mexico_City` with missed-run handling.
- Daily, weekly, monthly, and pre-change backup classes with operator-configurable retention.
- Retention dry-run and fail-closed path validation.
- Restore certification in a uniquely named, isolated MySQL 8.4 environment.
- Schema, Alembic, representative-data, cleanup, and source-preservation verification.
- Operator runbook updates and external encrypted-copy readiness.

## 4.2 Non-Goals / Out of Scope

- A new microservice, queue, API, frontend, table, or migration.
- Physical or snapshot backup, binary-log/PITR implementation, or replication.
- Automatic production restoration or production database replacement.
- Automatic schema migration during backup or restore certification.
- Cloud, S3-compatible, MinIO, or external-disk provider configuration.
- Changes to Restaurant, payment, fiscal, inventory, purchasing, or identity behavior.
- Deletion or reuse of protected source or historical Docker volumes.

## 4.3 Deferred

| ID | Requirement | Reason | Dependency | Blocking |
|---|---|---|---|---|
| DEF-001 | Encrypted off-host copy | Provider and credential ownership are operator decisions | Approved storage provider and credentials | NO |
| DEF-002 | Point-in-time recovery | Not required by this foundation and needs a separate RPO/design decision | Binary-log retention and infrastructure design | NO |
| DEF-003 | Automatic production restore | Destructive and requires incident-specific authority | Recovery authorization and runbook | NO |
| DEF-004 | Organization-wide legal retention | Legal/business policy is not available | Business/compliance authority | NO for configurable defaults |

---

# 5. EXISTING SYSTEM / DISCOVERY BASELINE

```text
Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Commit: ebb761d0b20f43780fe5a50f936f02b840e797d3
Migration head: 0067_internal_operational_message_foundation

Relevant backend: N/A
Relevant frontend: N/A
Relevant domain modules: N/A
Relevant tables: alembic_version plus restored business schema for verification only
Relevant endpoints: N/A
Relevant integrations: MySQL 8.4, Docker Compose, systemd, optional Pushgateway/upload command
Relevant tests: WS-33-B historical certification evidence; no focused current script test suite found
Relevant documentation:
  - docs/operations/DATABASE_BACKUP_RESTORE_RUNBOOK.md
  - docs/operations/LOCAL_PREPILOT.md
  - docs/workstreams/WS-33_B_PILOT_PLATFORM_AND_OPERATIONAL_SAFETY.md
```

Current runtime evidence on 2026-10-08:

```text
MySQL: 8.4.8
Database: ecip
Container: pryecip-mysql-1
Source volume: pryecip_mysql-data
Alembic current/head: 0067_internal_operational_message_foundation
Host systemd: 249 (249.11-0ubuntu3.22)
Requested calendar syntax: accepted by systemd-analyze
```

Existing components are classified as follows:

| Requirement | Status | Evidence / discrepancy |
|---|---|---|
| Transactional logical export | IMPLEMENTED | `mysql-backup.sh` uses `--single-transaction --quick` |
| Schema/data, triggers, routines, events | IMPLEMENTED | Existing `mysqldump` options |
| Compression and gzip test | IMPLEMENTED | Gzip output and `gzip -t` |
| SHA-256 | IMPLEMENTED | Sidecar created after artifact creation |
| Restrictive process umask | IMPLEMENTED | Both scripts use `umask 077` |
| Encrypted artifact option | IMPLEMENTED_NOT_CERTIFIED_CURRENTLY | OpenSSL option exists; no current execution evidence gathered for this SDD |
| Atomic complete backup publication | PARTIAL | Dump/compression uses partial files, but artifact becomes visible before checksum/metadata completion |
| Structured metadata | MISSING | Only Prometheus success/timestamp status exists |
| Overlap lock | MISSING | No backup lock exists |
| Safe retention | CONFLICTING | Broad `find ... -delete` has no dry-run, ownership/path guard, class policy, or last-known-good protection |
| systemd scheduling | MISSING | No backup service/timer found |
| Checksum required before restore | PARTIAL | Verification occurs only when a sidecar is readable |
| Restore import | IMPLEMENTED | `mysql-restore.sh` verifies gzip and streams into a configured target |
| Restore isolation enforcement | MISSING | Caller supplies host/database; script does not prove target isolation |
| Restore certification validation | MISSING | No built-in schema/data/Alembic/source-preservation evidence |
| Temporary restore cleanup | PARTIAL | Script cleans local work directory, not container/network/volume lifecycle |
| Historical isolated pilot restore | CERTIFIED | WS-33-B records successful encrypted restore and application checks |

`compose.pilot-local.yaml` provides reusable isolation patterns, but its named
`mysql-restore-data` volume and the destructive reset in `LOCAL_PREPILOT.md` are protected historical
resources for this task. New certification MUST use unique temporary resources and MUST NOT delete or
reuse those protected volumes.

---

# 6. REUSE ANALYSIS

| Component | Owner | Reuse | Required Change | Risk |
|---|---|---|---|---|
| `scripts/mysql-backup.sh` | Operations infrastructure | REUSE WITH EXTENSION | Safe config, locking, metadata, atomic publication, class-aware retention integration | Existing unsafe retention must not survive unchanged |
| `scripts/mysql-restore.sh` | Operations infrastructure | REUSE WITH EXTENSION | Require checksum and emit deterministic restore result | Must never be treated as isolation orchestration |
| Pilot restore Compose pattern | Pilot operations | REUSE WITH ADAPTER | Generate/use unique project, network, container, and volume | Reusing protected named volume is prohibited |
| Database backup/restore runbook | Operations | REUSE WITH EXTENSION | Add automated schedule, retention, certification, activation, and external encryption guidance | Documentation must not claim unverified activation |
| Existing secret/defaults-file pattern | Operations | REUSE AS-IS | Preserve non-echoing file-based credentials | File modes and ownership remain operator-controlled |
| Pushgateway status hook | Observability | REUSE WITH EXTENSION | Preserve compatibility; metadata/log evidence remains authoritative locally | Remote failure must be classified clearly |

```text
Candidate: reusable host-operated MySQL backup/recovery scripts
Domain-independent: YES
Likely reusable: YES
Recommended boundary: scripts/database plus operator-owned configuration/systemd templates
Extract now: NO
Reason: repository-local scripts are sufficient; no package or microservice is justified
```

The implementation MUST NOT duplicate database credentials, migration ownership, or Restaurant data
ownership.

---

# 7. ACTORS AND DOMAIN CONCEPTS

## 7.1 Actors

| Actor | Responsibility | Relevant Authorization |
|---|---|---|
| Platform operator | Configure paths, credentials, retention, install/activate timer, inspect evidence | Host and Docker access appropriate to the deployment |
| Backup scheduler | Invoke the approved backup command | Least privilege required to start the backup process |
| Backup identity | Read the selected MySQL database and required metadata | Existing `ecip_backup`-style privileges; no application mutation authority |
| Restore-certification operator | Select verified artifact and start isolated drill | Docker access and access to backup artifact; no source restore authorization |
| Recovery authority | Separately authorize a real restoration | Outside this capability's automatic behavior |

## 7.2 Domain Concepts

| Concept | Meaning | Authoritative Source | Technical Representation |
|---|---|---|---|
| Backup artifact | Compressed logical database export | This SDD after approval | `.sql.gz` or approved encrypted derivative |
| Backup set | Artifact, checksum, metadata, and completion evidence sharing one backup ID | This SDD after approval | Atomically published files/directories |
| Verified backup | Backup set whose dump completed and whose compression/checksum validations passed | This SDD after approval | Metadata state `BACKUP_VERIFIED` |
| Restore certification | Successful isolated import and required validation with source preservation | This SDD after approval | Certification evidence record |
| Known-good recovery point | Most recent verified backup with successful restore certification | This SDD after approval | Metadata/evidence linkage |

---

# 8. INVARIANTS

## MBR-INV-001 — Source protection

Rule: Backup and restore certification MUST NOT write to, recreate, replace, or remove the source
database, source container, source volume, or protected historical volumes.
Authority: This SDD; Global SDD failure/recovery and historical-integrity principles.
Enforcement: Explicit identity capture, isolated target creation, denylist checks, unique resource
names, and before/after evidence.
Failure behavior: Stop before restore; return nonzero.
Verification: Source container ID, volume, database, Alembic revision, and representative counts are
unchanged.

## MBR-INV-002 — No false success

Rule: Success MUST NOT be published until export, non-empty validation, compression integrity,
checksum, metadata, and atomic completion succeed. Restore certification MUST NOT pass unless the
isolated restore and all required validation complete.
Authority: Global SDD determinate-failure rule and this SDD.
Enforcement: Staged files, explicit state transitions, nonzero exits, and final atomic publication.
Failure behavior: Preserve the prior verified backup; retain or safely remove only owned partials.
Verification: Forced failures never produce `BACKUP_VERIFIED` or `RESTORE_CERTIFIED`.

## MBR-INV-003 — Secret and backup confidentiality

Rule: Credentials MUST NOT appear in source, arguments intended for logs, unit files, metadata, or
reports. Backup contents and directories are sensitive and access-restricted. External copies MUST
be encrypted.
Authority: Global SDD security rules, WS-33-B, and this SDD.
Enforcement: Protected defaults/credential files, `umask 077`, restrictive directory/file modes,
redacted logging, and encrypted external-copy boundary.
Failure behavior: Refuse execution when protected credential or destination requirements fail.
Verification: Permission and bounded secret-output tests.

## MBR-INV-004 — Single execution

Rule: Overlapping backups for the same managed root/database are prohibited.
Authority: This SDD after approval.
Enforcement: Non-blocking host lock owned by the backup command; systemd must not be the sole lock.
Failure behavior: Explicit nonzero conflict result without changing existing verified backups.
Verification: Concurrent invocation test.

## MBR-INV-005 — Retention containment

Rule: Retention may delete only verified, capability-owned backup sets under a validated managed
class directory and MUST preserve the only known-good recovery point.
Authority: WS-33-B operator control and this SDD after approval.
Enforcement: Canonical-path checks, naming/metadata ownership checks, dry-run, class policy, and
last-known-good guard.
Failure behavior: Fail closed with no deletion.
Verification: Unsafe path, unmanaged file, only-known-good, and dry-run tests.

## MBR-INV-006 — Operator authority

Rule: Retention durations, backup root, activation, and external destination remain operator
controlled. Defaults are configurable and are not immutable business limits.
Authority: WS-33-B and this SDD after approval.
Enforcement: Configuration contract and operator-controlled systemd installation.
Failure behavior: Missing or unsafe required configuration prevents execution or activation.
Verification: Configuration override and absent-configuration tests.

---

# 9. LIFECYCLE AND KEY FLOWS

## 9.1 State Model

```text
BACKUP_STARTED
      ↓
BACKUP_CREATED
      ↓
BACKUP_VERIFIED
      ↓
RESTORE_CERTIFIED

AUTOMATION_PREPARED
      ↓
AUTOMATION_ACTIVE
```

`AUTOMATION_ACTIVE` is an independent deployment state. It requires an installed, enabled, active
timer and one verified execution under the installed configuration. Capability certification does
not imply activation on any host.

| From | Action | To | Preconditions | Actor |
|---|---|---|---|---|
| None | Start backup | BACKUP_STARTED | Safe configuration, lock acquired, MySQL identity verified | Operator/scheduler |
| BACKUP_STARTED | Complete export | BACKUP_CREATED | Non-empty compressed artifact staged | Backup command |
| BACKUP_CREATED | Verify and publish | BACKUP_VERIFIED | Gzip, SHA-256, metadata, permissions complete | Backup command |
| BACKUP_VERIFIED | Isolated restore and validate | RESTORE_CERTIFIED | Unique isolated target and source baseline captured | Restore-certification operator |
| None | Install validated units/config | AUTOMATION_PREPARED | Operator authorization | Platform operator |
| AUTOMATION_PREPARED | Enable/start and verify run | AUTOMATION_ACTIVE | Timer installed/enabled/active and backup verified | Platform operator |

Forbidden transitions include publishing verification before checksum/metadata completion, marking a
failed/incomplete restore certified, and reporting automation active from repository files alone.

## 9.2 Key Use Cases

### UC-001 — Create and verify backup

Actor: Platform operator or scheduler.
Preconditions: Authorized root, protected credentials, reachable expected MySQL, no incompatible
migration, lock available.
Trigger: Manual command or timer.
Main flow: Validate configuration; verify identity/version; export; compress; test gzip; calculate
SHA-256; write metadata; verify modes; atomically publish complete backup set; record result.
Postconditions: One `BACKUP_VERIFIED` set or no new published set.
Failure cases: Dependency unavailable, identity mismatch, lock conflict, dump/gzip/checksum/metadata
failure, unsafe path, permissions failure.

### UC-002 — Apply retention

Actor: Platform operator or successful scheduled backup flow.
Preconditions: Managed root validated and at least one verified recovery point known.
Trigger: Dry-run command or post-backup retention phase.
Main flow: Enumerate only owned verified sets; classify by daily/weekly/monthly/pre-change; report or
delete eligible sets while preserving the known-good guard.
Postconditions: Policy-compliant retained sets; no unmanaged files affected.
Failure cases: Unsafe path, ambiguous metadata, incomplete set, cleanup error.

### UC-003 — Certify isolated restore

Actor: Restore-certification operator.
Preconditions: Explicit verified backup set and captured source baseline.
Trigger: Certification command.
Main flow: Verify checksum/gzip; create unique Compose project/network/volume/MySQL 8.4 target;
restore; verify database/schema/counts/objects/Alembic/representative non-sensitive data; compare
source baseline; record evidence; clean owned temporary resources.
Postconditions: `RESTORE_CERTIFIED`, or explicit failure with source unchanged.
Failure cases: Missing/corrupt artifact, checksum mismatch, startup/import/validation failure, source
identity collision, cleanup failure.

### UC-004 — Activate daily automation

Actor: Platform operator.
Preconditions: Approved implementation, safe configuration, validated unit/timer, sufficient host
permissions.
Trigger: Explicit operator installation/enablement.
Main flow: Install operator-owned config and units; enable/start timer; verify status, timezone,
`Persistent=true`, exact next execution, and one backup execution.
Postconditions: `AUTOMATION_ACTIVE` only when all activation evidence passes.
Failure cases: Unsupported calendar, privilege denial, inactive timer, failed backup.

---

# 10. OWNERSHIP

| Entity / State | Owner | Scope | Cross-Owner Access |
|---|---|---|---|
| Source business database | Existing database/application owners | Existing tenant/organization/location scopes | Read-only logical export by backup identity |
| Backup set | MySQL Backup & Recovery capability | Selected database and managed backup root | Operator-controlled access only |
| Retention configuration | Platform operator | Host/deployment | Read by capability; never overridden silently |
| systemd activation state | Platform operator/systemd | Host | Inspected for evidence only |
| Restore-test resources | MySQL Backup & Recovery capability | Unique certification run | No source runtime reuse |
| Certification evidence | MySQL Backup & Recovery capability/operator | Backup ID and certification run | Operational review only |

Backup metadata MUST retain the source database identity without becoming an alternative owner of
Restaurant data.

---

# 11. DATA MODEL AND INTEGRITY

## 11.1 Persistence

No application table or Alembic migration is required. Capability state is filesystem-based
operational evidence outside the repository and MySQL volume.

A completed backup set contains at minimum:

```text
artifact
artifact checksum sidecar
metadata record
completion/result evidence
```

Metadata fields:

- backup identifier;
- UTC start/completion timestamps;
- database name;
- MySQL version;
- source Compose project/service/container identity when available;
- artifact filename and class;
- compressed size;
- SHA-256;
- execution result and duration;
- Git HEAD when available;
- Alembic current revision when safely obtainable;
- encryption indicator, without key or secret details.

Metadata MUST NOT contain passwords, password hashes, tokens, JWTs, complete environment dumps, or
customer/personal row values.

## 11.2 Relationships

```text
BACKUP ID
 ├── artifact
 ├── checksum
 ├── metadata
 └── zero or more restore-certification evidence records
```

## 11.3 Integrity

- The checksum sidecar and metadata SHA-256 MUST agree with the published artifact.
- A backup set is incomplete unless all required files exist and metadata reports success.
- Retention MUST treat an incomplete or ambiguous set as non-deletable by default.
- Certification evidence MUST identify the exact backup SHA-256.
- Publication MUST use same-filesystem staging and atomic rename, or an equivalently atomic managed
  directory promotion.

## 11.4 Migration

```text
Current migration head: 0067_internal_operational_message_foundation
Migration required: NO
Affected tables: NONE
Data migration required: NO
Destructive change: NO
Backward compatibility: Existing backup/restore invocation remains supported where safe
Production considerations: No source database/container rebuild or schema change
```

## 11.5 Managed Storage and Retention Contract

The operator-configurable local backup-root default is:

```text
/home/rogelio/backups/pryecip/
```

That path is a deployment default, not a value to hardcode into reusable scripts. The configured
root MUST resolve outside the repository, MySQL data volume, and application images. Its managed
layout is:

```text
daily/
weekly/
monthly/
pre-change/
restore-tests/
logs/
```

The approved configurable retention defaults are:

| Class | Default | Operator authority |
|---|---:|---|
| Daily | 14 days | May override through approved configuration |
| Weekly | 8 weeks | May override through approved configuration |
| Monthly | 12 months | May override through approved configuration |
| Pre-change | No automatic expiry | Removal requires explicit operator authorization |

Weekly and monthly sets MAY be promoted from already verified daily sets rather than exported again.
Promotion MUST preserve the exact artifact SHA-256 and metadata lineage and MUST NOT reduce recovery
integrity. Retention is not applied destructively until backup and isolated-restore certification
have passed for the implementation baseline.

---

# 12. APPLICATION / SERVICE DESIGN

| Component | Responsibility | Inputs / Outputs | Dependencies |
|---|---|---|---|
| Backup command | Validate, lock, export, verify, and publish backup set | Operator config / verified set and logs | MySQL client, gzip, sha256sum, filesystem |
| Retention command/module | Dry-run and bounded deletion by class policy | Managed root/policy / plan and result | Backup metadata and filesystem |
| Restore-certification command | Create isolated target, restore, validate, prove preservation, clean | Verified set / certification evidence | Docker Compose, MySQL 8.4 |
| systemd service template | Run one configured backup without embedding secrets | Protected environment/config / process result | Docker/MySQL availability |
| systemd timer template | Invoke daily at approved local time and catch missed run | Calendar / service activation | systemd |
| Operator runbook | Manual operation, verification, activation, logs, recovery boundaries | Documentation | All components above |

Transaction ownership: No application transaction is introduced. `mysqldump --single-transaction`
owns the consistent logical read for transactional tables.
Side effects: Filesystem artifacts/evidence, optional approved upload/metrics, and uniquely owned
temporary Docker resources.
Failure behavior: Nonzero exit, explicit evidence, no false publication, no source mutation.

The timer contract is:

```ini
OnCalendar=*-*-* 03:00:00 America/Mexico_City
Persistent=true
```

The service MUST perform a bounded wait for Docker and the expected MySQL identity to become
available. Host systemd 249 accepts and correctly normalizes the timezone-qualified calendar. An
implementation on another host MUST validate the syntax before installation and use an equivalent
supported configuration only when it preserves 03:00 in `America/Mexico_City` and the persistent
missed-run behavior.

---

# 13. TRANSACTIONS, CONCURRENCY AND IDEMPOTENCY

## 13.1 Transaction Boundaries

Operation: Backup publication.
Reads/locks: Consistent MySQL read plus host execution lock.
Writes: Staged artifact/checksum/metadata and final managed backup set.
Commit point: Atomic promotion of the complete verified set.
Rollback behavior: Remove only owned partial files; preserve existing verified sets.
External side effects: Upload/metrics occur after local verification and are recorded separately;
their failure MUST NOT falsify local verification state.

Operation: Retention.
Reads/locks: Managed set metadata under the same capability lock or a compatible retention lock.
Writes: Removal of explicitly eligible owned sets only.
Commit point: Per-set deletion after plan validation.
Rollback behavior: Deleted files are not assumed recoverable; therefore guards run before deletion
and dry-run is required for certification.
External side effects: None.

## 13.2 Concurrency

Operation: Backup and retention.
Risk: Overlap, duplicate publication, or retention deleting an in-progress/new recovery point.
Locking strategy: Non-blocking advisory file lock in a validated operator-owned runtime/backup
location, scoped to managed root and database.
Lock order: Backup/retention lock before staging or enumeration; release after evidence completion.
Revalidation: Recheck destination identity and existing verified set after lock acquisition.
Conflict behavior: Explicit nonzero conflict; no wait that creates an unnecessary duplicate run.

Backup and incompatible schema migration MUST be mutually exclusive. The approved implementation
must either extend the existing controlled-migration entry point to acquire a shared database
operations lock or use an equivalent existing deployment lock proven to cover both operations.
An operator convention alone is insufficient. Failure to acquire the shared lock blocks the later
operation before it accesses or mutates the database.

Restore certification uses a unique run ID and resource names. It MUST reject any resolved container,
volume, network, or target matching protected source/historical identifiers.

## 13.3 Idempotency

Operation: Scheduled daily backup.
Required: YES.
Idempotency mechanism: Before export, detect an existing successful scheduled backup for the same
database and local calendar day under the active schedule/configuration.
Persisted evidence: Backup metadata and backup ID.
Replay behavior: Report an explicit successful no-op or already-satisfied result.
Duplicate side-effect prevention: Lock plus daily completion lookup.

Manual/pre-change backup requests are distinct executions and require unique backup IDs.

---

# 14. API AND DTO CONTRACTS

## 14.1 API

N/A — this capability exposes operator commands and filesystem evidence, not application HTTP APIs.

## 14.2 DTOs / Schemas

The metadata and certification evidence formats are executable operational contracts. Their
implementation SHOULD use a documented, versioned, machine-readable format. Required fields are
defined in Sections 11 and 28. Unknown additive fields MUST be tolerated by readers. Secret fields
are prohibited.

---

# 15. AUTHENTICATION AND AUTHORIZATION

## 15.1 Authentication

N/A — no application authentication is introduced. MySQL authentication uses existing protected
credential/defaults-file mechanisms.

## 15.2 Authorization

| Operation | Required Capability | Scope | Additional Rule |
|---|---|---|---|
| Backup | Host execution plus backup DB identity | Selected database | Read/metadata privileges only |
| Retention | Write/delete in validated managed root | Capability-owned backup sets | Dry-run and safety guards |
| Restore certification | Docker plus artifact read access | Unique isolated resources | No production/source restore grant |
| Install/activate timer | Operator-approved host permission | Specific host/user service | No privilege bypass |
| Production restore | Separate recovery authorization | Explicit incident target | Not granted by this capability |

---

# 16. AUDIT

| Operation | Actor | Evidence | Before/After Required |
|---|---|---|---|
| Backup attempt | Operator/scheduler | Backup ID, timestamps, result, duration, sanitized error | Source identity before; result after |
| Retention | Operator/scheduler | Policy, dry-run/apply mode, candidate IDs, retained/deleted IDs, result | Known-good set before/after |
| Restore certification | Operator | Artifact SHA-256, isolated resource IDs, validation results, cleanup | Source preservation before/after |
| Automation activation | Operator | Unit/timer validation, enabled/active state, next run, verified execution | Prepared/active state |

Evidence MUST be append-safe or uniquely named per run and MUST NOT expose backup contents or
credentials.

---

# 17. INTEGRATIONS AND CROSS-CAPABILITY DEPENDENCIES

## 17.1 External Integrations

System: MySQL 8.4.
Purpose: Source export and isolated restore target.
Credential ownership: Operator/runtime secret mechanism.
Timeout/retry: Availability waiting is bounded; automatic dump/restore retries are not permitted when
they could create ambiguous duplicate work.
Failure behavior: Nonzero and explicit evidence.
Idempotency: Section 13.3.
Persisted evidence: Sanitized metadata/certification record.

System: systemd.
Purpose: Daily host scheduling.
Credential ownership: Unit contains paths/references only, never secret values.
Failure behavior: Remain `AUTOMATION_PREPARED` or blocked; never claim active.

System: Future external storage.
Purpose: Encrypted off-host copy.
Port/adapter: Existing provider-neutral upload boundary may be retained.
Credential ownership: Operator.
Failure behavior: Report local verification and external-copy result separately.
Idempotency: Provider adapter must prevent ambiguous duplicate objects or use immutable backup IDs.

## 17.2 Internal Capability Dependencies

| Capability | Dependency | Direction | Contract | Failure Impact |
|---|---|---|---|---|
| Database migration | Read current revision; avoid incompatible concurrent migrations | Read-only | Alembic current/head | Missing safe revision is recorded; backup may proceed only per approved policy |
| Observability | Optional metrics publication | Outbound | Existing Pushgateway convention | Local result remains authoritative; publication failure reported |
| Restaurant capabilities | Representative non-sensitive validation only | Read-only during source baseline/restored checks | Existing schema/data | No domain mutation permitted |

## 17.3 Events / Async Processing

N/A — systemd invokes a synchronous command. No queue or new asynchronous infrastructure is required.

---

# 18. FRONTEND AND UX

N/A — no application frontend exists for this capability. Operator command output and runbook steps
MUST clearly distinguish success, failure, prepared, and active states.

---

# 19. INTERNATIONALIZATION AND GENERATED OUTPUTS

N/A — machine/operator evidence uses stable technical identifiers and UTC timestamps. The schedule
uses the named timezone `America/Mexico_City`; it MUST NOT depend on an ambiguous host-local timezone.

---

# 20. SECURITY AND PRIVACY

Security concerns:

- Logical backups may contain personal, fiscal, financial, authentication-adjacent, and operational
  business data.
- Credential leakage through unit files, process arguments, environment dumps, logs, or metadata.
- Restore into the wrong database or reuse/removal of a protected volume.
- Over-broad retention deletion or Git inclusion of artifacts.

Required controls:

- Protected MySQL defaults/credential file; no hardcoded or printed secrets.
- No plaintext passwords in systemd units or generated reports.
- `umask 077`; managed directories/files limited to the operator/service account.
- Backup paths outside MySQL volumes, repository, and application images.
- Existing Git ignore protections retained; bounded artifact scan included in verification.
- External copies encrypted before leaving the controlled host/storage trust boundary.
- Encryption keys/credentials stored separately from backup artifacts.
- Sanitized errors and metadata; no row values in evidence.
- Explicit source/protected-volume denylist plus positive ownership checks for temporary resources.

Local encryption at rest is supported by the existing script but is not assumed active until the
configured execution is verified. Global security authority is inherited from `GLOBAL_SDD.md`
Section 18; capability-specific controls in this section supplement rather than weaken it.

---

# 21. FAILURE AND RECOVERY

| Failure | Persisted State | User/System Result | Recovery |
|---|---|---|---|
| MySQL unavailable/wrong identity | No new set | Nonzero, sanitized error | Correct dependency/config and retry |
| Concurrent backup | Existing sets unchanged | Nonzero conflict or scheduled already-satisfied no-op | Wait for owner; inspect evidence |
| Dump/compression failure | Owned partial only | Nonzero; no verified publication | Remove owned partial safely; retry |
| Checksum/metadata/permission failure | No verified set | Nonzero | Correct cause; rerun |
| Metrics/upload failure | Local verified state recorded separately | Explicit partial external-effect failure | Retry approved external action without recreating dump where safe |
| Unsafe retention path | No deletion | Nonzero | Correct managed-root configuration |
| Retention cleanup failure | Some eligible sets may remain | Nonzero with exact owned set IDs | Operator review; no scope expansion |
| Missing/corrupt/checksum-mismatch backup | No restore target write | Nonzero | Select valid verified set |
| Temporary MySQL startup/import/validation failure | Source unchanged; temporary evidence retained as policy allows | Nonzero; not certified | Diagnose isolated target and retry |
| Temporary cleanup failure | Source unchanged; unique resources identified | Nonzero/failed certification cleanup status | Operator removes only listed owned resources |
| Timer install/enable failure | Automation not active | `AUTOMATION_PREPARED` or blocked | Obtain operator privilege/configuration |

No failure authorizes automatic production restoration or deletion outside owned resources.

---

# 22. COMPATIBILITY AND LEGACY

- Existing environment variables and safe backup/restore behavior SHOULD remain compatible where
  they do not violate this SDD.
- Existing WS-33-B encrypted backup, checksum, provider-neutral upload, and Pushgateway boundaries are
  preserved.
- Existing unsafe broad retention is not a compatibility guarantee and must be replaced within the
  implementation boundary.
- The historical pre-pilot restore volume remains protected; the new certification flow uses unique
  temporary resources instead.
- No existing application schema, client, session, API, or business workflow changes.

---

# 23. PERFORMANCE AND SCALABILITY

Expected load: One scheduled full logical backup per database per day plus operator-triggered runs.
Latency-sensitive operations: None; availability wait and command runtime must be bounded/observable.
Expected data size: Current database size is not encoded as a permanent assumption.
Concurrency considerations: One backup/retention owner per managed database/root.
Batch constraints: Retention enumerates only the managed naming/metadata scheme.
Known scale threshold: Full logical dump duration/storage must be monitored; alternative backup/PITR
architecture requires separate approved design when operational evidence justifies it.

---

# 24. IMPLEMENTATION BOUNDARIES

## Allowed

- Minimally extend or relocate existing backup/restore scripts into a coherent `scripts/database/`
  boundary while preserving compatible entry points where needed.
- Add focused script tests/fixtures, systemd templates, safe operator configuration examples, and
  operational documentation.
- Add restore-certification orchestration using uniquely named temporary Docker resources.
- Read source/runtime identity and non-sensitive counts for preservation evidence.

## Conditionally Allowed

- Modify existing runbooks only to reflect the approved design/as-built commands.
- Retain optional upload/Pushgateway support if secret and failure contracts remain conformant.
- Use an operator-owned configuration file or safe environment variables; exact format is an
  implementation choice if secrets remain protected.

## Prohibited

- Restaurant/backend/frontend behavior changes.
- New database tables, migrations, API endpoints, microservices, Celery, or Redis queues.
- Source database restoration, truncation, schema mutation, volume replacement, or container rebuild.
- Deletion/reuse of `pryecip_mysql-data`, `pryecip-prepilot_mysql-pilot-data`,
  `pryecip-prepilot_mysql-restore-data`, or `pryecip_recovery_mysql-data`.
- `docker compose down -v` or unbounded Docker cleanup.
- Hardcoded developer username/path in reusable logic.
- Cloud/provider selection or automatic production restore.

```text
Backend: NO
Frontend: NO
Database: NO
API: NO
Infrastructure: YES
External integration: NO (future boundary only)
```

---

# 25. IMPLEMENTATION SEQUENCE

1. Reconfirm repository/runtime baseline and reuse assessment.
2. Remediate existing script safety while preserving compatible behavior.
3. Implement focused backup verification, atomic backup-set publication, and evidence.
4. Implement metadata and safe class-aware retention with dry-run.
5. Add validated systemd service/timer templates and operator installation procedure.
6. Implement unique isolated restore certification and source-preservation evidence.
7. Execute negative-path and focused certification scenarios.
8. Reconcile operational documentation to verified as-built commands.
9. Leave host activation to the operator; verify activation only when authorized.

No implementation unit may proceed until the applicable Global SDD version and this Capability SDD
version are explicitly approved in that order.

---

# 26. TEST STRATEGY

| Requirement / Invariant | Test Level | Required Verification |
|---|---|---|
| Consistent backup options | Static/integration | Command includes required MySQL 8.4 options; successful dump |
| Atomic publication/no false success | Integration/negative | Inject failures at dump, gzip, checksum, metadata; no verified set |
| File security | Static/integration | Modes/ownership and secret-output scan |
| Metadata correctness | Integration | Values match artifact/runtime without secrets |
| Concurrency/idempotency | Integration | Overlap rejected; duplicate scheduled day suppressed |
| Retention containment | Unit/integration | Dry-run, unsafe path, unmanaged files, known-good guard |
| systemd | Static/host | `systemd-analyze verify`, calendar timezone, persistent, enabled/active evidence |
| Restore integrity | Integration | Missing/corrupt/checksum mismatch fail before import |
| Restore isolation | Integration/E2E | Unique project/network/volume; no public DB port; source denylist |
| Schema/data/Alembic | Integration/E2E | Required objects/counts/revision and representative non-sensitive data |
| Source preservation | E2E | Before/after source identity/revision/count evidence unchanged |
| Cleanup | Integration/negative | Unique resources removed; cleanup failure explicit |

No unrelated application test universe is required.

---

# 27. REGRESSION SCOPE

## Direct

Affected: Backup/restore scripts, metadata, retention, scheduler templates, runbook.
Risk: Data loss, false success, secret leakage, unrecoverable backup.
Verification: All Section 26 focused tests and certification scenarios.

## Secondary

Affected: Controlled migration's confirmed-backup input, optional Pushgateway/upload compatibility,
pilot operator procedures.
Dependency: Existing artifact/checksum and operational contracts.
Verification: Confirm compatible verified artifact/checksum consumption and documentation commands.

## Collateral

Affected: Git artifact protections and protected Docker resources.
Shared dependency: Repository ignore rules and Docker runtime.
Verification: Bounded artifact scan, repository diff, and source/protected-volume identity checks.

---

# 28. CERTIFICATION SCENARIOS

## V1 — Successful verified backup

Setup: Healthy expected MySQL 8.4 source and authorized empty managed daily directory.
Action: Run the backup command.
Expected result: One atomically published verified set with valid gzip, SHA-256, metadata, safe modes,
and explicit duration/result.
Evidence: Command result, artifact stat, gzip/checksum checks, metadata comparison.

## V2 — Concurrent execution protection

Setup: Hold the capability lock with one controlled backup execution.
Action: Start a second execution for the same database/root.
Expected result: Second execution returns explicit nonzero conflict and publishes no set.
Evidence: Exit codes, logs, artifact inventory.

## V3 — Safe retention

Setup: Managed verified daily/weekly/monthly sets, one known-good point, unmanaged files, and dry-run.
Action: Evaluate and then apply policy to eligible disposable test sets.
Expected result: Plan matches configured defaults/overrides; unmanaged and known-good files remain;
pre-change remains operator-controlled.
Evidence: Before/dry-run/after inventories and retention result.

## V4 — Unsafe retention rejection

Setup: Root, repository, MySQL volume-like path, symlink escape, or unowned directory target.
Action: Request retention.
Expected result: Nonzero, no deletion.
Evidence: Exit code and before/after inventory.

## V5 — Isolated restore certification

Setup: Explicit V1 backup and captured source baseline.
Action: Create unique isolated MySQL 8.4 resources, restore, validate, and clean.
Expected result: Checksum/gzip, database, schema objects, table counts, foreign keys, indexes,
triggers/routines/events where present, Alembic revision, and representative data pass; source is
unchanged; owned temporary resources are removed.
Evidence: Certification record with resource IDs and sanitized validation results.

For the protected `ecip` development database, representative checks SHOULD confirm configured
non-sensitive anchors for Carnitas Tenant, CMC Organization, and SLP-CARNITAS-MUNOZ Location when
those anchors are part of the authorized source baseline. Their absence MUST NOT fail certification
for a different authorized database; that database must provide its own expected non-sensitive
anchors or count contract.

## V6 — Corrupt/mismatched backup

Setup: Missing artifact, corrupt gzip, and checksum-mismatch variants.
Action: Run restore certification for each.
Expected result: Nonzero before import; no source change; no false certification.
Evidence: Exit codes, logs, source baseline.

## V7 — Dependency and restore failures

Setup: Missing MySQL service, forced dump failure, temporary startup failure, import failure.
Action: Execute applicable flow.
Expected result: Explicit nonzero result; previous verified backup preserved; source unchanged.
Evidence: Logs, backup inventory, source baseline.

## V8 — Cleanup failure

Setup: Controlled failure preventing removal of a uniquely owned temporary resource.
Action: Complete/abort restore certification.
Expected result: Certification reports cleanup failure and exact owned resource IDs; no broad cleanup
and no source effect.
Evidence: Exit/result record and resource inventory.

## V9 — Scheduling and activation

Setup: Approved units/config on authorized host.
Action: Verify/install/enable/start timer and execute service once.
Expected result: `OnCalendar=*-*-* 03:00:00 America/Mexico_City`, `Persistent=true`, overlap guard,
installed/enabled/active state, exact next run, and verified backup.
Evidence: `systemd-analyze`, unit status, timer listing, journal, backup metadata.

## V10 — Source preservation

Setup: Capture source container ID, mounted volume, database identity, Alembic revision, and approved
representative counts before V1/V5.
Action: Complete backup/restore certification.
Expected result: All captured source identifiers and counts are unchanged.
Evidence: Before/after comparison without personal/customer data.

---

# 29. ACCEPTANCE AND PASS / FAIL

## AC-001 — Backup

Requirement: V1 and backup failure paths conform.
Verification: V1, V2, V7.
PASS: Consistent export, gzip, checksum, metadata, atomic publication, permissions, and overlap guard
pass.
FAIL: Any false success, corrupt publication, unsafe permissions, or overlap occurs.

## AC-002 — Retention

Requirement: Operator-configurable class policies are safely enforced.
Verification: V3 and V4.
PASS: Dry-run and bounded apply preserve unmanaged/pre-change/only-known-good sets.
FAIL: An unsafe target is accepted or an unauthorized file is deleted.

## AC-003 — Scheduling

Requirement: Daily execution is correctly prepared and, when authorized, activated.
Verification: V9.
PASS: Units validate; timezone/persistence/lock are correct. `AUTOMATION_ACTIVE` additionally requires
installed, enabled, active, and verified execution evidence.
FAIL: Configuration is invalid or active is claimed without evidence.

## AC-004 — Restore certification

Requirement: A verified backup is recoverable in isolation.
Verification: V5, V6, V7, V8, V10.
PASS: Restore/schema/data/Alembic/source preservation/cleanup pass.
FAIL: Verification is incomplete, source is affected, or cleanup failure is hidden.

## AC-005 — Security

Requirement: Secrets and backup data remain protected.
Verification: Permission checks, config/unit inspection, logs/metadata scan, repository artifact scan.
PASS: No secret exposure; artifacts have restrictive access; external-copy boundary requires
encryption.
FAIL: A credential or sensitive row value is exposed or an archive enters Git.

Overall `PASS` requires all applicable criteria and scenarios, required regression, no unauthorized
deviation, no blocking security issue, and successful isolated restoration. A dump file alone is not
a certified backup.

---

# 30. STOP CONDITIONS

Implementation MUST stop when:

1. This SDD or its required higher authority is not approved for implementation.
2. Source/target identity or volume ownership is ambiguous.
3. Protected credentials cannot be accessed without exposure.
4. Isolation from the source database cannot be proven.
5. A required operation would mutate/recreate the source or a protected historical volume.
6. Retention cannot prove path and backup-set ownership.
7. Privileged installation lacks operator authorization.
8. A destructive production restore is requested without separate recovery authority.
9. Safe verification cannot be completed.

---

# 31. OPEN QUESTIONS, RISKS AND DEFERRED ITEMS

## Open Questions

| Question | Impact | Blocking | Required Authority |
|---|---|---|---|
| Which host account and installation path own the eventual systemd units/config? | Deployment-specific activation | NO for implementation; YES for activation | Platform operator |
| Which external encrypted destination and retention policy apply? | Off-host resilience | NO for local foundation | Platform operator/business/compliance |

## Risks

| Risk | Impact | Mitigation | Residual Risk |
|---|---|---|---|
| Logical dump duration grows | Longer backup/RPO exposure | Record duration/size; revisit architecture at measured threshold | Full dump remains non-incremental |
| Non-transactional table consistency | Some objects may not share transactional snapshot | Inventory/record applicable engine limitations; certify representative restore | MySQL logical-backup limitation |
| Local-only backup loss | Host loss removes backup | Future mandatory encrypted external copy | Present until provider activated |
| Operator misconfiguration | Wrong target/path or inactive automation | Fail-closed validation and activation evidence | Host access remains privileged |
| Cleanup failure | Temporary sensitive restore remains | Unique IDs, explicit failure, bounded operator cleanup | Manual action may be required |

## Deferred Items

See Section 4.3.

---

# 32. TRACEABILITY

| Requirement / Rule | Authority | SDD Section | Implementation | Verification |
|---|---|---|---|---|
| Reuse existing backup/restore | WS-33-B; Global reuse principle | 5, 6, 22 | Existing scripts with minimal extension | V1, V5 |
| Operator-controlled retention | WS-33-B | 8, 9, 13 | Configurable class policy | V3, V4 |
| Daily 03:00 local schedule | This SDD after approval | 9, 17 | systemd service/timer | V9 |
| Source protection | Global failure/history principles; this SDD | 8, 21, 24 | Isolation/denylist/baseline proof | V5, V10 |
| Secret protection | Global SDD; WS-33-B; this SDD | 8, 20 | Credential files, modes, redaction | AC-005 |
| No new schema/API/frontend | Global minimal change; this SDD | 3, 4, 24 | Infrastructure-only changes | Repository diff |
| Restore required for certification | This SDD after approval | 9, 28, 29 | Certification command | V5–V8 |

---

# 33. CERTIFICATION EVIDENCE

The approved design was implemented and certified without changing database schema, application
behavior, or the protected source. Historical approval evidence in Section 2.3 remains unchanged.

```text
SDD version: 0.1.1
Repository: /home/rogelio/proyectos/pryecip
Branch: feat/ws-00-01-runtime-reuse-baseline
Implementation baseline HEAD: 9b0cbe8ecc499a553ed008eac29237deedaba370
Working tree: P03 implementation pending controlled Git closure; unrelated ECIP_DATABASE_SCHEMA.txt preserved
Repository migration head: 0069_org_hq_provisioning
Protected source migration: 0067_internal_operational_message_foundation
Protected source: pryecip-mysql-1 / pryecip_mysql-data / ecip / MySQL 8.4.8
Result: PASS
Certification date: 2026-10-10 (America/Mexico_City)
Automation state: READY_FOR_ACTIVATION; host installation/activation NOT AUTHORIZED
External encrypted copy: NOT CONFIGURED (approved deferred boundary)
```

Executed evidence:

- Focused script suite: 32 PASS, 0 FAIL. It covered atomic publication, required metadata and
  checksum, restrictive modes, dump/checksum/source/import failures, overlap rejection, duplicate
  scheduled suppression, retention dry-run/apply and unsafe-target guards, incomplete/corrupt
  restore inputs, protected-target rejection, cleanup-failure reporting, and systemd contracts.
- Final backup set:
  `ecip_ecip_20261011T003812Z_p03-final-certification_441668`; 112562 bytes; SHA-256
  `d884a9698c064e392419eeb1cf75f5d69bee5757fec5423566b94af15cc316d1`;
  `BACKUP_VERIFIED`; owner-only modes.
- Isolated restore: unique MySQL 8.4 Compose project with an internal network, no published database
  port, and a task-owned volume. Import, checksum/gzip, 152 base tables, schema-object counts,
  Alembic `0067_internal_operational_message_foundation`, and representative per-table count hash
  passed. Unique resources were removed.
- Source preservation: container ID, `pryecip_mysql-data`, MySQL version, Alembic revision, base-table
  count, schema-object counts, and representative count hash matched before/after.
- Scheduling: rendered service/timer passed `systemd-analyze verify`; calendar normalized to 03:00
  `America/Mexico_City`; `Persistent=true`. No service or timer was installed, enabled, or started.
- Regression: controlled migration shares the database-operations lock; artifact/checksum consumers
  remain compatible; repository artifact scan, diff check, protected-resource inventory, and no-0070
  verification passed.

Certification scenario result:

```text
V1 PASS   V2 PASS   V3 PASS   V4 PASS   V5 PASS
V6 PASS   V7 PASS   V8 PASS   V9 PASS (prepared boundary; activation not authorized)
V10 PASS
```

---

# 34. DEFINITION OF READY

```text
[x] Authority is identified
[x] Capability boundary is explicit
[x] Scope is bounded
[x] Existing implementation was inspected
[x] Reuse was evaluated
[x] Critical domain concepts are N/A or defined as technical concepts
[x] Critical invariants are explicit
[x] Ownership is unambiguous
[x] Persistence is sufficiently designed (filesystem evidence; no DB persistence)
[x] API contracts are N/A
[x] Transactions/concurrency are defined
[x] Authorization/security requirements are defined
[x] Implementation boundaries are explicit
[x] Verification and certification criteria are defined
[x] Required governance/security design questions are resolved
```

The approved design governed the certified implementation recorded in Section 33.

---

# 35. DEFINITION OF DONE

The capability is done when:

```text
[x] Approved design is implemented
[x] Executable contracts conform to this SDD
[x] Critical invariants are verified
[x] Required focused tests pass
[x] Required direct/secondary/collateral regression passes
[x] V1–V10 pass where applicable
[x] No blocking security defect remains
[x] Isolated restore certification passes
[x] Source preservation passes
[x] Operational documentation matches verified commands
[x] Deployment activation state is reported independently and accurately
[x] The SDD is reconciled to certified as-built reality
```
