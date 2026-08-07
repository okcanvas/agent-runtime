from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.governance import validate_step_compliance_record
from scripts.step081_product_inventory import changed_paths, file_map, json_sha_without_self

STEP = "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
VERSION = "2.66.2"
RECORD = ROOT / "docs/evidence/STEP086R2_CONSTITUTION_COMPLIANCE.json"
BASELINE = ROOT / "specs/architecture/STEP081_PRODUCT_BASELINE_INVENTORY.json"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return payload


def _baseline_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["path"]): {"sha256": str(item["sha256"]), "size": int(item["size"])}
        for item in payload["files"]
    }


def validate(path: Path = RECORD) -> dict[str, Any]:
    record = _load(path)
    summary = validate_step_compliance_record(record)
    baseline = _load(BASELINE)
    actual_changed = changed_paths(_baseline_map(baseline), file_map(ROOT))
    architecture = _load(ROOT / "docs/evidence/STEP086R2_ARCHITECTURE_VALIDATION.json")
    connector = _load(ROOT / "docs/evidence/STEP086R2_CONNECTOR_CONTRACT_VALIDATION.json")
    python_regression = _load(ROOT / "docs/evidence/STEP086R2_PYTHON_REGRESSION.json")
    non_python = _load(ROOT / "docs/evidence/STEP086R2_NON_PYTHON_VALIDATION.json")
    installation = _load(ROOT / "docs/evidence/STEP086R2_INSTALLATION_VALIDATION.json")
    portability = _load(ROOT / "docs/evidence/STEP086R2_WINDOWS_SUBPROCESS_PORTABILITY_VALIDATION.json")
    acceptance = _load(ROOT / "docs/evidence/STEP086R2_ACCEPTANCE.json")
    issue_registry = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")
    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION and summary.step == STEP and summary.version == VERSION,
        "record_complete": summary.state == "COMPLETE" and summary.pending_external_gate_count == 0,
        "baseline_inventory_self_hash_exact": baseline.get("inventory_sha256_without_self") == json_sha_without_self(baseline, "inventory_sha256_without_self"),
        "changed_files_exact": record.get("changed_files") == actual_changed,
        "record_self_hash_exact": record.get("record_sha256_without_self") == json_sha_without_self(record, "record_sha256_without_self"),
        "all_constitution_gates_closed": summary.gate_result_count == 32,
        "all_clauses_traced": summary.applied_clause_count == summary.traceability_entry_count == 127,
        "architecture_passed": architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "connector_contract_passed": connector.get("state") == "PASSED" and connector.get("passed_checks") == connector.get("total_checks") == 11,
        "full_python_passed": python_regression.get("state") == "PASSED" and python_regression.get("passed_tests") == python_regression.get("total_tests") == 979 and python_regression.get("test_file_count") == len(list((ROOT / "tests").glob("test_*.py"))),
        "non_python_passed": non_python.get("state") == "PASSED" and non_python.get("node_passed_count") == 14 and non_python.get("reference_result_count") == 4 and not non_python.get("direct_reference_import_violations"),
        "installation_passed": installation.get("state") == "PASSED" and installation.get("passed_checks") == installation.get("total_checks") == 16,
        "portability_passed": portability.get("state") == "PASSED" and portability.get("passed_checks") == portability.get("total_checks") == 10,
        "acceptance_passed": acceptance.get("state") == "PASSED" and acceptance.get("passed_checks") == acceptance.get("total_checks") == 15,
        "issues_complete": all(f"OR-ISSUE-{number:03d}" in issue_registry for number in range(17, 99)),
        "windows_product_rerun_separate_from_constitution_gate": record.get("validation_environment", {}).get("step086r1_windows_deterministic") == "ACCEPTED_13_OF_13" and record.get("validation_environment", {}).get("step086r2_windows_deterministic") == "PENDING_EXTERNAL_PRODUCT_PROMOTION_GATE",
    }
    return {
        "schema_version": "okcanvas-step086r2-compliance-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
        "summary": summary.to_public_dict(),
        "actual_changed_file_count": len(actual_changed),
        "declared_changed_file_count": len(record.get("changed_files", [])),
        "unregistered_changed_files": sorted(set(actual_changed) - set(record.get("changed_files", []))),
        "stale_declared_changed_files": sorted(set(record.get("changed_files", [])) - set(actual_changed)),
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
