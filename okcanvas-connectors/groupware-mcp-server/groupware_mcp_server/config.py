from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


class ConfigurationError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable is not configured: {name}")
    if "\r" in value or "\n" in value:
        raise ConfigurationError(f"Environment variable contains an invalid newline: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    connector_bearer: str
    groupware_base_url: str
    groupware_api_bearer: str
    http_timeout_seconds: float = 10.0
    max_retry_attempts: int = 0
    notices_path: str = "/api/v1/notices/search"
    mail_path: str = "/api/v1/mail/search"
    calendar_path: str = "/api/v1/calendar/events/list"

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = _required_env("GROUPWARE_BASE_URL").rstrip("/")
        parsed = urlsplit(base_url)
        allow_http = os.environ.get("GROUPWARE_ALLOW_INSECURE_HTTP", "").strip() == "1"
        if parsed.scheme not in ({"http", "https"} if allow_http else {"https"}):
            raise ConfigurationError("GROUPWARE_BASE_URL must use HTTPS outside explicit local development")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigurationError("GROUPWARE_BASE_URL is unsafe")
        try:
            timeout = float(os.environ.get("GROUPWARE_HTTP_TIMEOUT_SECONDS", "10"))
            retries = int(os.environ.get("GROUPWARE_HTTP_MAX_RETRIES", "0"))
        except ValueError as exc:
            raise ConfigurationError("HTTP timeout or retry configuration is invalid") from exc
        if not 0.1 <= timeout <= 120:
            raise ConfigurationError("GROUPWARE_HTTP_TIMEOUT_SECONDS is out of range")
        if not 0 <= retries <= 2:
            raise ConfigurationError("GROUPWARE_HTTP_MAX_RETRIES is out of range")
        return cls(
            connector_bearer=_required_env("OKCANVAS_CONNECTOR_MCP_BEARER"),
            groupware_base_url=base_url,
            groupware_api_bearer=_required_env("GROUPWARE_API_BEARER"),
            http_timeout_seconds=timeout,
            max_retry_attempts=retries,
            notices_path=os.environ.get("GROUPWARE_NOTICES_SEARCH_PATH", "/api/v1/notices/search"),
            mail_path=os.environ.get("GROUPWARE_MAIL_SEARCH_PATH", "/api/v1/mail/search"),
            calendar_path=os.environ.get("GROUPWARE_CALENDAR_LIST_PATH", "/api/v1/calendar/events/list"),
        )
