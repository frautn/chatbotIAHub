import hashlib
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

import jwt
import pytest
import requests

from conftest import CLAIM, CLIENT_ID, ISS, PUBLIC_URL, resource_claims
from lti_gateway.app import create_app
from lti_gateway.config import AdminSSOSettings, Settings
from test_gateway import deep_link_claims

ADMIN_URL = "https://lti-admin.fcr.lat"
ADMIN_INTERNAL_URL = "http://open-webui-lti:8080"
ADMIN_LAUNCH = f"{PUBLIC_URL}/lti/admin/launch"
ADMIN_SETTINGS = AdminSSOSettings(ADMIN_URL, "shared-admin@example.com", ADMIN_INTERNAL_URL)
ADMIN_ACCOUNT = {
    "email": ADMIN_SETTINGS.email,
    "role": "admin",
    "token": "test-openwebui-session",
}


@pytest.fixture
def admin_client(client, settings):
    app = create_app(replace(settings, admin_sso=ADMIN_SETTINGS))
    app.config["TESTING"] = True
    return app.test_client()


def admin_launch(client, platform, claims=None, tamper=False):
    login = client.post(
        "/lti/login",
        data={
            "iss": ISS,
            "login_hint": "hint",
            "client_id": CLIENT_ID,
            "target_link_uri": ADMIN_LAUNCH,
        },
    )
    assert login.status_code == 302
    query = parse_qs(urlparse(login.headers["Location"]).query)
    token = platform.id_token(
        query["nonce"][0],
        {**(claims or resource_claims()), CLAIM + "target_link_uri": ADMIN_LAUNCH},
    )
    if tamper:
        token = token[:-4] + "AAAA"
    return client.post(
        "/lti/admin/launch", data={"state": query["state"][0], "id_token": token}
    )


def handoff_ticket(client, platform):
    response = admin_launch(client, platform)
    assert response.status_code == 200
    return re.search(r'name="ticket" value="([^"]+)"', response.text).group(1)


def complete(client, ticket):
    return client.post(
        "/lti/admin/complete", base_url=ADMIN_URL, data={"ticket": ticket}
    )


def signin_result(account=ADMIN_ACCOUNT, status=200):
    return Mock(status_code=status, json=Mock(return_value=account))


def test_admin_disabled_by_default(client):
    assert client.get("/lti/admin/config").status_code == 404
    assert client.post("/lti/admin/launch").status_code == 404
    assert client.post("/lti/admin/complete").status_code == 404
    response = client.post(
        "/lti/login",
        data={"iss": ISS, "login_hint": "hint", "client_id": CLIENT_ID,
              "target_link_uri": ADMIN_LAUNCH},
    )
    assert response.status_code == 400


def test_admin_config_is_separate_and_student_config_unchanged(admin_client):
    config = admin_client.get("/lti/admin/config").json
    assert config["tool_url"] == ADMIN_LAUNCH
    assert config["deep_linking_url"] == ADMIN_LAUNCH
    assert config["redirection_uris"] == [ADMIN_LAUNCH]
    assert admin_client.get("/lti/config").json["tool_url"] == f"{PUBLIC_URL}/lti/launch"


