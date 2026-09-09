# Database Migration, Backup, and Restore Runbook

One environment has one authoritative database. Local isolated MySQL is for development, migration rehearsal, destructive restore drills, and synthetic pre-pilot validation. The external MySQL instance is authoritative for real pilot data. There is no local/external continuous synchronization.

## Roles

- `ecip_runtime`: normal DML required by the API; no schema administration.
- `ecip_migrator`: DDL plus required DML for Alembic, used only by the explicit migration job.
- `ecip_backup`: read/lock metadata privileges needed by `mysqldump`.
- Restore administrator: isolated recovery or explicitly approved production recovery only.

Do not use or inject the MySQL root identity into the API.

## Controlled migration

1. Validate the intended commit/image/digest and stop release promotion.
2. Create a successful backup with checksum, encrypted or written directly to an encrypted off-host destination.
3. Set `CONFIRMED_BACKUP_ARTIFACT` to that non-empty artifact.
4. Run `scripts/controlled-migration.sh` with the production env file.
5. Confirm Alembic head and DB readiness, deploy the API, then verify `/ready` and a representative authenticated read.
6. On migration failure, do not deploy. Investigate against an isolated copy. Do not automatically downgrade.

## Backup

Install MySQL client tools, gzip, sha256sum, OpenSSL, and optionally curl on the controlled operations runner. Put client credentials in a `0600` MySQL defaults file. Set `MYSQL_DEFAULTS_FILE`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `BACKUP_DESTINATION_DIR`, `RELEASE_ID`, and `BACKUP_RETENTION_DAYS`, then run `scripts/mysql-backup.sh`.

Set `BACKUP_ENCRYPTION_KEY_FILE` for AES-256 encrypted output or mount an already encrypted destination. `BACKUP_UPLOAD_COMMAND` can copy the artifact and checksum to any approved off-host provider; it receives only `BACKUP_ARTIFACT` and `BACKUP_CHECKSUM`. `BACKUP_PUSHGATEWAY_URL` publishes success/failure status. RPO, RTO, retention, destination, and credentials are operator inputs.

## Isolated restore drill

1. Provision an empty isolated local/test MySQL database. Never target real pilot data.
2. Set the isolated host/database and `BACKUP_ARTIFACT`; run `scripts/mysql-restore.sh`.
3. Point the explicit migration job at the restored DB and run `alembic upgrade head`, then `alembic current`.
4. Verify representative row counts/identities with non-sensitive queries.
5. Start the exact API image against that DB, verify `/ready`, and execute a representative read.
6. Record artifact checksum, source release, target, head revision, timings, and outcome; destroy test data according to policy.

Recovery RTO is measured from incident authorization through verified readiness. Recovery point is the newest validated off-host artifact preceding the incident.
