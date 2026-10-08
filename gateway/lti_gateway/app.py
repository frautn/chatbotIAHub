import hashlib
import hmac
import unicodedata
from urllib.parse import quote

from flask import Flask, abort, jsonify, make_response, redirect, render_template_string, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pylti1p3.contrib.flask import FlaskMessageLaunch, FlaskOIDCLogin, FlaskRequest
from pylti1p3.deep_link import DeepLink
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.exception import LtiException, OIDCException
from pylti1p3.assignments_grades import AssignmentsGradesService
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.registration import Registration
from pylti1p3.service_connector import ServiceConnector
from pylti1p3.tool_config import ToolConfDict
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Settings, load_or_create_keys, load_platforms
from .store import LaunchStore
from .webui_client import find_resumable_chat

CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"
CLAIM_AGS = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
SSO_COOKIE = "lti_gw"
DEEPLINK_FORM = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Add chatbot activity</title>
<body style="font-family:sans-serif;max-width:32rem;margin:2rem auto">
<h1>Add chatbot activity</h1>
<form method="post" action="{{ action }}">
  <input type="hidden" name="state" value="{{ state }}">
  <p><label>Title<br><input name="title" value="Chatbot" required maxlength="255"></label></p>
  {% if models %}
  <p><label>Model<br>
    <select name="model">
      <option value="">(Open WebUI default)</option>
      {% for model_id, label in models %}
      <option value="{{ model_id }}">{{ label }}</option>
      {% endfor %}
    </select>
  </label></p>
  {% endif %}
  <p><label><input type="checkbox" name="graded" value="1"> Create a grade item</label></p>
  <p><label>Maximum score<br><input name="score_maximum" type="number" min="1" value="100"></label></p>
  <button type="submit">Add</button>
