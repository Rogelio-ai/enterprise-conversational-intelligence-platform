#!/bin/sh

mbr_die() {
    echo "mysql backup/recovery: $*" >&2
    exit 1
}

mbr_require_command() {
    command -v "$1" >/dev/null 2>&1 || mbr_die "required command is unavailable: $1"
}

mbr_require_private_file() {
    [ -r "$1" ] || mbr_die "$2 is not readable"
    mode=$(stat -c '%a' "$1")
    case "$mode" in 400|600) ;; *) mbr_die "$2 permissions must be 0400 or 0600" ;; esac
}

mbr_require_safe_token() {
    case "$2" in
        ''|*[!A-Za-z0-9._-]*) mbr_die "$1 contains unsupported characters" ;;
    esac
}

mbr_canonical_directory() {
    [ -d "$1" ] || mbr_die "directory does not exist: $1"
    readlink -f -- "$1"
}

mbr_validate_managed_root() {
    root_input=$1
    case "$root_input" in
        /*) ;;
        *) mbr_die 'BACKUP_DESTINATION_DIR must be an absolute path' ;;
    esac
    case "$root_input" in
        *'/../'*|*/..|*'/./'*|*/.) mbr_die 'backup root must not contain dot path components' ;;
    esac

    if [ ! -e "$root_input" ]; then
        old_umask=$(umask)
        umask 077
        mkdir -p -- "$root_input"
        umask "$old_umask"
    fi
    [ ! -L "$root_input" ] || mbr_die 'backup root must not be a symbolic link'
    root=$(mbr_canonical_directory "$root_input")
    lexical_root=${root_input%/}
    [ "$root" = "$lexical_root" ] || mbr_die 'backup root must not traverse symbolic links or aliases'
    case "$root" in
        /|/home|/tmp|/var|/var/lib|/var/lib/mysql) mbr_die "backup root is too broad or protected: $root" ;;
        /var/lib/mysql/*) mbr_die "backup root is inside protected MySQL storage: $root" ;;
    esac

    repository_root=${MBR_REPOSITORY_ROOT:-}
    if [ -z "$repository_root" ] && command -v git >/dev/null 2>&1; then
        repository_root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)
    fi
    if [ -n "$repository_root" ]; then
        repository_root=$(readlink -f -- "$repository_root")
        case "$root/" in "$repository_root/"*) mbr_die 'backup root must be outside the repository' ;; esac
    fi

    marker="$root/.mysql-backup-root"
    if [ ! -e "$marker" ]; then
        if find "$root" -mindepth 1 -maxdepth 1 ! -name '.mysql-backup-root' -print -quit | grep -q .; then
            mbr_die 'existing backup root is not capability-owned (ownership marker missing)'
        fi
        printf 'mysql-backup-recovery-v1\n' > "$marker"
    fi
    [ ! -L "$marker" ] || mbr_die 'managed-root marker must not be a symbolic link'
    [ "$(cat "$marker")" = 'mysql-backup-recovery-v1' ] || mbr_die 'managed-root marker is invalid'
    chmod 700 "$root"
    chmod 600 "$marker"
    printf '%s\n' "$root"
}

mbr_require_safe_managed_directory() {
    directory=$1
    [ ! -L "$directory" ] || mbr_die "managed directory must not be a symbolic link: $directory"
    mkdir -p -- "$directory"
    [ -d "$directory" ] && [ ! -L "$directory" ] || mbr_die "managed directory is unsafe: $directory"
    chmod 700 "$directory"
}

mbr_metadata_value() {
    key=$1
    file=$2
    awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; found=1; exit } END { if (!found) exit 1 }' "$file"
}

mbr_require_verified_set() {
    set_dir=$1
    [ -d "$set_dir" ] || mbr_die "backup set is not a directory: $set_dir"
    [ ! -L "$set_dir" ] || mbr_die 'backup set must not be a symbolic link'
    metadata="$set_dir/metadata.env"
    [ -f "$metadata" ] && [ ! -L "$metadata" ] || mbr_die 'backup metadata is missing or unsafe'
    [ "$(mbr_metadata_value schema_version "$metadata")" = '1' ] || mbr_die 'unsupported backup metadata version'
    [ "$(mbr_metadata_value verification_status "$metadata")" = 'BACKUP_VERIFIED' ] || mbr_die 'backup set is not verified'
    artifact_name=$(mbr_metadata_value archive_filename "$metadata") || mbr_die 'backup artifact metadata is missing'
    mbr_require_safe_token archive_filename "$artifact_name"
    artifact="$set_dir/$artifact_name"
    [ -f "$artifact" ] && [ ! -L "$artifact" ] || mbr_die 'backup artifact is missing or unsafe'
    [ -f "$artifact.sha256" ] && [ ! -L "$artifact.sha256" ] || mbr_die 'backup checksum is missing or unsafe'
}
