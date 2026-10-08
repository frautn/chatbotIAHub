# LTI 1.3 gateway

Flask service that lets Moodle launch Open WebUI as an LTI 1.3 External Tool:
OIDC login, launch validation, Deep Linking, automatic SSO into a student-facing
Open WebUI, and AGS score submission (no automatic grading policy).

## How SSO works

1. Moodle starts `/lti/login`, then POSTs a signed id_token to `/lti/launch`.
2. The gateway validates it, stores the AGS context, and sets a signed `lti_gw`
   cookie, then redirects to `/` (or `/?models=<id>` if the activity pins a
   model, see below).
3. nginx (`docker/nginx-lti.example.conf`) runs `auth_request` against `/auth`,
   which returns `X-LTI-Email`/`X-LTI-Name`/`X-LTI-Group`. nginx forwards them as
   `X-Forwarded-Email`/`X-Forwarded-Name`/`X-Forwarded-Groups`, which the
   `open-webui-lti` container trusts (`WEBUI_AUTH_TRUSTED_*`). Open WebUI creates
   the user on first visit and syncs their group membership on every sign-in.
4. The email is a stable hash of issuer + client + LTI `sub`; no real email is shared.
5. All launching students are put in the Open WebUI group named by
   `GATEWAY_STUDENT_GROUP` (`estudiantes` by default). **That group must already
   exist in Open WebUI** (*Admin Panel > Groups*) — Open WebUI's trusted-header
   group sync only adds users to groups matching an existing name, it does not
   create them. Open WebUI also removes the user from any other group not in
   this list, so don't reuse `estudiantes` for manual group assignments.

`open-webui-lti` trusts identity headers, so it is bound to `127.0.0.1` and must
only be reached through nginx. Keep the stock instance for administrators.

## Picking a model via Deep Linking

Set `GATEWAY_MODELS` (`LTI_GATEWAY_MODELS` in `docker/.env`) to the Open WebUI
model IDs teachers may offer, as comma-separated `id` or `id:Label` entries,
e.g. `cinematica-ej-1:Cinemática - Ejercicio 1,cinematica-ej-2:Cinemática -
Ejercicio 2`. When set, Moodle's "Add chatbot activity" Deep Linking form shows
a model picker; the chosen model is stored as an LTI custom parameter on the
resource link, and every resource launch of that activity redirects students
straight into Open WebUI with that model preselected (`/?models=<id>`). Leave
`GATEWAY_MODELS` empty to hide the picker and always use Open WebUI's default
model.

## Resuming a conversation

The gateway remembers, per resource link + learner, the Open WebUI chat they
used. The first time a learner launches an activity there's nothing to resume,
so they land on a new chat as usual. From the next launch onward, the gateway
signs in to Open WebUI on the learner's behalf (`GATEWAY_WEBUI_INTERNAL_URL`,
reachable only inside the Docker network) to find their most recent chat and
redirects straight to it (`/c/<chat_id>`), picking up the conversation where
they left off.

When the activity pins a model (see above), only a chat using that model is
eligible, so distinct activities never share a conversation. Without a pinned
model, the learner's single most recent chat is reused, which only disambiguates
correctly if the learner has one chatbot activity. `GATEWAY_WEBUI_INTERNAL_URL`
defaults to `http://open-webui-lti:8080` in `docker-compose-lti.yml`; clear it
to disable chat resuming entirely.

## Deploy

1. Set `LTI_PUBLIC_URL`, `LTI_GATEWAY_SECRET_KEY`, `LTI_GATEWAY_API_TOKEN`
   (`openssl rand -hex 32`) in `docker/.env`, and `START_LTI=true`; run `docker/start.sh`.
2. Install `docker/nginx-lti.example.conf` (set `server_name` and certificates).
3. In Moodle: *Site administration > Plugins > Activity modules > External tool >
   Manage tools > configure a tool manually*, LTI version 1.3, public key type
   "JWK keyset", using the URLs from `https://<LTI_PUBLIC_URL>/lti/config`. Enable
   Deep Linking (content selection URL = tool URL) and AGS ("Use this service for
   grade sync and column management"), and set "Default launch container" to
   "New window" (cookies in iframes are often blocked).
4. Copy the values Moodle shows (Platform ID, Client ID, Deployment ID, and its
   authentication/token/keyset URLs) into `platforms.json`:

   ```json
   {
     "https://moodle.example.com": {
       "client_id": "CLIENT_ID",
       "auth_login_url": "https://moodle.example.com/mod/lti/auth.php",
       "auth_token_url": "https://moodle.example.com/mod/lti/token.php",
       "key_set_url": "https://moodle.example.com/mod/lti/certs.php",
       "deployment_ids": ["1"]
     }
   }
   ```

   Then `docker cp platforms.json lti-gateway:/data/platforms.json` and
   `docker restart lti-gateway`.

## Submitting scores

The gateway only provides the AGS plumbing. A trusted backend submits scores:

```
curl -X POST http://127.0.0.1:8090/api/scores \
  -H "Authorization: Bearer $LTI_GATEWAY_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"iss":"...","client_id":"...","resource_link_id":"...","sub":"...","score_given":8,"score_maximum":10}'
```

A caller that only knows the Open WebUI chat (e.g. an Open WebUI Function
grading the conversation) can pass `chat_id` instead of
`iss`/`client_id`/`resource_link_id`/`sub` — the gateway resolves the LTI
identifiers from the same `launches` record that tracks chat resuming:

```
curl -X POST http://127.0.0.1:8090/api/scores \
  -H "Authorization: Bearer $LTI_GATEWAY_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"chat_id":"...","score_given":8,"score_maximum":10}'
```

This only resolves once the learner's `chat_id` has been recorded, which
requires `GATEWAY_WEBUI_INTERNAL_URL` to be set (see "Resuming a
conversation" above) — the chat must have been reached through at least one
resumed launch, or be set explicitly via `LaunchStore.set_chat_id`.

The learner must have launched the activity at least once. The endpoint is blocked in nginx.

## Operations

* Tool keys are generated in the `lti-gateway-data` volume (`/data/keys`); rotate by
  deleting them and restarting, then refresh the keyset in Moodle.
* Troubleshooting: `docker logs lti-gateway` shows the validation failure reason;
  clients only see a generic 400.

## Development

```
python -m venv venv && venv/bin/pip install -r gateway/requirements-dev.txt
venv/bin/python -m pytest gateway
```
