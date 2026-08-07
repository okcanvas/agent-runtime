from __future__ import annotations

import hmac

from fastapi import Header

from okcanvas_agent_runtime.application.errors import ControlAPIError


class LocalAdminAuthenticator:
    """Local-admin-only boundary for the first control API slice."""

    def __init__(self, admin_key: str) -> None:
        normalized = admin_key.strip()
        if len(normalized) < 16:
            raise ValueError("Control API admin key must contain at least 16 characters")
        self._admin_key = normalized

    async def require(
        self,
        x_okcanvas_admin_key: str | None = Header(default=None),
    ) -> None:
        if x_okcanvas_admin_key is None or not hmac.compare_digest(
            x_okcanvas_admin_key, self._admin_key
        ):
            raise ControlAPIError(
                status_code=401,
                code="ADMIN_AUTH_REQUIRED",
                message="Valid local administrator credentials are required",
            )


class LocalRunSubmitterAuthenticator:
    """Separate authority boundary for governed local model execution."""

    def __init__(self, submitter_key: str | None, *, admin_key: str) -> None:
        normalized = submitter_key.strip() if submitter_key else None
        if normalized is not None and len(normalized) < 16:
            raise ValueError("Run submitter key must contain at least 16 characters")
        if normalized is not None and hmac.compare_digest(normalized, admin_key.strip()):
            raise ValueError("Run submitter key must be distinct from the admin read key")
        self._submitter_key = normalized

    @property
    def configured(self) -> bool:
        return self._submitter_key is not None

    async def require(
        self,
        x_okcanvas_run_submitter_key: str | None = Header(
            default=None, alias="X-OKCanvas-Run-Submitter-Key"
        ),
    ) -> None:
        if self._submitter_key is None:
            raise ControlAPIError(
                status_code=503,
                code="RUN_SUBMISSION_NOT_CONFIGURED",
                message="Governed Run submission is not configured on this server",
            )
        if x_okcanvas_run_submitter_key is None or not hmac.compare_digest(
            x_okcanvas_run_submitter_key, self._submitter_key
        ):
            raise ControlAPIError(
                status_code=403,
                code="RUN_SUBMITTER_AUTHORITY_REQUIRED",
                message="Valid local Run-submitter authority is required",
            )
