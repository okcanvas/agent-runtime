from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.agent.tools.function import FunctionToolApprovalMode, FunctionToolRuntimeCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step038_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.function_tool_runtime_registry_implemented is True
    assert info.function_tool_runtime_registry_count == 4
    assert info.function_tool_read_only_nonapproval_supported is True
    assert info.function_tool_native_approval_supported is True
    assert info.function_tool_mixed_approval_modes_supported is False
    assert info.function_tool_raw_arguments_results_persisted is False
    assert info.function_tool_runtime_deterministic_accepted is True
    assert info.function_tool_runtime_windows_live_accepted is True
    runtimes = FunctionToolRuntimeCatalog(ROOT).list_runtimes()
    assert [(item.tool_id, item.approval_mode) for item in runtimes] == [
        ("local_text_fingerprint", FunctionToolApprovalMode.NEVER),
        ("local_text_metrics", FunctionToolApprovalMode.ALWAYS),
        ("project_readonly_inspect", FunctionToolApprovalMode.NEVER),
        ("sandbox_project_readonly_inspect", FunctionToolApprovalMode.NEVER),
    ]
    assert (ROOT / "scripts" / "run_step038_acceptance.py").is_file()
    assert (ROOT / "sh_run_step038_acceptance.cmd").is_file()
