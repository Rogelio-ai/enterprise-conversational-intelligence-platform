#!/bin/sh
set -eu
umask 077

: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${BACKUP_ARTIFACT:?BACKUP_ARTIFACT is required}"
[ -r "$MYSQL_DEFAULTS_FILE" ] || { echo 'MySQL credential file is not readable' >&2; exit 1; }
[ -r "$BACKUP_ARTIFACT" ] || { echo 'backup artifact is not readable' >&2; exit 1; }
[ -r "$BACKUP_ARTIFACT.sha256" ] && sha256sum -c "$BACKUP_ARTIFACT.sha256"

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/ecip-restore.XXXXXX")
cleanup() { rm -rf "$work_dir"; }
trap cleanup EXIT HUP INT TERM
compressed="$BACKUP_ARTIFACT"
case "$BACKUP_ARTIFACT" in
    *.enc)
        : "${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required for encrypted backup}"
        compressed="$work_dir/restore.sql.gz"
        openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
            -pass "file:$BACKUP_ENCRYPTION_KEY_FILE" -in "$BACKUP_ARTIFACT" -out "$compressed"
        ;;
esac
gzip -t "$compressed"
gzip -dc "$compressed" | mysql --defaults-extra-file="$MYSQL_DEFAULTS_FILE" \
    --host="$MYSQL_HOST" --port="${MYSQL_PORT:-3306}" "$MYSQL_DATABASE"
echo 'restore complete'
