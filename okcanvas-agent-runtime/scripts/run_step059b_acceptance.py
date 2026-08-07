from __future__ import annotations

import importlib.metadata
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, build_sdk_function_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def main() -> int:
    sdk_version = importlib.metadata.version("openai-agents")
    import agents
    from agents import Agent
    from agents.tool_context import ToolContext

    catalog = FunctionToolRuntimeCatalog(ROOT)
    tool_names: list[str] = []
    output_schema_present: list[bool] = []
    output_adapter_present: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="okcanvas-step059b-live-sdk-") as temp:
        workspace = Path(temp)
        (workspace / "src").mkdir()
        (workspace / "src/router.py").write_text(
            "def health():\n    return 'ok'\n", encoding="utf-8"
        )
        tools = []
        for index, tool_id in enumerate(
            ("local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"),
            start=1,
        ):
            tool = build_sdk_function_tool(
                catalog.resolve(tool_id),
                execution_id="execution_" + str(index) * 32,
                protected_text="Find the health route",
                workspace_root=workspace if tool_id == "project_readonly_inspect" else None,
            )
            tools.append(tool)
            tool_names.append(tool.name)
            output_schema_present.append(getattr(tool, "output_json_schema", None) is not None)
            output_adapter_present.append(getattr(tool, "_output_type_adapter", None) is not None)

        agent = Agent(
            name="STEP059B Actual SDK Tool Agent",
            instructions="Use the declared bounded read-only project Tool.",
            model="deterministic-no-network-model",
            tools=[tools[-1]],
            mcp_servers=[],
            handoffs=[],
            output_type=CodingAgentResult,
        )

    info = RuntimeInfo()
    checks = {
        "installed_sdk_version_exact": sdk_version == "0.19.0",
        "tool_context_absent_from_top_level_agents_export": not hasattr(agents, "ToolContext"),
        "tool_context_imported_from_exact_submodule": (
            ToolContext.__module__ == "agents.tool_context" and ToolContext.__name__ == "ToolContext"
        ),
        "all_three_product_tools_constructed_with_actual_sdk": tool_names
        == ["local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"],
        "actual_sdk_generated_output_schema_for_all_tools": output_schema_present
        == [True, True, True],
        "actual_sdk_bound_output_type_adapter_for_all_tools": output_adapter_present
        == [True, True, True],
        "actual_sdk_agent_constructed_with_project_tool": [tool.name for tool in agent.tools]
        == ["project_readonly_inspect"],
        "runtime_version_exact": info.version == "2.43.1",
        "runtime_step_exact": info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX",
        "product_import_path_exact": (
            info.actual_sdk_tool_context_import_path == "agents.tool_context.ToolContext"
        ),
        "top_level_export_not_expected": (
            info.actual_sdk_tool_context_top_level_export_expected is False
        ),
        "windows_live_accepted": info.actual_sdk_tool_context_windows_live_accepted is True,
    }
    payload = {
        "schema_version": "okcanvas-step059b-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "sdk_version": sdk_version,
        "tool_context_module": ToolContext.__module__,
        "tool_names": tool_names,
        "output_schema_present": output_schema_present,
        "output_adapter_present": output_adapter_present,
        "agent_tool_names": [tool.name for tool in agent.tools],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
