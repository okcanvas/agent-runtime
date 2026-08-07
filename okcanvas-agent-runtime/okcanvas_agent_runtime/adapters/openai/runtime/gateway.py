from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult, UsageSummary


@dataclass(frozen=True)
class GatewayRunResult:
    output: CodingAgentResult
    usage: UsageSummary
    trace_id: str
    response_id: str | None
    sdk_version: str


class AgentGateway(Protocol):
    async def run(
        self,
        *,
        request: str,
        run_id: str,
        settings: RuntimeSettings,
    ) -> GatewayRunResult: ...
