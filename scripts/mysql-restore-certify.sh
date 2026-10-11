#!/bin/sh
set -eu
umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$script_dir/mysql-backup-common.sh"

: "${BACKUP_SET_DIR:?BACKUP_SET_DIR is required}"
: "${SOURCE_CONTAINER:?SOURCE_CONTAINER is required}"
: "${SOURCE_VOLUME:?SOURCE_VOLUME is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
mbr_require_safe_token SOURCE_CONTAINER "$SOURCE_CONTAINER"
mbr_require_safe_token SOURCE_VOLUME "$SOURCE_VOLUME"
mbr_require_safe_token MYSQL_DATABASE "$MYSQL_DATABASE"
case "$SOURCE_CONTAINER" in pryecip-stagea1-candidate-mysql-20261009) mbr_die 'Stage A1 is not an authorized P03 backup source' ;; esac
for protected in pryecip_mysql-data pryecip-stagea1-candidate-data-20261009 pryecip-prepilot_mysql-pilot-data pryecip-prepilot_mysql-restore-data pryecip_recovery_mysql-data; do
    [ "$SOURCE_VOLUME" != "$protected" ] || [ "$SOURCE_CONTAINER" = pryecip-mysql-1 ] || mbr_die 'protected historical volume/source pairing rejected'
done
for command_name in docker gzip sha256sum openssl; do mbr_require_command "$command_name"; done
docker compose version >/dev/null
mbr_require_verified_set "$BACKUP_SET_DIR"
metadata="$BACKUP_SET_DIR/metadata.env"
[ "$(mbr_metadata_value database_name "$metadata")" = "$MYSQL_DATABASE" ] || mbr_die 'backup database identity does not match requested source'
metadata_container=$(mbr_metadata_value source_container_identity "$metadata")
metadata_volume=$(mbr_metadata_value source_volume_identity "$metadata")
[ "$metadata_container" = "$SOURCE_CONTAINER" ] || mbr_die 'backup source container metadata does not match'
[ "$metadata_volume" = "$SOURCE_VOLUME" ] || mbr_die 'backup source volume metadata does not match'

source_id=$(docker inspect "$SOURCE_CONTAINER" --format '{{.Id}}')
source_image=$(docker inspect "$SOURCE_CONTAINER" --format '{{.Config.Image}}')
mounted_volume=$(docker inspect "$SOURCE_CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}')
[ "$mounted_volume" = "$SOURCE_VOLUME" ] || mbr_die 'source container does not mount the expected source volume'

run_id="mysql-restore-cert-$(date -u +%Y%m%dT%H%M%SZ)-$$"
project=$(printf '%s' "$run_id" | tr 'A-Z_' 'a-z-')
case "$project" in pryecip|pryecip-stagea1-candidate|pryecip-prepilot) mbr_die 'unsafe certification project name' ;; esac
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/mysql-restore-cert.XXXXXX")
password_file="$work_dir/root-password"
openssl rand -hex 24 > "$password_file"
chmod 600 "$password_file"
export MYSQL_CERTIFICATION_PROJECT=$project
export MYSQL_CERTIFICATION_DATABASE=$MYSQL_DATABASE
export MYSQL_CERTIFICATION_ROOT_PASSWORD_FILE=$password_file
compose_file="$repo_root/compose.mysql-restore-certification.yaml"
resources_started=false
cleanup_result=NOT_STARTED

cert_compose() {
    docker compose --project-name "$project" --file "$compose_file" "$@"
}

cleanup() {
    if [ "$resources_started" = true ]; then
        if cert_compose down --volumes --remove-orphans >/dev/null 2>&1; then
            cleanup_result=PASS
        else
            cleanup_result=FAIL
            echo "isolated restore cleanup failed: project=$project container=${target_container:-unknown} volume=${target_mount:-${project}_data}" >&2
        fi
    fi
    rm -rf -- "$work_dir"
}
trap cleanup EXIT HUP INT TERM

source_query() {
    sql=$1
    docker exec "$SOURCE_CONTAINER" sh -c \
        'MYSQL_PWD="$MYSQL_PASSWORD" mysql --batch --skip-column-names -u"$MYSQL_USER" "$MYSQL_DATABASE" -e "$1"' sh "$sql"
}

data_count_sql="SET SESSION group_concat_max_len=1000000; SELECT GROUP_CONCAT(CONCAT('SELECT ''', REPLACE(table_name,'''',''''''), ''' AS table_name, COUNT(*) AS row_count FROM ', CHAR(96), REPLACE(table_name,CHAR(96),CONCAT(CHAR(96),CHAR(96))), CHAR(96)) ORDER BY table_name SEPARATOR ' UNION ALL ') INTO @q FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'; PREPARE s FROM @q; EXECUTE s; DEALLOCATE PREPARE s"

