import hashlib
import secrets
import sqlite3
import time

import requests
from flask import Flask, abort, current_app, make_response, render_template_string, request

from .config import AdminSSOSettings
from .webui_client import REQUEST_TIMEOUT

HANDOFF_TTL = 60
HANDOFF_PATH = "/lti/admin/complete"
OVERVIEW_PATH = "/admin/users/overview"
HANDOFF_FORM = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Open WebUI administration</title>
<body><form method="post" action="{{ action }}" id="handoff">
<input type="hidden" name="ticket" value="{{ ticket }}">
<button type="submit">Continue to Open WebUI administration</button>
</form><script nonce="{{ nonce }}">document.getElementById("handoff").submit();</script>
</body></html>"""
SIGNIN_PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Signing in to Open WebUI</title>
<body><p>Signing in to Open WebUI administration...</p>
<noscript>Sign-in requires JavaScript. Enable it, then reopen the activity from Moodle.</noscript>
<script nonce="{{ nonce }}">
try {
  localStorage.setItem("token", {{ token|tojson }});
  localStorage.removeItem("redirectPath");
  window.location.replace({{ target|tojson }});
} catch (error) {
  document.body.textContent = "Sign-in failed: allow browser storage, then reopen the activity from Moodle.";
}
</script></body></html>"""


def private_page(template: str, **context):
    nonce = secrets.token_urlsafe(24)
    response = make_response(render_template_string(template, nonce=nonce, **context))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'nonce-{nonce}'; "
        "form-action https:; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


class AdminSSO:
    """Single-use cross-origin handoff; never persist Open WebUI credentials or tokens."""

    def __init__(self, app: Flask, settings: AdminSSOSettings, path, session_ttl: int):
        self.settings = settings
        self.path = path
        self.session_ttl = session_ttl
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS admin_handoffs "
                "(digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)"
            )
        app.add_url_rule(HANDOFF_PATH, "admin_complete", self.complete, methods=["POST"])

    def launch_response(self):
        ticket = secrets.token_urlsafe(32)
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        now = int(time.time())
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM admin_handoffs WHERE expires <= ?", (now,))
            db.execute("INSERT INTO admin_handoffs VALUES (?, ?)", (digest, now + HANDOFF_TTL))
        return private_page(
            HANDOFF_FORM, action=self.settings.public_url + HANDOFF_PATH, ticket=ticket
        )

    def complete(self):
        if request.host_url.rstrip("/") != self.settings.public_url:
            abort(400, "Open the admin activity from Moodle on its configured host.")
        ticket = request.form.get("ticket", "")
        if not ticket or len(ticket) > 128:
            abort(400, "Missing or invalid admin handoff.")
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            # DELETE is atomic across gunicorn workers; only one request can redeem a ticket.
            result = db.execute(
                "DELETE FROM admin_handoffs WHERE digest = ? AND expires > ?",
                (digest, int(time.time())),
            )
            consumed = result.rowcount == 1
        if not consumed:
            abort(400, "Admin handoff expired or already used. Reopen the activity from Moodle.")

        try:
            signin = requests.post(
                self.settings.public_url + "/api/v1/auths/signin",
                json={"email": self.settings.email, "password": self.settings.password},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            signin.raise_for_status()
            if signin.status_code != 200:
                current_app.logger.error("Unexpected status from shared admin Open WebUI sign-in")
                abort(502, "Unexpected Open WebUI admin sign-in response.")
            account = signin.json()
        except (requests.RequestException, ValueError):
            # Do not log response bodies or exception URLs containing account credentials.
            current_app.logger.error("Shared admin Open WebUI sign-in failed")
            abort(502, "Open WebUI admin sign-in failed. Contact the administrator.")
        if (
            not isinstance(account, dict)
            or account.get("role") != "admin"
            or not isinstance(account.get("email"), str)
            or account["email"].casefold() != self.settings.email.casefold()
            or not isinstance(account.get("token"), str)
            or not account["token"]
        ):
            current_app.logger.error("Shared admin sign-in did not return the configured admin account")
            abort(403, "The configured Open WebUI account must be an existing administrator.")

        response = private_page(SIGNIN_PAGE, token=account["token"], target=OVERVIEW_PATH)
        response.set_cookie(
            "token", account["token"], max_age=self.session_ttl,
            secure=True, httponly=True, samesite="Lax", path="/",
        )
        return response
