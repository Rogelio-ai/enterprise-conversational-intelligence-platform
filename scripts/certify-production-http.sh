#!/bin/sh
set -eu

origin=${CERTIFICATION_ORIGIN:-https://127.0.0.1:18443}
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/ecip-http-cert.XXXXXX")
cleanup() { rm -rf "$work_dir"; }
trap cleanup EXIT HUP INT TERM

request() {
    path=$1
    expected=$2
    name=$3
    status=$(curl --insecure --silent --show-error --dump-header "$work_dir/$name.headers" \
        --output "$work_dir/$name.body" --write-out '%{http_code}' "$origin$path")
    [ "$status" = "$expected" ] || { echo "$path expected $expected, received $status" >&2; exit 1; }
    echo "$path: $status"
}

request /health 200 health
request /ready 200 ready
request /api/health 200 api
request /diner/ 200 diner
request /diner/deep/spa/path 200 diner_spa
request /staff/ 200 staff
request /staff/deep/spa/path 200 staff_spa
request /metrics 404 metrics
request /docs 404 docs
request /openapi.json 404 openapi

grep -qi '^Strict-Transport-Security:' "$work_dir/health.headers"
grep -qi '^Content-Security-Policy:' "$work_dir/health.headers"
grep -qi '^X-Content-Type-Options: nosniff' "$work_dir/health.headers"
grep -qi '/diner/assets/' "$work_dir/diner.body"
grep -qi '/staff/assets/' "$work_dir/staff.body"
grep -q '"status":"ready"' "$work_dir/ready.body"
echo 'HTTPS routing, SPA fallback, API readiness, and perimeter checks: PASS'
