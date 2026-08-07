from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.project_source_identity import force_project_root_first
force_project_root_first(ROOT)

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.governance import validate_step_compliance_record
from scripts.step081_product_inventory import (
    changed_paths,
    classified_workspace_residue,
    file_map,
    json_sha_without_self,
)

STEP = "STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION"
VERSION = "2.61.4"
RECORD = ROOT / "docs/evidence/STEP081D_CONSTITUTION_COMPLIANCE.json"
BASELINE = ROOT / "specs/architecture/STEP081_PRODUCT_BASELINE_INVENTORY.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _baseline_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["path"]): {"sha256": str(item["sha256"]), "size": int(item["size"])}
        for item in payload["files"]
    }


def validate(path: Path = RECORD) -> dict[str, Any]:
    record = _load(path)
    summary = validate_step_compliance_record(record)
    baseline = _load(BASELINE)
    current = file_map(ROOT)
    actual_changed = changed_paths(_baseline_map(baseline), current)
    workspace_residue = classified_workspace_residue(ROOT)
    architecture = _load(ROOT / "docs/evidence/STEP081D_ARCHITECTURE_VALIDATION.json")
    python_regression = _load(ROOT / "docs/evidence/STEP081D_PYTHON_REGRESSION.json")
    non_python = _load(ROOT / "docs/evidence/STEP081D_NON_PYTHON_VALIDATION.json")
    installation = _load(ROOT / "docs/evidence/STEP081D_INSTALLATION_VALIDATION.json")
    fresh = _load(ROOT / "docs/evidence/STEP081D_FRESH_ZIP_VALIDATION.json")
    issue_registry = (ROOT / "docs/issues/ISSUE_REGISTRY.md").read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION and summary.step == STEP and summary.version == VERSION,
        "baseline_zip_exact": baseline.get("baseline_zip_sha256") == "11a554e6a0fda3e728002ce915e9b3729622928919f30c5d30390814d2d29702",
        "baseline_inventory_self_hash_exact": baseline.get("inventory_sha256_without_self") == json_sha_without_self(baseline, "inventory_sha256_without_self"),
        "changed_files_exact": record.get("changed_files") == actual_changed,
        "record_self_hash_exact": record.get("record_sha256_without_self") == json_sha_without_self(record, "record_sha256_without_self"),
        "all_constitution_gates_closed": summary.gate_result_count == 32 and summary.pending_external_gate_count == 1,
        "all_clauses_traced": summary.applied_clause_count == 127 and summary.traceability_entry_count == 127,
        "architecture_passed": architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "full_python_passed": python_regression.get("state") == "PASSED" and python_regression.get("passed_tests") == python_regression.get("total_tests") == 921 and python_regression.get("test_file_count") == 230,
        "non_python_passed": non_python.get("state") == "PASSED" and non_python.get("node_tests_passed") is True and non_python.get("reference_result_count") == 4 and not non_python.get("direct_reference_import_violations"),
        "installation_passed": installation.get("state") == "PASSED" and installation.get("passed_checks") == installation.get("total_checks") == 16,
        "windows_subprocess_portability_passed": _load(ROOT / "docs/evidence/STEP081D_WINDOWS_SUBPROCESS_PORTABILITY_VALIDATION.json").get("state") == "PASSED",
        "fresh_zip_passed": fresh.get("state") == "PASSED" and fresh.get("python_regression", {}).get("passed_tests") == 921 and fresh.get("forbidden_entry_count") == 0,
        "execution_override_recorded": (ROOT / "docs/governance/STEP081_CONSOLIDATED_RESTRUCTURING_EXECUTION_OVERRIDE.md").is_file() and "OR-ISSUE-036" in issue_registry,
        "issues_complete": all(f"OR-ISSUE-{number:03d}" in issue_registry for number in range(17, 54)),
        "windows_only_pending": record.get("pending_external_gate_ids") == ["GATE-WINDOWS-LIVE"],
        "workspace_residue_classified": all(
            item.get("reason") in {
                "root_local_lockfile",
                "root_local_archive",
                "superseded_local_regression_evidence",
            }
            for item in workspace_residue
        ),
    }
    return {
        "schema_version": "okcanvas-step081d-compliance-validation-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
        "summary": summary.to_public_dict(),
        "actual_changed_file_count": len(actual_changed),
        "declared_changed_file_count": len(record.get("changed_files", [])),
        "unregistered_changed_files": sorted(set(actual_changed) - set(record.get("changed_files", []))),
        "stale_declared_changed_files": sorted(set(record.get("changed_files", [])) - set(actual_changed)),
        "classified_workspace_residue": workspace_residue,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
