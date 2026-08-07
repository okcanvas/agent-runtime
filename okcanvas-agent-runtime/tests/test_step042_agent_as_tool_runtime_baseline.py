from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import DEFAULT_OUTPUT

ROOT = Path(__file__).resolve().parents[1]


def test_step042_runtime_and_agent_tool_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_tools/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_tools/policy.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_tools/runtime.py"),
        ROOT / "specs/runtime/agent-as-tool-policy.json",
        ROOT / "specs/agents/agent-tool-manager-agent/definition.json",
        ROOT / "specs/agents/agent-tool-specialist-agent/definition.json",
        ROOT / "specs/evaluations/agent-as-tool-v1/case.json",
        ROOT / "scripts/run_step042_acceptance.py",
        ROOT / "sh_run_step042_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP042_AGENT_AS_TOOL_RUNTIME_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP042_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP042_VALIDATION.txt",
        ROOT / "docs/evidence/STEP041_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step042_baseline_identifiers_are_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.handoffs_enabled is True
    assert info.generic_agent_tools_enabled is True
    assert info.native_handoff_windows_live_accepted is True
    assert info.agent_as_tool_runtime_implemented is True
    assert info.agent_as_tool_parent_control_retained is True
    assert info.agent_as_tool_parent_run_config_inherited is False
    assert info.agent_as_tool_deterministic_accepted is True
    assert info.agent_as_tool_windows_live_accepted is True


def test_step042_agent_as_tool_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(
        encoding="utf-8"
    )
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(
        encoding="utf-8"
    )
    invocation = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/service.py")).read_text(
        encoding="utf-8"
    )
    policy = (ROOT / "specs/runtime/agent-as-tool-policy.json").read_text(encoding="utf-8")
    packaging = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    assert "build_sdk_agent_tool" in gateway
    assert "agent.tool.started" in execution
    assert "agent.tool.completed" in execution
    assert "begin_agent_tool" in invocation
    assert '"max_agent_tool_calls_per_run": 1' in policy
    assert '"inherit_parent_run_config": false' in policy
    assert '"required_workspace_access": "none"' in policy
    assert DEFAULT_OUTPUT.name in packaging
