from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
SDK_INIT = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/__init__.py"
SDK_CONTEXT = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/tool_context.py"
SDK_EXAMPLE = ROOT / "reference/upstream/openai-agents-python-0.19.0/examples/basic/lifecycle_example.py"
FACTORY = legacy_source_contract(ROOT, "okcanvas_agent_runtime/function_tools/factories.py")


def main() -> int:
    init_source = SDK_INIT.read_text(encoding="utf-8")
    context_source = SDK_CONTEXT.read_text(encoding="utf-8")
    example_source = SDK_EXAMPLE.read_text(encoding="utf-8")
    factory_source = FACTORY.read_text(encoding="utf-8")
    checks = {
        "immutable_sdk_top_level_does_not_export_tool_context": (
            "from .tool_context import ToolContext" not in init_source
            and '"ToolContext"' not in init_source
        ),
        "immutable_sdk_defines_tool_context_in_submodule": (
            "class ToolContext(RunContextWrapper[TContext]):" in context_source
        ),
        "immutable_sdk_examples_use_submodule_import": (
            "from agents.tool_context import ToolContext" in example_source
        ),
        "product_imports_function_tool_from_top_level": (
            "from agents import function_tool" in factory_source
        ),
        "product_imports_tool_context_from_submodule": (
            "from agents.tool_context import ToolContext" in factory_source
        ),
        "product_does_not_import_tool_context_from_top_level": (
            "from agents import ToolContext" not in factory_source
        ),
        "output_type_only_contract_preserved": (
            "output_type=runtime.output_model" in factory_source
            and "output_json_schema=runtime.output_model.model_json_schema()" not in factory_source
        ),
        "reference_import_boundary_preserved": "/reference" not in factory_source.replace("\\", "/"),
    }
    payload = {
        "schema_version": "okcanvas-step059b-deterministic-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "tool_context_import_path": "agents.tool_context.ToolContext",
    }
    out = ROOT / "docs/evidence/STEP059B_DETERMINISTIC_ACCEPTANCE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
