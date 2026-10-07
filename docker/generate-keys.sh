#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

cp -n .env.example .env && chmod 600 .env

sed -i "s|^LTI_GATEWAY_SECRET_KEY=.*|LTI_GATEWAY_SECRET_KEY='$(openssl rand -hex 32)'|" .env
sed -i "s|^LTI_GATEWAY_API_TOKEN=.*|LTI_GATEWAY_API_TOKEN='$(openssl rand -hex 32)'|" .env
sed -i "s|^WEBUI_SECRET_KEY=.*|WEBUI_SECRET_KEY='$(openssl rand -hex 32)'|" .env

PW=$(openssl rand -hex 32)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD='$PW'|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL='postgresql://webui_user:$PW@host.docker.internal:5432/webui_db'|" .env
unset PW

sed -i "s|^MOODLE_DB_PASS=.*|MOODLE_DB_PASS='$(openssl rand -hex 32)'|" .env

printf 'Generated keys and wrote them to %s/.env\n' "$script_dir"
