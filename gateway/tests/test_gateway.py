import json
from unittest.mock import patch

from itsdangerous import URLSafeTimedSerializer

from conftest import CLAIM, CLIENT_ID, ISS, LAUNCH_URL, PUBLIC_URL, post_launch, resource_claims

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


def test_identity_is_stable_per_user(client, platform):
    post_launch(client, platform, resource_claims())
    first = client.get("/auth").headers["X-LTI-Email"]
    post_launch(client, platform, resource_claims())
    assert client.get("/auth").headers["X-LTI-Email"] == first


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
    assert item["lineItem"]["scoreMaximum"] == 10
    assert claims["https://purl.imsglobal.org/spec/lti-dl/claim/data"] == "opaque"


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


def test_jwks_available_without_registered_platforms(settings):
    from lti_gateway.app import create_app

    keys = create_app(settings).test_client().get("/lti/jwks").get_json()["keys"]
    assert keys and keys[0]["kty"] == "RSA" and keys[0]["kid"]
