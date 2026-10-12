from urllib.parse import urlencode

from oauthlib.oauth1 import Client, RequestValidator, SignatureOnlyEndpoint

CONTENT_TYPE_FORM = "application/x-www-form-urlencoded"


class _LaunchValidator(RequestValidator):
    """Verifies OAuth 1.0a HMAC-SHA1 signed LTI 1.1 launches.

    No token flow is involved (LTI 1.1 signs requests with the consumer
    secret only); actual security comes from the signature check plus
    nonce+timestamp replay protection backed by the launch store.
    """

    enforce_ssl = False

    def __init__(self, secrets: dict[str, str], store):
        super().__init__()
        self._secrets = secrets
        self._store = store

    def check_client_key(self, client_key):
        # Consumer keys are admin-assigned, arbitrary strings (e.g. Moodle
        # allows any characters); the real check is validate_client_key below.
        return bool(client_key)

    def check_nonce(self, nonce):
        return bool(nonce)

    def validate_client_key(self, client_key, request):
        return client_key in self._secrets

    def get_client_secret(self, client_key, request):
        # A clearly-invalid placeholder for unknown keys, so timing stays
        # near-constant whether or not the key is registered (see oauthlib's
        # SignatureOnlyEndpoint.validate_request).
        return self._secrets.get(client_key, "unknown-consumer-key")

    def validate_timestamp_and_nonce(
        self, client_key, timestamp, nonce, request, request_token=None, access_token=None
    ):
        return self._store.check_and_record_nonce(client_key, nonce, timestamp)

    @property
    def dummy_client(self):
        return "unknown-consumer-key"


def verify_launch(url: str, params, secrets: dict[str, str], store) -> bool:
    """Validates an LTI 1.1 Basic Launch Request's OAuth 1.0a signature.

    `params` is the full set of POSTed form fields (including oauth_* ones),
    as an iterable of (key, value) pairs.
    """
    body = urlencode(list(params))
    endpoint = SignatureOnlyEndpoint(_LaunchValidator(secrets, store))
    valid, _ = endpoint.validate_request(
        url, http_method="POST", body=body, headers={"Content-Type": CONTENT_TYPE_FORM}
    )
    return valid


def sign_outcome_request(url: str, consumer_key: str, consumer_secret: str, body: str, content_type: str):
    """Signs a Basic Outcomes POX request with OAuth1 + oauth_body_hash.

    Returns (uri, headers, body) ready to send, mirroring oauthlib.oauth1.Client.sign.
    """
    client = Client(client_key=consumer_key, client_secret=consumer_secret)
    return client.sign(url, http_method="POST", body=body, headers={"Content-Type": content_type})