</form></body></html>"""


class ResourceLink(DeepLinkResource):
    """Omit empty `custom`: Moodle decodes `{}` to a PHP array and fails in params_to_string()."""

    def to_dict(self):
        item = super().to_dict()
        if not item.get("custom"):
            item.pop("custom", None)
        return item


def ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip()


def user_identity(settings: Settings, iss: str, client_id: str, sub: str, name: str):
    digest = hashlib.sha256(f"{iss}\n{client_id}\n{sub}".encode()).hexdigest()[:32]
    return f"lti-{digest}@{settings.email_domain}", ascii_fold(name) or "Learner"


def resolve_chat_id(store, settings, iss, client_id, link_id, sub, identity, model):
    """Chat id to resume for this resource link, if one can be determined.

    A resource link's chat id is sticky once found: the first launch after a
    chat exists claims it, and every later launch reuses it directly.
    """
    record = store.find(iss, client_id, link_id, sub)
    if not record:
        return None
    if record["chat_id"]:
        return record["chat_id"]
    if not settings.webui_internal_url:
        return None
    exclude = store.claimed_chat_ids(sub, link_id)
    chat_id = find_resumable_chat(
        settings.webui_internal_url, identity[0], identity[1], model, exclude
    )
    if chat_id:
        store.set_chat_id(iss, client_id, link_id, sub, chat_id)
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

    private_key, public_key = load_or_create_keys(settings.data_dir)
    platforms = load_platforms(settings.data_dir)
    tool_conf = ToolConfDict(platforms)
    for iss, conf in platforms.items():
        for item in conf if isinstance(conf, list) else [conf]:
            client_id = item["client_id"] if isinstance(conf, list) else None
            tool_conf.set_private_key(iss, private_key, client_id=client_id)
            tool_conf.set_public_key(iss, public_key, client_id=client_id)

    store = LaunchStore(settings.data_dir / "gateway.sqlite3")
    signer = URLSafeTimedSerializer(settings.secret_key)
    launch_url = f"{settings.public_url}/lti/launch"

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

    @app.errorhandler(LtiException)
    @app.errorhandler(OIDCException)
    def lti_error(error):
        app.logger.warning("LTI error: %s", error)
        return "Invalid LTI request.", 400

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/lti/jwks")
    def jwks():
        # Served before any platform is registered: Moodle needs it to create the client_id.
        return jsonify({"keys": [Registration.get_jwk(public_key)]})

    @app.get("/lti/config")
    def config():
        """URLs to paste into Moodle's manual LTI 1.3 tool configuration."""
        return jsonify(
            {
                "tool_url": launch_url,
                "initiate_login_url": f"{settings.public_url}/lti/login",
                "redirection_uris": [launch_url, f"{settings.public_url}/lti/deeplink"],
                "public_keyset_url": f"{settings.public_url}/lti/jwks",
                "deep_linking_url": launch_url,
            }
        )

    @app.route("/lti/login", methods=["GET", "POST"])
    def login():
        target = request.values.get("target_link_uri", "")
        if target != launch_url:
            abort(400)
        return FlaskOIDCLogin(FlaskRequest(), tool_conf).redirect(target)

    @app.post("/lti/launch")
    def launch():
        message = FlaskMessageLaunch(FlaskRequest(), tool_conf)
        data = message.get_launch_data()
        iss = message.get_iss()
        client_id = message.get_client_id()
        deployment_id = data[CLAIM + "deployment_id"]

        if message.is_deep_link_launch():
            message.get_deep_link()  # raises if deep_linking_settings are missing
            state = signer.dumps(
                {
                    "iss": iss,
                    "client_id": client_id,
                    "deployment_id": deployment_id,
                    "settings": data[
                        "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings"
                    ],
                },
                salt="deeplink",
            )
            return render_template_string(
                DEEPLINK_FORM,
                action=f"{settings.public_url}/lti/deeplink",
                state=state,
                models=settings.models,
            )

        if not message.is_resource_launch():
            abort(400)

        sub = data["sub"]
        link_id = data[CLAIM + "resource_link"]["id"]
        context = data.get(CLAIM + "context") or {}
        store.save(
            iss, client_id, deployment_id, link_id, sub, context.get("id"), data.get(CLAIM_AGS)
        )
        model = (data.get(CLAIM + "custom") or {}).get("model")
        identity = user_identity(settings, iss, client_id, sub, data.get("name", ""))
        chat_id = resolve_chat_id(store, settings, iss, client_id, link_id, sub, identity, model)
        return sso_response(identity, model, chat_id)

    @app.post("/lti/deeplink")
    def deeplink():
        try:
            state = signer.loads(request.form.get("state", ""), salt="deeplink", max_age=900)
        except BadSignature:
            abort(400)
        registration = tool_conf.find_registration_by_params(state["iss"], state["client_id"])
        link_settings = state["settings"]
        title = request.form.get("title", "Chatbot")[:255] or "Chatbot"

        resource = ResourceLink().set_url(launch_url).set_title(title)

        model = request.form.get("model", "").strip()
        if model:
            if settings.models and model not in dict(settings.models):
                abort(400)
            resource.set_custom_params({"model": model})

        if request.form.get("graded") and "ltiResourceLink" in link_settings.get(
            "accept_types", []
        ):
            try:
                maximum = float(request.form.get("score_maximum", "100"))
            except ValueError:
                abort(400)
            if not 0 < maximum <= 1_000_000:
                abort(400)
            resource.set_lineitem(LineItem().set_score_maximum(maximum).set_label(title))

        deep_link = DeepLink(registration, state["deployment_id"], link_settings)
        return deep_link.output_response_form([resource])

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

        chat_id = body.get("chat_id")
        if chat_id:
            # Caller only knows the Open WebUI chat (e.g. a grading function
            # running inside a chat), not the underlying LTI launch identifiers.
            record = store.find_by_chat_id(chat_id)
            if record:
                iss, client_id = record["iss"], record["client_id"]
                link_id, sub = record["resource_link_id"], record["sub"]
        else:
            try:
                iss, client_id = body["iss"], body["client_id"]
                link_id, sub = body["resource_link_id"], body["sub"]
            except KeyError:
                abort(400)
            record = store.find(iss, client_id, link_id, sub)

        if not record or not record["ags"]:
            abort(404)

        registration = tool_conf.find_registration_by_params(iss, client_id)
        ags = AssignmentsGradesService(ServiceConnector(registration), record["ags"])
        grade = (
            Grade()
            .set_score_given(given)
            .set_score_maximum(maximum)
            .set_activity_progress(body.get("activity_progress", "Completed"))
            .set_grading_progress(body.get("grading_progress", "FullyGraded"))
            .set_user_id(sub)
        )
        if body.get("comment"):
            grade.set_comment(str(body["comment"])[:1000])
        lineitem = None
        if not record["ags"].get("lineitem"):
            lineitem = (
                LineItem()
                .set_tag("chatbot")
                .set_score_maximum(maximum)
                .set_label(body.get("label", "Chatbot"))
                .set_resource_link_id(link_id)
            )
        ags.put_grade(grade, lineitem)
        return "", 204

    return app

