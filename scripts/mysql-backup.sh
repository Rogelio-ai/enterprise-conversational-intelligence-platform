#!/bin/sh
set -eu
umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$script_dir/mysql-backup-common.sh"

: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${BACKUP_DESTINATION_DIR:?BACKUP_DESTINATION_DIR is required}"
mbr_require_private_file "$MYSQL_DEFAULTS_FILE" 'MySQL credential file'
mbr_require_safe_token MYSQL_DATABASE "$MYSQL_DATABASE"
for command_name in mysqldump mysql gzip sha256sum flock readlink; do mbr_require_command "$command_name"; done

managed_root=$(mbr_validate_managed_root "$BACKUP_DESTINATION_DIR")
backup_class=${BACKUP_CLASS:-daily}
case "$backup_class" in daily|weekly|monthly|pre-change) ;; *) mbr_die 'invalid BACKUP_CLASS' ;; esac
class_dir="$managed_root/$backup_class"
for managed_dir in "$class_dir" "$managed_root/.locks" "$managed_root/logs"; do
    mbr_require_safe_managed_directory "$managed_dir"
done

operations_lock=${DATABASE_OPERATIONS_LOCK_FILE:-$managed_root/.locks/$MYSQL_DATABASE.operations.lock}
case "$operations_lock" in "$managed_root"/*) ;; *) mbr_die 'database operations lock must be inside the managed root' ;; esac
exec 9>"$operations_lock"
flock -n 9 || mbr_die 'another backup, retention, or migration operation holds the database lock'

availability_timeout=${MYSQL_AVAILABILITY_TIMEOUT_SECONDS:-60}
case "$availability_timeout" in ''|*[!0-9]*) mbr_die 'MYSQL_AVAILABILITY_TIMEOUT_SECONDS must be a non-negative integer' ;; esac
availability_deadline=$(( $(date +%s) + availability_timeout ))
database_identity=
while [ -z "$database_identity" ]; do
    database_identity=$(mysql --defaults-extra-file="$MYSQL_DEFAULTS_FILE" --host="$MYSQL_HOST" \
        --port="${MYSQL_PORT:-3306}" --batch --skip-column-names "$MYSQL_DATABASE" \
        -e 'SELECT DATABASE(), VERSION()' 2>/dev/null || true)
    [ -n "$database_identity" ] && break
    [ "$(date +%s)" -lt "$availability_deadline" ] || mbr_die 'expected MySQL source did not become available before timeout'
    sleep 2
done
actual_database=$(printf '%s\n' "$database_identity" | awk '{print $1}')
mysql_version=$(printf '%s\n' "$database_identity" | awk '{print $2}')
[ "$actual_database" = "$MYSQL_DATABASE" ] || mbr_die 'connected MySQL database identity does not match configuration'
expected_version_prefix=${MYSQL_EXPECTED_VERSION_PREFIX:-8.4.}
case "$mysql_version" in "$expected_version_prefix"*) ;; *) mbr_die 'MySQL source version is not compatible with the configured expectation' ;; esac

run_mode=${BACKUP_RUN_MODE:-manual}
case "$run_mode" in manual|scheduled) ;; *) mbr_die 'BACKUP_RUN_MODE must be manual or scheduled' ;; esac
local_date=$(TZ=America/Mexico_City date +%F)
if [ "$run_mode" = scheduled ]; then
    for metadata in "$managed_root/daily"/*/metadata.env; do
        [ -f "$metadata" ] || continue
        [ "$(mbr_metadata_value database_name "$metadata" 2>/dev/null || true)" = "$MYSQL_DATABASE" ] || continue
        [ "$(mbr_metadata_value run_mode "$metadata" 2>/dev/null || true)" = scheduled ] || continue
        [ "$(mbr_metadata_value schedule_local_date "$metadata" 2>/dev/null || true)" = "$local_date" ] || continue
        [ "$(mbr_metadata_value verification_status "$metadata" 2>/dev/null || true)" = BACKUP_VERIFIED ] || continue
        echo "scheduled backup already satisfied for $MYSQL_DATABASE on $local_date"
        exit 0
    done
fi

started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date +%s)
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
release=${RELEASE_ID:-unknown-release}
safe_release=$(printf '%s' "$release" | tr -cd 'A-Za-z0-9._-')
[ -n "$safe_release" ] || safe_release=unknown-release
backup_id="ecip_${MYSQL_DATABASE}_${timestamp}_${safe_release}_$$"
mbr_require_safe_token backup_id "$backup_id"
stage_dir="$class_dir/.partial-$backup_id"
final_dir="$class_dir/$backup_id"
[ ! -e "$final_dir" ] || mbr_die 'backup identifier already exists'
mkdir "$stage_dir"
chmod 700 "$stage_dir"

raw="$stage_dir/$backup_id.sql.partial"
compressed="$stage_dir/$backup_id.sql.gz.partial"
plain_name="$backup_id.sql.gz"
plain="$stage_dir/$plain_name"
status_file=${BACKUP_STATUS_FILE:-$managed_root/logs/last-backup.prom}

