from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Awaitable, Callable, Protocol

from okcanvas_agent_runtime.agent.definitions import AgentDefinition
from okcanvas_agent_runtime.application.execution.contracts import GatewayLifecycleEvent
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, UsageSummary

LifecycleSink = Callable[[GatewayLifecycleEvent], Awaitable[None]]
ToolExecutor = Callable[[], Awaitable[dict[str, Any]]]

# One model turn requests the protected Tool and a second turn finalizes after approval/rejection.
LOCAL_TOOL_APPROVAL_MAX_TURNS = 2


@dataclass(frozen=True)
class ToolApprovalGatewayPrepare:
    state_json: dict[str, Any]
    tool_name: str
    call_id: str
    arguments: str
    trace_id: str | None
    response_id: str | None
    usage: UsageSummary


@dataclass(frozen=True)
class ToolApprovalGatewayResume:
    output: CodingAgentResult | None
    trace_id: str | None
    response_id: str | None
    usage: UsageSummary
    remaining_interruptions: int
    tool_executed: bool


def build_sdk_function_tool(*args: Any, **kwargs: Any) -> Any:
    """Historical monkeypatch surface forwarded to the canonical Agent Tool factory."""
    factory = getattr(
        import_module("okcanvas_agent_runtime.agent.tools.function"),
        "build_sdk_function_tool",
    )
    return factory(*args, **kwargs)


class ToolApprovalGateway(Protocol):
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
    ) -> ToolApprovalGatewayPrepare: ...

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
    ) -> ToolApprovalGatewayResume: ...


def __getattr__(name: str):
    # Historical import compatibility without a static Application -> Adapter dependency.
    if name == "OpenAILocalToolApprovalGateway":
        value = getattr(
            import_module("okcanvas_agent_runtime.adapters.openai.local_tool_approval"),
            name,
        )
        globals()[name] = value
        return value
    raise AttributeError(name)


__all__ = [
    "LOCAL_TOOL_APPROVAL_MAX_TURNS",
    "LifecycleSink",
    "ToolExecutor",
    "ToolApprovalGateway",
    "ToolApprovalGatewayPrepare",
    "ToolApprovalGatewayResume",
    "build_sdk_function_tool",
    "OpenAILocalToolApprovalGateway",
]
