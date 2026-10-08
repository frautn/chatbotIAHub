import json
from unittest.mock import patch

from itsdangerous import URLSafeTimedSerializer

from conftest import (
    CLAIM,
    CLIENT_ID,
    DEPLOYMENT_ID,
    ISS,
    LAUNCH_URL,
    PUBLIC_URL,
    post_launch,
    resource_claims,
)

AGS = {
    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
    "lineitem": f"{ISS}/lineitems/1",
}
CLAIM_AGS = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"


def test_resource_launch_sets_sso_and_auth_returns_trusted_headers(client, platform):
    response = post_launch(client, platform, resource_claims())
    assert response.status_code == 302
    assert response.headers["Location"] == f"{PUBLIC_URL}/"

    auth = client.get("/auth")
    assert auth.status_code == 204
    assert auth.headers["X-LTI-Email"].startswith("lti-")
    assert auth.headers["X-LTI-Email"].endswith("@lti.invalid")
    assert auth.headers["X-LTI-Name"] == "Ana Perez"
    assert auth.headers["X-LTI-Group"] == "estudiantes"


def test_auth_omits_group_header_when_student_group_is_empty(settings, platform):
    settings.data_dir.joinpath("platforms.json").write_text(
        json.dumps(
            {
                ISS: {
                    "client_id": CLIENT_ID,
                    "auth_login_url": f"{ISS}/auth",
                    "auth_token_url": f"{ISS}/token",
                    "key_set": platform.jwks,
                    "deployment_ids": [DEPLOYMENT_ID],
                }
            }
        )
    )
    object.__setattr__(settings, "student_group", "")
    from lti_gateway.app import create_app

    client = create_app(settings).test_client()
    post_launch(client, platform, resource_claims())
    assert "X-LTI-Group" not in client.get("/auth").headers


def test_identity_is_stable_per_user(client, platform):
    post_launch(client, platform, resource_claims())
    first = client.get("/auth").headers["X-LTI-Email"]
    post_launch(client, platform, resource_claims())
    assert client.get("/auth").headers["X-LTI-Email"] == first


def _client_with_webui_internal_url(settings, platform, url):
    object.__setattr__(settings, "webui_internal_url", url)
    from lti_gateway.app import create_app

    settings.data_dir.joinpath("platforms.json").write_text(
        json.dumps(
            {
                ISS: {
                    "client_id": CLIENT_ID,
                    "auth_login_url": f"{ISS}/auth",
                    "auth_token_url": f"{ISS}/token",
                    "key_set": platform.jwks,
                    "deployment_ids": [DEPLOYMENT_ID],
                }
            }
        )
    )
    app = create_app(settings)
    app.config["TESTING"] = True
    return app.test_client()


def test_relaunch_resumes_previous_chat(settings, platform):
    client = _client_with_webui_internal_url(settings, platform, "http://openwebui.internal")

    with patch("lti_gateway.app.find_resumable_chat", return_value="chat-123") as mocked:
        response = post_launch(client, platform, resource_claims())
    assert response.headers["Location"] == f"{PUBLIC_URL}/c/chat-123"
    mocked.assert_called_once()

    # The chat id is now stored on the resource link: no lookup is needed again.
    with patch("lti_gateway.app.find_resumable_chat") as mocked_again:
        response = post_launch(client, platform, resource_claims())
    assert response.headers["Location"] == f"{PUBLIC_URL}/c/chat-123"
    mocked_again.assert_not_called()


def test_no_chat_to_resume_falls_back_to_new_chat(settings, platform):
    client = _client_with_webui_internal_url(settings, platform, "http://openwebui.internal")

    with patch("lti_gateway.app.find_resumable_chat", return_value=None) as mocked:
        response = post_launch(client, platform, resource_claims())
    assert response.headers["Location"] == f"{PUBLIC_URL}/"
    mocked.assert_called_once()


def test_resume_lookup_skipped_without_webui_internal_url(client, platform):
    with patch("lti_gateway.app.find_resumable_chat") as mocked:
        response = post_launch(client, platform, resource_claims())
    assert response.headers["Location"] == f"{PUBLIC_URL}/"
    mocked.assert_not_called()


