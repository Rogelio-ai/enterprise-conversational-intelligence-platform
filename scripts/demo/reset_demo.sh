#!/usr/bin/env sh
set -eu

if [ "${DEMO_ENV:-}" != "demo" ]; then
  echo 'REFUSED: run with DEMO_ENV=demo; no default is accepted.' >&2
  exit 64
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repo_dir/compose.demo.yaml"

if [ ! -f "$compose_file" ] || ! grep -q '^name: pryecip-demo$' "$compose_file"; then
  echo 'REFUSED: the isolated pryecip-demo Compose boundary was not found.' >&2
  exit 65
fi

cd "$repo_dir"
docker compose -f "$compose_file" down --volumes --remove-orphans
docker compose -f "$compose_file" up -d --build
