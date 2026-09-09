#!/bin/sh
set -eu

: "${PRODUCTION_ENV_FILE:?PRODUCTION_ENV_FILE is required}"
: "${CONFIRMED_BACKUP_ARTIFACT:?CONFIRMED_BACKUP_ARTIFACT is required}"
[ -s "$CONFIRMED_BACKUP_ARTIFACT" ] || { echo 'confirmed backup artifact is absent or empty' >&2; exit 1; }
[ ! -r "$CONFIRMED_BACKUP_ARTIFACT.sha256" ] || sha256sum -c "$CONFIRMED_BACKUP_ARTIFACT.sha256"

compose="docker compose --env-file $PRODUCTION_ENV_FILE -f compose.production.yaml"
$compose --profile migration run --rm migrate
$compose --profile migration run --rm migrate alembic current
echo 'controlled migration and head verification: PASS'
