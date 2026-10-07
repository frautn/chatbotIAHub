#!/usr/bin/env bash
# Removes this project's containers and networks (Open WebUI, Moodle, LTI gateway, PostgreSQL).
# Volumes (databases, uploads, Moodle data) are kept unless --volumes is given.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

args=(--remove-orphans)
case "${1:-}" in
  "") ;;
  --volumes)
    printf 'This will DELETE all project volumes (databases, uploads, Moodle data).\n'
    read -r -p 'Type "delete" to continue: ' answer
    [[ "$answer" == "delete" ]] || { printf 'Aborted.\n'; exit 1; }
    args+=(--volumes)
    ;;
  *)
    printf 'Usage: %s [--volumes]\n' "$0" >&2
    exit 2
    ;;
esac

if [[ -f "$script_dir/.env" ]]; then
  set -a
  source "$script_dir/.env"
  set +a
fi

# The compose files require these variables even for "down"; placeholders are fine here.
export MOODLE_SRC_DIR="${MOODLE_SRC_DIR:-/unused}"
export MOODLE_DB_PASS="${MOODLE_DB_PASS:-unused}"
export MOODLE_WWWROOT="${MOODLE_WWWROOT:-https://unused}"
export LTI_PUBLIC_URL="${LTI_PUBLIC_URL:-https://unused}"
export LTI_GATEWAY_SECRET_KEY="${LTI_GATEWAY_SECRET_KEY:-unused}"

for name in lti moodle openwebui postgres; do
  docker compose -f "$script_dir/docker-compose-$name.yml" down "${args[@]}"
done

printf 'Removed Open WebUI, Moodle, LTI gateway and PostgreSQL containers.\n'
