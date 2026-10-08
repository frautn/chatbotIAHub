import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


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

        return cls(
            secret_key=required("GATEWAY_SECRET_KEY"),
            public_url=required("GATEWAY_PUBLIC_URL").rstrip("/"),
            data_dir=Path(os.environ.get("GATEWAY_DATA_DIR", "/data")),
            api_token=os.environ.get("GATEWAY_API_TOKEN", ""),
            session_ttl=int(os.environ.get("GATEWAY_SESSION_TTL", "28800")),
            email_domain=os.environ.get("GATEWAY_USER_EMAIL_DOMAIN", "lti.invalid"),
            student_group=os.environ.get("GATEWAY_STUDENT_GROUP", "estudiantes"),
            models=parse_models(os.environ.get("GATEWAY_MODELS", "")),
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