def test_auth_rejects_missing_and_forged_sessions(client):
    assert client.get("/auth").status_code == 401
    forged = URLSafeTimedSerializer("wrong").dumps({"email": "a@b", "name": "x"}, salt="sso")
    client.set_cookie("lti_gw", forged, domain="tool.test")
    assert client.get("/auth").status_code == 401


def test_tampered_launch_is_rejected(client, platform):
    response = post_launch(client, platform, resource_claims(), tamper=True)
    assert response.status_code == 400
    assert client.get("/auth").status_code == 401


def test_launch_without_login_state_is_rejected(client, platform):
    token = platform.id_token("nonce", resource_claims())
    response = client.post("/lti/launch", data={"id_token": token, "state": "x"})
    assert response.status_code == 400


def test_login_rejects_foreign_target(client):
    response = client.post(
        "/lti/login",
        data={
            "iss": ISS,
            "login_hint": "h",
            "target_link_uri": "https://evil.test/",
            "client_id": CLIENT_ID,
        },
    )
    assert response.status_code == 400


def test_jwks_and_config(client):
    assert client.get("/lti/jwks").get_json()["keys"][0]["kty"] == "RSA"
    assert client.get("/lti/config").get_json()["tool_url"] == LAUNCH_URL


def deep_link_claims():
    return {
        CLAIM + "message_type": "LtiDeepLinkingRequest",
        "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings": {
            "deep_link_return_url": f"{ISS}/return",
            "accept_types": ["ltiResourceLink"],
            "accept_presentation_document_targets": ["window"],
            "data": "opaque",
        },
    }


