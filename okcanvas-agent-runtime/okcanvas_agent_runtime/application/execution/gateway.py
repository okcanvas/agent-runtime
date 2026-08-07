from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from okcanvas_agent_runtime.agent.definitions import AgentDefinition
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.ports import SessionRuntimePort
from okcanvas_agent_runtime.domain.attachments.models import PreparedLocalAttachment
from okcanvas_agent_runtime.domain.project_snapshots.models import PreparedProjectSnapshot
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity

from okcanvas_agent_runtime.application.execution.contracts import GenericGatewayRunResult, GatewayLifecycleEvent

LifecycleSink = Callable[[GatewayLifecycleEvent], Awaitable[None]]


class GenericAgentGateway(Protocol):
    async def run(
        self,
        *,
        definition: AgentDefinition,
        request: str,
        run_id: str,
        settings: RuntimeSettings,
        lifecycle_sink: LifecycleSink,
        session_id: str | None = None,
        session_runtime: SessionRuntimePort | None = None,
        attachment: PreparedLocalAttachment | None = None,
        project_snapshot: PreparedProjectSnapshot | None = None,
        delegated_mcp_identity: DelegatedMCPIdentity | None = None,
    ) -> GenericGatewayRunResult: ...
