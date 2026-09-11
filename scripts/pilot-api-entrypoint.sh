#!/bin/sh
set -eu

load_secret() {
  variable=$1
  eval "file_path=\${${variable}_FILE:-}"
  if [ -n "$file_path" ]; then
    [ -r "$file_path" ] || {
      echo "secret file for $variable is not readable" >&2
      exit 1
    }
    value=$(tr -d '\r\n' < "$file_path")
    [ -n "$value" ] || {
      echo "secret file for $variable is empty" >&2
      exit 1
    }
    export "$variable=$value"
    unset "${variable}_FILE"
  fi
}

stage_secret_file() {
  variable=$1
  eval "source_path=\${${variable}:-}"
  [ -n "$source_path" ] || return 0
  [ -r "$source_path" ] || {
    echo "secret file for $variable is not readable" >&2
    exit 1
  }
  destination=/run/pryecip-secrets/$(basename "$source_path")
  install -d -o ecip -g ecip -m 0700 /run/pryecip-secrets
  install -o ecip -g ecip -m 0400 "$source_path" "$destination"
  export "$variable=$destination"
}

load_secret MYSQL_PASSWORD
load_secret AUTH_JWT_SECRET
load_secret RESTAURANT_ACCESS_CODE_SECRET
load_secret CONEKTA_PRIVATE_KEY
stage_secret_file PILOT_ADMIN_PASSWORD_FILE
stage_secret_file PILOT_STAFF_PASSWORD_FILE

exec setpriv --reuid=ecip --regid=ecip --init-groups "$@"