def test_deep_linking_round_trip(client, platform):
    import re

    import jwt

    response = post_launch(client, platform, deep_link_claims())
    assert response.status_code == 200
    state = re.search(r'name="state" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    assert "<select name=\"model\">" not in response.get_data(as_text=True)

    result = client.post(
        "/lti/deeplink",
        data={"state": state, "title": "Tutor", "graded": "1", "score_maximum": "10"},
    )
    assert result.status_code == 200
    html = result.get_data(as_text=True)
    assert f"{ISS}/return" in html
    token = re.search(r'name="JWT"\s+value="([^"]+)"', html).group(1)
    claims = jwt.decode(token, options={"verify_signature": False})
    item = claims["https://purl.imsglobal.org/spec/lti-dl/claim/content_items"][0]
    assert item["url"] == LAUNCH_URL and item["title"] == "Tutor"
    assert "custom" not in item
    assert item["lineItem"]["scoreMaximum"] == 10
    assert claims["https://purl.imsglobal.org/spec/lti-dl/claim/data"] == "opaque"


def _client_with_models(settings, platform, models):
    object.__setattr__(settings, "models", models)
    from lti_gateway.app import create_app

    settings.data_dir.joinpath("platforms.json").write_text(
        json.dumps(
            {
                ISS: {
                    "client_id": CLIENT_ID,
                    "auth_login_url": f"{ISS}/auth",
                    "auth_token_url": f"{ISS}/token",
                    "key_set": platform.jwks,
                    "deployment_ids": [DEPLOYMENT_ID],
                }
            }
        )
    )
    app = create_app(settings)
    app.config["TESTING"] = True
    return app.test_client()


def test_deep_link_form_offers_configured_models(settings, platform):
    client = _client_with_models(
        settings, platform, (("cinematica-ej-1", "Cinemática 1"), ("cinematica-ej-2", "Cinemática 2"))
    )
    response = post_launch(client, platform, deep_link_claims())
    html = response.get_data(as_text=True)
    assert '<option value="cinematica-ej-1">Cinemática 1</option>' in html
    assert '<option value="cinematica-ej-2">Cinemática 2</option>' in html


def test_deeplink_stores_chosen_model_as_custom_param_and_launch_preselects_it(settings, platform):
    import re

    import jwt

    client = _client_with_models(settings, platform, (("cinematica-ej-1", "Cinemática 1"),))
    response = post_launch(client, platform, deep_link_claims())
    state = re.search(r'name="state" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    result = client.post(
        "/lti/deeplink",
        data={"state": state, "title": "Tutor", "model": "cinematica-ej-1"},
    )
    assert result.status_code == 200
    token = re.search(r'name="JWT"\s+value="([^"]+)"', result.get_data(as_text=True)).group(1)
    claims = jwt.decode(token, options={"verify_signature": False})
    item = claims["https://purl.imsglobal.org/spec/lti-dl/claim/content_items"][0]
    assert item["custom"] == {"model": "cinematica-ej-1"}

    launch_response = post_launch(
        client, platform, resource_claims(**{CLAIM + "custom": {"model": "cinematica-ej-1"}})
    )
    assert launch_response.status_code == 302
    assert launch_response.headers["Location"] == f"{PUBLIC_URL}/?models=cinematica-ej-1"


def test_deeplink_rejects_unknown_model(settings, platform):
    import re

    client = _client_with_models(settings, platform, (("cinematica-ej-1", "Cinemática 1"),))
    response = post_launch(client, platform, deep_link_claims())
    state = re.search(r'name="state" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    result = client.post(
        "/lti/deeplink",
        data={"state": state, "title": "Tutor", "model": "not-a-real-model"},
    )
    assert result.status_code == 400


def test_deeplink_rejects_bad_state(client):
    assert client.post("/lti/deeplink", data={"state": "bad"}).status_code == 400


def test_scores_requires_token(client):
    assert client.post("/api/scores", json={}).status_code == 401


def test_scores_unknown_launch_is_404(client):
    body = {
        "iss": ISS,
        "client_id": CLIENT_ID,
        "resource_link_id": "nope",
        "sub": "user-42",
        "score_given": 5,
        "score_maximum": 10,
    }
    response = client.post("/api/scores", json=body, headers={"Authorization": "Bearer api-token"})
    assert response.status_code == 404


def test_scores_are_sent_to_platform_with_stored_ags_claim(client, platform):
    post_launch(client, platform, resource_claims(**{CLAIM_AGS: AGS}))
    body = {
        "iss": ISS,
        "client_id": CLIENT_ID,
        "resource_link_id": "link-1",
        "sub": "user-42",
        "score_given": 7,
        "score_maximum": 10,
    }
    with patch(
        "pylti1p3.service_connector.ServiceConnector.make_service_request", return_value={}
    ) as request:
        response = client.post(
            "/api/scores", json=body, headers={"Authorization": "Bearer api-token"}
        )
    assert response.status_code == 204
    args, kwargs = request.call_args
    assert args[1] == f"{ISS}/lineitems/1/scores"
    sent = json.loads(kwargs["data"])
    assert sent["scoreGiven"] == 7 and sent["userId"] == "user-42"


def test_scores_by_chat_id_resolves_lti_identifiers(client, platform, settings):
    from lti_gateway.store import LaunchStore

    post_launch(client, platform, resource_claims(**{CLAIM_AGS: AGS}))
    LaunchStore(settings.data_dir / "gateway.sqlite3").set_chat_id(
        ISS, CLIENT_ID, "link-1", "user-42", "chat-abc"
    )
    body = {"chat_id": "chat-abc", "score_given": 7, "score_maximum": 10}
    with patch(
        "pylti1p3.service_connector.ServiceConnector.make_service_request", return_value={}
    ) as request:
        response = client.post(
            "/api/scores", json=body, headers={"Authorization": "Bearer api-token"}
        )
    assert response.status_code == 204
    sent = json.loads(request.call_args.kwargs["data"])
    assert sent["scoreGiven"] == 7 and sent["userId"] == "user-42"


def test_scores_by_unknown_chat_id_is_404(client):
    body = {"chat_id": "nope", "score_given": 5, "score_maximum": 10}
    response = client.post("/api/scores", json=body, headers={"Authorization": "Bearer api-token"})
    assert response.status_code == 404


def test_jwks_available_without_registered_platforms(settings):
    from lti_gateway.app import create_app

    keys = create_app(settings).test_client().get("/lti/jwks").get_json()["keys"]
    assert keys and keys[0]["kty"] == "RSA" and keys[0]["kid"]
