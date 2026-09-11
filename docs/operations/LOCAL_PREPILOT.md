# Local pre-pilot MySQL and minimum dataset

This boundary is **LOCAL PRE-PILOT**, not production and not the final pilot database. It uses
MySQL 8.4 on an internal Docker network, separate migration/runtime identities, named volumes,
external secret files, the existing Alembic chain, `app.bootstrap_admin`, and the explicit
`app.bootstrap_pilot_minimum` operator command.

Create an owner-only environment file outside Git with paths for
`MYSQL_PASSWORD_FILE`, `MYSQL_MIGRATION_PASSWORD_FILE`, `MYSQL_ROOT_PASSWORD_FILE`,
`AUTH_JWT_SECRET_FILE`, `DINER_ACCESS_SECRET_FILE`,
`PILOT_ADMIN_PASSWORD_FILE`, `PILOT_STAFF_PASSWORD_FILE`, and `PILOT_BACKUP_DIR`.
The administrator password must remain in the existing protected
`PILOT_ADMIN_PASSWORD_FILE`; do not copy it into the environment or command line. Generate the
three MySQL passwords and the synthetic staff password as independent hexadecimal values. Secret
files must be owner-only and the backup directory must not be readable by other users.

Set the protected environment-file path for the commands below and load only its path variables:

```bash
PILOT_ENV_FILE=/protected/pilot-local.env
set -a
. "$PILOT_ENV_FILE"
set +a
```

Run the controlled sequence:

```bash
docker compose --env-file /protected/pilot-local.env -f compose.pilot-local.yaml up -d mysql
docker compose --env-file /protected/pilot-local.env -f compose.pilot-local.yaml --profile tools run --rm migrate
docker compose --env-file /protected/pilot-local.env -f compose.pilot-local.yaml --profile tools run --rm bootstrap
docker compose --env-file /protected/pilot-local.env -f compose.pilot-local.yaml up -d api
```

The bootstrap is repeatable and returns only non-secret identifiers. It creates an active Connector
record and destination prerequisite for `workstation_hp_p1005`, but never creates an enrollment or
credential. Its Conekta TEST executor remains `INACTIVE` with no key material; activation belongs to
the separate Conekta TEST certification procedure.

Run the bootstrap a second time. Its JSON must report `already_configured`, an
`objects_created_count` of `0`, and the same IDs. Verify both API probes:

```bash
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile tools run --rm bootstrap
curl --fail --silent --show-error http://127.0.0.1:18080/health
curl --fail --silent --show-error http://127.0.0.1:18080/ready
```

## Persistence check

Record the bootstrap IDs, restart MySQL, and then force-recreate only its container. Neither action
removes the named volume. Wait for MySQL and the API to become healthy after each action, rerun the
bootstrap, and confirm the same IDs with zero creations.

```bash
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml restart mysql
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml up -d --wait mysql api
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  up -d --wait --force-recreate mysql
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml up -d --wait api
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile tools run --rm bootstrap
```

## Protected backup and isolated restore

Create a consistent logical backup with the existing `scripts/mysql-backup.sh` and the migration
identity. The generated client option file lives only under `/run`; no database password is placed
on a command line or in the backup. Keep the basename printed by the command for restoration.

```bash
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml exec -T \
  -e MYSQL_DEFAULTS_FILE=/run/ecip-migration.cnf \
  -e MYSQL_HOST=127.0.0.1 -e MYSQL_PORT=3306 \
  -e MYSQL_DATABASE="${MYSQL_DATABASE:-pryecip_pilot_local}" \
  -e BACKUP_DESTINATION_DIR=/backup -e RELEASE_ID=ws-33-c2a-local \
  mysql /opt/pryecip/scripts/mysql-backup.sh
```

The following reset is destructive only to the disposable `mysql-restore-data` volume. It does not
touch `mysql-pilot-data`. Verify the checksum before importing into the isolated restore network:

```bash
backup_name=ecip_pryecip_pilot_local_YYYYMMDDTHHMMSSZ_ws-33-c2a-local.sql.gz
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile restore rm --stop --force api-restore mysql-restore
docker volume rm pryecip-prepilot_mysql-restore-data
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile restore up -d --wait mysql-restore
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile restore exec -T \
  -e MYSQL_DEFAULTS_FILE=/run/ecip-migration.cnf \
  -e MYSQL_HOST=127.0.0.1 -e MYSQL_PORT=3306 \
  -e MYSQL_DATABASE="${MYSQL_DATABASE:-pryecip_pilot_local}" \
  -e BACKUP_ARTIFACT="/backup/$backup_name" \
  mysql-restore /opt/pryecip/scripts/mysql-restore.sh
docker compose --env-file "$PILOT_ENV_FILE" -f compose.pilot-local.yaml \
  --profile restore up -d --wait api-restore
curl --fail --silent --show-error http://127.0.0.1:18081/health
curl --fail --silent --show-error http://127.0.0.1:18081/ready
```

Compare the Alembic revision and minimum-record counts between `mysql` and `mysql-restore`. The
runtime identity must show only `SELECT`, `INSERT`, `UPDATE`, `DELETE`, and `EXECUTE` grants on the
pilot database. MySQL has no host `ports` mapping; only the two loopback API ports are published.

This workstream stops before Conekta TEST execution, Connector enrollment, credential generation,
or print E2E. Those steps require their separate operator-controlled procedures and inputs.
