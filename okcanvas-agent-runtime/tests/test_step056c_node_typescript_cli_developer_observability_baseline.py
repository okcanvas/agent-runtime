from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import include

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step056c_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.node_agent_cli_debug_mode_implemented is True
    assert info.node_agent_cli_debug_default_enabled is False
    assert info.node_agent_cli_debug_runtime_toggle_implemented is True
    assert info.node_agent_cli_debug_preflight_visible is True
    assert info.node_agent_cli_debug_persisted_sse_visible is True
    assert info.node_agent_cli_debug_artifact_json_visible is True
    assert info.node_agent_cli_post_run_evaluation_implemented is True
    assert info.node_agent_cli_explicit_initial_agent_selection is True
    assert info.node_agent_cli_developer_observability_deterministic_accepted is True
    assert info.node_agent_cli_developer_observability_windows_live_accepted is False


def test_step056c_node_package_and_launcher_contract() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == "0.5.0"
    assert package["bin"]["okcanvas-agent"] == "./dist/cli.js"
    assert package.get("dependencies") in (None, {})
    assert (ROOT / "scripts" / "run_step056c_acceptance.py").is_file()
    assert (ROOT / "sh_run_step056c_acceptance.cmd").is_file()
    assert include(CLI / "dist" / "cli.js") is True


def test_step056c_debug_mode_is_opt_in_and_control_api_only() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((CLI / "src").glob("*.ts")))
    assert 'case "--debug"' in source
    assert 'case "/debug"' in source
    assert 'case "/status"' in source
    assert 'case "/evaluate"' in source
    assert "confirmation_challenge" in source
    assert "/events/stream" in source
    assert "OKCANVAS_DEFAULT_AGENT_ID" in source
    assert "okcanvas_agent_runtime" not in source
    assert "python" not in source.lower()
