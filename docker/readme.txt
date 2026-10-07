It starts Postgres, waits for it to become healthy, then starts Open WebUI. Set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and OPENAI_API_KEY in the environment before running it; OPENAI_API_BASE_URL is configurable too.

For an external database, set START_POSTGRES=false and provide DATABASE_URL. The Compose files now accept these variables, and the two services remain on separate networks. Postgres credentials here configure the database; Open WebUI user accounts are created through its web interface.

.env
Keep the file out of Git and restrict its permissions with chmod 600 docker/.env; it contains secrets.


Generate keys
-------------
cd docker
cp -n .env.example .env && chmod 600 .env

sed -i "s|^LTI_GATEWAY_SECRET_KEY=.*|LTI_GATEWAY_SECRET_KEY='$(openssl rand -hex 32)'|" .env
sed -i "s|^LTI_GATEWAY_API_TOKEN=.*|LTI_GATEWAY_API_TOKEN='$(openssl rand -hex 32)'|" .env
sed -i "s|^WEBUI_SECRET_KEY=.*|WEBUI_SECRET_KEY='$(openssl rand -hex 32)'|" .env

PW=$(openssl rand -hex 32)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD='$PW'|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL='postgresql://webui_user:$PW@host.docker.internal:5432/webui_db'|" .env
unset PW

Moodle 5.3
----------
Moodle's source code is NOT part of this repo; it's built from a separate checkout
(e.g. a git clone of https://github.com/moodle/moodle.git on the MOODLE_503_STABLE
branch) living anywhere on the OCI server. docker-compose-moodle.yml builds the
image straight from that checkout using the Dockerfile that lives at its root.

One-time setup:
1. Clone Moodle 5.3 somewhere on the server, e.g. /opt/moodle503.
2. Set in docker/.env: MOODLE_SRC_DIR (path from step 1), MOODLE_DB_PASS,
   MOODLE_WWWROOT (e.g. https://moodle.example.com), and optionally
   MOODLE_DB_NAME / MOODLE_DB_USER / MOODLE_WEB_PORT.
3. With Postgres already running, create the Moodle database/role once:
     ./init-moodle-db.sh
   This reuses the existing pgsql-moodlewebui container; it does not touch webui_db.
4. ./start.sh (set START_MOODLE=false to skip it). This builds the Moodle image,
   then starts the "moodle" web container plus a "moodle-cron" sidecar that runs
   admin/cli/cron.php every 60s.
5. Copy docker/nginx-moodle.example.conf to /etc/nginx/sites-available, rename it,
   set the real server_name and certificate paths, symlink it into sites-enabled,
   then reload nginx. It proxies to 127.0.0.1:${MOODLE_WEB_PORT:-8081}.
6. Visit MOODLE_WWWROOT in a browser to run the Moodle install wizard (creates the
   database tables and the admin account). Rebuild with `docker compose -f
   docker-compose-moodle.yml up -d --build` after pulling new Moodle code.

config.php is generated at container startup from the MOODLE_DB_* / MOODLE_WWWROOT
environment variables (see the Dockerfile) - do not edit it inside the container,
edit the env vars and recreate the containers instead.

LTI gateway
-----------
See ../gateway/README.md. Set START_LTI=true plus the LTI_* variables in docker/.env;
start.sh then builds and starts docker-compose-lti.yml (the lti-gateway service and
the student-facing openwebui-lti instance). Use nginx-lti.example.conf as the public front end.

sudo ln -s /etc/nginx/sites-available/lti.retag.lat /etc/nginx/sites-enabled/

Running both Open WebUI instances
---------------------------------
The stock (admin/professor) and LTI (student) instances share Postgres and one
data volume (uploads, vector store), and must share WEBUI_SECRET_KEY. Pin
OPENWEBUI_IMAGE to the same explicit version tag for both and upgrade by
restarting one instance first so DB migrations don't race. Persistent settings
(e.g. ENABLE_SIGNUP, DEFAULT_USER_ROLE) live in the DB and apply to both.
