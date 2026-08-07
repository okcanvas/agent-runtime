from __future__ import annotations

import importlib.metadata
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, build_sdk_function_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def main() -> int:
    sdk_version = importlib.metadata.version("openai-agents")
    catalog = FunctionToolRuntimeCatalog(ROOT)
    tool_names: list[str] = []
    output_schema_present: list[bool] = []
    output_adapter_present: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="okcanvas-step059a-live-sdk-") as temp:
        workspace = Path(temp)
        (workspace / "src").mkdir()
        (workspace / "src/router.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
        for index, tool_id in enumerate(("local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"), start=1):
            tool = build_sdk_function_tool(
                catalog.resolve(tool_id),
                execution_id="execution_" + str(index) * 32,
                protected_text="Find the health route",
                workspace_root=workspace if tool_id == "project_readonly_inspect" else None,
            )
            tool_names.append(tool.name)
            output_schema_present.append(getattr(tool, "output_json_schema", None) is not None)
            output_adapter_present.append(getattr(tool, "_output_type_adapter", None) is not None)

    info = RuntimeInfo()
    checks = {
        "installed_sdk_version_exact": sdk_version == "0.19.0",
        "all_three_product_tools_constructed_with_actual_sdk": tool_names == ["local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"],
        "actual_sdk_generated_output_schema_for_all_tools": output_schema_present == [True, True, True],
        "actual_sdk_bound_output_type_adapter_for_all_tools": output_adapter_present == [True, True, True],
        "runtime_version_exact": info.version == "2.43.1",
        "runtime_step_exact": info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX",
        "dual_output_contract_disabled": info.actual_sdk_function_tool_output_json_schema_dual_binding is False,
        "output_type_only_enabled": info.actual_sdk_function_tool_output_type_only is True,
    }
    payload = {
        "schema_version": "okcanvas-step059a-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "sdk_version": sdk_version,
        "tool_names": tool_names,
        "output_schema_present": output_schema_present,
        "output_adapter_present": output_adapter_present,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
