from __future__ import annotations

from tests.artifact_test_support import artifact_service

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource

ROOT = Path(__file__).resolve().parents[1]


class MCPGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        assert definition.mcp_servers == ("reference-catalog",)
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.started",
                {
                    "server_id": "reference-catalog",
                    "tool_name": "search_reference",
                    "arguments_persisted": False,
                },
                source=EventSource.MCP,
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.completed",
                {
                    "server_id": "reference-catalog",
                    "tool_name": "search_reference",
                    "result_persisted": False,
                },
                source=EventSource.MCP,
            )
        )
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="reference checked",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=2, input_tokens=10, output_tokens=5, total_tokens=15),
            trace_id="trace_mcp",
            response_id="resp",
            sdk_version="0.19.0",
        )


def test_product_store_persists_mcp_events_without_tool_payloads(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    envelope = asyncio.run(
        GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            definitions=AgentDefinitionCatalog(ROOT),
            store=store,
            gateway=MCPGateway(),
            artifact_root=tmp_path / "artifacts",
            artifact_service=artifact_service(store, tmp_path / "artifacts"),
        ).run(
            agent_definition_id="reference-research-agent",
            request="Find RunState in the reference.",
            settings=RuntimeSettings(model="model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "SUCCEEDED"
    events = store.list_events(envelope.run_id)
    mcp_events = [event for event in events if event.source is EventSource.MCP]
    assert [event.event_type for event in mcp_events] == ["tool.started", "tool.completed"]
    database = (tmp_path / "product.sqlite3").read_bytes()
    assert b"Find RunState in the reference" not in database
    assert b"secret" not in database
