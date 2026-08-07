from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step056_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.immutable_provider_identifier_windows_live_accepted is True
    assert info.tui_client_implemented is True
    assert info.tui_client_mode == "loopback-control-api-persisted-sse"
    assert info.tui_client_loopback_only is True
    assert info.tui_client_direct_runtime_access is False
    assert info.tui_client_session_enabled is False
    assert info.tui_client_approval_decision_enabled is False
    assert info.tui_client_deterministic_accepted is True
    assert info.tui_client_windows_live_accepted is True
    assert (component_asset_root(ROOT, "tui_client.package") / "app.py").is_file()
    assert (ROOT / "scripts" / "run_step056_acceptance.py").is_file()
    assert (ROOT / "sh_tui.cmd").is_file()
    assert (ROOT / "sh_run_step056_acceptance.cmd").is_file()
