from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import include

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step057_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.node_agent_cli_session_enabled is True
    assert info.node_agent_cli_runtime_session_conversation_implemented is True
    assert info.node_agent_cli_canonical_conversational_agent_id == "conversational-coding-agent"
    assert info.node_agent_cli_session_auto_create_implemented is True
    assert info.node_agent_cli_session_list_implemented is True
    assert info.node_agent_cli_session_resume_implemented is True
    assert info.node_agent_cli_session_clear_implemented is True
    assert info.node_agent_cli_session_new_boundary_implemented is True
    assert info.node_agent_cli_session_restart_resume_deterministic_accepted is True
    assert info.node_agent_cli_session_windows_live_accepted is True


def test_step057_conversational_agent_binding() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("conversational-coding-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert definition.session_mode == "sqlite-v1"
    assert definition.workspace_access == "none"
    assert definition.tools == ()
    assert definition.mcp_servers == ()
    assert definition.handoffs == ()
    assert definition.agent_tools == ()
    assert definition.guardrails == ()
    assert binding.execution_path == "sqlite-session-execution-v1"


def test_step057_node_package_session_contract() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((CLI / "src").glob("*.ts")))
    assert package["version"] == "0.5.0"
    assert package["bin"]["okcanvas-agent"] == "./dist/cli.js"
    assert package.get("dependencies") in (None, {})
    assert "/v1/sessions" in source
    assert "session_id" in source
    assert 'case "/new"' in source
    assert 'case "/sessions"' in source
    assert 'case "/resume"' in source
    assert 'case "/clear"' in source
    assert 'case "/history"' in source
    assert "okcanvas_agent_runtime" not in source
    assert "python" not in source.lower()
    assert include(CLI / "dist" / "cli.js") is True


def test_step057_default_agent_environment_is_launcher_accepted() -> None:
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    example = (ROOT / ".env.local.example").read_text(encoding="utf-8")
    assert '"OKCANVAS_DEFAULT_AGENT_ID"' in entrypoint
    assert "OKCANVAS_DEFAULT_AGENT_ID=conversational-coding-agent" in example


def test_step057_acceptance_and_launcher_present() -> None:
    assert (ROOT / "scripts" / "run_step057_acceptance.py").is_file()
    assert (ROOT / "sh_run_step057_acceptance.cmd").is_file()
    assert (ROOT / "docs" / "evidence" / "STEP057_ACCEPTANCE.json").is_file()
