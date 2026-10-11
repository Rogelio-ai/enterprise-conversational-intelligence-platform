#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/mysql-backup-tests.XXXXXX")
cleanup() { rm -rf -- "$test_root"; }
trap cleanup EXIT HUP INT TERM

pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok %s - %s\n' "$pass" "$1"; }
not_ok() { fail=$((fail + 1)); printf 'not ok %s - %s\n' "$((pass + fail))" "$1" >&2; }
assert() { name=$1; shift; if "$@"; then ok "$name"; else not_ok "$name"; fi; }
expect_failure() { "$@" >/dev/null 2>&1 && return 1; return 0; }

mock_bin="$test_root/bin"
mkdir "$mock_bin"
cat > "$mock_bin/mysqldump" <<'EOF'
#!/bin/sh
[ "${MOCK_DUMP_FAIL:-0}" != 1 ] || exit 7
printf '%s\n' 'CREATE TABLE sample (id INT PRIMARY KEY);' 'INSERT INTO sample VALUES (1);'
EOF
cat > "$mock_bin/mysql" <<'EOF'
#!/bin/sh
case "$*" in
    *'SELECT DATABASE(), VERSION()'*) printf 'ecip\t8.4.8\n' ;;
    *'version_num'*) printf '0067_internal_operational_message_foundation\n' ;;
    *) cat >/dev/null; [ "${MOCK_IMPORT_FAIL:-0}" != 1 ] || exit 9 ;;
esac
EOF
chmod +x "$mock_bin/mysqldump" "$mock_bin/mysql"

credentials="$test_root/client.cnf"
printf '[client]\nuser=test\npassword=test-only\n' > "$credentials"
chmod 600 "$credentials"
backup_root="$test_root/backups"

run_backup() {
    PATH="$mock_bin:$PATH" MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 \
        MYSQL_DATABASE=ecip BACKUP_DESTINATION_DIR="$backup_root" RELEASE_ID=test \
        SOURCE_CONTAINER_IDENTITY=test-source SOURCE_VOLUME_IDENTITY=test-volume "$repo_root/scripts/mysql-backup.sh"
}

