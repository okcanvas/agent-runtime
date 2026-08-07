from __future__ import annotations

import importlib.metadata
from typing import Any

from pydantic import ValidationError

from okcanvas_agent_runtime.agent.definitions import AgentDefinition
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, build_sdk_trace_run_config_kwargs
from okcanvas_agent_runtime.agent.skills import resolve_effective_instructions
from okcanvas_agent_runtime.agent.tools.function import (
    FunctionToolApprovalMode,
    FunctionToolRuntime,
    FunctionToolRuntimeCatalog,
    invocation_prompt,
)
from okcanvas_agent_runtime.application.approvals import gateway as approval_gateway
from okcanvas_agent_runtime.application.approvals.gateway import (
    LOCAL_TOOL_APPROVAL_MAX_TURNS,
    LifecycleSink,
    ToolApprovalGatewayPrepare,
    ToolApprovalGatewayResume,
    ToolExecutor,
)
from okcanvas_agent_runtime.application.execution.contracts import GatewayLifecycleEvent
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.domain.runs import EventSource

def _usage(value: Any) -> UsageSummary:
    inp = getattr(value, "input_tokens_details", None)
    out = getattr(value, "output_tokens_details", None)
    return UsageSummary(
        requests=int(getattr(value, "requests", 0) or 0),
        input_tokens=int(getattr(value, "input_tokens", 0) or 0),
        output_tokens=int(getattr(value, "output_tokens", 0) or 0),
        total_tokens=int(getattr(value, "total_tokens", 0) or 0),
        cached_input_tokens=int(getattr(inp, "cached_tokens", 0) or 0),
        reasoning_tokens=int(getattr(out, "reasoning_tokens", 0) or 0),
    )


