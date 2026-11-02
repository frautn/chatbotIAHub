#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$script_dir/.env" ]]; then
  set -a
  source "$script_dir/.env"
  set +a
fi

export POSTGRES_USER="${POSTGRES_USER:-webui_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-some_strong_password}"
export POSTGRES_DB="${POSTGRES_DB:-webui_db}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENWEBUI_IMAGE="${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:main}"
export WEBUI_PORT="${WEBUI_PORT:-3000}"
export WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@host.docker.internal:${POSTGRES_PORT}/${POSTGRES_DB}}"

export LTI_PUBLIC_URL="${LTI_PUBLIC_URL:-}"
export LTI_GATEWAY_SECRET_KEY="${LTI_GATEWAY_SECRET_KEY:-}"
export LTI_GATEWAY_API_TOKEN="${LTI_GATEWAY_API_TOKEN:-}"
export LTI_GATEWAY_PORT="${LTI_GATEWAY_PORT:-8090}"
export LTI_WEBUI_PORT="${LTI_WEBUI_PORT:-3001}"

start_postgres="${START_POSTGRES:-true}"
case "$start_postgres" in
  1|true|TRUE|yes|YES)
    docker compose -f "$script_dir/docker-compose-postgres.yml" up -d --wait
    ;;
  0|false|FALSE|no|NO)
    printf 'Skipping local Postgres and CloudBeaver containers.\n'
    ;;
  *)
    printf 'START_POSTGRES must be true or false (got: %s).\n' "$start_postgres" >&2
    exit 2
    ;;
esac

docker compose -f "$script_dir/docker-compose-openwebui.yml" up -d


start_lti="${START_LTI:-false}"
case "$start_lti" in
  1|true|TRUE|yes|YES)
    : "${LTI_PUBLIC_URL:?Set LTI_PUBLIC_URL, e.g. https://chat.example.com}"
    : "${LTI_GATEWAY_SECRET_KEY:?Set LTI_GATEWAY_SECRET_KEY}"
    docker compose -f "$script_dir/docker-compose-lti.yml" up -d --build
    ;;
  0|false|FALSE|no|NO)
    printf 'Skipping LTI gateway containers.\n'
    ;;
  *)
    printf 'START_LTI must be true or false (got: %s).\n' "$start_lti" >&2
    exit 2
    ;;
esac