cleanup() { rm -rf -- "$stage_dir"; }
trap cleanup EXIT HUP INT TERM

publish_status() {
    if [ -n "${BACKUP_PUSHGATEWAY_URL:-}" ]; then
        curl --fail --silent --show-error --data-binary "@$status_file" "$BACKUP_PUSHGATEWAY_URL/metrics/job/ecip_backup"
    fi
}

if ! mysqldump --defaults-extra-file="$MYSQL_DEFAULTS_FILE" \
    --host="$MYSQL_HOST" --port="${MYSQL_PORT:-3306}" \
    --single-transaction --quick --routines --events --triggers \
    --set-gtid-purged=OFF --no-tablespaces "$MYSQL_DATABASE" > "$raw"; then
    printf 'ecip_backup_success 0\necip_backup_timestamp_seconds %s\n' "$(date +%s)" > "$status_file"
    publish_status || true
    mbr_die 'logical export failed'
fi
[ -s "$raw" ] || mbr_die 'logical export was empty'
gzip -9 -c "$raw" > "$compressed"
gzip -t "$compressed"
rm -f "$raw"
mv "$compressed" "$plain"

artifact_name=$plain_name
encryption=false
if [ -n "${BACKUP_ENCRYPTION_KEY_FILE:-}" ]; then
    mbr_require_private_file "$BACKUP_ENCRYPTION_KEY_FILE" 'backup encryption key file'
    artifact_name="$plain_name.enc"
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:$BACKUP_ENCRYPTION_KEY_FILE" -in "$plain" -out "$stage_dir/$artifact_name.partial"
    mv "$stage_dir/$artifact_name.partial" "$stage_dir/$artifact_name"
    rm -f "$plain"
    encryption=true
fi
artifact="$stage_dir/$artifact_name"
sha256=$(sha256sum "$artifact" | awk '{print $1}')
printf '%s  %s\n' "$sha256" "$artifact_name" > "$artifact.sha256"
(cd "$stage_dir" && sha256sum -c "$artifact_name.sha256" >/dev/null)
archive_size=$(stat -c '%s' "$artifact")
alembic_revision=$(mysql --defaults-extra-file="$MYSQL_DEFAULTS_FILE" --host="$MYSQL_HOST" \
    --port="${MYSQL_PORT:-3306}" --batch --skip-column-names \
    -e "SELECT version_num FROM \`$MYSQL_DATABASE\`.alembic_version LIMIT 1" 2>/dev/null || true)
source_container=${SOURCE_CONTAINER_IDENTITY:-unknown}
source_volume=${SOURCE_VOLUME_IDENTITY:-unknown}
for value in "$mysql_version" "$alembic_revision" "$source_container" "$source_volume"; do
    case "$value" in *'='*|*'
'*) mbr_die 'runtime metadata contains unsupported characters' ;; esac
done
completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
duration_seconds=$(( $(date +%s) - started_epoch ))
git_head=$(git -C "$script_dir/.." rev-parse HEAD 2>/dev/null || printf unknown)
cat > "$stage_dir/metadata.env" <<EOF
schema_version=1
backup_id=$backup_id
created_at_utc=$started_at
completed_at_utc=$completed_at
database_name=$MYSQL_DATABASE
source_container_identity=$source_container
source_volume_identity=$source_volume
mysql_version=$mysql_version
backup_class=$backup_class
run_mode=$run_mode
schedule_local_date=$local_date
archive_filename=$artifact_name
archive_size_bytes=$archive_size
sha256=$sha256
verification_status=BACKUP_VERIFIED
execution_result=SUCCESS
duration_seconds=$duration_seconds
git_head=$git_head
alembic_revision=$alembic_revision
encrypted=$encryption
EOF
printf 'BACKUP_VERIFIED\n' > "$stage_dir/result"
chmod 600 "$stage_dir"/*
mv "$stage_dir" "$final_dir"
trap - EXIT HUP INT TERM

printf 'ecip_backup_success 1\necip_backup_timestamp_seconds %s\n' "$(date +%s)" > "$status_file"
if [ -n "${BACKUP_UPLOAD_COMMAND:-}" ]; then
    BACKUP_ARTIFACT="$final_dir/$artifact_name" BACKUP_CHECKSUM="$final_dir/$artifact_name.sha256" sh -c "$BACKUP_UPLOAD_COMMAND"
fi
publish_status
if [ "${BACKUP_APPLY_RETENTION:-0}" = 1 ]; then
    BACKUP_DESTINATION_DIR="$managed_root" DATABASE_OPERATIONS_LOCK_FILE="$operations_lock" \
        RETENTION_LOCK_HELD=1 RETENTION_MODE=apply "$script_dir/mysql-backup-retention.sh"
fi
echo "backup complete: $final_dir"
