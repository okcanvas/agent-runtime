from __future__ import annotations

import hmac
import ipaddress
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from okcanvas_agent_protocols.approval import decision_confirmation_challenge


class ApprovalOperatorError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code



def _validate_loopback_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL must use http or https",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL must not contain credentials, query, or fragment",
        )
    if parsed.path not in {"", "/"}:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL must not contain a path",
        )
    hostname = parsed.hostname
    if not hostname:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL must include a host",
        )
    loopback = hostname.casefold() == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_REMOTE_URL_FORBIDDEN",
            "Approval credentials may only be sent to a loopback Control API",
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL contains an invalid port",
        ) from exc
    if port is None:
        raise ApprovalOperatorError(
            "APPROVAL_OPERATOR_BASE_URL_INVALID",
            "Approval operator base URL must include an explicit port",
        )
    return normalized


@dataclass(frozen=True)
class ApprovalOperatorConfig:
    base_url: str
    admin_key: str
    submitter_key: str | None = None
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        base_url = _validate_loopback_base_url(self.base_url)
        admin_key = self.admin_key.strip()
        submitter_key = self.submitter_key.strip() if self.submitter_key else None
        if len(admin_key) < 16:
            raise ApprovalOperatorError(
                "ADMIN_AUTH_NOT_CONFIGURED",
                "A local administrator key of at least 16 characters is required",
            )
        if submitter_key is not None and len(submitter_key) < 16:
            raise ApprovalOperatorError(
                "RUN_SUBMITTER_AUTH_NOT_CONFIGURED",
                "A local Run-submitter key of at least 16 characters is required",
            )
        if submitter_key is not None and hmac.compare_digest(admin_key, submitter_key):
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_AUTHORITY_NOT_SEPARATED",
                "Administrator and Run-submitter keys must be distinct",
            )
        if self.timeout_seconds <= 0 or self.timeout_seconds > 600:
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_TIMEOUT_INVALID",
                "Approval operator timeout must be greater than zero and at most 600 seconds",
            )
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "admin_key", admin_key)
        object.__setattr__(self, "submitter_key", submitter_key)

    @classmethod
    def from_env(
        cls,
        *,
        base_url_override: str | None = None,
        require_submitter: bool = False,
    ) -> "ApprovalOperatorConfig":
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
        admin_key = os.getenv("OKCANVAS_CONTROL_ADMIN_KEY", "").strip()
        submitter_key = os.getenv("OKCANVAS_RUN_SUBMITTER_KEY", "").strip() or None
        if len(admin_key) < 16:
            raise ApprovalOperatorError(
                "ADMIN_AUTH_NOT_CONFIGURED",
                "A local administrator key of at least 16 characters is required",
            )
        if require_submitter and (submitter_key is None or len(submitter_key) < 16):
            raise ApprovalOperatorError(
                "RUN_SUBMITTER_AUTH_NOT_CONFIGURED",
                "A distinct local Run-submitter key of at least 16 characters is required",
            )
        if submitter_key is not None and hmac.compare_digest(admin_key, submitter_key):
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_AUTHORITY_NOT_SEPARATED",
                "Administrator and Run-submitter keys must be distinct",
            )
        return cls(
            base_url=_validate_loopback_base_url(base_url),
            admin_key=admin_key,
            submitter_key=submitter_key,
        )


class LocalApprovalOperatorClient:
    """Minimal loopback-only operator client for one-at-a-time approval decisions."""

    def __init__(
        self,
        config: ApprovalOperatorConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LocalApprovalOperatorClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_approvals(
        self,
        *,
        state: str | None = "PENDING",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 200 or offset < 0:
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_ARGUMENT_INVALID",
                "limit must be 1..200 and offset must be non-negative",
            )
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if state:
            params["state"] = state.upper()
        payload = self._request(
            "GET",
            "/v1/tool-approvals",
            params=params,
            submitter=False,
        )
        approvals = payload.get("approvals")
        if not isinstance(approvals, list):
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_RESPONSE_INVALID",
                "Control API returned an invalid approval list",
            )
        enriched: list[dict[str, Any]] = []
        for item in approvals:
            if not isinstance(item, dict):
                continue
            safe = dict(item)
            if safe.get("state") == "PENDING":
                approval_id = str(safe.get("approval_id") or "")
                run_id = str(safe.get("run_id") or "")
                safe["approve_confirmation"] = decision_confirmation_challenge(
                    approval_id=approval_id,
                    run_id=run_id,
                    decision="APPROVE",
                )
                safe["reject_confirmation"] = decision_confirmation_challenge(
                    approval_id=approval_id,
                    run_id=run_id,
                    decision="REJECT",
                )
            enriched.append(safe)
        return {
            "schema_version": "okcanvas-local-approval-operator-list-v1",
            "total": int(payload.get("total") or 0),
            "limit": int(payload.get("limit") or limit),
            "offset": int(payload.get("offset") or offset),
            "approvals": enriched,
        }

    def decide(
        self,
        *,
        approval_id: str,
        decision: str,
        confirmation: str,
    ) -> dict[str, Any]:
        normalized = decision.strip().upper()
        approval = self._request(
            "GET",
            f"/v1/tool-approvals/{approval_id}/inbox",
            submitter=False,
        )
        expected = decision_confirmation_challenge(
            approval_id=str(approval.get("approval_id") or ""),
            run_id=str(approval.get("run_id") or ""),
            decision=normalized,
        )
        if not hmac.compare_digest(confirmation, expected):
            raise ApprovalOperatorError(
                "TOOL_APPROVAL_CONFIRMATION_MISMATCH",
                "The exact approval decision confirmation is required",
            )
        return self._request(
            "POST",
            f"/v1/tool-approvals/{approval_id}/decision",
            json={"decision": normalized, "confirmation": confirmation},
            submitter=True,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        submitter: bool,
    ) -> dict[str, Any]:
        headers = {"X-OKCanvas-Admin-Key": self._config.admin_key}
        if submitter:
            if not self._config.submitter_key:
                raise ApprovalOperatorError(
                    "RUN_SUBMITTER_AUTH_NOT_CONFIGURED",
                    "Run-submitter authority is required for an approval decision",
                )
            headers["X-OKCanvas-Run-Submitter-Key"] = self._config.submitter_key
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_CONNECTION_FAILED",
                "Unable to reach the local Control API",
            ) from exc
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            code = str(error.get("code") or "APPROVAL_OPERATOR_API_ERROR")
            message = str(error.get("message") or "Control API request failed")
            raise ApprovalOperatorError(code, message, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_RESPONSE_INVALID",
                "Control API returned non-JSON data",
            ) from exc
        if not isinstance(payload, dict):
            raise ApprovalOperatorError(
                "APPROVAL_OPERATOR_RESPONSE_INVALID",
                "Control API returned an invalid JSON object",
            )
        return payload
