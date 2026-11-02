import json
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lti_gateway.app import create_app  # noqa: E402
from lti_gateway.config import Settings  # noqa: E402

ISS = "https://moodle.test"
CLIENT_ID = "client-1"
DEPLOYMENT_ID = "1"
PUBLIC_URL = "http://tool.test"
LAUNCH_URL = f"{PUBLIC_URL}/lti/launch"
CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"


class FakePlatform:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid="platform-key", alg="RS256", use="sig")
        self.jwks = {"keys": [jwk]}

    def id_token(self, nonce: str, extra: dict) -> str:
        claims = {
            "iss": ISS,
            "aud": CLIENT_ID,
            "sub": "user-42",
            "name": "Ana Pérez",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "nonce": nonce,
            CLAIM + "deployment_id": DEPLOYMENT_ID,
            CLAIM + "version": "1.3.0",
            CLAIM + "target_link_uri": LAUNCH_URL,
            CLAIM + "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"],
            **extra,
        }
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "platform-key"})


@pytest.fixture
def platform():
    return FakePlatform()


@pytest.fixture
def settings(tmp_path):
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
def client(settings, platform):
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


def do_login(client):
    response = client.post(
        "/lti/login",
        data={
            "iss": ISS,
            "login_hint": "hint",
            "target_link_uri": LAUNCH_URL,
            "client_id": CLIENT_ID,
            "lti_message_hint": "m",
        },
    )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["Location"]).query)
    return query["state"][0], query["nonce"][0]


def post_launch(client, platform, extra, tamper=False):
    state, nonce = do_login(client)
    token = platform.id_token(nonce, extra)
    if tamper:
        token = token[:-4] + "AAAA"
    return client.post("/lti/launch", data={"id_token": token, "state": state})


def resource_claims(**extra):
    return {
        CLAIM + "message_type": "LtiResourceLinkRequest",
        CLAIM + "resource_link": {"id": "link-1"},
        CLAIM + "context": {"id": "course-1"},
        **extra,
    }
