from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, build_sdk_function_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def main() -> int:
    captured: list[dict[str, object]] = []
    fake_agents = types.ModuleType("agents")

    class FakeToolContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    def fake_function_tool(**kwargs):
        if kwargs.get("output_type") is not None and kwargs.get("output_json_schema") is not None:
            raise RuntimeError("output_type and output_json_schema cannot both be provided.")
        captured.append(kwargs)
        def decorate(func):
            return SimpleNamespace(name=kwargs["name_override"], invoke=func)
        return decorate

    fake_tool_context = types.ModuleType("agents.tool_context")
    fake_tool_context.ToolContext = FakeToolContext
    fake_agents.function_tool = fake_function_tool
    sys.modules["agents"] = fake_agents
    sys.modules["agents.tool_context"] = fake_tool_context

    sdk_source = (ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py").read_text(encoding="utf-8")
    factory_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/function_tools/factories.py")).read_text(encoding="utf-8")
    tool_names: list[str] = []
    project_relative_path = None
    with tempfile.TemporaryDirectory(prefix="okcanvas-step059a-") as temp:
        workspace = Path(temp)
        (workspace / "src").mkdir()
        (workspace / "src/router.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
        catalog = FunctionToolRuntimeCatalog(ROOT)
        for index, tool_id in enumerate(("local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"), start=1):
            tool = build_sdk_function_tool(
                catalog.resolve(tool_id),
                execution_id="execution_" + str(index) * 32,
                protected_text="Find the health route",
                workspace_root=workspace if tool_id == "project_readonly_inspect" else None,
            )
            tool_names.append(tool.name)
            if tool_id == "project_readonly_inspect":
                result = asyncio.run(tool.invoke(SimpleNamespace(context={"execution_id": "execution_" + "3" * 32}), "execution_" + "3" * 32))
                project_relative_path = result.inspected_files[0]

    info = RuntimeInfo()
    checks = {
        "immutable_sdk_mutual_exclusion_confirmed": 'raise UserError("output_type and output_json_schema cannot both be provided.")' in sdk_source,
        "product_factory_uses_output_type": "output_type=runtime.output_model" in factory_source,
        "product_factory_omits_output_json_schema_argument": "output_json_schema=runtime.output_model.model_json_schema()" not in factory_source,
        "all_registered_function_tools_constructed": tool_names == ["local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"],
        "all_sdk_bindings_use_exactly_one_output_contract": len(captured) == 3 and all(item.get("output_type") is not None and item.get("output_json_schema") is None for item in captured),
        "project_tool_still_returns_relative_evidence": project_relative_path == "src/router.py",
        "runtime_version_exact": info.version == "2.43.1",
        "runtime_step_exact": info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX",
        "prior_bounded_project_policy_preserved": info.bounded_project_readonly_coding_workflow_implemented and not info.bounded_project_readonly_write_enabled and not info.bounded_project_readonly_shell_enabled,
        "reference_import_boundary_preserved": "/reference" not in factory_source.replace("\\", "/"),
    }
    payload = {
        "schema_version": "okcanvas-step059a-deterministic-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "tool_names": tool_names,
        "project_relative_path": project_relative_path,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
