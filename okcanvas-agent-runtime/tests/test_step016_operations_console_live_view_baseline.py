from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step016_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.persisted_sse_implemented is True
    assert info.persisted_sse_cursor_resume_accepted is True
    assert info.operations_console_persisted_live_view_implemented is True
    assert info.operations_console_live_view_mode == "authenticated-fetch-sse"
    assert info.operations_console_live_view_deterministic_accepted is True
    assert info.operations_console_live_view_windows_live_accepted is False
    assert info.local_operations_console_mode == "read-only-local-admin"


def test_step016_assets_use_product_owned_persisted_sse_adapter() -> None:
    assets = component_asset_root(ROOT, "operations_console.assets")
    html = (assets / "index.html").read_text(encoding="utf-8")
    script = (assets / "console.js").read_text(encoding="utf-8")
    parser = (assets / "persisted-sse.js").read_text(encoding="utf-8")
    assert "/console/assets/persisted-sse.js" in html
    assert "OKCanvasPersistedSSE.stream" in script
    assert "createParser" in parser
    assert "EventSource" not in script + parser
    assert "/reference" not in script + parser
