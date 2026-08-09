from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step015_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.acceptance_workspace_windows_live_accepted is True
    assert info.operations_summary_api_implemented is True
    assert info.operations_task_run_list_api_implemented is True
    assert info.local_operations_console_implemented is True
    assert info.local_operations_console_mode == "read-only-local-admin"
    assert info.local_operations_console_deterministic_accepted is True
    assert info.local_operations_console_windows_live_accepted is False
    assert info.local_operations_console_framework == "server-owned-static-assets"


def test_step015_assets_are_product_owned_and_dependency_free() -> None:
    assets = component_asset_root(ROOT, "operations_console.assets")
    html = (assets / "index.html").read_text(encoding="utf-8")
    script = (assets / "console.js").read_text(encoding="utf-8")
    assert "https://" not in html
    assert "http://" not in html
    assert "/console/assets/console.js" in html
    assert "/console/assets/console.css" in html
    assert "sessionStorage" in script
    assert "localStorage" not in script
