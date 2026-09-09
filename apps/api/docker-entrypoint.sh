#!/bin/sh
set -eu

load_secret() {
    variable="$1"
    file_variable="${variable}_FILE"
    eval "file_path=\${$file_variable:-}"
    if [ -n "$file_path" ]; then
        [ -r "$file_path" ] || { echo "secret file for $variable is not readable" >&2; exit 1; }
        value=$(tr -d '\r\n' < "$file_path")
        [ -n "$value" ] || { echo "secret file for $variable is empty" >&2; exit 1; }
        export "$variable=$value"
        unset "$file_variable"
    fi
}

load_secret MYSQL_PASSWORD
load_secret AUTH_JWT_SECRET
load_secret RESTAURANT_ACCESS_CODE_SECRET
load_secret CONEKTA_PRIVATE_KEY

exec "$@"
