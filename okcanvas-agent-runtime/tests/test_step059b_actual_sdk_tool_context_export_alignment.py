from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, build_sdk_function_tool
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = ROOT / "reference/upstream/openai-agents-python-0.19.0"
SDK_INIT = SDK_ROOT / "src/agents/__init__.py"
SDK_TOOL_CONTEXT = SDK_ROOT / "src/agents/tool_context.py"
SDK_EXAMPLE = SDK_ROOT / "examples/basic/lifecycle_example.py"
FACTORY = legacy_source_contract(ROOT, "okcanvas_agent_runtime/function_tools/factories.py")


def _install_exact_export_fake(monkeypatch):
    captured: list[dict[str, object]] = []
    fake_agents = types.ModuleType("agents")
    fake_tool_context = types.ModuleType("agents.tool_context")

    class FakeToolContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    class FakeAgent:
        def __init__(self, **kwargs):
            self.tools = list(kwargs.get("tools", ()))
            self.kwargs = kwargs

    def fake_function_tool(**kwargs):
        captured.append(kwargs)

        def decorate(func):
            return SimpleNamespace(
                name=kwargs["name_override"],
                output_json_schema={"type": "object"},
                _output_type_adapter=object(),
                invoke=func,
            )

        return decorate

    fake_agents.Agent = FakeAgent
    fake_agents.function_tool = fake_function_tool
    fake_tool_context.ToolContext = FakeToolContext
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.tool_context", fake_tool_context)
    return fake_agents, FakeToolContext, captured


def test_immutable_sdk_tool_context_export_contract() -> None:
    init_source = SDK_INIT.read_text(encoding="utf-8")
    context_source = SDK_TOOL_CONTEXT.read_text(encoding="utf-8")
    example_source = SDK_EXAMPLE.read_text(encoding="utf-8")
    assert "from .tool_context import ToolContext" not in init_source
    assert '"ToolContext"' not in init_source
    assert "class ToolContext(RunContextWrapper[TContext]):" in context_source
    assert "from agents.tool_context import ToolContext" in example_source


def test_product_factory_uses_exact_sdk_import_path() -> None:
    source = FACTORY.read_text(encoding="utf-8")
    assert "from agents import function_tool" in source
    assert "from agents.tool_context import ToolContext" in source
    assert "from agents import ToolContext" not in source


def test_fake_sdk_mirrors_real_export_and_full_agent_construction(monkeypatch) -> None:
    fake_agents, fake_context, captured = _install_exact_export_fake(monkeypatch)
    assert not hasattr(fake_agents, "ToolContext")
    assert fake_context.__name__ == "FakeToolContext"

    catalog = FunctionToolRuntimeCatalog(ROOT)
    tools = []
    with tempfile.TemporaryDirectory(prefix="okcanvas-step059b-") as temp:
        workspace = Path(temp)
        (workspace / "src").mkdir()
        (workspace / "src/router.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
        for index, tool_id in enumerate(
            ("local_text_fingerprint", "local_text_metrics", "project_readonly_inspect"),
            start=1,
        ):
            tools.append(
                build_sdk_function_tool(
                    catalog.resolve(tool_id),
                    execution_id="execution_" + str(index) * 32,
                    protected_text="Find the health route",
                    workspace_root=workspace if tool_id == "project_readonly_inspect" else None,
                )
            )
    agent = fake_agents.Agent(
        name="STEP059B Tool Agent",
        instructions="Use the declared Tool.",
        model="deterministic-model",
        tools=[tools[-1]],
        mcp_servers=[],
        handoffs=[],
        output_type=CodingAgentResult,
    )
    assert [tool.name for tool in tools] == [
        "local_text_fingerprint",
        "local_text_metrics",
        "project_readonly_inspect",
    ]
    assert [tool.name for tool in agent.tools] == ["project_readonly_inspect"]
    assert len(captured) == 3


def test_step059b_runtime_info_and_handoff_documents() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.actual_sdk_tool_context_export_alignment_implemented is True
    assert info.actual_sdk_tool_context_import_path == "agents.tool_context.ToolContext"
    assert info.actual_sdk_tool_context_top_level_export_expected is False
    assert info.actual_sdk_tool_context_fake_sdk_mirrors_export_structure is True
    assert info.actual_sdk_tool_context_deterministic_accepted is True
    assert info.actual_sdk_tool_context_windows_live_accepted is True
    assert (ROOT / "docs/plans/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION.md").is_file()
    assert (ROOT / "docs/reference/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION_CODE_AUDIT.md").is_file()
    assert (ROOT / "docs/evidence/STEP059A_WINDOWS_ACTUAL_SDK_TOOL_CONTEXT_IMPORT_FAILURE_SUMMARY.json").is_file()
