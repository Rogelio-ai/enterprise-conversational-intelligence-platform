#!/usr/bin/env sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repo_dir/compose.demo.yaml"

if [ ! -f "$compose_file" ] || ! grep -q '^name: pryecip-demo$' "$compose_file"; then
  echo 'REFUSED: the isolated pryecip-demo Compose boundary was not found.' >&2
  exit 65
fi

cd "$repo_dir"
docker compose -f "$compose_file" up -d --build
