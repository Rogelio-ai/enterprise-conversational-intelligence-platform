#!/bin/sh
set -eu

failed=0
for tracked in $(git ls-files); do
    case "$tracked" in
        *.pem|*.key|*.p12|*.pfx|*.sql|*.dump|*.backup|*.sqlite|*.sqlite3|.env|.env.*)
            [ "$tracked" = .env.example ] || { echo "forbidden tracked artifact category: $tracked" >&2; failed=1; }
            ;;
    esac
done

if git grep -IEn '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|sk_(live|test)_[A-Za-z0-9]{16,})' -- . ':!scripts/verify-release-artifacts.sh'; then
    echo 'credential-like material detected' >&2
    failed=1
fi

for image in ${API_IMAGE:-} ${DINER_WEB_IMAGE:-} ${STAFF_WEB_IMAGE:-} ${CONNECTOR_IMAGE:-} ${INGRESS_IMAGE:-}; do
    [ -z "$image" ] && continue
    case "$image" in *:latest|*:latest@*) echo "latest is forbidden: $image" >&2; failed=1 ;; esac
done

[ "$failed" -eq 0 ] || exit 1
echo 'release artifact and bounded secret check: PASS'
