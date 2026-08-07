from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step059_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.node_agent_cli_tool_sub_agent_workflow_windows_live_accepted is True
    assert info.function_tool_runtime_registry_count == 4
    assert info.bounded_project_readonly_coding_workflow_implemented is True
    assert info.bounded_project_readonly_agent_id == "project-readonly-coding-agent"
    assert info.bounded_project_readonly_tool_id == "project_readonly_inspect"
    assert info.bounded_project_readonly_max_files == 3000
    assert info.bounded_project_readonly_max_total_bytes == 32 * 1024 * 1024
    assert info.bounded_project_readonly_max_file_bytes == 512 * 1024
    assert info.bounded_project_readonly_max_evidence_files == 4
    assert info.bounded_project_readonly_shell_enabled is False
    assert info.bounded_project_readonly_network_enabled is False
    assert info.bounded_project_readonly_write_enabled is False
    assert info.bounded_project_readonly_symlink_following_enabled is False
    assert info.bounded_project_readonly_deterministic_accepted is True
    assert info.bounded_project_readonly_windows_live_accepted is True


def test_step059_agent_and_tool_contracts() -> None:
    agent = AgentDefinitionCatalog(ROOT).resolve("project-readonly-coding-agent")
    tool = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    assert agent.tools == ("project_readonly_inspect",)
    assert agent.session_mode == "disabled"
    assert not agent.mcp_servers and not agent.handoffs and not agent.agent_tools and not agent.guardrails
    assert tool.approval_mode.value == "NEVER"
    assert tool.read_only is True
    assert tool.filesystem_access == "read-only"
    assert tool.network_access == "none"
    assert tool.shell_access == "none"
    assert tool.arguments_persisted is False
    assert tool.result_persisted_in_events is False


def test_step059_node_cli_and_acceptance_present() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((CLI / "src").glob("*.ts")))
    assert package["version"] == "0.5.0"
    assert package.get("dependencies") in (None, {})
    assert "project_readonly_inspect" in source
    assert "설정된 프로젝트의 텍스트 파일을 제한적으로 읽기 가능" in source
    assert "boundedEvidence" in source
    assert "okcanvas_agent_runtime" not in source
    assert (ROOT / "scripts" / "run_step059_acceptance.py").is_file()
    assert (ROOT / "sh_run_step059_acceptance.cmd").is_file()
    assert (ROOT / "docs" / "evidence" / "STEP059_ACCEPTANCE.json").is_file()