class OpenAILocalToolApprovalGateway:
    @staticmethod
    def _load() -> tuple[Any, ...]:
        from agents import Agent, ModelSettings, RunConfig, RunHooks, Runner, RunState, gen_trace_id, set_default_openai_key

        version = importlib.metadata.version("openai-agents")
        if version != EXPECTED_OPENAI_AGENTS_VERSION:
            raise RuntimeError(
                f"openai-agents version {version} does not match {EXPECTED_OPENAI_AGENTS_VERSION}"
            )
        return (
            Agent,
            ModelSettings,
            RunConfig,
            RunHooks,
            Runner,
            RunState,
            gen_trace_id,
            set_default_openai_key,
            version,
        )

    @staticmethod
    def _runtime(definition: AgentDefinition) -> FunctionToolRuntime:
        project_root = definition.definition_path.parents[3]
        runtimes = FunctionToolRuntimeCatalog(project_root).resolve_many(definition.tools)
        if (
            len(runtimes) != 1
            or runtimes[0].approval_mode is not FunctionToolApprovalMode.ALWAYS
        ):
            raise RuntimeError("Approval gateway requires exactly one ALWAYS Function Tool")
        return runtimes[0]

    @classmethod
    def _agent(
        cls,
        *,
        definition: AgentDefinition,
        model: str,
        execution_id: str,
        executor: ToolExecutor,
        sdk: tuple[Any, ...],
        require_tool: bool,
    ) -> tuple[Any, FunctionToolRuntime]:
        Agent, ModelSettings, *_rest = sdk
        runtime = cls._runtime(definition)
        sdk_tool = approval_gateway.build_sdk_function_tool(
            runtime,
            execution_id=execution_id,
            executor=executor,
        )
        agent = Agent(
            name=definition.name,
            instructions=resolve_effective_instructions(definition),
            model=model,
            tools=[sdk_tool],
            handoffs=[],
            output_type=CodingAgentResult,
            model_settings=ModelSettings(tool_choice="required" if require_tool else "auto"),
        )
        return agent, runtime

    @staticmethod
    def _hooks(
        *,
        definition: AgentDefinition,
        settings: RuntimeSettings,
        sink: LifecycleSink,
        sdk: tuple[Any, ...],
        runtime: FunctionToolRuntime,
    ) -> Any:
        RunHooks = sdk[3]

        class Hooks(RunHooks):
            async def on_agent_start(self, context, agent):  # type: ignore[no-untyped-def]
                await sink(
                    GatewayLifecycleEvent(
                        "agent.started",
                        {"agent_id": definition.agent_id, "agent_name": definition.name},
                    )
                )

            async def on_llm_start(  # type: ignore[no-untyped-def]
                self, context, agent, system_prompt, input_items
            ):
                await sink(
                    GatewayLifecycleEvent(
                        "model.started",
                        {
                            "agent_id": definition.agent_id,
                            "model": settings.model,
                            "input_item_count": len(input_items),
                        },
                    )
                )

            async def on_llm_end(self, context, agent, response):  # type: ignore[no-untyped-def]
                await sink(
                    GatewayLifecycleEvent(
                        "model.completed",
                        {
                            "agent_id": definition.agent_id,
                            "response_id": getattr(response, "response_id", None),
                            "output_item_count": len(getattr(response, "output", ()) or ()),
                        },
                    )
                )

            async def on_tool_start(self, context, agent, tool):  # type: ignore[no-untyped-def]
                observed_name = str(
                    getattr(context, "tool_name", None) or getattr(tool, "name", "")
                )
                if observed_name != runtime.tool_id:
                    raise RuntimeError("Approval Tool identity drifted during execution")
                await sink(
                    GatewayLifecycleEvent(
                        "tool.started",
                        {
                            "tool_id": runtime.tool_id,
                            "runtime_version": runtime.runtime_version,
                            "approval_required": True,
                            "arguments_persisted": False,
                            "tool_call_id_present": bool(
                                getattr(context, "tool_call_id", None)
                            ),
                        },
                        "okcanvas-function-tool-started-v1",
                        EventSource.AGENT_SDK,
                    )
                )

            async def on_tool_end(self, context, agent, tool, result):  # type: ignore[no-untyped-def]
                observed_name = str(
                    getattr(context, "tool_name", None) or getattr(tool, "name", "")
                )
                if observed_name != runtime.tool_id:
                    raise RuntimeError("Approval Tool identity drifted during completion")
                await sink(
                    GatewayLifecycleEvent(
                        "tool.completed",
                        {
                            "tool_id": runtime.tool_id,
                            "runtime_version": runtime.runtime_version,
                            "approval_required": True,
                            "result_persisted": False,
                            "result_present": result is not None,
                            "tool_call_id_present": bool(
                                getattr(context, "tool_call_id", None)
                            ),
                        },
                        "okcanvas-function-tool-completed-v1",
                        EventSource.AGENT_SDK,
                    )
                )

            async def on_agent_end(self, context, agent, output):  # type: ignore[no-untyped-def]
                await sink(
                    GatewayLifecycleEvent(
                        "agent.completed",
                        {
                            "agent_id": definition.agent_id,
                            "output_contract": definition.output_contract,
                        },
                    )
                )

        return Hooks()

    @staticmethod
    def _config(RunConfig: Any, definition: AgentDefinition, run_id: str, trace_id: str):
        project_root = definition.definition_path.parents[3]
        trace_export_policy = TraceExportPolicyCatalog(project_root).resolve()
        trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
        return RunConfig(
            workflow_name=definition.workflow_name,
            trace_id=trace_id,
            group_id=run_id,
            **trace_run_config_settings,
            trace_metadata={
                "run_id": run_id,
                "agent_definition_id": definition.agent_id,
                "approval_mode": "function-tool",
                "function_tool_ids": list(definition.tools),
                "trace_export_policy_id": trace_export_policy.policy_id,
                "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                "provider_trace_export_enabled": False,
            },
        )

    async def prepare(
        self,
        *,
        definition: AgentDefinition,
        execution_id: str,
        run_id: str,
        settings: RuntimeSettings,
        lifecycle_sink: LifecycleSink,
        executor: ToolExecutor,
        session: Any | None = None,
    ) -> ToolApprovalGatewayPrepare:
        sdk = self._load()
        Agent, ModelSettings, RunConfig, RunHooks, Runner, RunState, gen_trace_id, set_key, _ = sdk
        if not settings.api_key or not settings.model:
            raise RuntimeError("SDK credentials are not configured")
        set_key(settings.api_key)
        agent, runtime = self._agent(
            definition=definition,
            model=settings.model,
            execution_id=execution_id,
            executor=executor,
            sdk=sdk,
            require_tool=True,
        )
        trace_id = gen_trace_id()
        result = await Runner.run(
            agent,
            invocation_prompt(runtime, execution_id),
            context={"execution_id": execution_id},
            max_turns=LOCAL_TOOL_APPROVAL_MAX_TURNS,
            hooks=self._hooks(
                definition=definition,
                settings=settings,
                sink=lifecycle_sink,
                sdk=sdk,
                runtime=runtime,
            ),
            run_config=self._config(RunConfig, definition, run_id, trace_id),
            session=session,
        )
        interruptions = list(result.interruptions)
        if len(interruptions) != 1:
            raise RuntimeError(
                f"Expected one Tool approval interruption, got {len(interruptions)}"
            )
        item = interruptions[0]
        return ToolApprovalGatewayPrepare(
            result.to_state().to_json(strict_context=True),
            str(item.name or ""),
            str(item.call_id or ""),
            str(item.arguments or ""),
            trace_id,
            result.last_response_id,
            _usage(result.context_wrapper.usage),
        )

    async def resume(
        self,
        *,
        definition: AgentDefinition,
        state_json: dict[str, Any],
        decision: str,
        run_id: str,
        settings: RuntimeSettings,
        lifecycle_sink: LifecycleSink,
        executor: ToolExecutor,
        session: Any | None = None,
    ) -> ToolApprovalGatewayResume:
        sdk = self._load()
        Agent, ModelSettings, RunConfig, RunHooks, Runner, RunState, gen_trace_id, set_key, _ = sdk
        if not settings.api_key or not settings.model:
            raise RuntimeError("SDK credentials are not configured")
        set_key(settings.api_key)
        executed = False

        async def counted() -> dict[str, Any]:
            nonlocal executed
            if executed:
                raise RuntimeError("Local Function Tool attempted more than once")
            executed = True
            return await executor()

        agent, runtime = self._agent(
            definition=definition,
            model=settings.model,
            execution_id="execution_" + "0" * 32,
            executor=counted,
            sdk=sdk,
            require_tool=False,
        )
        state = await RunState.from_json(agent, state_json, strict_context=True)
        items = list(state.get_interruptions())
        if len(items) != 1 or str(items[0].name or "") != runtime.tool_id:
            raise RuntimeError("Persisted Function Tool interruption identity mismatch")
        if decision == "APPROVE":
            state.approve(items[0])
        elif decision == "REJECT":
            state.reject(
                items[0],
                rejection_message="The local Function Tool call was rejected by the operator.",
            )
        else:
            raise ValueError("Unknown decision")
        trace_id = gen_trace_id()
        result = await Runner.run(
            agent,
            state,
            hooks=self._hooks(
                definition=definition,
                settings=settings,
                sink=lifecycle_sink,
                sdk=sdk,
                runtime=runtime,
            ),
            run_config=self._config(RunConfig, definition, run_id, trace_id),
            session=session,
        )
        output = None
        if decision == "APPROVE":
            try:
                output = result.final_output_as(
                    CodingAgentResult, raise_if_incorrect_type=True
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise RuntimeError("Approval resume output contract failed") from exc
        return ToolApprovalGatewayResume(
            output=output,
            trace_id=trace_id,
            response_id=result.last_response_id,
            usage=_usage(result.context_wrapper.usage),
            remaining_interruptions=len(list(result.interruptions)),
            tool_executed=executed,
        )
