It starts Postgres, waits for it to become healthy, starts CloudBeaver, then starts Open WebUI. Set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and OPENAI_API_KEY in the environment before running it; OPENAI_API_BASE_URL is configurable too.

For an external database, set START_POSTGRES=false and provide DATABASE_URL. The Compose files now accept these variables, and the two services remain on separate networks. Postgres credentials here configure the database; Open WebUI user accounts are created through its web interface.
START_POSTGRES=false also skips CloudBeaver.

.env
Keep the file out of Git and restrict its permissions with chmod 600 docker/.env; it contains secrets.


Prerequisites
-------------
cd docker
git clone https://github.com/open-webui/open-webui.git open-webui-custom
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
  Postgres + CloudBeaver + Open WebUI (set them to true in docker/.env to also test Moodle/LTI).
- When START_MOODLE=true, it runs the stock moodlehq/moodle-docker toolkit
  (docker/moodle-docker) against docker/moodle503 instead of the production
  docker-compose-moodle.yml/Dockerfile.moodle build - see "Moodle (local
  development)" below.
- Fails fast with a clear message naming the conflicting POSTGRES_PORT/CLOUDBEAVER_PORT/WEBUI_PORT/
  MOODLE_DEV_WEB_PORT/LTI_GATEWAY_PORT/LTI_WEBUI_PORT if that port is already taken
  by something else on your machine, instead of docker's raw bind error. Re-running
  it against its own already-running containers is safe (not treated as a conflict).
- Prints the local URLs for whatever it started.

