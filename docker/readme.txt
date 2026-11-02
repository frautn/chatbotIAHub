It starts Postgres, waits for it to become healthy, starts CloudBeaver, then starts Open WebUI. Set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and OPENAI_API_KEY in the environment before running it; OPENAI_API_BASE_URL is configurable too.

For an external database, set START_POSTGRES=false and provide DATABASE_URL. Postgres credentials here configure the database; Open WebUI user accounts are created through its web interface.

START_POSTGRES=false also skips CloudBeaver.

.env
Keep the file out of Git and restrict its permissions with chmod 600 docker/.env; it contains secrets.


Prerequisites
-------------


Generate keys
-------------
Run generate-keys.sh to populate the keys in .env


Local development
-----------------
Making this work completely local is hard work. The current setup is not suitable for local development, it only works with a machine accessible from the internet.


CloudBeaver (browser database administration)
--------------------------------------------
CloudBeaver starts with the local PostgreSQL stack in start.sh. 
To add it to an already-running database without recreating
PostgreSQL, run from the repository root:

  docker compose -f docker/docker-compose-postgres.yml up -d --no-deps cloudbeaver

For HTTPS access at https://pg.fcr.lat (use your own url), use nginx-pg.fcr.lat.conf.
It proxies to the local-only CloudBeaver port and requires nginx Basic Auth in
addition to CloudBeaver's own login. 
Complete the first-run setup over the SSH tunnel first.
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

sudo ln -s /etc/nginx/sites-available/lti.fcr.lat /etc/nginx/sites-enabled/

LTI 1.1 gateway
---------------
Runs alongside the LTI 1.3 lti-gateway, sharing the same openwebui-lti instance/group;
both are started together by docker-compose-lti.yml under START_LTI=true. Set the
LTI11_* variables in docker/.env (LTI11_PUBLIC_URL, LTI11_GATEWAY_SECRET_KEY,
LTI11_GATEWAY_API_TOKEN, LTI11_CONSUMER_KEY, LTI11_CONSUMER_SECRET, etc.).

Unlike LTI 1.3 there is no dynamic registration: a consumer key/secret pair must be
entered manually both in Moodle's "External tool" activity config and in the
gateway's own consumers.json:


0. If we need to cerate these keys or renew them, we need to load the .env values 
  cd /home/ubuntu/chatbotIAHub/docker
  set -a
  source .env
  set +a
1. echo '{"'"$LTI11_CONSUMER_KEY"'": "'"$LTI11_CONSUMER_SECRET"'"}' > consumers.json
2. docker cp consumers.json lti11-gateway:/data/consumers.json
3. docker restart lti11-gateway   # consumers.json is only read at startup

In Moodle, configure the External tool manually (LTI version 1.1/1.2) with:
- Tool URL:       https://lti11.fcr.lat/lti11/launch
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


Update openwebui:
-----------------
docker compose -f docker-compose-openwebui.yml pull