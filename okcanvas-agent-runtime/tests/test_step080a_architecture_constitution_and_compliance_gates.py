from __future__ import annotations

import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.governance import (
    ArchitectureConstitutionError,
    resolve_architecture_constitution,
    validate_step_compliance_record,
)
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.validate_architecture_constitution import validate

ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION_SHA = "262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa"


def _valid_record() -> dict[str, object]:
    return {
        "schema_version": "okcanvas-step-constitution-compliance-v1",
        "step": "TEST_STEP",
        "version": "0.0.0",
        "constitution_sha256": CONSTITUTION_SHA,
        "applied_clauses": ["GOV-005"],
        "changed_files": ["tests/example.py"],
        "gate_results": [
            {"gate_id": gate_id, "status": "PASS"}
            for gate_id in json.loads(
                (ROOT / "specs/architecture/constitution/OKCANVAS_AGENT_RUNTIME_ARCHITECTURE_CONSTITUTION.json")
                .read_text(encoding="utf-8")
            )["required_gate_ids"]
        ],
        "traceability": [
            {
                "clause_id": "GOV-005",
                "implementation_files": [],
                "test_files": ["tests/example.py"],
                "acceptance_checks": ["traceability_complete"],
                "evidence_files": [],
                "issue_ids": [],
                "status": "COMPLETE",
            }
        ],
        "unregistered_changed_files": [],
        "open_clause_ids": [],
        "unexecuted_required_gate_ids": [],
        "pending_external_gate_ids": [],
        "state": "COMPLETE",
    }


def test_packaged_constitution_identity_and_counts_are_exact() -> None:
    snapshot = resolve_architecture_constitution()
    assert snapshot.constitution_id == (
        "OKCANVAS_AGENT_RUNTIME_CLIENT_TRANSPORT_AGENT_ARCHITECTURE_CONSTITUTION"
    )
    assert snapshot.constitution_version == "1.0.0"
    assert snapshot.authority_state == "RATIFIED_ARCHITECTURE_CONSTITUTION"
    assert snapshot.constitution_sha256 == CONSTITUTION_SHA
    assert snapshot.clause_count == 127
    assert snapshot.required_gate_count == 32
    assert snapshot.normative_annex_count == 12
    assert snapshot.source_inventory_count == 9
    assert snapshot.product_source_movement_allowed is False


def test_full_constitution_bundle_integrity_and_coverage_pass() -> None:
    result = validate()
    assert result["state"] == "PASSED"
    assert result["passed_checks"] == result["total_checks"] == 16
    assert all(item["match"] for item in result["file_results"])


def test_step_compliance_record_requires_closed_clauses_gates_and_changed_files() -> None:
    summary = validate_step_compliance_record(_valid_record())
    assert summary.state == "COMPLETE"
    assert summary.applied_clause_count == 1
    assert summary.changed_file_count == 1

    record = _valid_record()
    record["open_clause_ids"] = ["GOV-005"]
    with pytest.raises(ArchitectureConstitutionError, match="open clauses"):
        validate_step_compliance_record(record)

    record = _valid_record()
    record["changed_files"] = ["tests/example.py", "src/unregistered.py"]
    with pytest.raises(ArchitectureConstitutionError, match="missing from traceability"):
        validate_step_compliance_record(record)

    record = _valid_record()
    record["gate_results"] = [
        {
            **result,
            **({"status": "NOT_APPLICABLE"} if result["gate_id"] == "GATE-TRACEABILITY-COMPLETE" else {}),
        }
        for result in record["gate_results"]
    ]
    with pytest.raises(ArchitectureConstitutionError, match="code evidence"):
        validate_step_compliance_record(record)


def test_runtime_info_exposes_ratified_constitution_without_unlocking_source_movement() -> None:
    info = RuntimeInfo()
    assert info.architecture_constitution_integrated is True
    assert info.architecture_constitution_sha256 == CONSTITUTION_SHA
    assert info.architecture_constitution_clause_count == 127
    assert info.architecture_constitution_required_gate_count == 32
    assert info.architecture_constitution_source_movement_allowed is False
    assert info.architecture_step_compliance_gate_implemented is True
    assert info.architecture_constitution_deterministic_accepted is True
    assert info.architecture_constitution_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_normative_bundle_and_runtime_resource_are_identical() -> None:
    canonical = json.loads(
        (ROOT / "specs/architecture/constitution/OKCANVAS_AGENT_RUNTIME_ARCHITECTURE_CONSTITUTION.json")
        .read_text(encoding="utf-8")
    )
    runtime = json.loads(
        (legacy_source_contract(ROOT, "okcanvas_agent_runtime/core/governance/resources/architecture_constitution.json"))
        .read_text(encoding="utf-8")
    )
    assert runtime == canonical


def test_step_compliance_rejects_missing_mandatory_gate() -> None:
    payload = _valid_record()
    payload["gate_results"] = payload["gate_results"][:-1]
    with pytest.raises(ArchitectureConstitutionError, match="close every constitution gate"):
        validate_step_compliance_record(payload)


def test_step_compliance_allows_only_windows_live_as_external_pending() -> None:
    record = _valid_record()
    record["gate_results"] = [
        {
            **result,
            **(
                {
                    "status": "PENDING_EXTERNAL",
                    "code_evidence": "Windows live acceptance must be run on the packaged candidate.",
                }
                if result["gate_id"] == "GATE-WINDOWS-LIVE"
                else {}
            ),
        }
        for result in record["gate_results"]
    ]
    record["pending_external_gate_ids"] = ["GATE-WINDOWS-LIVE"]
    record["state"] = "DETERMINISTIC_COMPLETE_WINDOWS_PENDING"
    summary = validate_step_compliance_record(record)
    assert summary.pending_external_gate_count == 1
    assert summary.state == "DETERMINISTIC_COMPLETE_WINDOWS_PENDING"

    record = _valid_record()
    record["gate_results"][0] = {
        "gate_id": record["gate_results"][0]["gate_id"],
        "status": "PENDING_EXTERNAL",
        "code_evidence": "not allowed",
    }
    record["pending_external_gate_ids"] = [record["gate_results"][0]["gate_id"]]
    record["state"] = "DETERMINISTIC_COMPLETE_WINDOWS_PENDING"
    with pytest.raises(ArchitectureConstitutionError, match="Only GATE-WINDOWS-LIVE"):
        validate_step_compliance_record(record)


def test_step080a_compliance_validator_closes_every_changed_file_and_gate() -> None:
    from scripts.validate_step080a_compliance import validate

    result = validate()
    assert result["state"] == "SUPERSEDED_BY_STEP081"
    assert result["passed_checks"] == result["total_checks"] == 8
    assert result["summary"]["gate_result_count"] == 32
    assert result["summary"]["pending_external_gate_count"] == 1
    assert result["superseding_step"] == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
