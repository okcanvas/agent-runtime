from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from okcanvas_agent_runtime.core.paths import PROJECT_ROOT
from okcanvas_agent_runtime.agent.sdk.coding_agent import AGENT_ID, build_agent
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, RuntimeErrorCode, UsageSummary
from okcanvas_agent_runtime.core.errors import RuntimeFailure
from okcanvas_agent_runtime.adapters.openai.runtime.gateway import GatewayRunResult
from okcanvas_agent_runtime.adapters.openai.runtime.sdk_readiness import inspect_sdk
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, build_sdk_trace_run_config_kwargs


def _nested_int(value: Any, attribute: str) -> int:
    nested = getattr(value, attribute, None)
    return int(nested or 0)


def _usage_summary(usage: Any) -> UsageSummary:
    return UsageSummary(
        requests=int(getattr(usage, "requests", 0) or 0),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        cached_input_tokens=_nested_int(
            getattr(usage, "input_tokens_details", None), "cached_tokens"
        ),
        reasoning_tokens=_nested_int(
            getattr(usage, "output_tokens_details", None), "reasoning_tokens"
        ),
    )


class OpenAIAgentsGateway:
    async def run(
        self,
        *,
        request: str,
        run_id: str,
        settings: RuntimeSettings,
    ) -> GatewayRunResult:
        readiness = inspect_sdk(settings)
        if not readiness.ready:
            issue = readiness.issues[0]
            raise RuntimeFailure(issue.code, issue.message)

        assert settings.model is not None
        assert settings.api_key is not None

        try:
            from agents import Agent, RunConfig, Runner, gen_trace_id, set_default_openai_key
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeFailure(
                RuntimeErrorCode.SDK_NOT_INSTALLED,
                f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} is not installed",
                detail_type=type(exc).__name__,
            ) from exc

        trace_id = gen_trace_id()
        set_default_openai_key(settings.api_key)
        agent = build_agent(Agent, model=settings.model)
        trace_export_policy = TraceExportPolicyCatalog(PROJECT_ROOT).resolve()
        trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
        run_config = RunConfig(
            workflow_name=settings.workflow_name,
            trace_id=trace_id,
            group_id=run_id,
            **trace_run_config_settings,
            trace_metadata={
                "run_id": run_id,
                "agent_id": AGENT_ID,
                "trace_export_policy_id": trace_export_policy.policy_id,
                "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                "provider_trace_export_enabled": False,
            },
        )

        try:
            result = await Runner.run(
                agent,
                request,
                max_turns=settings.max_turns,
                run_config=run_config,
            )
        except Exception as exc:
            raise RuntimeFailure(
                RuntimeErrorCode.SDK_RUN_FAILED,
                "OpenAI Agents SDK run failed",
                retryable=True,
                detail_type=type(exc).__name__,
            ) from exc

        try:
            output = result.final_output_as(CodingAgentResult, raise_if_incorrect_type=True)
            if not isinstance(output, CodingAgentResult):
                output = CodingAgentResult.model_validate(output)
        except (TypeError, ValidationError, ValueError) as exc:
            raise RuntimeFailure(
                RuntimeErrorCode.OUTPUT_CONTRACT_INVALID,
                "The Agent output did not match CodingAgentResult",
                detail_type=type(exc).__name__,
            ) from exc

        usage = _usage_summary(result.context_wrapper.usage)
        return GatewayRunResult(
            output=output,
            usage=usage,
            trace_id=trace_id,
            response_id=result.last_response_id,
            sdk_version=importlib.metadata.version("openai-agents"),
        )
