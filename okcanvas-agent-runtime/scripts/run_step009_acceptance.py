from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.adapters.mcp.servers.reference_catalog import ReferenceCatalogMCPTools
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/STEP009_ACCEPTANCE.json"


class DeterministicMCPGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        for tool_name in ("search_reference", "read_reference_file"):
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.started",
                    {
                        "server_id": "reference-catalog",
                        "tool_name": tool_name,
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
                        "tool_name": tool_name,
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
                summary="RunState reference evidence was inspected through read-only MCP.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=3, input_tokens=60, output_tokens=20, total_tokens=80),
            trace_id="trace_step009",
            response_id="resp",
            sdk_version="0.19.0",
        )



async def _run() -> dict[str, object]:
    before = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    server = MCPServerCatalog(ROOT).resolve("reference-catalog")
    tools = ReferenceCatalogMCPTools(ROOT, max_result_chars=server.max_result_chars)
    search_text = tools.search_reference("RunState", ["openai-agents-python"], 4)
    search = json.loads(search_text)
    read_text = tools.read_reference_file(
        "openai-agents-python", "src/agents/run_state.py", 1, 30
    )
    read = json.loads(read_text)

    with AcceptanceWorkspace(step_id="STEP009", output=OUTPUT) as workspace:
        root = workspace.root
        store = SQLiteProductStore(root / "product.sqlite3")
        store.initialize()
        request = "Find the RunState implementation using the read-only reference MCP tools."
        envelope = await GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            definitions=AgentDefinitionCatalog(ROOT),
            store=store,
            gateway=DeterministicMCPGateway(),
            artifact_root=root / "artifacts",
        ).run(
            agent_definition_id="reference-research-agent",
            request=request,
            settings=RuntimeSettings(model="deterministic-model", api_key="sentinel-secret"),
            live_opt_in=True,
        )
        events = store.list_events(envelope.run_id)
        database = (root / "product.sqlite3").read_bytes()
        mcp_events = [event for event in events if event.source is EventSource.MCP]
        after = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
        checks = {
            "server_allowlisted": server.server_id == "reference-catalog",
            "tools_exact": server.allowed_tools == ("search_reference", "read_reference_file"),
            "server_read_only": server.read_only is True,
            "search_found_runstate": any(
                item["relative_path"] == "src/agents/run_state.py"
                for item in search["result"]["matches"]
            ),
            "read_exact_path": read["result"]["relative_path"] == "src/agents/run_state.py",
            "read_bounded": len(read["result"]["lines"]) == 30,
            "execution_succeeded": envelope.state == "SUCCEEDED",
            "mcp_events_persisted": [item.event_type for item in mcp_events]
            == ["tool.started", "tool.completed", "tool.started", "tool.completed"],
            "mcp_event_sources": all(item.source is EventSource.MCP for item in mcp_events),
            "tool_arguments_not_persisted": request.encode() not in database,
            "api_key_not_persisted": b"sentinel-secret" not in database,
            "tool_result_not_persisted": b"class RunState" not in database,
            "references_unchanged": before == after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step009-deterministic-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "checks": checks,
            "server": server.to_public_dict(),
            "event_types": [item.event_type for item in events],
            "event_sources": [item.source.value for item in events],
            "reference_verification": after,
        }
        return workspace.finalize(payload)


def main() -> int:
    payload = asyncio.run(_run())
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
