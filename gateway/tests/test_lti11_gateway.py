import json
import sys
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qsl, urlparse

import pytest
from oauthlib.oauth1 import SIGNATURE_TYPE_BODY, Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lti_gateway.lti11.app import create_app  # noqa: E402
from lti_gateway.lti11.config import Settings  # noqa: E402

CONSUMER_KEY = "consumer-1"
CONSUMER_SECRET = "s3cr3t"
PUBLIC_URL = "http://tool.test"
LAUNCH_URL = f"{PUBLIC_URL}/lti11/launch"


@pytest.fixture
def settings(tmp_path):
    tmp_path.joinpath("consumers.json").write_text(json.dumps({CONSUMER_KEY: CONSUMER_SECRET}))
    return Settings(
        secret_key="test-secret",
        public_url=PUBLIC_URL,
        data_dir=tmp_path,
        api_token="api-token",
        session_ttl=3600,
        email_domain="lti.invalid",
        student_group="estudiantes",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    app.config["TESTING"] = True
    return app.test_client()


def launch_params(**extra):
    return {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "resource_link_id": "link-1",
        "user_id": "user-42",
        "lis_person_name_full": "Ana Pérez",
        "context_id": "course-1",
        "roles": "Learner",
        **extra,
    }


def sign(params, consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET, url=LAUNCH_URL, **client_kwargs):
    oauth_client = Client(
        client_key=consumer_key,
        client_secret=consumer_secret,
        signature_type=SIGNATURE_TYPE_BODY,
        **client_kwargs,
    )
    _, _, body = oauth_client.sign(
        url, http_method="POST", body=params, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    return dict(parse_qsl(body))


def post_launch(client, params, **sign_kwargs):
    return client.post("/lti11/launch", data=sign(params, **sign_kwargs), base_url=PUBLIC_URL)


def test_resource_launch_sets_sso_and_auth_returns_trusted_headers(client):
    response = post_launch(client, launch_params())
    assert response.status_code == 302
    assert response.headers["Location"] == f"{PUBLIC_URL}/"

    auth = client.get("/auth", base_url=PUBLIC_URL)
    assert auth.status_code == 204
    assert auth.headers["X-LTI-Email"].startswith("lti11-")
    assert auth.headers["X-LTI-Email"].endswith("@lti.invalid")
    assert auth.headers["X-LTI-Name"] == "Ana Perez"
    assert auth.headers["X-LTI-Group"] == "estudiantes"


def test_identity_is_stable_per_user(client):
    post_launch(client, launch_params())
    first = client.get("/auth", base_url=PUBLIC_URL).headers["X-LTI-Email"]
    post_launch(client, launch_params())
    assert client.get("/auth", base_url=PUBLIC_URL).headers["X-LTI-Email"] == first


def test_tampered_signature_is_rejected(client):
    signed = sign(launch_params())
    signed["oauth_signature"] = signed["oauth_signature"][:-4] + "AAAA"
    response = client.post("/lti11/launch", data=signed, base_url=PUBLIC_URL)
    assert response.status_code == 401
    assert client.get("/auth").status_code == 401


def test_unknown_consumer_key_is_rejected(client):
    response = post_launch(client, launch_params(), consumer_key="not-registered")
    assert response.status_code == 401


def test_wrong_secret_is_rejected(client):
    response = post_launch(client, launch_params(), consumer_secret="wrong-secret")
    assert response.status_code == 401


def test_replayed_nonce_is_rejected(client):
    signed = sign(launch_params(), nonce="fixed-nonce", timestamp=str(int(time.time())))
    first = client.post("/lti11/launch", data=signed, base_url=PUBLIC_URL)
    assert first.status_code == 302
    second = client.post("/lti11/launch", data=signed, base_url=PUBLIC_URL)
    assert second.status_code == 401


def test_custom_model_is_preselected(client):
    response = post_launch(client, launch_params(custom_model="cinematica-1"))
    assert urlparse(response.headers["Location"]).query == "models=cinematica-1"


def test_unknown_model_is_ignored_when_allowlisted(settings):
    object.__setattr__(settings, "models", (("cinematica-1", "Cinemática 1"),))
    app = create_app(settings)
    app.config["TESTING"] = True
    client = app.test_client()
    response = post_launch(client, launch_params(custom_model="not-allowed"))
    assert response.headers["Location"] == f"{PUBLIC_URL}/"


def _client_with_webui_internal_url(settings, url):
    object.__setattr__(settings, "webui_internal_url", url)
    app = create_app(settings)
    app.config["TESTING"] = True
    return app.test_client()


def test_relaunch_resumes_previous_chat(settings):
    client = _client_with_webui_internal_url(settings, "http://openwebui.internal")
    with patch("lti_gateway.lti11.app.find_resumable_chat", return_value="chat-123") as mocked:
        response = post_launch(client, launch_params())
    assert response.headers["Location"] == f"{PUBLIC_URL}/c/chat-123"
    mocked.assert_called_once()

    with patch("lti_gateway.lti11.app.find_resumable_chat") as mocked_again:
        response = post_launch(client, launch_params())
    assert response.headers["Location"] == f"{PUBLIC_URL}/c/chat-123"
    mocked_again.assert_not_called()


def test_auth_rejects_missing_and_forged_sessions(client):
    from itsdangerous import URLSafeTimedSerializer

    assert client.get("/auth").status_code == 401
    forged = URLSafeTimedSerializer("wrong").dumps({"email": "a@b", "name": "x"}, salt="sso")
    client.set_cookie("lti11_gw", forged, domain="tool.test")
    assert client.get("/auth").status_code == 401


def test_scores_endpoint_submits_outcome(client):
    post_launch(
        client,
        launch_params(
            lis_result_sourcedid="sourced-1", lis_outcome_service_url="https://moodle.test/outcomes"
        ),
    )
    success_response = (
        "<imsx_POXEnvelopeResponse><imsx_POXHeader><imsx_POXResponseHeaderInfo>"
        "<imsx_statusInfo><imsx_codeMajor>success</imsx_codeMajor></imsx_statusInfo>"
        "</imsx_POXResponseHeaderInfo></imsx_POXHeader></imsx_POXEnvelopeResponse>"
    )
    with patch("lti_gateway.lti11.outcomes.requests.post") as mocked_post:
        mocked_post.return_value.text = success_response
        mocked_post.return_value.raise_for_status = lambda: None
        response = client.post(
            "/api/scores",
            headers={"Authorization": "Bearer api-token"},
            json={
                "consumer_key": CONSUMER_KEY,
                "resource_link_id": "link-1",
                "user_id": "user-42",
                "score_given": 8,
                "score_maximum": 10,
            },
        )
    assert response.status_code == 204
    sent_body = mocked_post.call_args.kwargs["data"]
    assert "<textString>0.8000</textString>" in sent_body


def test_scores_endpoint_requires_token(client):
    response = client.post(
        "/api/scores",
        json={
            "consumer_key": CONSUMER_KEY,
            "resource_link_id": "link-1",
            "user_id": "user-42",
            "score_given": 8,
            "score_maximum": 10,
        },
    )
    assert response.status_code == 401


def test_scores_endpoint_404s_without_a_launch(client):
    response = client.post(
        "/api/scores",
        headers={"Authorization": "Bearer api-token"},
        json={
            "consumer_key": CONSUMER_KEY,
            "resource_link_id": "unknown-link",
            "user_id": "user-42",
            "score_given": 8,
            "score_maximum": 10,
        },
    )
    assert response.status_code == 404
