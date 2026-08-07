from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from okcanvas_agent_runtime.core.paths import PROJECT_ROOT
from okcanvas_agent_runtime.core.config import CodexWriteSettings, EXPECTED_OPENAI_AGENTS_VERSION
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness, inspect_codex_readiness
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, build_sdk_trace_run_config_kwargs


ApprovalExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ApprovalGatewayPrepareResult:
    state_json: dict[str, Any]
    tool_name: str
    call_id: str
    arguments: str
    trace_id: str | None
    response_id: str | None
    agent_usage: UsageSummary


@dataclass(frozen=True)
class ApprovalGatewayResumeResult:
    final_output: Any
    remaining_interruptions: int
    trace_id: str | None
    response_id: str | None
    agent_usage: UsageSummary


def _usage_summary(usage: Any) -> UsageSummary:
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return UsageSummary(
        requests=int(getattr(usage, "requests", 0) or 0),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        cached_input_tokens=int(getattr(input_details, "cached_tokens", 0) or 0),
        reasoning_tokens=int(getattr(output_details, "reasoning_tokens", 0) or 0),
    )


class OpenAICodexApprovalGateway:
    def readiness(self, settings: CodexWriteSettings) -> CodexReadiness:
        return inspect_codex_readiness(settings.as_readonly_settings())

    @staticmethod
    def _load_sdk() -> tuple[Any, ...]:
        from agents import Agent, ModelSettings, RunConfig, Runner, RunState, RunContextWrapper
        from agents.decorators import tool
        from agents import gen_trace_id, set_default_openai_key

        version = importlib.metadata.version("openai-agents")
        if version != EXPECTED_OPENAI_AGENTS_VERSION:
            raise RuntimeError(
                f"openai-agents version {version} does not match {EXPECTED_OPENAI_AGENTS_VERSION}"
            )
        return (
            Agent,
            ModelSettings,
            RunConfig,
            Runner,
            RunState,
            RunContextWrapper,
            tool,
            gen_trace_id,
            set_default_openai_key,
            version,
        )

    @staticmethod
    def _build_agent(
        *,
        Agent: Any,
        ModelSettings: Any,
        RunContextWrapper: Any,
        tool_decorator: Any,
        model: str,
        executor: ApprovalExecutor,
    ) -> Any:
        async def raw_tool(ctx: Any, execution_id: str) -> dict[str, Any]:
            context = dict(ctx.context)
            if execution_id != context.get("execution_id"):
                raise RuntimeError("Execution identifier mismatch")
            return await executor(context)

        raw_tool.__name__ = "codex_workspace_write"
        raw_tool.__doc__ = "Execute the pre-authorized Codex write plan exactly once."
        raw_tool.__annotations__ = {
            "ctx": RunContextWrapper[dict[str, Any]],
            "execution_id": str,
            "return": dict[str, Any],
        }
        approval_tool = tool_decorator(
            name_override="codex_workspace_write",
            description_override="Execute the pre-authorized disposable workspace write plan.",
            needs_approval=True,
            failure_error_function=None,
        )(raw_tool)
        return Agent(
            name="OKCanvas Codex Write Approval Agent",
            instructions=(
                "Call codex_workspace_write exactly once using the execution_id in the user "
                "message. Do not alter it and do not call any other tool. If the call is rejected, "
                "acknowledge the rejection and do not request the tool again."
            ),
            model=model,
            tools=[approval_tool],
            handoffs=[],
            model_settings=ModelSettings(tool_choice="required", max_tokens=120),
            tool_use_behavior="stop_on_first_tool",
        )

    @staticmethod
    def _run_config(RunConfig: Any, *, workflow_name: str, trace_id: str) -> Any:
        trace_export_policy = TraceExportPolicyCatalog(PROJECT_ROOT).resolve()
        trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
        return RunConfig(
            workflow_name=workflow_name,
            trace_id=trace_id,
            group_id=trace_id,
            **trace_run_config_settings,
            trace_metadata={
                "trace_export_policy_id": trace_export_policy.policy_id,
                "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                "provider_trace_export_enabled": False,
            },
        )

    async def prepare(
        self,
        *,
        settings: CodexWriteSettings,
        context: dict[str, Any],
        executor: ApprovalExecutor,
    ) -> ApprovalGatewayPrepareResult:
        (
            Agent,
            ModelSettings,
            RunConfig,
            Runner,
            _RunState,
            RunContextWrapper,
            tool_decorator,
            gen_trace_id,
            set_default_openai_key,
            _version,
        ) = self._load_sdk()
        assert settings.api_key and settings.agent_model
        set_default_openai_key(settings.api_key)
        agent = self._build_agent(
            Agent=Agent,
            ModelSettings=ModelSettings,
            RunContextWrapper=RunContextWrapper,
            tool_decorator=tool_decorator,
            model=settings.agent_model,
            executor=executor,
        )
        trace_id = gen_trace_id()
        result = await Runner.run(
            agent,
            f'Invoke codex_workspace_write with execution_id="{context["execution_id"]}".',
            context=context,
            max_turns=1,
            run_config=self._run_config(
                RunConfig,
                workflow_name="OKCanvas Codex Write Approval Prepare",
                trace_id=trace_id,
            ),
        )
        interruptions = list(result.interruptions)
        if len(interruptions) != 1:
            raise RuntimeError(f"Expected one approval interruption, got {len(interruptions)}")
        interruption = interruptions[0]
        state_json = result.to_state().to_json(strict_context=True)
        return ApprovalGatewayPrepareResult(
            state_json=state_json,
            tool_name=str(interruption.name or ""),
            call_id=str(interruption.call_id or ""),
            arguments=str(interruption.arguments or ""),
            trace_id=trace_id,
            response_id=getattr(result, "last_response_id", None),
            agent_usage=_usage_summary(result.context_wrapper.usage),
        )

    async def resume(
        self,
        *,
        settings: CodexWriteSettings,
        state_json: dict[str, Any],
        decision: str,
        executor: ApprovalExecutor,
    ) -> ApprovalGatewayResumeResult:
        (
            Agent,
            ModelSettings,
            RunConfig,
            Runner,
            RunState,
            RunContextWrapper,
            tool_decorator,
            gen_trace_id,
            set_default_openai_key,
            _version,
        ) = self._load_sdk()
        assert settings.api_key and settings.agent_model
        set_default_openai_key(settings.api_key)
        agent = self._build_agent(
            Agent=Agent,
            ModelSettings=ModelSettings,
            RunContextWrapper=RunContextWrapper,
            tool_decorator=tool_decorator,
            model=settings.agent_model,
            executor=executor,
        )
        state = await RunState.from_json(agent, state_json, strict_context=True)
        interruptions = list(state.get_interruptions())
        if len(interruptions) != 1:
            raise RuntimeError(f"Expected one persisted interruption, got {len(interruptions)}")
        if decision == "APPROVE":
            state.approve(interruptions[0])
        elif decision == "REJECT":
            state.reject(
                interruptions[0],
                rejection_message="The whole-run Codex workspace write was rejected by the operator.",
            )
        else:
            raise ValueError("Unknown approval decision")
        trace_id = gen_trace_id()
        result = await Runner.run(
            agent,
            state,
            run_config=self._run_config(
                RunConfig,
                workflow_name="OKCanvas Codex Write Approval Resume",
                trace_id=trace_id,
            ),
        )
        return ApprovalGatewayResumeResult(
            final_output=result.final_output,
            remaining_interruptions=len(result.interruptions),
            trace_id=trace_id,
            response_id=getattr(result, "last_response_id", None),
            agent_usage=_usage_summary(result.context_wrapper.usage),
        )
