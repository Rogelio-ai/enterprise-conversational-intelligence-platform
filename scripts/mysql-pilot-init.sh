#!/bin/sh
set -eu

[ -r /var/run/mysqld/ecip-runtime-password ] || {
  echo 'runtime MySQL password secret is not readable' >&2
  exit 1
}
runtime_password=$(tr -d '\r\n' < /var/run/mysqld/ecip-runtime-password)
runtime_user=${MYSQL_RUNTIME_USER:?MYSQL_RUNTIME_USER is required}
database=${MYSQL_DATABASE:?MYSQL_DATABASE is required}

cleanup() {
  rm -f /var/run/mysqld/ecip-runtime-password
}
trap cleanup EXIT HUP INT TERM

[ -n "$runtime_password" ] || {
  echo 'runtime MySQL password secret is empty' >&2
  exit 1
}

case "$runtime_user:$database" in
  *[!A-Za-z0-9_:-]*)
    echo 'pilot MySQL identifiers must be alphanumeric, underscore, or hyphen' >&2
    exit 1
    ;;
esac
case "$runtime_password" in
  *[!A-Fa-f0-9]*)
    echo 'pilot MySQL runtime password must be generated hexadecimal data' >&2
    exit 1
    ;;
esac

MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql --protocol=socket -uroot <<SQL
CREATE USER IF NOT EXISTS '$runtime_user'@'%' IDENTIFIED BY '$runtime_password';
ALTER USER '$runtime_user'@'%' IDENTIFIED BY '$runtime_password';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON \`$database\`.* TO '$runtime_user'@'%';
FLUSH PRIVILEGES;
SQL