@pytest.mark.parametrize("is_admin", [False, True])
def test_student_and_admin_clients_share_one_issuer(client, settings, platform, is_admin):
    registrations = [
        {
            "client_id": client_id,
            "auth_login_url": f"{ISS}/auth",
            "auth_token_url": f"{ISS}/token",
            "key_set": platform.jwks,
            "deployment_ids": [deployment_id],
        }
        for client_id, deployment_id in [(CLIENT_ID, "1"), ("admin-client", "2")]
    ]
    settings.data_dir.joinpath("platforms.json").write_text(json.dumps({ISS: registrations}))
    app = create_app(replace(settings, admin_sso=ADMIN_SETTINGS))
    app.config["TESTING"] = True
    multi_client = app.test_client()
    client_id = "admin-client" if is_admin else CLIENT_ID
    deployment_id = "2" if is_admin else "1"
    path = "/lti/admin/launch" if is_admin else "/lti/launch"
    target = PUBLIC_URL + path
    login = multi_client.post(
        "/lti/login",
        data={"iss": ISS, "login_hint": "hint", "client_id": client_id,
              "target_link_uri": target},
    )
    assert login.status_code == 302
    query = parse_qs(urlparse(login.headers["Location"]).query)
    assert query["client_id"] == [client_id]
    token = platform.id_token(
        query["nonce"][0],
        resource_claims(**{
            "aud": client_id,
            CLAIM + "deployment_id": deployment_id,
            CLAIM + "target_link_uri": target,
        }),
    )
    with patch("lti_gateway.app.find_resumable_chat", return_value=None):
        response = multi_client.post(path, data={"state": query["state"][0], "id_token": token})
    if is_admin:
        assert response.status_code == 200
        assert f'action="{ADMIN_URL}/lti/admin/complete"' in response.text
        assert multi_client.get_cookie("lti_gw") is None
    else:
        assert response.status_code == 302
        assert response.headers["Location"] == f"{PUBLIC_URL}/"
        assert multi_client.get("/auth").headers["X-LTI-Group"] == "estudiantes"


def test_learner_launch_creates_only_opaque_handoff(admin_client, platform, settings):
    with patch("lti_gateway.app.find_resumable_chat") as resume:
        response = admin_launch(admin_client, platform)
    resume.assert_not_called()
    assert response.status_code == 200
    assert f'action="{ADMIN_URL}/lti/admin/complete"' in response.text
    assert ADMIN_SETTINGS.email not in response.text
    assert ADMIN_INTERNAL_URL not in response.text
    assert admin_client.get_cookie("lti_gw") is None
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    ticket = re.search(r'name="ticket" value="([^"]+)"', response.text).group(1)
    with sqlite3.connect(settings.data_dir / "admin-sso.sqlite3") as db:
        row = db.execute("SELECT digest FROM admin_handoffs").fetchone()
    assert row[0] == hashlib.sha256(ticket.encode()).hexdigest()
    with sqlite3.connect(settings.data_dir / "gateway.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM launches").fetchone()[0] == 0
    assert admin_client.get("/auth").status_code == 401


def test_admin_launch_requires_valid_lti_and_matching_target(admin_client, platform):
    assert admin_launch(admin_client, platform, tamper=True).status_code == 400
    assert admin_client.post(
        "/lti/admin/launch", data={"id_token": "forged", "state": "no-login"}
    ).status_code == 400

    from conftest import do_login

    state, nonce = do_login(admin_client)
    token = platform.id_token(nonce, resource_claims())
    assert admin_client.post(
        "/lti/admin/launch", data={"state": state, "id_token": token}
    ).status_code == 400


def test_admin_deep_link_is_ungraded_and_has_no_student_custom_params(admin_client, platform):
    response = admin_launch(admin_client, platform, deep_link_claims())
    assert response.status_code == 200
    token = re.search(r'name="JWT"\s+value="([^"]+)"', response.text).group(1)
    data = jwt.decode(token, options={"verify_signature": False})
    item = data["https://purl.imsglobal.org/spec/lti-dl/claim/content_items"][0]
    assert item["url"] == ADMIN_LAUNCH
    assert item["title"] == "Open WebUI users overview"
    assert "lineItem" not in item
    assert "custom" not in item


def test_admin_handoff_signs_in_once_and_sets_target_host_session(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result()) as signin:
        response = complete(admin_client, ticket)
        replay = complete(admin_client, ticket)
    assert response.status_code == 200
    assert replay.status_code == 400
    signin.assert_called_once_with(
        ADMIN_INTERNAL_URL + "/api/v1/auths/signin",
        json={"email": ADMIN_SETTINGS.email, "password": "lti-gateway"},
        headers={"X-Forwarded-Email": ADMIN_SETTINGS.email},
        timeout=5, allow_redirects=False,
    )
    assert 'localStorage.setItem("token", "test-openwebui-session")' in response.text
    assert 'window.location.replace("/admin/users/overview")' in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert "nonce-" in response.headers["Content-Security-Policy"]
    cookie = response.headers["Set-Cookie"]
    assert "token=test-openwebui-session;" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    assert "Domain=" not in cookie
    assert admin_client.get_cookie("token", domain="tool.test") is None


