#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

docker compose -f "$script_dir/docker-compose-openwebui.yml" stop
docker compose -f "$script_dir/docker-compose-moodle.yml" stop
docker compose -f "$script_dir/docker-compose-lti.yml" stop
docker compose -f "$script_dir/docker-compose-postgres.yml" stop

printf 'Stopped Open WebUI, Moodle, LTI gateway and PostgreSQL containers.\n'