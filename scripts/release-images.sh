#!/bin/sh
set -eu

action=${1:-build}
case "$action" in build|publish) ;; *) echo "usage: $0 [build|publish]" >&2; exit 2 ;; esac

git diff --quiet && git diff --cached --quiet || {
    echo 'release image builds require a clean certified commit' >&2
    exit 1
}

commit=$(git rev-parse --verify HEAD)
case "$commit" in *[!0-9a-f]*|'') echo "invalid Git commit identity" >&2; exit 1 ;; esac
tag="git-$commit"
registry=${REGISTRY:?REGISTRY is required}
namespace=${REGISTRY_NAMESPACE:?REGISTRY_NAMESPACE is required}

build_image() {
    name=$1
    context=$2
    image="$registry/$namespace/$name:$tag"
    docker build --pull --label "org.opencontainers.image.revision=$commit" -t "$image" "$context"
    digest=$(docker image inspect "$image" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)
    printf '%s\t%s\t%s\n' "$name" "$image" "${digest:-digest-available-after-push}"
    if [ "$action" = publish ]; then docker push "$image"; docker image inspect "$image" --format '{{index .RepoDigests 0}}'; fi
}

build_image restaurant-api apps/api
build_image restaurant-diner-web apps/diner-web
build_image restaurant-staff-web apps/staff-web
build_image restaurant-local-connector connectors/restaurant_local_connector
build_image restaurant-ingress deploy/ingress

printf 'release_id=%s\n' "$tag"
