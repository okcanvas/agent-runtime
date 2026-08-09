from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import include

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step056b_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.tui_client_windows_live_accepted is True
    assert info.node_agent_cli_implemented is True
    assert info.node_agent_cli_language == "TypeScript"
    assert info.node_agent_cli_persistent_loop is True
    assert info.node_agent_cli_session_enabled is True
    assert info.node_agent_cli_evaluation_default_enabled is False
    assert info.node_agent_cli_deterministic_accepted is True
    assert info.node_agent_cli_windows_live_accepted is False


def test_node_cli_package_and_source_contract() -> None:
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    assert package["bin"]["okcanvas-agent"] == "./dist/cli.js"
    assert package.get("dependencies") in (None, {})
    assert package["engines"]["node"] == ">=22.0.0"
    assert (CLI / "src" / "cli.ts").is_file()
    assert (CLI / "dist" / "cli.js").is_file()
    assert (ROOT / "scripts" / "run_step056b_acceptance.py").is_file()
    assert (ROOT / "sh_run_step056b_acceptance.cmd").is_file()


def test_node_cli_is_control_api_only_and_python_independent() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((CLI / "src").glob("*.ts"))
    )
    launcher = (ROOT / "sh_tui.cmd").read_text(encoding="utf-8")
    assert "/v1/run-submissions/preflight" in source
    assert "/events/stream" in source
    assert "okcanvas_agent_runtime" not in source
    assert "python" not in source.lower()
    assert "node \"clients\\cli\\dist\\cli.js\" %*" in launcher
    assert ".venv\\Scripts\\python.exe" not in launcher


def test_node_cli_dist_is_retained_in_source_package() -> None:
    assert include(CLI / "dist" / "cli.js") is True
    assert include(CLI / "src" / "cli.ts") is True


def test_single_canonical_environment_template() -> None:
    assert (ROOT / ".env.local.example").is_file()
    assert not (ROOT / ".env.example").exists()
    assert not (ROOT / ".env.local.cmd.example").exists()