@pytest.mark.parametrize("ticket", ["", "forged", "x" * 129])
def test_invalid_handoff_never_contacts_openwebui(admin_client, ticket):
    with patch("lti_gateway.admin_sso.requests.post") as signin:
        assert complete(admin_client, ticket).status_code == 400
    signin.assert_not_called()


def test_expired_handoff_is_rejected(admin_client, platform, settings):
    ticket = handoff_ticket(admin_client, platform)
    with sqlite3.connect(settings.data_dir / "admin-sso.sqlite3") as db:
        db.execute("UPDATE admin_handoffs SET expires = 0")
    with patch("lti_gateway.admin_sso.requests.post") as signin:
        assert complete(admin_client, ticket).status_code == 400
    signin.assert_not_called()


def test_wrong_host_does_not_consume_ticket(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result()) as signin:
        assert admin_client.post(
            "/lti/admin/complete", data={"ticket": ticket}
        ).status_code == 400
        signin.assert_not_called()
        assert complete(admin_client, ticket).status_code == 200


def test_browser_identity_headers_are_not_forwarded_to_internal_signin(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result()) as signin:
        response = admin_client.post(
            "/lti/admin/complete", base_url=ADMIN_URL, data={"ticket": ticket},
            headers={
                "X-Forwarded-Email": "attacker@example.com",
                "X-Forwarded-Role": "admin",
                "X-Forwarded-Groups": "estudiantes",
            },
        )
    assert response.status_code == 200
    assert signin.call_args.kwargs["headers"] == {"X-Forwarded-Email": ADMIN_SETTINGS.email}


def test_concurrent_redemption_only_signs_in_once(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)

    def redeem():
        with admin_client.application.test_client() as client:
            return complete(client, ticket).status_code

    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result()) as signin:
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: redeem(), range(2)))
    assert sorted(statuses) == [200, 400]
    signin.assert_called_once()


def test_ticket_survives_gateway_restart(admin_client, platform, settings):
    ticket = handoff_ticket(admin_client, platform)
    restarted = create_app(replace(settings, admin_sso=ADMIN_SETTINGS)).test_client()
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result()):
        assert complete(restarted, ticket).status_code == 200


@pytest.mark.parametrize("account", [
    {**ADMIN_ACCOUNT, "role": "user"},
    {**ADMIN_ACCOUNT, "email": "someone-else@example.com"},
    {**ADMIN_ACCOUNT, "token": ""},
    {"challenge_token": "mfa-required"},
    ["not-an-account"],
    {},
    None,
])
def test_handoff_requires_configured_existing_admin(admin_client, platform, account):
    ticket = handoff_ticket(admin_client, platform)
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result(account)):
        response = complete(admin_client, ticket)
    assert response.status_code == 403
    assert "Set-Cookie" not in response.headers
    assert "localStorage" not in response.text


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("unreachable"),
    requests.Timeout("timeout"),
    requests.HTTPError("unauthorized"),
    ValueError("invalid JSON"),
])
def test_backend_failures_are_explicit_and_ticket_is_consumed(admin_client, platform, failure):
    ticket = handoff_ticket(admin_client, platform)
    with patch("lti_gateway.admin_sso.requests.post", side_effect=failure):
        response = complete(admin_client, ticket)
    assert response.status_code == 502
    assert "Set-Cookie" not in response.headers
    assert "Contact the administrator" in response.text
    assert complete(admin_client, ticket).status_code == 400