source_snapshot() {
    destination=$1
    source_version=$(source_query 'SELECT VERSION()')
    source_revision=$(source_query 'SELECT version_num FROM alembic_version LIMIT 1')
    source_tables=$(source_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'")
    source_objects=$(source_query "SELECT CONCAT((SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.events WHERE event_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND constraint_type='FOREIGN KEY'),':',(SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE()))")
    source_query "$data_count_sql" | sha256sum | awk '{print $1}' > "$work_dir/source-data-hash"
    {
        printf 'container_id=%s\n' "$source_id"
        printf 'container_image=%s\n' "$source_image"
        printf 'volume=%s\n' "$mounted_volume"
        printf 'mysql_version=%s\n' "$source_version"
        printf 'alembic_revision=%s\n' "$source_revision"
        printf 'base_table_count=%s\n' "$source_tables"
        printf 'object_counts=%s\n' "$source_objects"
        printf 'data_count_hash=%s\n' "$(cat "$work_dir/source-data-hash")"
    } > "$destination"
}

source_snapshot "$work_dir/source-before"
artifact_name=$(mbr_metadata_value archive_filename "$metadata")
artifact="$BACKUP_SET_DIR/$artifact_name"
(cd "$BACKUP_SET_DIR" && sha256sum -c "$artifact_name.sha256")
compressed=$artifact
case "$artifact" in
    *.enc)
        : "${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required for encrypted backup}"
        compressed="$work_dir/restore.sql.gz"
        openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
            -pass "file:$BACKUP_ENCRYPTION_KEY_FILE" -in "$artifact" -out "$compressed"
        ;;
esac
gzip -t "$compressed"

cert_compose config --quiet
cert_compose up --detach --wait mysql
resources_started=true
target_container=$(cert_compose ps --quiet mysql)
[ -n "$target_container" ] || mbr_die 'isolated restore container was not created'
[ "$target_container" != "$source_id" ] || mbr_die 'restore target resolved to the source container'
target_mount=$(docker inspect "$target_container" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}')
case "$target_mount" in "$project"*) ;; *) mbr_die 'restore target volume is not owned by the unique certification project' ;; esac
for protected in pryecip_mysql-data pryecip-stagea1-candidate-data-20261009 pryecip-prepilot_mysql-pilot-data pryecip-prepilot_mysql-restore-data pryecip_recovery_mysql-data; do
    [ "$target_mount" != "$protected" ] || mbr_die 'restore target resolved to a protected volume'
done
[ -z "$(docker port "$target_container")" ] || mbr_die 'restore target unexpectedly publishes a host port'

gzip -dc "$compressed" | cert_compose exec --no-TTY mysql sh -c \
    'MYSQL_PWD="$(cat /run/secrets/root_password)" mysql -uroot "$MYSQL_DATABASE"'
target_query() {
    sql=$1
    cert_compose exec --no-TTY mysql sh -c \
        'MYSQL_PWD="$(cat /run/secrets/root_password)" mysql --batch --skip-column-names -uroot "$MYSQL_DATABASE" -e "$1"' sh "$sql"
}
target_version=$(target_query 'SELECT VERSION()')
target_revision=$(target_query 'SELECT version_num FROM alembic_version LIMIT 1')
target_tables=$(target_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'")
target_objects=$(target_query "SELECT CONCAT((SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.events WHERE event_schema=DATABASE()),':',(SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND constraint_type='FOREIGN KEY'),':',(SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE()))")
target_query "$data_count_sql" | sha256sum | awk '{print $1}' > "$work_dir/target-data-hash"
[ "$target_revision" = "$(mbr_metadata_value alembic_revision "$metadata")" ] || mbr_die 'restored Alembic revision does not match backup metadata'
[ "$target_tables" = "$(awk -F= '$1=="base_table_count" {print $2}' "$work_dir/source-before")" ] || mbr_die 'restored base-table count differs from source'
[ "$target_objects" = "$(awk -F= '$1=="object_counts" {print $2}' "$work_dir/source-before")" ] || mbr_die 'restored schema-object counts differ from source'
[ "$(cat "$work_dir/target-data-hash")" = "$(cat "$work_dir/source-data-hash")" ] || mbr_die 'restored representative table counts differ from source'

source_snapshot "$work_dir/source-after"
cmp -s "$work_dir/source-before" "$work_dir/source-after" || mbr_die 'source identity, schema, revision, or representative counts changed'
cert_compose down --volumes --remove-orphans
resources_started=false
cleanup_result=PASS

evidence_dir="$BACKUP_SET_DIR/restore-certifications"
mkdir -p "$evidence_dir"
evidence_tmp="$evidence_dir/.partial-$run_id.env"
artifact_sha=$(mbr_metadata_value sha256 "$metadata")
cat > "$evidence_tmp" <<EOF
schema_version=1
certification_id=$run_id
backup_id=$(mbr_metadata_value backup_id "$metadata")
backup_sha256=$artifact_sha
started_source_container_id=$source_id
source_volume=$SOURCE_VOLUME
source_mysql_version=$(awk -F= '$1=="mysql_version" {print $2}' "$work_dir/source-before")
source_alembic_revision=$(awk -F= '$1=="alembic_revision" {print $2}' "$work_dir/source-before")
restored_mysql_version=$target_version
restored_alembic_revision=$target_revision
base_table_count=$target_tables
schema_object_counts=$target_objects
representative_data_count_hash=$(cat "$work_dir/target-data-hash")
source_preservation=PASS
cleanup=PASS
result=RESTORE_CERTIFIED
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 600 "$evidence_tmp"
mv "$evidence_tmp" "$evidence_dir/$run_id.env"
printf '%s\n' "$run_id" > "$BACKUP_SET_DIR/KNOWN_GOOD"
chmod 600 "$BACKUP_SET_DIR/KNOWN_GOOD"
trap - EXIT HUP INT TERM
rm -rf -- "$work_dir"
echo "isolated restore certified: $evidence_dir/$run_id.env"
