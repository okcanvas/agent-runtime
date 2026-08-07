from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from okcanvas_agent_runtime.core.governance.architecture_constitution import ArchitectureConstitutionError, resolve_architecture_constitution, _load_resource


@dataclass(frozen=True)
class StepComplianceSummary:
    step: str
    version: str
    constitution_sha256: str
    applied_clause_count: int
    changed_file_count: int
    gate_result_count: int
    traceability_entry_count: int
    pending_external_gate_count: int
    state: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "version": self.version,
            "constitution_sha256": self.constitution_sha256,
            "applied_clause_count": self.applied_clause_count,
            "changed_file_count": self.changed_file_count,
            "gate_result_count": self.gate_result_count,
            "traceability_entry_count": self.traceability_entry_count,
            "pending_external_gate_count": self.pending_external_gate_count,
            "state": self.state,
        }


def validate_step_compliance_record(payload: dict[str, Any]) -> StepComplianceSummary:
    if payload.get("schema_version") != "okcanvas-step-constitution-compliance-v1":
        raise ArchitectureConstitutionError("Invalid STEP constitution compliance schema")
    snapshot = resolve_architecture_constitution()
    if payload.get("constitution_sha256") != snapshot.constitution_sha256:
        raise ArchitectureConstitutionError("STEP compliance record uses a different constitution")

    constitution = _load_resource("architecture_constitution.json")
    known_clauses = {item["id"] for item in constitution["clauses"]}
    known_gates = set(constitution["required_gate_ids"])

    applied = payload.get("applied_clauses")
    changed_files = payload.get("changed_files")
    gate_results = payload.get("gate_results")
    traceability = payload.get("traceability")
    if not isinstance(applied, list) or not applied:
        raise ArchitectureConstitutionError("STEP compliance record must list applied clauses")
    if len(set(applied)) != len(applied) or not set(applied).issubset(known_clauses):
        raise ArchitectureConstitutionError("STEP compliance record has unknown or duplicate clauses")
    if not isinstance(changed_files, list) or not changed_files:
        raise ArchitectureConstitutionError("STEP compliance record must list every changed file")
    if len(set(changed_files)) != len(changed_files):
        raise ArchitectureConstitutionError("STEP compliance record changed files must be unique")
    if not all(isinstance(item, str) and item and not item.startswith("/") for item in changed_files):
        raise ArchitectureConstitutionError("STEP compliance changed files must be relative paths")
    if not isinstance(gate_results, list):
        raise ArchitectureConstitutionError("STEP compliance record gate results must be a list")
    if not isinstance(traceability, list):
        raise ArchitectureConstitutionError("STEP compliance traceability must be a list")

    gate_ids: list[str] = []
    pending_external_gate_ids: list[str] = []
    for result in gate_results:
        if not isinstance(result, dict):
            raise ArchitectureConstitutionError("STEP compliance gate results must be objects")
        gate_id = result.get("gate_id")
        status = result.get("status")
        gate_ids.append(gate_id)
        if gate_id not in known_gates:
            raise ArchitectureConstitutionError(f"Unknown STEP compliance gate {gate_id}")
        if status not in {"PASS", "NOT_APPLICABLE", "PENDING_EXTERNAL"}:
            raise ArchitectureConstitutionError(f"Gate {gate_id} has an invalid status")
        if status == "PENDING_EXTERNAL":
            if gate_id != "GATE-WINDOWS-LIVE":
                raise ArchitectureConstitutionError(
                    f"Only GATE-WINDOWS-LIVE may remain externally pending, not {gate_id}"
                )
            pending_external_gate_ids.append(str(gate_id))
        if status in {"NOT_APPLICABLE", "PENDING_EXTERNAL"} and not result.get("code_evidence"):
            raise ArchitectureConstitutionError(
                f"Gate {gate_id} needs code evidence when not marked PASS"
            )
    if len(gate_ids) != len(set(gate_ids)):
        raise ArchitectureConstitutionError("STEP compliance gate results must be unique")
    if set(gate_ids) != known_gates:
        missing = sorted(known_gates - set(gate_ids))
        extra = sorted(set(gate_ids) - known_gates)
        raise ArchitectureConstitutionError(
            f"STEP compliance must close every constitution gate: missing={missing}, extra={extra}"
        )

    trace_by_clause: dict[str, dict[str, Any]] = {}
    covered_files: set[str] = set()
    for item in traceability:
        if not isinstance(item, dict):
            raise ArchitectureConstitutionError("STEP compliance traceability entries must be objects")
        clause_id = item.get("clause_id")
        if clause_id in trace_by_clause:
            raise ArchitectureConstitutionError(f"Duplicate traceability entry for {clause_id}")
        if clause_id not in applied:
            raise ArchitectureConstitutionError(f"Traceability entry {clause_id} is not applied")
        if item.get("status") != "COMPLETE":
            raise ArchitectureConstitutionError(f"Traceability entry {clause_id} remains open")
        implementation_files = item.get("implementation_files")
        tests = item.get("test_files")
        acceptance = item.get("acceptance_checks")
        evidence = item.get("evidence_files")
        issues = item.get("issue_ids")
        for name, value in (
            ("implementation_files", implementation_files),
            ("test_files", tests),
            ("acceptance_checks", acceptance),
            ("evidence_files", evidence),
            ("issue_ids", issues),
        ):
            if not isinstance(value, list):
                raise ArchitectureConstitutionError(
                    f"Traceability {clause_id} field {name} must be a list"
                )
        covered_files.update(str(value) for value in implementation_files)
        covered_files.update(str(value) for value in tests)
        covered_files.update(str(value) for value in evidence)
        trace_by_clause[str(clause_id)] = item

    if set(trace_by_clause) != set(applied):
        missing = sorted(set(applied) - set(trace_by_clause))
        raise ArchitectureConstitutionError(
            f"STEP compliance traceability is incomplete: {missing}"
        )
    uncovered_changed = sorted(set(changed_files) - covered_files)
    if uncovered_changed:
        raise ArchitectureConstitutionError(
            f"Changed files are missing from traceability: {uncovered_changed}"
        )
    if payload.get("unregistered_changed_files") not in ([], None):
        raise ArchitectureConstitutionError("STEP compliance has unregistered changed files")
    if payload.get("open_clause_ids") not in ([], None):
        raise ArchitectureConstitutionError("STEP compliance has open clauses")
    if payload.get("unexecuted_required_gate_ids") not in ([], None):
        raise ArchitectureConstitutionError("STEP compliance has unexecuted required gates")
    declared_pending = payload.get("pending_external_gate_ids", [])
    if not isinstance(declared_pending, list) or sorted(declared_pending) != sorted(pending_external_gate_ids):
        raise ArchitectureConstitutionError(
            "STEP compliance pending external gates do not match gate results"
        )
    expected_state = (
        "DETERMINISTIC_COMPLETE_WINDOWS_PENDING"
        if pending_external_gate_ids
        else "COMPLETE"
    )
    if payload.get("state") != expected_state:
        raise ArchitectureConstitutionError(
            f"STEP compliance state must be {expected_state}"
        )

    return StepComplianceSummary(
        step=str(payload.get("step")),
        version=str(payload.get("version")),
        constitution_sha256=snapshot.constitution_sha256,
        applied_clause_count=len(applied),
        changed_file_count=len(changed_files),
        gate_result_count=len(gate_results),
        traceability_entry_count=len(traceability),
        pending_external_gate_count=len(pending_external_gate_ids),
        state=expected_state,
    )
