from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.application.execution.output_registry import (
    list_output_contracts,
    resolve_output_contract,
)
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step032_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.agent_output_contract_runtime_registry_implemented is True
    assert info.agent_output_contract_runtime_registry_count == 2
    assert info.generic_gateway_business_domain_decoupled is True
    assert info.contract_specific_invalid_final_output_recovery_implemented is True
    assert info.coding_agent_invalid_final_output_recovery_enabled is False
    assert info.agent_output_contract_runtime_registry_deterministic_accepted is True
    assert info.agent_output_contract_runtime_registry_windows_live_accepted is True


def test_step032_registry_and_gateway_boundary() -> None:
    contract_names = {contract.contract_name for contract in list_output_contracts()}
    assert {"CodingAgentResult", "StoreReplenishmentReviewResult"} <= contract_names
    assert not resolve_output_contract(
        "CodingAgentResult"
    ).supports_invalid_final_output_recovery
    coding = resolve_output_contract("CodingAgentResult")
    replenishment = resolve_output_contract("StoreReplenishmentReviewResult")
    assert coding.implementation_id == "coding-agent-result-runtime-v1"
    assert replenishment.implementation_id == "store-replenishment-result-runtime-v1"
    assert len(coding.definition_sha256) == 64
    assert len(replenishment.definition_sha256) == 64
    assert not coding.supports_invalid_final_output_recovery
    assert replenishment.supports_invalid_final_output_recovery
    gateway_source = read_component_source(ROOT, "execution.openai_gateway")
    assert "StoreReplenishment" not in gateway_source
    assert "build_store_replenishment_result" not in gateway_source


def test_step032_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP032_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 19
    assert all(payload["checks"].values())
    assert payload["contract_count"] == 2
    assert payload["coding_invalid"]["error_code"] == "SDK_RUN_FAILED"
    assert payload["replenishment_invalid"]["total_reorder_units"] == 19
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"


def test_windows_entrypoint_routes_step032_acceptance(monkeypatch) -> None:
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
    assert windows_entrypoint.run(["agent-output-contract-registry-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step032_acceptance.py") in command
