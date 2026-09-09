#!/bin/sh
set -eu
: "${PRODUCTION_ENV_FILE:?PRODUCTION_ENV_FILE is required}"

compose="docker compose --env-file $PRODUCTION_ENV_FILE -f compose.production.yaml"
$compose config --quiet
$compose pull api diner-web staff-web ingress prometheus alertmanager pushgateway
$compose up -d --no-build api diner-web staff-web prometheus alertmanager pushgateway ingress
$compose ps
echo 'verify HTTPS /health, /ready, /diner/, /staff/, then record image digests'
