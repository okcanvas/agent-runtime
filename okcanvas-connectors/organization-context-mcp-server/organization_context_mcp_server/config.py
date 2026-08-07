from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    connector_bearer: str
    organization_context_base_url: str
    organization_context_api_bearer: str
    http_timeout_seconds: float = 5.0
    max_retry_attempts: int = 0

    @classmethod
    def from_env(cls) -> "Settings":
        connector_bearer = os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_CONNECTOR_BEARER", "").strip()
        base_url = os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_BASE_URL", "").strip().rstrip("/")
        api_bearer = os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_API_BEARER", "").strip()
        if not connector_bearer:
            raise RuntimeError("OKCANVAS_ORGANIZATION_CONTEXT_CONNECTOR_BEARER is required")
        if not base_url:
            raise RuntimeError("OKCANVAS_ORGANIZATION_CONTEXT_BASE_URL is required")
        if not api_bearer:
            raise RuntimeError("OKCANVAS_ORGANIZATION_CONTEXT_API_BEARER is required")
        timeout = float(os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_HTTP_TIMEOUT_SECONDS", "5"))
        retries = int(os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_MAX_RETRY_ATTEMPTS", "0"))
        if timeout <= 0:
            raise RuntimeError("Organization Context HTTP timeout must be positive")
        if retries < 0 or retries > 2:
            raise RuntimeError("Organization Context retry attempts must be between 0 and 2")
        return cls(
            connector_bearer=connector_bearer,
            organization_context_base_url=base_url,
            organization_context_api_bearer=api_bearer,
            http_timeout_seconds=timeout,
            max_retry_attempts=retries,
        )
