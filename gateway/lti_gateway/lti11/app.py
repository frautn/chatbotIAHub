import hashlib
import hmac
from urllib.parse import quote

from flask import Flask, abort, make_response, redirect, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix

from ..app import ascii_fold
from ..webui_client import find_resumable_chat
from .config import Settings, load_consumers
from .oauth1 import verify_launch
from .outcomes import send_replace_result
from .store import LaunchStore

SSO_COOKIE = "lti11_gw"
LAUNCH_MESSAGE_TYPE = "basic-lti-launch-request"


def user_identity(settings: Settings, consumer_key: str, user_id: str, name: str):
    digest = hashlib.sha256(f"{consumer_key}\n{user_id}".encode()).hexdigest()[:32]
    return f"lti11-{digest}@{settings.email_domain}", ascii_fold(name) or "Learner"


def claim_chat_by_email(store, settings, email, chat_id):
    """Link a chat to its launch by identity hash, for a learner's very first
    chat (mirrors the LTI 1.3 gateway's equivalent helper, see app.py there)."""
    prefix, suffix = "lti11-", f"@{settings.email_domain}"
    if not (email.startswith(prefix) and email.endswith(suffix)):
        return None
    digest = email[len(prefix) : -len(suffix)]
    for candidate in store.unclaimed():
        expected = hashlib.sha256(
            f"{candidate['consumer_key']}\n{candidate['user_id']}".encode()
        ).hexdigest()[:32]
        if expected == digest:
            store.set_chat_id(
                candidate["consumer_key"], candidate["resource_link_id"], candidate["user_id"], chat_id
            )
            return candidate
    return None


def resolve_chat_id(store, settings, consumer_key, link_id, user_id, identity, model):
    """Chat id to resume for this resource link, if one can be determined."""
    record = store.find(consumer_key, link_id, user_id)
    if not record:
        return None
    if record["chat_id"]:
        return record["chat_id"]
    if not settings.webui_internal_url:
        return None
    exclude = store.claimed_chat_ids(user_id, link_id)
    chat_id = find_resumable_chat(settings.webui_internal_url, identity[0], identity[1], model, exclude)
    if chat_id:
        store.set_chat_id(consumer_key, link_id, user_id, chat_id)
    return chat_id


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.secret_key = settings.secret_key
    app.config.update(
        SESSION_COOKIE_SECURE=settings.secure,
        SESSION_COOKIE_SAMESITE="None" if settings.secure else "Lax",
        SESSION_COOKIE_HTTPONLY=True,
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    secrets = load_consumers(settings.data_dir)
    store = LaunchStore(settings.data_dir / "gateway-lti11.sqlite3")
    signer = URLSafeTimedSerializer(settings.secret_key)

    def sso_response(identity: tuple[str, str], model: str | None = None, chat_id: str | None = None):
        if chat_id:
            # Resuming a previously opened chat for this resource link.
            target = f"{settings.public_url}/c/{chat_id}"
        else:
            target = f"{settings.public_url}/"
            if model:
                # Open WebUI preselects this model for the new chat from the `models` query param.
                target += f"?models={quote(model)}"
        response = redirect(target)
        response.set_cookie(
            SSO_COOKIE,
            signer.dumps({"email": identity[0], "name": identity[1]}, salt="sso"),
            max_age=settings.session_ttl,
            secure=settings.secure,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        return response

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.post("/lti11/launch")
    def launch():
        if not secrets:
            abort(503)
        if not verify_launch(request.url, request.form.items(multi=True), secrets, store):
            abort(401)
        if request.form.get("lti_message_type") != LAUNCH_MESSAGE_TYPE:
            abort(400)

        consumer_key = request.form.get("oauth_consumer_key", "")
        user_id = request.form.get("user_id", "")
        link_id = request.form.get("resource_link_id", "")
        if not (consumer_key and user_id and link_id):
            abort(400)

        name = request.form.get("lis_person_name_full") or request.form.get(
            "lis_person_name_given", ""
        )
        context_id = request.form.get("context_id")
        sourcedid = request.form.get("lis_result_sourcedid")
        outcome_url = request.form.get("lis_outcome_service_url")
        store.save(consumer_key, link_id, user_id, context_id, sourcedid, outcome_url)

        model = (request.form.get("custom_model") or "").strip()
        if model and settings.models and model not in dict(settings.models):
            app.logger.warning("Ignoring unknown custom_model %r for consumer %s", model, consumer_key)
            model = ""

        identity = user_identity(settings, consumer_key, user_id, name)
        chat_id = resolve_chat_id(store, settings, consumer_key, link_id, user_id, identity, model)
        return sso_response(identity, model, chat_id)

    @app.get("/auth")
    def auth():
        """nginx auth_request target: maps the gateway session to Open WebUI trusted headers."""
        try:
            identity = signer.loads(
                request.cookies.get(SSO_COOKIE, ""), salt="sso", max_age=settings.session_ttl
            )
        except BadSignature:
            return "", 401
        response = make_response("", 204)
        response.headers["X-LTI-Email"] = identity["email"]
        response.headers["X-LTI-Name"] = identity["name"]
        if settings.student_group:
            response.headers["X-LTI-Group"] = settings.student_group
        return response

    @app.post("/api/scores")
    def scores():
        if not settings.api_token:
            abort(404)
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(supplied, settings.api_token):
            abort(401)
        body = request.get_json(silent=True) or {}
        try:
            given = float(body["score_given"])
            maximum = float(body["score_maximum"])
        except (KeyError, TypeError, ValueError):
            abort(400)
        if maximum <= 0:
            abort(400)

        chat_id = body.get("chat_id")
        if chat_id:
            # Caller only knows the Open WebUI chat (e.g. a grading function
            # running inside a chat), not the underlying LTI launch identifiers.
            record = store.find_by_chat_id(chat_id)
            if not record and body.get("email"):
                # The learner's first-ever chat: resolve_chat_id hasn't linked it yet.
                record = claim_chat_by_email(store, settings, body["email"], chat_id)
        else:
            try:
                consumer_key = body["consumer_key"]
                link_id = body["resource_link_id"]
                user_id = body["user_id"]
            except KeyError:
                abort(400)
            record = store.find(consumer_key, link_id, user_id)

        if not record or not record["outcome_service_url"] or not record["sourcedid"]:
            abort(404)
        secret = secrets.get(record["consumer_key"])
        if not secret:
            abort(404)

        score = max(0.0, min(1.0, given / maximum))
        ok = send_replace_result(
            record["outcome_service_url"], record["consumer_key"], secret, record["sourcedid"], score
        )
        if not ok:
            abort(502)
        return "", 204

    return app