output=$(run_backup)
set_dir=${output#backup complete: }
metadata="$set_dir/metadata.env"
artifact_name=$(awk -F= '$1=="archive_filename" {print $2}' "$metadata")
assert 'verified backup set is atomically published' test -f "$set_dir/result"
assert 'metadata reports BACKUP_VERIFIED' grep -qx 'verification_status=BACKUP_VERIFIED' "$metadata"
assert 'published checksum verifies' sh -c "cd '$set_dir' && sha256sum -c '$artifact_name.sha256' >/dev/null"
assert 'published archive passes gzip integrity' gzip -t "$set_dir/$artifact_name"
assert 'no partial set is published' sh -c "! find '$backup_root' -name '.partial-*' -print -quit | grep -q ."
assert 'backup set directory is owner-only' test "$(stat -c '%a' "$set_dir")" = 700
assert 'backup metadata is owner-only' test "$(stat -c '%a' "$metadata")" = 600

scheduled_first=$(PATH="$mock_bin:$PATH" MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 \
    MYSQL_DATABASE=ecip BACKUP_DESTINATION_DIR="$backup_root" RELEASE_ID=scheduled BACKUP_RUN_MODE=scheduled \
    SOURCE_CONTAINER_IDENTITY=test-source SOURCE_VOLUME_IDENTITY=test-volume "$repo_root/scripts/mysql-backup.sh")
scheduled_second=$(PATH="$mock_bin:$PATH" MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 \
    MYSQL_DATABASE=ecip BACKUP_DESTINATION_DIR="$backup_root" RELEASE_ID=scheduled BACKUP_RUN_MODE=scheduled \
    SOURCE_CONTAINER_IDENTITY=test-source SOURCE_VOLUME_IDENTITY=test-volume "$repo_root/scripts/mysql-backup.sh")
assert 'duplicate scheduled run is a successful no-op' sh -c "printf '%s' '$scheduled_second' | grep -q 'already satisfied'"

lock="$backup_root/.locks/ecip.operations.lock"
( flock -n 8; sleep 3 ) 8>"$lock" & lock_pid=$!
sleep 0.2
assert 'overlapping backup is rejected' expect_failure run_backup
wait "$lock_pid"

before_sets=$(find "$backup_root/daily" -mindepth 1 -maxdepth 1 -type d | wc -l)
assert 'failed dump exits nonzero' expect_failure env PATH="$mock_bin:$PATH" MOCK_DUMP_FAIL=1 \
    MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_DESTINATION_DIR="$backup_root" RELEASE_ID=failure "$repo_root/scripts/mysql-backup.sh"
after_sets=$(find "$backup_root/daily" -mindepth 1 -maxdepth 1 -type d | wc -l)
assert 'failed dump publishes no backup set' test "$before_sets" = "$after_sets"

checksum_bin="$test_root/checksum-bin"
mkdir "$checksum_bin"
ln -s "$mock_bin/mysqldump" "$checksum_bin/mysqldump"
ln -s "$mock_bin/mysql" "$checksum_bin/mysql"
cat > "$checksum_bin/sha256sum" <<'EOF'
#!/bin/sh
exit 8
EOF
chmod +x "$checksum_bin/sha256sum"
assert 'checksum failure exits nonzero' expect_failure env PATH="$checksum_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_DESTINATION_DIR="$backup_root" RELEASE_ID=checksum-failure "$repo_root/scripts/mysql-backup.sh"
assert 'checksum failure publishes no backup set' test "$before_sets" = "$(find "$backup_root/daily" -mindepth 1 -maxdepth 1 -type d | wc -l)"

unavailable_bin="$test_root/unavailable-bin"
mkdir "$unavailable_bin"
ln -s "$mock_bin/mysqldump" "$unavailable_bin/mysqldump"
cat > "$unavailable_bin/mysql" <<'EOF'
#!/bin/sh
exit 10
EOF
chmod +x "$unavailable_bin/mysql"
assert 'unavailable source fails after bounded wait' expect_failure env PATH="$unavailable_bin:$PATH" \
    MYSQL_AVAILABILITY_TIMEOUT_SECONDS=0 MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=unavailable \
    MYSQL_DATABASE=ecip BACKUP_DESTINATION_DIR="$backup_root" "$repo_root/scripts/mysql-backup.sh"

chmod 644 "$credentials"
assert 'unsafe credential permissions are rejected' expect_failure run_backup
chmod 600 "$credentials"
assert 'repository destination is rejected' expect_failure env PATH="$mock_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_DESTINATION_DIR="$repo_root/test-backups" "$repo_root/scripts/mysql-backup.sh"

old_set="$backup_root/daily/old-verified-set"
cp -a "$set_dir" "$old_set"
touch -d '40 days ago' "$old_set"
unmanaged="$backup_root/daily/unmanaged"
mkdir "$unmanaged"
printf 'do not delete\n' > "$unmanaged/file"
BACKUP_DESTINATION_DIR="$backup_root" DAILY_RETENTION_DAYS=14 RETENTION_MODE=dry-run \
    "$repo_root/scripts/mysql-backup-retention.sh" >/dev/null
assert 'retention dry-run preserves eligible verified set' test -d "$old_set"
BACKUP_DESTINATION_DIR="$backup_root" DAILY_RETENTION_DAYS=14 RETENTION_MODE=apply \
    "$repo_root/scripts/mysql-backup-retention.sh" >/dev/null
assert 'retention deletes only eligible owned verified set' test ! -e "$old_set"
assert 'retention preserves unmanaged content' test -f "$unmanaged/file"
assert 'retention preserves at least one verified set' test -d "$set_dir"

unsafe_root="$test_root/unowned"
mkdir "$unsafe_root"
printf 'unmanaged\n' > "$unsafe_root/file"
assert 'retention rejects unowned existing destination' expect_failure env BACKUP_DESTINATION_DIR="$unsafe_root" \
    "$repo_root/scripts/mysql-backup-retention.sh"
ln -s "$backup_root" "$test_root/backup-link"
assert 'retention rejects symlink root' expect_failure env BACKUP_DESTINATION_DIR="$test_root/backup-link" \
    "$repo_root/scripts/mysql-backup-retention.sh"

restore_credentials="$test_root/restore.cnf"
cp "$credentials" "$restore_credentials"
rm "$set_dir/$artifact_name.sha256"
assert 'restore rejects incomplete set without checksum' expect_failure env PATH="$mock_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$restore_credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_ARTIFACT="$set_dir/$artifact_name" "$repo_root/scripts/mysql-restore.sh"
sha256sum "$set_dir/$artifact_name" | sed "s#  .*#  $artifact_name#" > "$set_dir/$artifact_name.sha256"
cp "$set_dir/$artifact_name" "$test_root/corrupt.sql.gz"
printf 'corruption\n' >> "$test_root/corrupt.sql.gz"
sha256sum "$set_dir/$artifact_name" | sed 's#  .*#  corrupt.sql.gz#' > "$test_root/corrupt.sql.gz.sha256"
assert 'restore rejects checksum mismatch' expect_failure env PATH="$mock_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$restore_credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_ARTIFACT="$test_root/corrupt.sql.gz" "$repo_root/scripts/mysql-restore.sh"
sha256sum "$test_root/corrupt.sql.gz" | sed 's#  .*#  corrupt.sql.gz#' > "$test_root/corrupt.sql.gz.sha256"
assert 'restore rejects corrupt gzip even with matching checksum' expect_failure env PATH="$mock_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$restore_credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_ARTIFACT="$test_root/corrupt.sql.gz" "$repo_root/scripts/mysql-restore.sh"
assert 'restore reports import failure' expect_failure env PATH="$mock_bin:$PATH" MOCK_IMPORT_FAIL=1 \
    MYSQL_DEFAULTS_FILE="$restore_credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_ARTIFACT="$set_dir/$artifact_name" "$repo_root/scripts/mysql-restore.sh"
assert 'restore rejects protected source target' expect_failure env PATH="$mock_bin:$PATH" \
    MYSQL_DEFAULTS_FILE="$restore_credentials" MYSQL_HOST=127.0.0.1 MYSQL_DATABASE=ecip \
    BACKUP_ARTIFACT="$set_dir/$artifact_name" RESTORE_TARGET_CONTAINER=pryecip-mysql-1 \
    "$repo_root/scripts/mysql-restore.sh"

docker_bin="$test_root/docker-bin"
mkdir "$docker_bin"
cat > "$docker_bin/docker" <<'EOF'
#!/bin/sh
case "$1" in
    inspect)
        case "$2" in
            test-source)
                case "$*" in *'.Mounts'*) printf 'test-volume\n' ;; *'.Config.Image'*) printf 'mysql:8.4\n' ;; *) printf 'source-container-id\n' ;; esac
                ;;
            fake-target-id) printf '%s_data\n' "$MYSQL_CERTIFICATION_PROJECT" ;;
        esac
        ;;
    port) exit 0 ;;
    exec)
        case "$*" in
            *'SELECT VERSION()'*) printf '8.4.8\n' ;;
            *'version_num'*) printf '0067_internal_operational_message_foundation\n' ;;
            *'information_schema.triggers'*) printf '0:0:0:0:1\n' ;;
            *'COUNT(*) FROM information_schema.tables'*) printf '1\n' ;;
            *'group_concat_max_len'*) printf 'sample\t1\n' ;;
        esac
        ;;
    compose)
        case "$*" in
            *' version') exit 0 ;;
            *' config --quiet') exit 0 ;;
            *' up --detach --wait mysql') exit 0 ;;
            *' ps --quiet mysql') printf 'fake-target-id\n' ;;
            *' exec --no-TTY mysql '*)
                case "$*" in
                    *'SELECT VERSION()'*) printf '8.4.8\n' ;;
                    *'version_num'*) printf '0067_internal_operational_message_foundation\n' ;;
                    *'information_schema.triggers'*) printf '0:0:0:0:1\n' ;;
                    *'COUNT(*) FROM information_schema.tables'*) printf '1\n' ;;
                    *'group_concat_max_len'*) printf 'sample\t1\n' ;;
                    *) cat >/dev/null ;;
                esac
                ;;
            *' down --volumes --remove-orphans') exit 41 ;;
            *) exit 0 ;;
        esac
        ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$docker_bin/docker"
