import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..config import parse_models


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
            webui_internal_url=os.environ.get("GATEWAY_WEBUI_INTERNAL_URL", "").rstrip("/"),
        )


def load_consumers(data_dir: Path) -> dict[str, str]:
    """Consumer key -> secret pairs for LTI 1.1 launches.

    Unlike LTI 1.3 there is no dynamic registration: a teacher/admin manually
    configures a legacy "External tool" in Moodle with a consumer key/secret,
    which must also be added here (`consumers.json` in the data dir), e.g.:
    `{"some-consumer-key": "some-secret"}` or `{"key": {"secret": "...", "label": "..."}}`.
    """
    path = data_dir / "consumers.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {
        key: (value["secret"] if isinstance(value, dict) else value)
        for key, value in raw.items()
    }
