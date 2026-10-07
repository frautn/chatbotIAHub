#!/usr/bin/env bash
# Removes containers/networks started by start-dev.sh (Open WebUI, Moodle dev
# via moodle-docker, LTI gateway, PostgreSQL). Volumes (databases, uploads) are
# kept unless --volumes is given. Separate from remove.sh, which only knows
# about the production docker-compose-moodle.yml.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

args=(--remove-orphans)
case "${1:-}" in
  "") ;;
  --volumes)
    printf 'This will DELETE all project volumes (databases, uploads, Moodle dev data).\n'
    read -r -p 'Type "delete" to continue: ' answer
    [[ "$answer" == "delete" ]] || { printf 'Aborted.\n'; exit 1; }
    args+=(--volumes)
    ;;
  *)
    printf 'Usage: %s [--volumes]\n' "$0" >&2
    exit 2
    ;;
esac

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# The LTI compose file requires these variables even for "down"; placeholders are fine here.
export LTI_PUBLIC_URL="${LTI_PUBLIC_URL:-https://unused}"
export LTI_GATEWAY_SECRET_KEY="${LTI_GATEWAY_SECRET_KEY:-unused}"

for name in lti openwebui postgres; do
  docker compose -f "$script_dir/docker-compose-$name.yml" down "${args[@]}"
done

MOODLE_DEV_SRC_DIR="${MOODLE_DEV_SRC_DIR:-$script_dir/moodle503}"
moodle_docker_bin="$script_dir/moodle-docker/bin/moodle-docker-compose"
if [[ -x "$moodle_docker_bin" && -d "$MOODLE_DEV_SRC_DIR" ]]; then
  MOODLE_DOCKER_WWWROOT="$MOODLE_DEV_SRC_DIR" \
  MOODLE_DOCKER_DB="${MOODLE_DOCKER_DB:-pgsql}" \
  COMPOSE_PROJECT_NAME="${MOODLE_DEV_PROJECT_NAME:-moodle-dev}" \
    "$moodle_docker_bin" down "${args[@]}"
fi

printf 'Removed Open WebUI, Moodle (dev), LTI gateway and PostgreSQL containers.\n'
