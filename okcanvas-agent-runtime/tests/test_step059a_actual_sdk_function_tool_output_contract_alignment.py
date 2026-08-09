from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, build_sdk_function_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
SDK_TOOL = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py"


def _install_exact_fake_sdk(monkeypatch):
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
            return SimpleNamespace(
                name=kwargs["name_override"],
                output_type=kwargs.get("output_type"),
                output_json_schema=kwargs.get("output_json_schema"),
                invoke=func,
            )

        return decorate

    fake_tool_context = types.ModuleType("agents.tool_context")
    fake_tool_context.ToolContext = FakeToolContext
    fake_agents.function_tool = fake_function_tool
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.tool_context", fake_tool_context)
    return captured


def test_step059a_runtime_info_and_documents() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.actual_sdk_function_tool_output_alignment_implemented is True
    assert info.actual_sdk_function_tool_output_type_only is True
    assert info.actual_sdk_function_tool_output_json_schema_dual_binding is False
    assert info.actual_sdk_function_tool_mutual_exclusion_guarded is True
    assert info.actual_sdk_function_tool_deterministic_accepted is True
    assert info.actual_sdk_function_tool_windows_live_accepted is True
    assert (ROOT / "docs/plans/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION.md").is_file()
    assert (ROOT / "docs/reference/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION_CODE_AUDIT.md").is_file()
    assert (ROOT / "docs/evidence/STEP059_WINDOWS_REAL_OPENAI_FUNCTION_TOOL_FAILURE_SUMMARY.json").is_file()
    assert (ROOT / "docs/evidence/STEP059A_DETERMINISTIC_ACCEPTANCE.json").is_file()


def test_immutable_sdk_declares_output_contracts_mutually_exclusive() -> None:
    source = SDK_TOOL.read_text(encoding="utf-8")
    assert 'raise UserError("output_type and output_json_schema cannot both be provided.")' in source
    assert "This low-level escape hatch is mutually exclusive with ``output_type``." in source


def test_product_factory_binds_exactly_one_sdk_output_contract(monkeypatch, tmp_path: Path) -> None:
    captured = _install_exact_fake_sdk(monkeypatch)
    catalog = FunctionToolRuntimeCatalog(ROOT)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/router.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")

    tools = []
    for index, tool_id in enumerate(
        ("local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"), start=1
    ):
        runtime = catalog.resolve(tool_id)
        tools.append(
            build_sdk_function_tool(
                runtime,
                execution_id="execution_" + str(index) * 32,
                protected_text="Find the health route",
                workspace_root=tmp_path if tool_id == "project_readonly_inspect" else None,
            )
        )

    assert [tool.name for tool in tools] == [
        "local_text_fingerprint",
        "local_text_metrics",
        "project_readonly_inspect",
    ]
    assert len(captured) == 3
    assert all(item.get("output_type") is not None for item in captured)
    assert all(item.get("output_json_schema") is None for item in captured)

    project_output = asyncio.run(
        tools[-1].invoke(
            SimpleNamespace(context={"execution_id": "execution_" + "3" * 32}),
            "execution_" + "3" * 32,
        )
    )
    assert project_output.inspected_files == ["src/router.py"]


def test_product_source_has_no_dual_sdk_output_binding() -> None:
    source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/function_tools/factories.py")).read_text(
        encoding="utf-8"
    )
    call = source[source.index("tool = function_tool(") : source.index(")(raw_tool)")]
    assert "output_type=runtime.output_model" in call
    assert "output_json_schema=" not in call
