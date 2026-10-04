#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export POSTGRES_USER="${POSTGRES_USER:-webui_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-some_strong_password}"
export POSTGRES_DB="${POSTGRES_DB:-webui_db}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@host.docker.internal:5432/${POSTGRES_DB}}"

start_postgres="${START_POSTGRES:-true}"
case "$start_postgres" in
  1|true|TRUE|yes|YES)
    docker compose -f "$script_dir/docker-compose-postgres.yml" up -d --wait
    ;;
  0|false|FALSE|no|NO)
    printf 'Skipping local Postgres container.\n'
    ;;
  *)
    printf 'START_POSTGRES must be true or false (got: %s).\n' "$start_postgres" >&2
    exit 2
    ;;
esac

docker compose -f "$script_dir/docker-compose-openwebui.yml" up -d