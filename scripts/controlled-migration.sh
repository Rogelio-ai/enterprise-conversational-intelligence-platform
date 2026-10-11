#!/bin/sh
set -eu

: "${PRODUCTION_ENV_FILE:?PRODUCTION_ENV_FILE is required}"
: "${CONFIRMED_BACKUP_ARTIFACT:?CONFIRMED_BACKUP_ARTIFACT is required}"
: "${DATABASE_OPERATIONS_LOCK_FILE:?DATABASE_OPERATIONS_LOCK_FILE is required}"
[ -s "$CONFIRMED_BACKUP_ARTIFACT" ] || { echo 'confirmed backup artifact is absent or empty' >&2; exit 1; }
[ ! -r "$CONFIRMED_BACKUP_ARTIFACT.sha256" ] || sha256sum -c "$CONFIRMED_BACKUP_ARTIFACT.sha256"
command -v flock >/dev/null 2>&1 || { echo 'flock is required' >&2; exit 1; }
mkdir -p "$(dirname "$DATABASE_OPERATIONS_LOCK_FILE")"
exec 9>"$DATABASE_OPERATIONS_LOCK_FILE"
flock -n 9 || { echo 'database backup/migration operation already in progress' >&2; exit 1; }

compose="docker compose --env-file $PRODUCTION_ENV_FILE -f compose.production.yaml"
$compose --profile migration run --rm migrate
$compose --profile migration run --rm migrate alembic current
echo 'controlled migration and head verification: PASS'
