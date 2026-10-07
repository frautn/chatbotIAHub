#!/usr/bin/env bash
# Stops everything start-dev.sh may have started, including the moodle-docker
# based Moodle dev environment (separate from stop.sh, which only knows about
# the production docker-compose-moodle.yml).
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

docker compose -f "$script_dir/docker-compose-openwebui.yml" stop
docker compose -f "$script_dir/docker-compose-lti.yml" stop
docker compose -f "$script_dir/docker-compose-postgres.yml" stop

MOODLE_DEV_SRC_DIR="${MOODLE_DEV_SRC_DIR:-$script_dir/moodle503}"
moodle_docker_bin="$script_dir/moodle-docker/bin/moodle-docker-compose"
if [[ -x "$moodle_docker_bin" && -d "$MOODLE_DEV_SRC_DIR" ]]; then
  MOODLE_DOCKER_WWWROOT="$MOODLE_DEV_SRC_DIR" \
  MOODLE_DOCKER_DB="${MOODLE_DOCKER_DB:-pgsql}" \
  COMPOSE_PROJECT_NAME="${MOODLE_DEV_PROJECT_NAME:-moodle-dev}" \
    "$moodle_docker_bin" stop
fi

printf 'Stopped Open WebUI, Moodle (dev), LTI gateway and PostgreSQL containers.\n'
