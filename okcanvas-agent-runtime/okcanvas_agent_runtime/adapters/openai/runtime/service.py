from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import RunEnvelope, RuntimeErrorCode, RuntimeErrorPayload, UsageSummary
from okcanvas_agent_runtime.core.errors import RuntimeFailure
from okcanvas_agent_runtime.adapters.openai.runtime.gateway import AgentGateway

MAX_REQUEST_CHARS = 100_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _input_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AgentRuntimeService:
    def __init__(self, gateway: AgentGateway):
        self._gateway = gateway

    async def run(
        self,
        *,
        request: str,
        settings: RuntimeSettings,
        live_opt_in: bool,
        request_id: str | None = None,
    ) -> RunEnvelope:
        run_id = _identifier("run")
        effective_request_id = request_id or _identifier("req")
        started_at = _utc_now()
        started_ns = time.monotonic_ns()
        normalized = request.strip()

        def failed(failure: RuntimeFailure, *, live_call: bool = False) -> RunEnvelope:
            completed_at = _utc_now()
            return RunEnvelope(
                run_id=run_id,
                request_id=effective_request_id,
                state="FAILED",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                model=settings.model,
                sdk_version=None,
                trace_id=None,
                response_id=None,
                input_sha256=_input_sha256(normalized),
                live_call=live_call,
                usage=UsageSummary(),
                error=RuntimeErrorPayload(
                    code=failure.code,
                    message=failure.public_message,
                    retryable=failure.retryable,
                    detail_type=failure.detail_type,
                ),
            )

        if not normalized:
            return failed(
                RuntimeFailure(RuntimeErrorCode.INVALID_REQUEST, "Request must not be blank")
            )
        if len(normalized) > MAX_REQUEST_CHARS:
            return failed(
                RuntimeFailure(
                    RuntimeErrorCode.INVALID_REQUEST,
                    f"Request exceeds the {MAX_REQUEST_CHARS} character limit",
                )
            )
        if not live_opt_in:
            return failed(
                RuntimeFailure(
                    RuntimeErrorCode.LIVE_OPT_IN_REQUIRED,
                    "Live model execution requires the explicit confirmation flag",
                )
            )

        try:
            gateway_result = await self._gateway.run(
                request=normalized,
                run_id=run_id,
                settings=settings,
            )
        except RuntimeFailure as failure:
            model_call_attempted = failure.code in {
                RuntimeErrorCode.SDK_RUN_FAILED,
                RuntimeErrorCode.OUTPUT_CONTRACT_INVALID,
            }
            return failed(failure, live_call=model_call_attempted)
        except Exception as exc:
            return failed(
                RuntimeFailure(
                    RuntimeErrorCode.INTERNAL_ERROR,
                    "Unexpected runtime failure",
                    detail_type=type(exc).__name__,
                ),
                live_call=True,
            )

        completed_at = _utc_now()
        return RunEnvelope(
            run_id=run_id,
            request_id=effective_request_id,
            state="SUCCEEDED",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
            model=settings.model,
            sdk_version=gateway_result.sdk_version,
            trace_id=gateway_result.trace_id,
            response_id=gateway_result.response_id,
            input_sha256=_input_sha256(normalized),
            live_call=True,
            result=gateway_result.output,
            usage=gateway_result.usage,
        )
