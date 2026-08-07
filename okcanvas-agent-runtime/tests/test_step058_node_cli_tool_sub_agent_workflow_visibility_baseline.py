from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step058_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.node_agent_cli_session_windows_live_accepted is True
    assert info.node_agent_cli_safe_read_only_tool_enabled is True
    assert info.node_agent_cli_native_handoff_enabled is True
    assert info.node_agent_cli_agent_as_tool_enabled is True
    assert info.node_agent_cli_capability_progress_visible is True
    assert info.node_agent_cli_invocation_tree_visible is True
    assert info.node_agent_cli_approval_tool_enabled is False
    assert info.node_agent_cli_mcp_enabled is False
    assert info.node_agent_cli_guardrail_enabled is False
    assert info.node_agent_cli_tool_sub_agent_workflow_deterministic_accepted is True
    assert info.node_agent_cli_tool_sub_agent_workflow_windows_live_accepted is True


def test_step058_node_cli_capability_boundary() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((CLI / "src").glob("*.ts")))
    assert package["version"] == "0.5.0"
    assert package.get("dependencies") in (None, {})
    assert "approval_mode === \"NEVER\"" in source
    assert "read_only === true" in source
    assert 'event.event_type === "tool.started"' in source
    assert 'event.event_type === "agent.handoff"' in source
    assert 'event.event_type === "agent.tool.started"' in source
    assert 'case "/invocations"' in source
    assert "okcanvas_agent_runtime" not in source
    assert "node:sqlite" not in source.lower()


def test_step058_acceptance_and_launcher_present() -> None:
    assert (ROOT / "scripts" / "run_step058_acceptance.py").is_file()
    assert (ROOT / "sh_run_step058_acceptance.cmd").is_file()
    assert (ROOT / "docs" / "evidence" / "STEP058_ACCEPTANCE.json").is_file()
