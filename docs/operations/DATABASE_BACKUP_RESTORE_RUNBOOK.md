# Database Migration, Backup, and Restore Runbook

One environment has one authoritative database. Backups are sensitive operational data. Restore
certification always uses a unique isolated MySQL environment; it never targets the source or a
protected historical volume.

## Roles and prerequisites

- `ecip_runtime`: normal application DML; no schema administration.
- `ecip_migrator`: DDL and required migration DML, used only by the controlled migration job.
- `ecip_backup`-style identity: the least privileges required for `mysqldump`, metadata reads, and
  the selected database. Use an existing operator-approved identity; never add privileges as part of
  a backup run.
- Restore administrator: isolated recovery drills or separately authorized real recovery only.

Install MySQL 8.4 client tools, `gzip`, `sha256sum`, `flock`, `openssl`, Docker Compose, and
optionally `curl`. The configured backup root must be an absolute, service-owned `0700` directory
outside the repository, application images, and MySQL volumes. The scripts initialize an empty root
with `.mysql-backup-root`; a non-empty unmarked directory is rejected.

Store client credentials in a protected MySQL defaults file:

```ini
[client]
user=ecip_backup
password=REPLACE_OUTSIDE_GIT
```

The file must be `0400` or `0600`. Do not put passwords in unit files, command arguments,
metadata, logs, or this repository.

## Configuration

Start from `deploy/systemd/mysql-backup.conf.example`. Required values are
`MYSQL_DEFAULTS_FILE`, `MYSQL_HOST`, `MYSQL_DATABASE`, and `BACKUP_DESTINATION_DIR`. Record the
verified source container and volume identities with `SOURCE_CONTAINER_IDENTITY` and
`SOURCE_VOLUME_IDENTITY` when Docker supplies the source.

The managed layout is:

```text
daily/        verified daily backup sets
weekly/       verified weekly backup sets
monthly/      verified monthly backup sets
pre-change/   operator-controlled backup sets
restore-tests/
logs/
.locks/
```

Each published set contains the archive, mandatory SHA-256 sidecar, `metadata.env`, and `result`.
Publication occurs only after the export, gzip, checksum, metadata, and restrictive permissions
pass. The metadata format is versioned and contains no secrets or row values.

## Manual backup

Verify the exact source container, `/var/lib/mysql` volume, database, available space, and the
absence of a competing migration or scheduler. Then load the protected configuration and run:

```bash
set -a
. /etc/pryecip/mysql-backup.conf
set +a
BACKUP_RUN_MODE=manual BACKUP_CLASS=daily scripts/mysql-backup.sh
```

Use `BACKUP_CLASS=pre-change` for an explicitly operator-controlled recovery point. Manual runs
always receive unique IDs. Scheduled runs use `BACKUP_RUN_MODE=scheduled` and return a successful
no-op when that database already has a verified daily set for the current
`America/Mexico_City` calendar day.

Backup and controlled migration must use the same `DATABASE_OPERATIONS_LOCK_FILE`. Lock conflict is
an explicit nonzero result before either operation accesses or mutates the database.

## Checksum and metadata verification

Given a backup-set directory:

```bash
set_dir=/absolute/managed/root/daily/ecip_ecip_TIMESTAMP_RELEASE_PID
artifact=$(awk -F= '$1=="archive_filename" {print $2}' "$set_dir/metadata.env")
(cd "$set_dir" && sha256sum -c "$artifact.sha256")
gzip -t "$set_dir/$artifact"
grep -Fx 'verification_status=BACKUP_VERIFIED' "$set_dir/metadata.env"
```

For encrypted `.enc` artifacts, verify SHA-256 first and decrypt to an owner-only temporary file
with the separately protected key before `gzip -t`. An archive without its sidecar and successful
metadata is incomplete and must not be restored or removed by retention.

## Retention

Defaults are configurable: daily 14 days, weekly 8 weeks, monthly 12 months, and no automatic
expiry for pre-change sets. Always review a dry-run before an operator-initiated apply:

```bash
BACKUP_DESTINATION_DIR=/var/lib/pryecip/backups \
  RETENTION_MODE=dry-run scripts/mysql-backup-retention.sh

BACKUP_DESTINATION_DIR=/var/lib/pryecip/backups \
  RETENTION_MODE=apply scripts/mysql-backup-retention.sh
```

