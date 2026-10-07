#!/usr/bin/env bash
# One-off helper: creates the Moodle role + database inside the already-running
# shared Postgres container (pgsql-moodlewebui), without touching webui_db.
# Safe to re-run; it is idempotent.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$script_dir/.env" ]]; then
  set -a
  source "$script_dir/.env"
  set +a
fi

PG_CONTAINER="${PG_CONTAINER:-pgsql-moodlewebui}"
PG_SUPERUSER="${POSTGRES_USER:-webui_user}"
PG_SUPERDB="${POSTGRES_DB:-webui_db}"

MOODLE_DB_NAME="${MOODLE_DB_NAME:-moodle_db}"
MOODLE_DB_USER="${MOODLE_DB_USER:-moodle_user}"
MOODLE_DB_PASS="${MOODLE_DB_PASS:?Set MOODLE_DB_PASS before running this script}"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_SUPERUSER" -d "$PG_SUPERDB" <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${MOODLE_DB_USER}') THEN
      CREATE ROLE "${MOODLE_DB_USER}" LOGIN PASSWORD '${MOODLE_DB_PASS}';
   ELSE
      ALTER ROLE "${MOODLE_DB_USER}" WITH PASSWORD '${MOODLE_DB_PASS}';
   END IF;
END
\$\$;
SQL

exists="$(docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_SUPERUSER" -d "$PG_SUPERDB" -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '${MOODLE_DB_NAME}'")"

if [[ "$exists" != "1" ]]; then
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_SUPERUSER" -d "$PG_SUPERDB" \
    -c "CREATE DATABASE \"${MOODLE_DB_NAME}\" OWNER \"${MOODLE_DB_USER}\" ENCODING 'UTF8'"
fi

printf 'Moodle database "%s" and role "%s" are ready on container "%s".\n' \
  "$MOODLE_DB_NAME" "$MOODLE_DB_USER" "$PG_CONTAINER"
