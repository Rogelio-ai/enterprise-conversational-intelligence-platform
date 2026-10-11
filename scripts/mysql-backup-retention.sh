#!/bin/sh
set -eu
umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$script_dir/mysql-backup-common.sh"

: "${BACKUP_DESTINATION_DIR:?BACKUP_DESTINATION_DIR is required}"
managed_root=$(mbr_validate_managed_root "$BACKUP_DESTINATION_DIR")
mode=${RETENTION_MODE:-dry-run}
case "$mode" in dry-run|apply) ;; *) mbr_die 'RETENTION_MODE must be dry-run or apply' ;; esac
daily_days=${DAILY_RETENTION_DAYS:-14}
weekly_weeks=${WEEKLY_RETENTION_WEEKS:-8}
monthly_months=${MONTHLY_RETENTION_MONTHS:-12}
for value in "$daily_days" "$weekly_weeks" "$monthly_months"; do
    case "$value" in ''|*[!0-9]*) mbr_die 'retention values must be non-negative integers' ;; esac
done

if [ "${RETENTION_LOCK_HELD:-0}" != 1 ]; then
    mbr_require_command flock
    operations_lock=${DATABASE_OPERATIONS_LOCK_FILE:-$managed_root/.locks/retention.operations.lock}
    case "$operations_lock" in "$managed_root"/*) ;; *) mbr_die 'retention lock must be inside the managed root' ;; esac
    mbr_require_safe_managed_directory "$managed_root/.locks"
    exec 9>"$operations_lock"
    flock -n 9 || mbr_die 'another backup or retention operation holds the lock'
fi

now=$(date +%s)
weekly_seconds=$(( weekly_weeks * 7 * 86400 ))
daily_seconds=$(( daily_days * 86400 ))
monthly_cutoff=$(date -u -d "$monthly_months months ago" +%s)
result_log="$managed_root/logs/retention-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
mbr_require_safe_managed_directory "$managed_root/logs"

printf 'mode=%s\n' "$mode" > "$result_log"
for class in daily weekly monthly; do
    class_dir="$managed_root/$class"
    [ -d "$class_dir" ] || continue
    [ ! -L "$class_dir" ] || mbr_die "retention class is a symbolic link: $class"
    newest=
    newest_time=0
    for set_dir in "$class_dir"/*; do
        [ -d "$set_dir" ] || continue
        [ ! -L "$set_dir" ] || continue
        if (mbr_require_verified_set "$set_dir") 2>/dev/null; then
            set_time=$(stat -c '%Y' "$set_dir")
            if [ "$set_time" -gt "$newest_time" ]; then newest=$set_dir; newest_time=$set_time; fi
        fi
    done
    for set_dir in "$class_dir"/*; do
        [ -d "$set_dir" ] || continue
        [ ! -L "$set_dir" ] || { printf 'retained_unsafe=%s\n' "$set_dir" >> "$result_log"; continue; }
        if ! (mbr_require_verified_set "$set_dir") 2>/dev/null; then
            printf 'retained_unmanaged_or_incomplete=%s\n' "$set_dir" >> "$result_log"
            continue
        fi
        [ "$set_dir" != "$newest" ] || { printf 'retained_last_verified=%s\n' "$set_dir" >> "$result_log"; continue; }
        [ ! -f "$set_dir/KNOWN_GOOD" ] || { printf 'retained_known_good=%s\n' "$set_dir" >> "$result_log"; continue; }
        set_time=$(stat -c '%Y' "$set_dir")
        eligible=false
        case "$class" in
            daily) [ $((now - set_time)) -gt "$daily_seconds" ] && eligible=true ;;
            weekly) [ $((now - set_time)) -gt "$weekly_seconds" ] && eligible=true ;;
            monthly) [ "$set_time" -lt "$monthly_cutoff" ] && eligible=true ;;
        esac
        if [ "$eligible" = true ]; then
            printf 'eligible=%s\n' "$set_dir" >> "$result_log"
            if [ "$mode" = apply ]; then
                rm -rf -- "$set_dir"
                printf 'deleted=%s\n' "$set_dir" >> "$result_log"
            fi
        else
            printf 'retained_policy=%s\n' "$set_dir" >> "$result_log"
        fi
    done
done
printf 'result=SUCCESS\n' >> "$result_log"
chmod 600 "$result_log"
echo "retention $mode complete: $result_log"