cleanup_error="$test_root/cleanup-error.log"
if PATH="$docker_bin:$PATH" BACKUP_SET_DIR="$set_dir" SOURCE_CONTAINER=test-source \
    SOURCE_VOLUME=test-volume MYSQL_DATABASE=ecip "$repo_root/scripts/mysql-restore-certify.sh" \
    >"$test_root/cleanup-output.log" 2>"$cleanup_error"; then
    not_ok 'cleanup failure prevents false restore certification'
else
    assert 'cleanup failure prevents false restore certification' grep -q 'isolated restore cleanup failed: project=' "$cleanup_error"
    assert 'cleanup failure reports exact owned container' grep -q 'container=fake-target-id' "$cleanup_error"
fi

rendered_service="$test_root/pryecip-mysql-backup.service"
sed -e "s#@BACKUP_SERVICE_USER@#$(id -un)#" -e "s#@BACKUP_SERVICE_GROUP@#$(id -gn)#" \
    -e "s#@BACKUP_CONFIG_FILE@#$repo_root/deploy/systemd/mysql-backup.conf.example#" \
    -e "s#@INSTALL_ROOT@#$repo_root#" -e "s#@BACKUP_DESTINATION_DIR@#$backup_root#" \
    "$repo_root/deploy/systemd/pryecip-mysql-backup.service.in" > "$rendered_service"
assert 'systemd service and timer validate' systemd-analyze verify "$rendered_service" "$repo_root/deploy/systemd/pryecip-mysql-backup.timer"
assert 'timer is persistent' grep -qx 'Persistent=true' "$repo_root/deploy/systemd/pryecip-mysql-backup.timer"
assert 'timer uses approved timezone-qualified 03:00 schedule' grep -Fqx 'OnCalendar=*-*-* 03:00:00 America/Mexico_City' "$repo_root/deploy/systemd/pryecip-mysql-backup.timer"

printf '%s\n' "tests_passed=$pass" "tests_failed=$fail"
[ "$fail" -eq 0 ]
