from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from okcanvas_agent_clients.tui.config import TUIClientConfig, TUIClientError
from okcanvas_agent_clients.tui.sse import parse_sse_json


class LocalTUIControlClient:
    """Loopback-only client over the existing governed Control API."""

    def __init__(
        self,
        config: TUIClientConfig,
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
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    def __enter__(self) -> "LocalTUIControlClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/healthz", authority="none")

    def list_agents(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/v1/agent-definitions", authority="admin")
        items = payload.get("definitions")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise TUIClientError(
                "TUI_RESPONSE_INVALID",
                "Control API returned an invalid Agent definition list",
            )
        return list(items)

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/agent-definitions/{agent_id}",
            authority="admin",
        )

    def list_evaluation_cases(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/v1/evaluation-cases", authority="admin")
        items = payload.get("cases")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise TUIClientError(
                "TUI_RESPONSE_INVALID",
                "Control API returned an invalid Evaluation case list",
            )
        return list(items)

    def preflight(
        self,
        *,
        agent_definition_id: str,
        request: str,
        idempotency_key: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "agent_definition_id": agent_definition_id,
            "input": request,
            "idempotency_key": idempotency_key,
        }
        if model:
            body["model"] = model
        return self._request(
            "POST",
            "/v1/run-submissions/preflight",
            authority="submitter",
            json=body,
        )

    def confirm(self, *, submission_id: str, confirmation: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/run-submissions/{submission_id}/confirm",
            authority="submitter",
            json={"confirmation": confirmation},
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/runs/{run_id}", authority="admin")

    def list_invocations(self, run_id: str) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/v1/runs/{run_id}/invocations",
            authority="admin",
        )
        items = payload.get("invocations")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise TUIClientError(
                "TUI_RESPONSE_INVALID",
                "Control API returned an invalid Invocation list",
            )
        return list(items)

    def get_artifact(self, run_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/runs/{run_id}/artifact",
            authority="admin",
        )

    def evaluate_run(self, *, run_id: str, case_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/runs/{run_id}/evaluations",
            authority="admin",
            json={"case_id": case_id},
        )

    def stream_events(self, *, run_id: str, cursor: int = 0) -> Iterator[dict[str, Any]]:
        headers = self._headers("admin")
        headers.update(
            {
                "Accept": "text/event-stream",
                "Last-Event-ID": str(max(cursor, 0)),
            }
        )
        try:
            with self._client.stream(
                "GET",
                f"/v1/runs/{run_id}/events/stream",
                params={"cursor": max(cursor, 0)},
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    self._raise_api_error(response)
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    raise TUIClientError(
                        "TUI_SSE_RESPONSE_INVALID",
                        "Control API persisted event endpoint did not return text/event-stream",
                    )
                yield from parse_sse_json(response.iter_lines())
        except TUIClientError:
            raise
        except httpx.HTTPError as exc:
            raise TUIClientError(
                "TUI_CONNECTION_FAILED",
                "Unable to reach the local Control API persisted event stream",
            ) from exc

    def _headers(self, authority: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        if authority in {"admin", "submitter"}:
            headers["X-OKCanvas-Admin-Key"] = self._config.admin_key
        if authority == "submitter":
            headers["X-OKCanvas-Run-Submitter-Key"] = self._config.submitter_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        authority: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                json=json,
                headers=self._headers(authority),
            )
        except httpx.HTTPError as exc:
            raise TUIClientError(
                "TUI_CONNECTION_FAILED",
                "Unable to reach the local Control API",
            ) from exc
        if response.status_code >= 400:
            self._raise_api_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise TUIClientError(
                "TUI_RESPONSE_INVALID",
                "Control API returned non-JSON data",
            ) from exc
        if not isinstance(payload, dict):
            raise TUIClientError(
                "TUI_RESPONSE_INVALID",
                "Control API returned an invalid JSON object",
            )
        return payload

    @staticmethod
    def _raise_api_error(response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        code = str(payload.get("code") or "TUI_CONTROL_API_ERROR")
        message = str(payload.get("message") or "Control API request failed")
        raise TUIClientError(code, message, status_code=response.status_code)