Retention considers only complete capability-owned set directories below validated class paths. It
preserves unmanaged/incomplete content, the newest verified set in every class, `KNOWN_GOOD` sets,
pre-change sets, active operations, and anything outside the managed root. Symlink and unmarked-root
checks fail closed. Decisions are recorded under `logs/`.

## Isolated restore certification

The certification command requires one verified backup set and the exact source identity:

```bash
BACKUP_SET_DIR=/absolute/managed/root/daily/BACKUP_ID \
SOURCE_CONTAINER=pryecip-mysql-1 \
SOURCE_VOLUME=pryecip_mysql-data \
MYSQL_DATABASE=ecip \
scripts/mysql-restore-certify.sh
```

The command verifies metadata, SHA-256, and gzip before import; creates a unique Compose project,
internal-only network, MySQL 8.4 container, and task-owned volume; exposes no database port; imports
the dump; compares schema-object counts, Alembic revision, and per-table count fingerprint; verifies
the source before/after snapshot; and removes only its unique resources. Successful evidence is
written under the backup set's `restore-certifications/`, and the set receives `KNOWN_GOOD`.

`scripts/mysql-restore.sh` remains the low-level import primitive. It requires a checksum and rejects
known protected targets, but it does not by itself prove isolation or recovery certification.

The normal development source is historically at Alembic `0067_internal_operational_message_foundation`
while repository head is later. A faithful restored revision of `0067` proves backup/restore
fidelity; it does not prove current application schema conformance. Do not migrate either source or
restore target during P03 certification.

## Daily systemd automation

The repository contains prepared templates:

- `deploy/systemd/pryecip-mysql-backup.service.in`
- `deploy/systemd/pryecip-mysql-backup.timer`
- `deploy/systemd/mysql-backup.conf.example`

The timer runs at 03:00 in `America/Mexico_City` and has `Persistent=true`. Before rendering or
installing the service, the platform operator must choose the service account/group, installation
root, protected config path, and backup root; verify ownership, `0400`/`0600` credentials, capacity,
source identity, and no competing scheduler; render every `@...@` placeholder; and run:

```bash
systemd-analyze verify /etc/systemd/system/pryecip-mysql-backup.service \
  /etc/systemd/system/pryecip-mysql-backup.timer
```

Only separately authorized host activation may run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pryecip-mysql-backup.timer
systemctl is-enabled pryecip-mysql-backup.timer
systemctl is-active pryecip-mysql-backup.timer
systemctl list-timers pryecip-mysql-backup.timer
journalctl -u pryecip-mysql-backup.service
```

`AUTOMATION_ACTIVE` additionally requires one successful service execution, a verified backup set,
and successful isolated restore evidence. Repository templates or timer installation alone mean
only `READY_FOR_ACTIVATION`.

## Failure handling and recovery

- A failed export/checksum/metadata operation publishes no verified set; correct the dependency or
  configuration and retry.
- A lock conflict means another backup, retention, or migration owns the operation; inspect it and
  retry later.
- A corrupt/mismatched/incomplete archive must fail before import. Select another verified set.
- Isolated startup/import/validation failure is not certification. Preserve sanitized evidence as
  needed and remove only the listed unique project resources.
- Cleanup failure must report the exact unique project/container/volume. Never use broad Docker
  cleanup or delete protected volumes.
- Real recovery into an authoritative database requires separate incident-specific authorization.
  Stop traffic, reverify the selected known-good set, capture target identity, execute the approved
  recovery plan, and verify readiness/data before resuming traffic. No automatic production restore
  or Alembic downgrade is authorized.

## Controlled migration

1. Validate the intended commit/image/digest and stop release promotion.
2. Select a non-empty verified backup artifact; verify its checksum and restore evidence.
3. Set `CONFIRMED_BACKUP_ARTIFACT` and the same `DATABASE_OPERATIONS_LOCK_FILE` used by backup.
4. Run `scripts/controlled-migration.sh` with the production environment file.
5. Confirm Alembic head and DB readiness, deploy, then verify `/ready` and a representative read.
6. On failure, do not deploy or automatically downgrade. Investigate against an isolated copy.

## External-copy limitation

External replication is not configured by this repository. `BACKUP_UPLOAD_COMMAND` remains a
provider-neutral boundary and may be used only after an operator selects a destination, credentials,
retention, idempotency behavior, and encryption. Never transmit an unencrypted database archive
outside the controlled local storage boundary. Until an encrypted off-host copy is configured and
verified, external disaster recovery is **NOT CONFIGURED**, not PASS.
