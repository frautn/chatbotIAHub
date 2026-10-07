It starts Postgres, waits for it to become healthy, then starts Open WebUI. Set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and OPENAI_API_KEY in the environment before running it; OPENAI_API_BASE_URL is configurable too.

For an external database, set START_POSTGRES=false and provide DATABASE_URL. The Compose files now accept these variables, and the two services remain on separate networks. Postgres credentials here configure the database; Open WebUI user accounts are created through its web interface.

.env
Keep the file out of Git and restrict its permissions with chmod 600 docker/.env; it contains secrets.


Prerequisites
-------------
cd docker
git clone https://github.com/moodlehq/moodle-docker.git
git clone -b MOODLE_503_STABLE git://git.moodle.org/moodle.git moodle503
cp .dockerignore.moodle moodle503/.dockerignore
cp Dockerfile.moodle moodle503/Dockerfile


Generate keys
-------------

Run generate-keys.sh


Local development
-----------------

Run start-dev.sh instead of start.sh for a local dev loop:
- Generates docker/.env for you (via generate-keys.sh) if it doesn't exist yet.
- Defaults START_MOODLE and START_LTI to false, so a plain run only brings up
  Postgres + Open WebUI (set them to true in docker/.env to also test Moodle/LTI).
- When START_MOODLE=true, it runs the stock moodlehq/moodle-docker toolkit
  (docker/moodle-docker) against docker/moodle503 instead of the production
  docker-compose-moodle.yml/Dockerfile.moodle build - see "Moodle (local
  development)" below.
- Fails fast with a clear message naming the conflicting POSTGRES_PORT/WEBUI_PORT/
  MOODLE_DEV_WEB_PORT/LTI_GATEWAY_PORT/LTI_WEBUI_PORT if that port is already taken
  by something else on your machine, instead of docker's raw bind error. Re-running
  it against its own already-running containers is safe (not treated as a conflict).
- Prints the local URLs for whatever it started.

Stop with ./stop-dev.sh, remove with ./remove-dev.sh (these also tear down the
moodle-docker containers; the plain ./stop.sh / ./remove.sh only know about the
production docker-compose-moodle.yml and won't touch them).


Order of scripts
----------------

0) ./generate-keys.sh
1) Set: START_MOODLE=false
2) ./start.sh
3) ./init-moodle-db.sh 
4) ./stop.sh
5) Set: START_MOODLE=true
5) ./start.sh


Moodle 5.3
----------
Moodle's source code is NOT part of this repo; it's built from a separate checkout
(e.g. a git clone of https://github.com/moodle/moodle.git on the MOODLE_503_STABLE
branch) living anywhere on the OCI server. docker-compose-moodle.yml builds the
image straight from that checkout using the Dockerfile that lives at its root.

One-time setup:
1. Clone Moodle 5.3 somewhere on the server, e.g. /opt/moodle503 (done in prerequisites, at docker/moodle503)
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

Moodle (local development)
---------------------------
start-dev.sh uses the stock moodlehq/moodle-docker toolkit instead of the
production build above - it's the "intended for local development" workflow
upstream Moodle maintainers themselves use (zero-config, live-mounted source,
own disposable Postgres + Mailpit), so there's no image to rebuild after every
code change and no real MOODLE_WWWROOT/TLS setup needed.

1. Prerequisites already cover this (docker/moodle-docker + docker/moodle503).
2. Set START_MOODLE=true in docker/.env, then run ./start-dev.sh. It will:
   - Copy moodle-docker/config.docker-template.php to moodle503/config.php
     (only if that file doesn't already exist - safe to re-run).
   - Start moodle-docker's webserver + its own Postgres + Mailpit under the
     "moodle-dev" Compose project (MOODLE_DEV_PROJECT_NAME), isolated from the
     webui_user/webui_db Postgres used by Open WebUI.
   - Print the one-time admin/cli/install_database.php command to run.
3. Visit http://localhost:${MOODLE_DEV_WEB_PORT:-8000} once installed. Outgoing
   mail is caught by Mailpit at the same host/port under /_/mail.
4. Edit code directly in docker/moodle503; changes take effect on refresh (no
   rebuild/restart needed, since the source directory is bind-mounted).
5. Use docker/moodle-docker/bin/moodle-docker-compose (with MOODLE_DOCKER_WWWROOT,
   MOODLE_DOCKER_DB and COMPOSE_PROJECT_NAME set as start-dev.sh does) directly for
   anything beyond start/stop, e.g. running behat/phpunit - see
   docker/moodle-docker/README.md.

Stop with ./stop-dev.sh, remove with ./remove-dev.sh (./remove-dev.sh --volumes
also drops the moodle-dev Postgres data, which is disposable/test data anyway).

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

To delete the containers: ./remove.sh (keeps data); ./remove.sh --volumes also deletes all data.
