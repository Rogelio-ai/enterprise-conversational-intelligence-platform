#!/bin/sh
set -eu
umask 077

: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${BACKUP_DESTINATION_DIR:?BACKUP_DESTINATION_DIR is required}"
[ -r "$MYSQL_DEFAULTS_FILE" ] || { echo 'MySQL credential file is not readable' >&2; exit 1; }
mkdir -p "$BACKUP_DESTINATION_DIR"

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
release=${RELEASE_ID:-unknown-release}
safe_release=$(printf '%s' "$release" | tr -cd 'A-Za-z0-9._-')
base="$BACKUP_DESTINATION_DIR/ecip_${MYSQL_DATABASE}_${timestamp}_${safe_release}"
plain="$base.sql.gz"
partial="$plain.partial"
raw="$base.sql.partial"
status_file=${BACKUP_STATUS_FILE:-$BACKUP_DESTINATION_DIR/last-backup.prom}

publish_status() {
    if [ -n "${BACKUP_PUSHGATEWAY_URL:-}" ]; then
        curl --fail --silent --show-error --data-binary "@$status_file" "$BACKUP_PUSHGATEWAY_URL/metrics/job/ecip_backup"
    fi
}

cleanup() { rm -f "$partial" "$raw" "$plain.enc.partial"; }
trap cleanup EXIT HUP INT TERM

if mysqldump --defaults-extra-file="$MYSQL_DEFAULTS_FILE" \
    --host="$MYSQL_HOST" --port="${MYSQL_PORT:-3306}" \
    --single-transaction --quick --routines --events --triggers \
    --set-gtid-purged=OFF --no-tablespaces "$MYSQL_DATABASE" > "$raw" \
    && [ -s "$raw" ] \
    && gzip -9 -c "$raw" > "$partial" \
    && gzip -t "$partial"; then
    rm -f "$raw"
    mv "$partial" "$plain"
else
    printf 'ecip_backup_success 0\necip_backup_timestamp_seconds %s\n' "$(date +%s)" > "$status_file"
    publish_status || true
    echo 'backup failed' >&2
    exit 1
fi

artifact="$plain"
if [ -n "${BACKUP_ENCRYPTION_KEY_FILE:-}" ]; then
    [ -r "$BACKUP_ENCRYPTION_KEY_FILE" ] || { echo 'backup encryption key file is not readable' >&2; exit 1; }
    encrypted="$plain.enc"
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:$BACKUP_ENCRYPTION_KEY_FILE" -in "$plain" -out "$encrypted.partial"
    mv "$encrypted.partial" "$encrypted"
    rm -f "$plain"
    artifact="$encrypted"
fi

sha256sum "$artifact" > "$artifact.sha256"
printf 'ecip_backup_success 1\necip_backup_timestamp_seconds %s\n' "$(date +%s)" > "$status_file"

if [ -n "${BACKUP_UPLOAD_COMMAND:-}" ]; then
    BACKUP_ARTIFACT="$artifact" BACKUP_CHECKSUM="$artifact.sha256" sh -c "$BACKUP_UPLOAD_COMMAND"
fi
publish_status
if [ "${BACKUP_RETENTION_DAYS:-0}" -gt 0 ]; then
    find "$BACKUP_DESTINATION_DIR" -maxdepth 1 -type f -name 'ecip_*' -mtime "+$BACKUP_RETENTION_DAYS" -delete
fi
echo "backup complete: $artifact"
