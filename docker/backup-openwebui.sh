#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--help" ]]; then
  printf 'Usage: bash %s [backup-directory]\n' "$0"
  printf 'Live backup of local PostgreSQL and Open WebUI data; no containers are stopped.\n'
  printf 'Default directory: $HOME/backups/openwebui. Requires docker, python3, tar, sha256sum.\n'
  exit 0
fi
if [[ "$#" -gt 1 || "${1:-}" == -* ]]; then
  printf 'Usage: bash %s [backup-directory]\n' "$0" >&2
  exit 2
fi

for tool in docker python3 tar sha256sum find sort xargs; do
  command -v "$tool" >/dev/null || { printf 'Missing required tool: %s\n' "$tool" >&2; exit 1; }
done

backup_root="${1:-$HOME/backups/openwebui}"
mkdir -p -- "$backup_root"
backup_root="$(cd -- "$backup_root" && pwd)"
backup_dir="$(mktemp -d "$backup_root/openwebui-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.partial")"
pg_container="${PG_CONTAINER:-pgsql-moodlewebui}"

cleanup() {
  local status="$?"
  trap - EXIT
  rm -f -- "$backup_dir/pg-connection"
  if [[ "$status" -ne 0 ]]; then
    printf 'ERROR: Backup failed; incomplete files remain at %s\n' "$backup_dir" >&2
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'WARNING: Live backup; database and files are not a single point-in-time snapshot.\n' >&2
printf 'Do not edit the database or deploy/recreate containers during this backup.\n' >&2
printf 'Backing up to %s\n' "$backup_dir"

docker inspect "$pg_container" > "$backup_dir/postgres-container.json"
docker ps -a --format '{{.Names}}' > "$backup_dir/container-names.txt"
webui_containers=()
for container in openwebui-for-moodle openwebui-lti; do
  if grep -Fxq "$container" "$backup_dir/container-names.txt"; then
    webui_containers+=("$container")
  fi
done
if [[ "${#webui_containers[@]}" -eq 0 ]]; then
  printf 'No Open WebUI containers found.\n' >&2
  exit 1
fi
docker inspect "${webui_containers[@]}" > "$backup_dir/openwebui-containers.json"

# Read actual runtime configuration rather than potentially stale docker/.env values.
python3 - "$backup_dir" <<'PY'
import json
import pathlib
import sys
from urllib.parse import unquote, urlsplit

root = pathlib.Path(sys.argv[1])
postgres = json.loads((root / "postgres-container.json").read_text())[0]
containers = json.loads((root / "openwebui-containers.json").read_text())


def env(container):
    return dict(item.split("=", 1) for item in container["Config"]["Env"])


def require(condition, message):
    if not condition:
        sys.exit("ERROR: " + message)


require(postgres["State"]["Running"], "PostgreSQL container must be running.")
pg_env = env(postgres)
connections = set()
volumes = set()
running = []
for container in containers:
    settings = env(container)
    url = urlsplit(settings.get("DATABASE_URL", ""))
    require(url.scheme in ("postgres", "postgresql"), "Only PostgreSQL DATABASE_URL is supported.")
    require(not url.query and not url.fragment, "DATABASE_URL query options are not supported.")
    database = unquote(url.path.lstrip("/"))
    require(database == pg_env.get("POSTGRES_DB"), "DATABASE_URL does not match local POSTGRES_DB.")
    port = url.port or 5432
    local_hosts = {"postgres", postgres["Name"].lstrip("/")}
    published = postgres["NetworkSettings"]["Ports"].get("5432/tcp") or []
    local_connection = (
        url.hostname in local_hosts and port == 5432
    ) or (
        url.hostname == "host.docker.internal"
        and any(int(binding["HostPort"]) == port for binding in published)
    )
    require(local_connection, "DATABASE_URL must point to this local PostgreSQL container.")
    credentials = (unquote(url.username or ""), unquote(url.password or ""), database)
    require(credentials[0], "DATABASE_URL must include a username.")
    require(all("\n" not in value and "\r" not in value for value in credentials),
            "Database credentials containing newlines are not supported.")
    connections.add(credentials)
    mounts = [m for m in container["Mounts"] if m["Destination"] == "/app/backend/data"]
    require(len(mounts) == 1 and mounts[0]["Type"] == "volume",
            "Expected one named volume at /app/backend/data.")
    require(not any(m["Destination"].startswith("/app/backend/data/") for m in container["Mounts"]),
            "Nested data mounts require a separate backup strategy.")
    volumes.add(mounts[0]["Name"])
    if container["State"]["Running"]:
        running.append(container["Name"].lstrip("/"))
require(len(connections) == 1, "Open WebUI instances must share database credentials.")
require(len(volumes) == 1, "Open WebUI instances must share one data volume.")
require(running, "At least one Open WebUI container must be running to archive its data.")
(root / "pg-connection").write_text("\n".join(next(iter(connections))) + "\n")
(root / "data-container").write_text(running[0] + "\n")
(root / "data-volume").write_text(next(iter(volumes)) + "\n")
PY

mkdir "$backup_dir/config"
for config in docker-compose-openwebui.yml docker-compose-lti.yml docker-compose-postgres.yml .env; do
  if [[ -f "$script_dir/$config" ]]; then
    cp -- "$script_dir/$config" "$backup_dir/config/$config"
    chmod 600 "$backup_dir/config/$config"
  elif [[ "$config" == ".env" ]]; then
    printf 'WARNING: docker/.env is absent; runtime environment is saved in container metadata.\n' >&2
  else
    printf 'Required configuration file missing: %s\n' "$config" >&2
    exit 1
  fi
done
date -u +%Y-%m-%dT%H:%M:%SZ > "$backup_dir/started-at.txt"

printf 'Dumping PostgreSQL...\n'
docker exec -i "$pg_container" sh -eu -c '
  IFS= read -r PGUSER
  IFS= read -r PGPASSWORD
  IFS= read -r PGDATABASE
  export PGUSER PGPASSWORD PGDATABASE
  export PGHOST=127.0.0.1 PGPORT=5432
  exec pg_dump --format=custom
' < "$backup_dir/pg-connection" > "$backup_dir/database.dump"
rm -- "$backup_dir/pg-connection"
docker exec -i "$pg_container" pg_restore --list \
  < "$backup_dir/database.dump" > "$backup_dir/database-contents.txt"

read -r data_container < "$backup_dir/data-container"
printf 'Archiving the complete /app/backend/data directory...\n'
docker exec "$data_container" tar --create --gzip --file=- \
  --directory=/app/backend/data . > "$backup_dir/data.tar.gz"
tar -tzf "$backup_dir/data.tar.gz" > /dev/null
date -u +%Y-%m-%dT%H:%M:%SZ > "$backup_dir/finished-at.txt"

cat > "$backup_dir/RESTORE.txt" <<'TEXT'
LIVE BACKUP: PostgreSQL is transactionally consistent, but the database and data
archive are NOT a combined point-in-time snapshot. Live vector stores may require
recovery/reindexing even when tar reported no changed files.

This directory contains secrets, user information, chats and uploads. Protect it
and copy it to encrypted off-server storage. Files are NOT encrypted at rest here.

Verify integrity from this directory: sha256sum --check SHA256SUMS

Recovery outline (test on an isolated deployment first):
1. Use the recorded Open WebUI image versions/digests in openwebui-containers.json.
   Container images themselves are not included. Runtime metadata contains the
   original environment, including WEBUI_SECRET_KEY and database credentials.
2. Provision a compatible PostgreSQL server and an empty database owned by the
   application role. Database roles/passwords are not created by database.dump.
3. Restore using pg_restore --no-owner --no-privileges --exit-on-error, targeting
   that empty database. Never restore over a live production database.
4. With ALL Open WebUI instances stopped, extract data.tar.gz into an empty shared
   data volume (named in data-volume), preserving numeric ownership/permissions.
5. Restore deployment configuration and WEBUI_SECRET_KEY, adjust DATABASE_URL
   for the restored database, and start one Open WebUI instance before the other.
6. Check logins, chats, uploaded files, and knowledge/vector-store searches.

Not included: Moodle database/files, LTI gateway volumes, CloudBeaver workspace,
external vector databases/object storage, nginx certificates or Docker images.
Back up those separately if used. Do not apply source .env blindly on another
host: it may point back to production services.
TEXT

(
  cd -- "$backup_dir"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS
)
completed_dir="${backup_dir%.partial}"
mv -- "$backup_dir" "$completed_dir"
backup_dir="$completed_dir"
printf '\nBackup complete: %s\n' "$backup_dir"
printf 'Live backup: not a combined point-in-time snapshot. Store an encrypted copy off-server.\n'
