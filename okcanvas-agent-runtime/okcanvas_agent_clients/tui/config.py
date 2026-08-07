from __future__ import annotations

import hmac
import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse


class TUIClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_loopback_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL must use http or https",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL must not contain credentials, query, or fragment",
        )
    if parsed.path not in {"", "/"}:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL must not contain a path",
        )
    hostname = parsed.hostname
    if not hostname:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL must include a host",
        )
    loopback = hostname.casefold() == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise TUIClientError(
            "TUI_REMOTE_URL_FORBIDDEN",
            "TUI credentials may only be sent to a loopback Control API",
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL contains an invalid port",
        ) from exc
    if port is None:
        raise TUIClientError(
            "TUI_BASE_URL_INVALID",
            "TUI Control API URL must include an explicit port",
        )
    return normalized


@dataclass(frozen=True)
class TUIClientConfig:
    base_url: str
    admin_key: str
    submitter_key: str
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        base_url = validate_loopback_base_url(self.base_url)
        admin_key = self.admin_key.strip()
        submitter_key = self.submitter_key.strip()
        if len(admin_key) < 16:
            raise TUIClientError(
                "TUI_ADMIN_AUTH_NOT_CONFIGURED",
                "A local administrator key of at least 16 characters is required",
            )
        if len(submitter_key) < 16:
            raise TUIClientError(
                "TUI_RUN_SUBMITTER_AUTH_NOT_CONFIGURED",
                "A local Run-submitter key of at least 16 characters is required",
            )
        if hmac.compare_digest(admin_key, submitter_key):
            raise TUIClientError(
                "TUI_AUTHORITY_NOT_SEPARATED",
                "Administrator and Run-submitter keys must be distinct",
            )
        if self.timeout_seconds <= 0 or self.timeout_seconds > 600:
            raise TUIClientError(
                "TUI_TIMEOUT_INVALID",
                "TUI timeout must be greater than zero and at most 600 seconds",
            )
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "admin_key", admin_key)
        object.__setattr__(self, "submitter_key", submitter_key)

    @classmethod
    def from_env(cls, *, base_url_override: str | None = None) -> "TUIClientConfig":
        host = os.getenv("OKCANVAS_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        port = os.getenv("OKCANVAS_API_PORT", "8765").strip() or "8765"
        host_for_url = f"[{host}]" if ":" in host else host
        base_url = (
            base_url_override
            or os.getenv("OKCANVAS_CONTROL_BASE_URL")
            or f"http://{host_for_url}:{port}"
        )
        return cls(
            base_url=base_url,
            admin_key=os.getenv("OKCANVAS_CONTROL_ADMIN_KEY", ""),
            submitter_key=os.getenv("OKCANVAS_RUN_SUBMITTER_KEY", ""),
        )
