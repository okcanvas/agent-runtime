from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step039_baseline_and_native_streaming_contract() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    app = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/app.py")).read_text()
    runner = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/interactive_runner/assets/runner.js")).read_text()
    assert "Runner.run_streamed" in gateway
    assert "async for sdk_event in result.stream_events()" in gateway
    assert "/v1/runs/{run_id}/sdk-stream" in app
    assert "X-OKCanvas-Stream-Durability" in app
    assert "/sdk-stream?cursor=" in runner
    assert "nativeStreamController" in runner
    assert "response.function_call_arguments.delta" not in runner