def test_backend_redirect_is_not_followed(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    with patch(
        "lti_gateway.admin_sso.requests.post", return_value=signin_result(status=302)
    ):
        assert complete(admin_client, ticket).status_code == 502


def test_backend_invalid_json_is_reported(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    response = signin_result()
    response.json.side_effect = ValueError("invalid JSON")
    with patch("lti_gateway.admin_sso.requests.post", return_value=response):
        assert complete(admin_client, ticket).status_code == 502


def test_session_token_is_escaped_in_inline_script(admin_client, platform):
    ticket = handoff_ticket(admin_client, platform)
    account = {**ADMIN_ACCOUNT, "token": '</script><script>alert("bad")</script>'}
    with patch("lti_gateway.admin_sso.requests.post", return_value=signin_result(account)):
        response = complete(admin_client, ticket)
    assert response.status_code == 200
    assert account["token"] not in response.text
    assert "\\u003c/script\\u003e" in response.text


def test_student_launch_still_uses_student_sso_with_admin_enabled(admin_client, platform):
    from conftest import post_launch

    with patch("lti_gateway.admin_sso.requests.post") as signin:
        response = post_launch(admin_client, platform, resource_claims())
    assert response.status_code == 302
    assert response.headers["Location"] == f"{PUBLIC_URL}/"
    assert admin_client.get("/auth").headers["X-LTI-Group"] == "estudiantes"
    signin.assert_not_called()


@pytest.mark.parametrize("url", [
    "http://owui.fcr.lat", "https://owui.fcr.lat/path", "https://user@owui.fcr.lat",
    "https://owui.fcr.lat?query=1", "https://owui.fcr.lat#fragment",
])
def test_admin_url_must_be_https_origin(url):
    with pytest.raises(ValueError):
        AdminSSOSettings(url, ADMIN_SETTINGS.email, ADMIN_INTERNAL_URL)


@pytest.mark.parametrize("url", [
    "", "ftp://open-webui-lti", "http://user:password@open-webui-lti",
    "http://open-webui-lti/path", "http://open-webui-lti?query=1",
])
def test_admin_internal_url_must_be_http_origin(url):
    with pytest.raises(ValueError):
        AdminSSOSettings(ADMIN_URL, ADMIN_SETTINGS.email, url)


def test_admin_and_student_hosts_must_be_distinct(settings):
    admin = AdminSSOSettings("https://tool.test", ADMIN_SETTINGS.email, ADMIN_INTERNAL_URL)
    with pytest.raises(ValueError, match="different hostnames"):
        replace(settings, admin_sso=admin)


@pytest.mark.parametrize("email", ["", " ", "admin@example.com\r\nX-Injected: value"])
def test_invalid_shared_admin_email_is_rejected(email):
    with pytest.raises(ValueError):
        AdminSSOSettings(ADMIN_URL, email, ADMIN_INTERNAL_URL)


def test_admin_config_is_explicit_and_requires_internal_url(monkeypatch):
    monkeypatch.setenv("GATEWAY_SECRET_KEY", "test-secret")
    monkeypatch.setenv("GATEWAY_PUBLIC_URL", PUBLIC_URL)
    monkeypatch.setenv("GATEWAY_ADMIN_ENABLED", "false")
    assert Settings.from_env().admin_sso is None
    monkeypatch.setenv("GATEWAY_ADMIN_ENABLED", "true")
    monkeypatch.setenv("GATEWAY_ADMIN_PUBLIC_URL", ADMIN_URL)
    monkeypatch.setenv("GATEWAY_ADMIN_EMAIL", ADMIN_SETTINGS.email)
    monkeypatch.delenv("GATEWAY_ADMIN_WEBUI_INTERNAL_URL", raising=False)
    with pytest.raises(RuntimeError, match="GATEWAY_ADMIN_WEBUI_INTERNAL_URL"):
        Settings.from_env()
    monkeypatch.setenv("GATEWAY_ADMIN_WEBUI_INTERNAL_URL", ADMIN_INTERNAL_URL)
    monkeypatch.delenv("GATEWAY_ADMIN_PASSWORD", raising=False)
    assert Settings.from_env().admin_sso == ADMIN_SETTINGS
