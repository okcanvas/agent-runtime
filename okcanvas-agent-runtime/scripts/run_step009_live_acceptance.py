from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.baseline import PROJECT_VERSION
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, OpenAIGenericAgentGateway
from okcanvas_agent_runtime.adapters.mcp.clients import create_openai_mcp_runtime
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _tool_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", ()) or ():
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    if not parts:
        raise RuntimeError("MCP Tool result did not contain text content")
    return "\n".join(parts)


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


async def _run(acceptance_root: Path) -> int:
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    before = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    definition = MCPServerCatalog(ROOT).resolve("reference-catalog")
    runtime = create_openai_mcp_runtime((definition,), project_root=ROOT)
    protocol: dict[str, object] = {}
    async with runtime.manager as manager:
        server = manager.active_servers[0]
        listed = await server.list_tools()
        protocol["listed_tools"] = [tool.name for tool in listed]
        search_result = await server.call_tool(
            "search_reference",
            {
                "query": "RunState",
                "reference_ids": ["openai-agents-python"],
                "max_results": 4,
            },
        )
        search = json.loads(_tool_text(search_result))
        read_result = await server.call_tool(
            "read_reference_file",
            {
                "reference_id": "openai-agents-python",
                "path": "src/agents/run_state.py",
                "start_line": 1,
                "end_line": 30,
            },
        )
        read = json.loads(_tool_text(read_result))
        protocol["search"] = search
        protocol["read"] = read

    database_path = acceptance_root / "product.sqlite3"
    store = SQLiteProductStore(database_path)
    store.initialize()
    request = (
        "Use search_reference first, then read_reference_file for "
        "openai-agents-python src/agents/run_state.py lines 1 through 30. "
        "Explain only confirmed RunState responsibilities and list anything unverified."
    )
    envelope = await GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=OpenAIGenericAgentGateway(),
        artifact_root=acceptance_root / "artifacts",
    ).run(
        agent_definition_id="reference-research-agent",
        request=request,
        settings=RuntimeSettings.from_env(),
        live_opt_in=True,
    )
    events = store.list_events(envelope.run_id) if envelope.run_id else []
    mcp_events = [event for event in events if event.source is EventSource.MCP]
    after = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    database = database_path.read_bytes()
    api_key = os.getenv("OPENAI_API_KEY", "")
    checks = {
        "protocol_connected": protocol.get("listed_tools") == list(definition.allowed_tools),
        "protocol_search_found_runstate": any(
            item["relative_path"] == "src/agents/run_state.py"
            for item in protocol["search"]["result"]["matches"]
        ),
        "protocol_read_exact": protocol["read"]["result"]["relative_path"]
        == "src/agents/run_state.py",
        "agent_execution_succeeded": envelope.state == "SUCCEEDED",
        "tool_started_recorded": sum(item.event_type == "tool.started" for item in mcp_events) >= 2,
        "tool_completed_recorded": sum(item.event_type == "tool.completed" for item in mcp_events) >= 2,
        "mcp_event_source": bool(mcp_events) and all(item.source is EventSource.MCP for item in mcp_events),
        "tool_arguments_redacted": request.encode("utf-8") not in database,
        "api_key_redacted": not api_key or api_key.encode("utf-8") not in database,
        "reference_content_not_in_database": b"class RunState" not in database,
        "artifact_verified": bool(envelope.artifact_id)
        and store.verify_artifact(envelope.artifact_id).sha256 == envelope.artifact_sha256,
        "references_unchanged": before == after,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step009-live-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "acceptance_id": acceptance_root.name,
        "project_version": PROJECT_VERSION,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "checks": checks,
        "mcp_server": definition.to_public_dict(),
        "protocol": protocol,
        "envelope": envelope.model_dump(mode="json"),
        "event_types": [item.event_type for item in events],
        "mcp_events": [
            {
                "sequence": item.sequence,
                "event_type": item.event_type,
                "source": item.source.value,
                "payload": item.payload,
            }
            for item in mcp_events
        ],
        "reference_verification_before": before,
        "reference_verification_after": after,
    }
    _write_atomic(acceptance_root / "acceptance-summary.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    print(f"Acceptance evidence: {acceptance_root}")
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-id")
    args = parser.parse_args()
    if os.getenv("OKCANVAS_STEP009_LIVE_ACCEPTANCE") != "1":
        print("STEP009 live acceptance requires OKCANVAS_STEP009_LIVE_ACCEPTANCE=1")
        return 2
    acceptance_id = args.acceptance_id or f"{_stamp()}-{uuid.uuid4().hex[:8]}"
    acceptance_root = ROOT / "docs/evidence/step009-live" / acceptance_id
    if acceptance_root.exists():
        print(f"Acceptance directory already exists: {acceptance_root}")
        return 2
    acceptance_root.mkdir(parents=True)
    return asyncio.run(_run(acceptance_root))


if __name__ == "__main__":
    raise SystemExit(main())
