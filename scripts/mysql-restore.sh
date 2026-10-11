#!/bin/sh
set -eu
umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$script_dir/mysql-backup-common.sh"

: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${BACKUP_ARTIFACT:?BACKUP_ARTIFACT is required}"
mbr_require_private_file "$MYSQL_DEFAULTS_FILE" 'MySQL credential file'
[ -r "$BACKUP_ARTIFACT" ] || mbr_die 'backup artifact is not readable'
[ -r "$BACKUP_ARTIFACT.sha256" ] || mbr_die 'backup checksum is required'
case "${RESTORE_TARGET_CONTAINER:-}" in pryecip-mysql-1|pryecip-stagea1-candidate-mysql-20261009) mbr_die 'protected restore target rejected' ;; esac
case "${RESTORE_TARGET_VOLUME:-}" in pryecip_mysql-data|pryecip-stagea1-candidate-data-20261009|pryecip-prepilot_mysql-pilot-data|pryecip-prepilot_mysql-restore-data|pryecip_recovery_mysql-data) mbr_die 'protected restore volume rejected' ;; esac

(cd "$(dirname "$BACKUP_ARTIFACT")" && sha256sum -c "$(basename "$BACKUP_ARTIFACT").sha256")
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/ecip-restore.XXXXXX")
cleanup() { rm -rf -- "$work_dir"; }
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
echo 'restore complete: RESTORE_IMPORTED'
