import asyncio

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, RuntimeErrorCode, UsageSummary
from okcanvas_agent_runtime.core.errors import RuntimeFailure
from okcanvas_agent_runtime.adapters.openai.runtime.gateway import GatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.service import AgentRuntimeService


class SuccessfulGateway:
    async def run(self, *, request, run_id, settings):
        assert request == "inspect supplied text"
        assert run_id.startswith("run_")
        assert settings.model == "test-model"
        return GatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Only supplied text was inspected.",
                findings=[],
                unverified=["Repository state"],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
            ),
            trace_id="trace_test",
            response_id="resp_test",
            sdk_version="0.19.0",
        )


class FailingGateway:
    async def run(self, *, request, run_id, settings):
        raise RuntimeFailure(RuntimeErrorCode.SDK_RUN_FAILED, "SDK failed", retryable=True)


def test_service_success_contract() -> None:
    service = AgentRuntimeService(SuccessfulGateway())
    envelope = asyncio.run(
        service.run(
            request="  inspect supplied text  ",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
            request_id="req_known",
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert envelope.request_id == "req_known"
    assert envelope.live_call is True
    assert envelope.trace_id == "trace_test"
    assert envelope.usage.total_tokens == 20
    assert envelope.result is not None
    assert envelope.error is None
    assert len(envelope.input_sha256) == 64
    assert "secret" not in envelope.model_dump_json()


def test_service_refuses_unconfirmed_live_call_before_gateway() -> None:
    service = AgentRuntimeService(FailingGateway())
    envelope = asyncio.run(
        service.run(
            request="do work",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=False,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.live_call is False
    assert envelope.error is not None
    assert envelope.error.code == RuntimeErrorCode.LIVE_OPT_IN_REQUIRED


def test_service_preserves_canonical_gateway_failure() -> None:
    service = AgentRuntimeService(FailingGateway())
    envelope = asyncio.run(
        service.run(
            request="do work",
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code == RuntimeErrorCode.SDK_RUN_FAILED
    assert envelope.error.retryable is True
    assert envelope.live_call is True
    assert "secret" not in envelope.model_dump_json()
