import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(frozen=True)
class AdminSSOSettings:
    public_url: str
    email: str
    internal_url: str

    def __post_init__(self):
        url = urlsplit(self.public_url)
        if (
            url.scheme != "https" or not url.hostname or url.username or url.password
            or url.path or url.query or url.fragment
        ):
            raise ValueError("GATEWAY_ADMIN_PUBLIC_URL must be an HTTPS origin without a path")
        internal = urlsplit(self.internal_url)
        if (
            internal.scheme not in ("http", "https") or not internal.hostname
            or internal.username or internal.password or internal.path
            or internal.query or internal.fragment
        ):
            raise ValueError("GATEWAY_ADMIN_WEBUI_INTERNAL_URL must be an HTTP(S) origin")
        if not self.email.strip() or any(c in self.email for c in ("\r", "\n")):
            raise ValueError("Shared admin email must be set and contain no newlines")


@dataclass(frozen=True)
class Settings:
    secret_key: str
    public_url: str
    data_dir: Path
    api_token: str
    session_ttl: int
    email_domain: str
    student_group: str
    models: tuple[tuple[str, str], ...] = ()
    webui_internal_url: str = ""
    admin_sso: AdminSSOSettings | None = None

    def __post_init__(self):
        if self.admin_sso and (
            urlsplit(self.admin_sso.public_url).hostname == urlsplit(self.public_url).hostname
        ):
            raise ValueError("Admin and student public URLs must use different hostnames")

    @property
    def secure(self) -> bool:
        return self.public_url.startswith("https://")

    @classmethod
    def from_env(cls) -> "Settings":
        def required(name: str) -> str:
            value = os.environ.get(name, "")
            if not value:
                raise RuntimeError(f"{name} must be set")
            return value

        admin_enabled = os.environ.get("GATEWAY_ADMIN_ENABLED", "false").lower()
        if admin_enabled not in ("true", "false"):
            raise ValueError("GATEWAY_ADMIN_ENABLED must be true or false")
        admin_sso = None
        if admin_enabled == "true":
            admin_sso = AdminSSOSettings(
                public_url=required("GATEWAY_ADMIN_PUBLIC_URL").rstrip("/"),
                email=required("GATEWAY_ADMIN_EMAIL").strip(),
                internal_url=required("GATEWAY_ADMIN_WEBUI_INTERNAL_URL").rstrip("/"),
            )

        return cls(
            secret_key=required("GATEWAY_SECRET_KEY"),
            public_url=required("GATEWAY_PUBLIC_URL").rstrip("/"),
            data_dir=Path(os.environ.get("GATEWAY_DATA_DIR", "/data")),
            api_token=os.environ.get("GATEWAY_API_TOKEN", ""),
            session_ttl=int(os.environ.get("GATEWAY_SESSION_TTL", "28800")),
            email_domain=os.environ.get("GATEWAY_USER_EMAIL_DOMAIN", "lti.invalid"),
            student_group=os.environ.get("GATEWAY_STUDENT_GROUP", "estudiantes"),
            models=parse_models(os.environ.get("GATEWAY_MODELS", "")),
            webui_internal_url=os.environ.get("GATEWAY_WEBUI_INTERNAL_URL", "").rstrip("/"),
            admin_sso=admin_sso,
        )


def parse_models(raw: str) -> tuple[tuple[str, str], ...]:
    """`GATEWAY_MODELS` format: comma-separated `id` or `id:Label` entries.

    These are the Open WebUI model IDs teachers may pin an activity to
    (e.g. `cinematica-ej-1:Cinemática - Ejercicio 1`).
    """
    models = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        model_id, _, label = entry.partition(":")
        model_id = model_id.strip()
        if model_id:
            models.append((model_id, label.strip() or model_id))
    return tuple(models)


def load_platforms(data_dir: Path) -> dict:
    """Platform registrations in PyLTI1p3 ToolConfDict format (issuer -> config)."""
    path = data_dir / "platforms.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_or_create_keys(data_dir: Path) -> tuple[str, str]:
    key_dir = data_dir / "keys"
    private_path = key_dir / "private.pem"
    public_path = key_dir / "public.pem"
    if not private_path.exists():
        key_dir.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        private_path.chmod(0o600)
        public_path.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    return private_path.read_text(), public_path.read_text()
