#!/usr/bin/env bash
# Local-development variant of start.sh:
#  - auto-generates docker/.env (via generate-keys.sh) on first run instead of
#    requiring a manual step
#  - defaults Moodle and the LTI gateway to off, so a plain run only brings up
#    Postgres + Open WebUI (the fast dev loop)
#  - when Moodle is enabled, uses the stock moodlehq/moodle-docker toolkit
#    (live-mounted checkout, own Postgres/Mailpit) instead of the production
#    docker-compose-moodle.yml/Dockerfile.moodle build
#  - fails fast with a clear message if a configured port is already taken,
#    instead of docker's raw "address already in use" error
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ ! -f .env ]]; then
  printf 'No docker/.env found; generating one with ./generate-keys.sh...\n'
  ./generate-keys.sh
  printf 'Edit docker/.env (e.g. OPENAI_API_KEY) if needed, then re-run this script.\n'
fi

set -a
source .env
set +a

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

# Moodle here uses the stock moodlehq/moodle-docker toolkit (docker/moodle-docker),
# not the production docker-compose-moodle.yml/Dockerfile.moodle: it mounts the
# checkout live (no image build, edits take effect immediately) and runs its own
# isolated Postgres + Mailpit, under the separate "moodle-dev" compose project.
export MOODLE_DEV_SRC_DIR="${MOODLE_DEV_SRC_DIR:-$script_dir/moodle503}"
export MOODLE_DOCKER_DB="${MOODLE_DOCKER_DB:-pgsql}"
export MOODLE_DEV_WEB_PORT="${MOODLE_DEV_WEB_PORT:-8000}"
export MOODLE_DEV_PROJECT_NAME="${MOODLE_DEV_PROJECT_NAME:-moodle-dev}"

export LTI_PUBLIC_URL="${LTI_PUBLIC_URL:-}"
export LTI_GATEWAY_SECRET_KEY="${LTI_GATEWAY_SECRET_KEY:-}"
export LTI_GATEWAY_API_TOKEN="${LTI_GATEWAY_API_TOKEN:-}"
export LTI_GATEWAY_PORT="${LTI_GATEWAY_PORT:-8090}"
export LTI_WEBUI_PORT="${LTI_WEBUI_PORT:-3001}"

# Dev loop default: only Postgres + Open WebUI, unless .env says otherwise.
start_postgres="${START_POSTGRES:-true}"
start_moodle="${START_MOODLE:-false}"
start_lti="${START_LTI:-false}"

# True if something is already listening on 127.0.0.1:$1.
port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && { exec 3>&-; return 0; }
  return 1
}

# True if the listener on $1 is this project's own container for compose
# project $2 (so re-running the script against an already-running stack
# doesn't get flagged as a conflict).
owned_by_us() {
  docker ps --filter "label=com.docker.compose.project=$2" --format '{{.Ports}}' 2>/dev/null \
    | grep -qE "(^|:)$1->"
}

port_conflict=0
check_port() {
  local port="$1" project="$2" label="$3"
  if port_in_use "$port" && ! owned_by_us "$port" "$project"; then
    printf 'Error: port %s (%s) is already in use by something else on this machine.\n' "$port" "$label" >&2
    printf '  Set a different value for %s in docker/.env and re-run this script.\n' "$label" >&2
    port_conflict=1
  fi
}

case "$start_postgres" in
  1|true|TRUE|yes|YES) check_port "$POSTGRES_PORT" "pgsql-moodlewebui" "POSTGRES_PORT" ;;
esac
check_port "$WEBUI_PORT" "openwebui-for-moodle" "WEBUI_PORT"
case "$start_moodle" in
  1|true|TRUE|yes|YES) check_port "$MOODLE_DEV_WEB_PORT" "$MOODLE_DEV_PROJECT_NAME" "MOODLE_DEV_WEB_PORT" ;;
esac
case "$start_lti" in
  1|true|TRUE|yes|YES)
    check_port "$LTI_GATEWAY_PORT" "lti-gateway" "LTI_GATEWAY_PORT"
    check_port "$LTI_WEBUI_PORT" "lti-gateway" "LTI_WEBUI_PORT"
    ;;
esac
[[ "$port_conflict" -eq 0 ]] || exit 1

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

moodle_dev_installed=0
case "$start_moodle" in
  1|true|TRUE|yes|YES)
    moodle_docker_bin="$script_dir/moodle-docker/bin/moodle-docker-compose"
    if [[ ! -x "$moodle_docker_bin" ]]; then
      printf 'Error: docker/moodle-docker is missing. See "Prerequisites" in docker/readme.txt.\n' >&2
      exit 1
    fi
    if [[ ! -d "$MOODLE_DEV_SRC_DIR" ]]; then
      printf 'Error: Moodle checkout not found at %s. See "Prerequisites" in docker/readme.txt.\n' "$MOODLE_DEV_SRC_DIR" >&2
      exit 1
    fi
    if [[ -f "$MOODLE_DEV_SRC_DIR/config.php" ]]; then
      moodle_dev_installed=1
    fi
    cp -n "$script_dir/moodle-docker/config.docker-template.php" "$MOODLE_DEV_SRC_DIR/config.php"
    export MOODLE_DOCKER_WWWROOT="$MOODLE_DEV_SRC_DIR"
    export COMPOSE_PROJECT_NAME="$MOODLE_DEV_PROJECT_NAME"
    export MOODLE_DOCKER_WEB_PORT="$MOODLE_DEV_WEB_PORT"
    "$moodle_docker_bin" up -d
    "$script_dir/moodle-docker/bin/moodle-docker-wait-for-db"
    unset COMPOSE_PROJECT_NAME
    ;;
  0|false|FALSE|no|NO)
    printf 'Skipping Moodle containers.\n'
    ;;
  *)
    printf 'START_MOODLE must be true or false (got: %s).\n' "$start_moodle" >&2
    exit 2
    ;;
esac

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

printf '\nLocal dev stack is up:\n'
printf '  Open WebUI: http://127.0.0.1:%s\n' "$WEBUI_PORT"
[[ "$start_postgres" =~ ^(1|true|TRUE|yes|YES)$ ]] && printf '  Postgres:   postgresql://127.0.0.1:%s/%s\n' "$POSTGRES_PORT" "$POSTGRES_DB"
if [[ "$start_moodle" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
  printf '  Moodle (dev): http://localhost:%s\n' "$MOODLE_DEV_WEB_PORT"
  printf '  Mailpit:      http://localhost:%s/_/mail\n' "$MOODLE_DEV_WEB_PORT"
  if [[ "$moodle_dev_installed" -eq 0 ]]; then
    printf '  First run: install the Moodle site once with:\n'
    printf '    docker/moodle-docker/bin/moodle-docker-compose exec webserver php admin/cli/install_database.php \\\n'
    printf '      --agree-license --fullname="Dev Moodle" --shortname="dev_moodle" --adminpass="test1234!" --adminemail="admin@example.com"\n'
  fi
fi
[[ "$start_lti" =~ ^(1|true|TRUE|yes|YES)$ ]] && printf '  LTI gateway: http://127.0.0.1:%s\n  LTI Open WebUI: http://127.0.0.1:%s\n' "$LTI_GATEWAY_PORT" "$LTI_WEBUI_PORT"
printf 'Stop with ./stop-dev.sh, remove with ./remove-dev.sh.\n'
