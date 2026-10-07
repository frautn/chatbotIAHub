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
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENWEBUI_IMAGE="${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:main}"
export WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@host.docker.internal:5432/${POSTGRES_DB}}"

export MOODLE_SRC_DIR="${MOODLE_SRC_DIR:-}"
export MOODLE_DB_HOST="${MOODLE_DB_HOST:-host.docker.internal}"
export MOODLE_DB_PORT="${MOODLE_DB_PORT:-5432}"
export MOODLE_DB_NAME="${MOODLE_DB_NAME:-moodle_db}"
export MOODLE_DB_USER="${MOODLE_DB_USER:-moodle_user}"
export MOODLE_DB_PASS="${MOODLE_DB_PASS:-}"
export MOODLE_WWWROOT="${MOODLE_WWWROOT:-}"
export MOODLE_WEB_PORT="${MOODLE_WEB_PORT:-8081}"

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
    printf 'Skipping local Postgres container.\n'
    ;;
  *)
    printf 'START_POSTGRES must be true or false (got: %s).\n' "$start_postgres" >&2
    exit 2
    ;;
esac

docker compose -f "$script_dir/docker-compose-openwebui.yml" up -d

start_moodle="${START_MOODLE:-true}"
case "$start_moodle" in
  1|true|TRUE|yes|YES)
    : "${MOODLE_SRC_DIR:?Set MOODLE_SRC_DIR to the absolute path of your Moodle 5.3 checkout}"
    : "${MOODLE_DB_PASS:?Set MOODLE_DB_PASS}"
    : "${MOODLE_WWWROOT:?Set MOODLE_WWWROOT, e.g. https://moodle.example.com}"
    docker compose -f "$script_dir/docker-compose-moodle.yml" up -d --build
    ;;
  0|false|FALSE|no|NO)
    printf 'Skipping Moodle containers.\n'
    ;;
  *)
    printf 'START_MOODLE must be true or false (got: %s).\n' "$start_moodle" >&2
    exit 2
    ;;
esac
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