Stop with ./stop-dev.sh, remove with ./remove-dev.sh (these also tear down the
moodle-docker containers; the plain ./stop.sh / ./remove.sh only know about the
production docker-compose-moodle.yml and won't touch them).

CloudBeaver (browser database administration)
--------------------------------------------
CloudBeaver starts with the local PostgreSQL stack in both start.sh and
start-dev.sh. To add it to an already-running database without recreating
PostgreSQL, run from the repository root:

  docker compose -f docker/docker-compose-postgres.yml up -d --no-deps cloudbeaver

Open http://127.0.0.1:8978 and complete the first-run setup to create a
CloudBeaver administrator account (separate from database and Open WebUI users).
For a remote server, forward the local-only port over SSH:

  ssh -N -L 8978:127.0.0.1:8978 user@your-server

Then open http://127.0.0.1:8978 on your own computer. Do not expose the setup
wizard or database administration interface without access controls.
For VS Code Remote SSH, forwarding port 8978 in the Ports panel also works.

For HTTPS access at https://pg.fcr.lat, use nginx-pg.fcr.lat.conf. It proxies
to the local-only CloudBeaver port and requires nginx Basic Auth in addition to
CloudBeaver's own login. Complete the first-run setup over the SSH tunnel first.
Point the domain's DNS at the server, and configure certificate/key paths in the
example to use a certificate covering pg.fcr.lat. From the repository root:

  sudo htpasswd -c /etc/nginx/cloudbeaver.htpasswd dbadmin
  sudo chown root:www-data /etc/nginx/cloudbeaver.htpasswd
  sudo chmod 640 /etc/nginx/cloudbeaver.htpasswd
  sudo cp docker/nginx-pg.fcr.lat.conf /etc/nginx/sites-available/pg.fcr.lat
  sudo ln -s /etc/nginx/sites-available/pg.fcr.lat /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx

The htpasswd utility is provided by apache2-utils on Ubuntu; install it if
missing. Use your nginx worker group instead of www-data on other distributions.
Use htpasswd without -c when adding users to an existing password file.
If CLOUDBEAVER_PORT is customized, update proxy_pass in the nginx example too.

Create a PostgreSQL connection with:
- Host: postgres (the Docker service name, not localhost)
- Port: 5432 (internal port, regardless of POSTGRES_PORT)
- Database: the POSTGRES_DB value in docker/.env (default: webui_db)
- Username/password: the existing database credentials configured by
  POSTGRES_USER / POSTGRES_PASSWORD. Do not change those values to connect to
  an existing database; changing environment variables does not reset its users.

Use Test Connection before saving. A read-only query such as SELECT current_database(),
current_user; verifies which database and role you are using. Prefer read-only
queries when inspecting Open WebUI settings; direct edits can bypass application
validation and may require restarting both Open WebUI instances.

CLOUDBEAVER_PORT overrides the host port (default 8978); adjust the tunnel to
match. CLOUDBEAVER_IMAGE overrides the image (default dbeaver/cloudbeaver:latest);
pin an explicit release tag for controlled upgrades.
CloudBeaver accounts and saved connection settings persist in the
cloudbeaver-workspace volume. The existing stop/remove scripts include
CloudBeaver; remove.sh --volumes and remove-dev.sh --volumes also delete its
workspace, as well as the databases and other project data.


Open WebUI backups (no downtime)
--------------------------------
From the repository root:

  bash docker/backup-openwebui.sh /secure/path/to/backups

The default destination is ~/backups/openwebui. The script requires Docker
access, python3, GNU tar in the running Open WebUI container, and standard Linux
utilities. PG_CONTAINER overrides the local PostgreSQL container name (default
pgsql-moodlewebui). It supports this repository's named Open WebUI containers,
their shared named data volume, and the local PostgreSQL database; external
databases, URL query options, and alternative mount layouts fail explicitly.
It does not source docker/.env or stop/pause/restart any services.

Each private, timestamped directory contains:
- database.dump: a custom-format pg_dump of the actual runtime Open WebUI DB.
- data.tar.gz: all files under /app/backend/data, including uploads, vector-store
  files and any secret-key file stored there.
- config/: Compose files and docker/.env if present.
- Container metadata: runtime environment (including WEBUI_SECRET_KEY), image
  versions/digests, and volume information for both Open WebUI instances.
- SHA256SUMS, timestamps, and RESTORE.txt with recovery guidance.

WARNING: This is a live backup, NOT a single point-in-time snapshot of database
and files. pg_dump is transactionally consistent, but uploads and vector-store
files may change while being archived. GNU tar errors, including detected file
changes, cause failure; a successful archive still cannot guarantee consistency
of live vector-store files. Avoid uploads/database edits/deployments during the
backup. For guaranteed database/file consistency, use a maintenance window or a
coordinated storage snapshot strategy instead.

Failed backups return nonzero and retain a clearly marked .partial directory;
only verified archives get a completed directory name. Verification reads the
database archive table of contents, reads the compressed tar and checks file
hashes; it does not perform a test restore. Test recovery in an isolated stack.
For integrity checks, cd into a completed backup and run:

  sha256sum --check SHA256SUMS

Backups include secrets and personal data and are NOT encrypted. Keep them
outside the repository, restrict access, and keep encrypted off-server copies.
There is no automatic retention/deletion. Database roles/passwords must be
provisioned before restoring with --no-owner --no-privileges.
Moodle data, LTI gateway volumes, CloudBeaver workspace, external storage/vector
services, nginx TLS files, and Docker images are not part of this backup.


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

Moodle 5.3 External tool (LTI 1.3) settings for https://lti.fcr.lat:
- Tool URL:                 https://lti.fcr.lat/lti/launch
- Public keyset:            https://lti.fcr.lat/lti/jwks
- Initiate login URL:       https://lti.fcr.lat/lti/login
- Redirection URI(s):       https://lti.fcr.lat/lti/launch
                            https://lti.fcr.lat/lti/deeplink
- Content selection URL:    https://lti.fcr.lat/lti/launch

Set the public key type to "JWK keyset" and enable Deep Linking. These URLs are
also available from https://lti.fcr.lat/lti/config.

sudo ln -s /etc/nginx/sites-available/lti.retag.lat /etc/nginx/sites-enabled/

LTI 1.1 gateway
---------------
Runs alongside the LTI 1.3 lti-gateway, sharing the same openwebui-lti instance/group;
both are started together by docker-compose-lti.yml under START_LTI=true. Set the
LTI11_* variables in docker/.env (LTI11_PUBLIC_URL, LTI11_GATEWAY_SECRET_KEY,
LTI11_GATEWAY_API_TOKEN, LTI11_CONSUMER_KEY, LTI11_CONSUMER_SECRET, etc.).

Unlike LTI 1.3 there is no dynamic registration: a consumer key/secret pair must be
entered manually both in Moodle's "External tool" activity config and in the
gateway's own consumers.json:

1. echo '{"'"$LTI11_CONSUMER_KEY"'": "'"$LTI11_CONSUMER_SECRET"'"}' > consumers.json
2. docker cp consumers.json lti11-gateway:/data/consumers.json
3. docker restart lti11-gateway   # consumers.json is only read at startup

In Moodle, configure the External tool manually (LTI version 1.1/1.2) with:
- Tool URL:       https://lti1.retag.lat/lti11/launch
- Consumer key:   $LTI11_CONSUMER_KEY
- Shared secret:  $LTI11_CONSUMER_SECRET
- Custom parameters (optional, to pin a model): model=<id-from-LTI11_GATEWAY_MODELS>

Use nginx-lti1.retag.lat.conf (or nginx-lti11.example.conf as a generic template)
as the public front end, proxying /lti11/ and /_lti11_auth to 127.0.0.1:8091.

sudo ln -s /etc/nginx/sites-available/lti1.retag.lat /etc/nginx/sites-enabled/

Running both Open WebUI instances
---------------------------------
The stock (admin/professor) and LTI (student) instances share Postgres and one
data volume (uploads, vector store), and must share WEBUI_SECRET_KEY. Pin
OPENWEBUI_IMAGE to the same explicit version tag for both and upgrade by
restarting one instance first so DB migrations don't race. Persistent settings
(e.g. ENABLE_SIGNUP, DEFAULT_USER_ROLE) live in the DB and apply to both.

To delete the containers: ./remove.sh (keeps data); ./remove.sh --volumes also deletes all data.

Default title, follow-up and tag generation preferences
------------------------------------------------------
Both Open WebUI Compose services default the personal automatic-title,
follow-up and tag generation toggles to off using DEFAULT_INTERFACE_SETTINGS:

  {"language": "es-ES", "title": {"auto": false}, "autoFollowUps": false, "autoTags": false}

There is no enclosing "ui" key in this variable. DEFAULT_USER_SETTINGS is not
read by the installed Open WebUI versions (v0.12.2 and v0.12.3). If docker/.env
sets DEFAULT_INTERFACE_SETTINGS, include title.auto, autoFollowUps and autoTags
there too: that value replaces the Compose default rather than merging with it.

ENABLE_TITLE_GENERATION=false controls the server-side title-generation task;
ENABLE_FOLLOW_UP_GENERATION=false controls the server-side follow-up task.
ENABLE_TAGS_GENERATION=false controls the server-side tag-generation task.
These variables do not set the user's personal toggles.

On an existing installation, saved database configuration takes precedence over
these environment defaults. In the administrator's default Interface settings,
turn off automatic title, follow-up and tag generation and save. This updates
ui.default_interface_settings; rebuilding images or recreating containers alone
does not replace that saved value. Both instances share it through PostgreSQL.
For existing installations, also disable follow-up and tag generation in the
admin task settings (task.follow_up.enable and task.tags.enable); their saved
values override the environment too.
Users without a personal override (including new users) inherit the default;
an explicit personal choice is preserved. Reload the page to fetch new defaults.
Do not delete volumes or disable all persistent configuration to apply this change.
