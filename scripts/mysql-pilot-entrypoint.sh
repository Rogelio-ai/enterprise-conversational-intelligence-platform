#!/bin/sh
set -eu

[ -r /run/secrets/mysql_password ] || {
  echo 'runtime MySQL password secret is not readable' >&2
  exit 1
}
[ -r /run/secrets/mysql_migration_password ] || {
  echo 'migration MySQL password secret is not readable' >&2
  exit 1
}
[ -r /run/secrets/mysql_root_password ] || {
  echo 'root MySQL password secret is not readable' >&2
  exit 1
}
runtime_password=$(tr -d '\r\n' < /run/secrets/mysql_password)
migration_password=$(tr -d '\r\n' < /run/secrets/mysql_migration_password)
root_password=$(tr -d '\r\n' < /run/secrets/mysql_root_password)
[ -n "$runtime_password" ] || {
  echo 'runtime MySQL password secret is empty' >&2
  exit 1
}
[ -n "$migration_password" ] || {
  echo 'migration MySQL password secret is empty' >&2
  exit 1
}
[ -n "$root_password" ] || {
  echo 'root MySQL password secret is empty' >&2
  exit 1
}
case "$runtime_password:$migration_password:$root_password" in
  *[!A-Fa-f0-9:]* )
    echo 'pilot MySQL passwords must be generated hexadecimal data' >&2
    exit 1
    ;;
esac

umask 077
mkdir -p /var/run/mysqld
chown mysql:mysql /var/run/mysqld
rm -f /var/run/mysqld/ecip-runtime-password
if [ ! -d /var/lib/mysql/mysql ]; then
  printf '%s' "$runtime_password" > /var/run/mysqld/ecip-runtime-password
  chown mysql:mysql /var/run/mysqld/ecip-runtime-password
fi
printf '[client]\nuser=%s\npassword=%s\n' "$MYSQL_USER" "$migration_password" \
  > /run/ecip-migration.cnf
printf '[client]\nuser=root\npassword=%s\n' "$root_password" > /run/ecip-root.cnf
rm -f /var/lib/mysql/.ecip-migration.cnf
unset runtime_password migration_password root_password

exec /usr/local/bin/docker-entrypoint.sh "$@"
