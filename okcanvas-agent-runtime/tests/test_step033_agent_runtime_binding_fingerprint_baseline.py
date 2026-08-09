from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step033_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.commerce_snapshot_bounded_quantities_windows_live_accepted is True
    assert info.agent_output_contract_runtime_registry_windows_live_accepted is True
    assert info.agent_runtime_binding_fingerprint_implemented is True
    assert info.agent_runtime_binding_schema_version == "okcanvas-agent-runtime-binding-v1"
    assert info.agent_runtime_binding_current_execution_path_count == 3
    assert info.agent_runtime_binding_sdk_version_bound is True
    assert info.agent_runtime_binding_output_contract_bound is True
    assert info.agent_runtime_binding_mcp_definition_and_module_bound is True
    assert info.agent_runtime_binding_local_tool_policy_and_implementation_bound is True
    assert info.agent_runtime_binding_submission_fingerprint_bound is True
    assert info.agent_runtime_binding_ledger_bound is True
    assert info.agent_runtime_binding_protected_payload_bound is True
    assert info.agent_runtime_binding_drift_fails_before_product_state is True
    assert info.agent_runtime_binding_deterministic_accepted is True
    assert info.agent_runtime_binding_windows_live_accepted is True


def test_current_agent_runtime_bindings_are_distinct_and_complete() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    catalog = AgentRuntimeBindingCatalog(ROOT)
    coding = catalog.resolve(definitions.resolve("coding-agent"))
    mcp = catalog.resolve(definitions.resolve("reference-research-agent"))
    local_tool = catalog.resolve(definitions.resolve("local-text-metrics-agent"))

    assert coding.schema_version == "okcanvas-agent-runtime-binding-v1"
    assert coding.execution_path == "generic-agent-execution-v1"
    assert mcp.execution_path == "generic-agent-execution-v1"
    assert local_tool.execution_path == "governed-function-tool-approval-v1"
    assert len({
        coding.runtime_binding_sha256,
        mcp.runtime_binding_sha256,
        local_tool.runtime_binding_sha256,
    }) == 3
    assert coding.mcp_servers == ()
    assert coding.local_tools == ()
    assert len(mcp.mcp_servers) == 1
    assert len(local_tool.local_tools) == 1
    for binding in (coding, mcp, local_tool):
        assert len(binding.runtime_binding_sha256) == 64
        assert len(binding.execution_engine_sha256) == 64
        assert len(binding.output_contract_runtime_sha256) == 64


def test_step033_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP033_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 20
    assert all(payload["checks"].values())
    assert payload["binding_count"] == 3
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["output_runtime_drift"]["replay_failure"] == "RunSubmissionIdempotencyConflict"
    assert payload["output_runtime_drift"]["confirmation_failure"] == "RunSubmissionIntegrityError"
    assert payload["mcp_drift"]["confirmation_failure"] == "RunSubmissionIntegrityError"
    assert payload["local_tool_drift"]["prepare_failure"] == "ToolApprovalIntegrityError"
    for section in ("output_runtime_drift", "mcp_drift", "local_tool_drift"):
        assert payload[section]["product_counts"]["tasks"] == 0
        assert payload[section]["product_counts"]["runs"] == 0


def test_windows_entrypoint_routes_step033_acceptance(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: ({}, None),
    )

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["agent-runtime-binding-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step033_acceptance.py") in command


def test_step033_windows_launcher_uses_project_venv() -> None:
    launcher = (ROOT / "sh_run_step033_acceptance.cmd").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert (
        '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py '
        "agent-runtime-binding-acceptance %*"
    ) in launcher
    assert "\npython " not in launcher.lower()
