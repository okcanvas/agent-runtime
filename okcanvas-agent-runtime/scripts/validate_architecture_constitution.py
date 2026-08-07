from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
for candidate in (PACKAGE_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from okcanvas_agent_runtime.core.governance import resolve_architecture_constitution

SPEC_ROOT = ROOT / "specs/architecture/constitution"
DEFAULT_OUTPUT = ROOT / "docs/evidence/ARCHITECTURE_CONSTITUTION_VALIDATION.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def validate() -> dict[str, Any]:
    snapshot = resolve_architecture_constitution()
    constitution = _load(SPEC_ROOT / "OKCANVAS_AGENT_RUNTIME_ARCHITECTURE_CONSTITUTION.json")
    integrity = _load(SPEC_ROOT / "BUNDLE_INTEGRITY.json")
    coverage = _load(SPEC_ROOT / "CONSTITUTION_COVERAGE_MATRIX.json")
    traceability = _load(SPEC_ROOT / "CONSTITUTION_TRACEABILITY_MATRIX.json")
    gates = _load(SPEC_ROOT / "CONSTITUTION_GATE_CATALOG.json")

    expected_files = integrity.get("files")
    if not isinstance(expected_files, list):
        raise ValueError("Bundle integrity file inventory is invalid")
    file_results: list[dict[str, Any]] = []
    for record in expected_files:
        if not isinstance(record, dict):
            raise ValueError("Bundle integrity file records must be objects")
        relative = Path(str(record["path"]))
        path = SPEC_ROOT / relative
        actual = _sha(path) if path.is_file() else None
        file_results.append(
            {
                "path": relative.as_posix(),
                "exists": path.is_file(),
                "expected_sha256": record.get("sha256"),
                "actual_sha256": actual,
                "match": actual == record.get("sha256"),
            }
        )

    clause_ids = [item["id"] for item in constitution["clauses"]]
    gate_ids = constitution["required_gate_ids"]
    trace_ids = [item["clause_id"] for item in traceability["entries"]]
    coverage_clause_ids = {
        clause_id
        for item in coverage["coverage"]
        for clause_id in item.get("covered_by", [])
    }
    catalog_gate_ids = [item["gate_id"] for item in gates["gates"]]

    checks = {
        "runtime_snapshot_resolves": snapshot.clause_count == 127
        and snapshot.required_gate_count == 32,
        "constitution_identity_exact": snapshot.constitution_id
        == "OKCANVAS_AGENT_RUNTIME_CLIENT_TRANSPORT_AGENT_ARCHITECTURE_CONSTITUTION"
        and snapshot.constitution_version == "1.0.0"
        and snapshot.authority_state == "RATIFIED_ARCHITECTURE_CONSTITUTION",
        "constitution_sha_exact": snapshot.constitution_sha256
        == "262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa",
        "source_baseline_exact": snapshot.source_step
        == "STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION"
        and snapshot.source_version == "2.60.0",
        "source_movement_still_blocked": snapshot.product_source_movement_allowed is False,
        "bundle_inventory_exact": integrity.get("file_count") == len(expected_files) == 18,
        "bundle_files_exist_and_match": all(item["match"] for item in file_results),
        "clause_count_and_ids_exact": len(clause_ids) == len(set(clause_ids)) == 127,
        "gate_count_and_ids_exact": len(gate_ids) == len(set(gate_ids)) == 32
        and set(gate_ids) == set(catalog_gate_ids),
        "all_gates_mandatory": all(item.get("mandatory") is True for item in gates["gates"]),
        "traceability_complete": len(trace_ids) == len(set(trace_ids)) == 127
        and set(trace_ids) == set(clause_ids)
        and traceability.get("constitution_sha256") == snapshot.constitution_sha256,
        "coverage_complete": coverage.get("coverage_item_count") == 36
        and coverage.get("uncovered_items") == []
        and coverage_clause_ids.issubset(set(clause_ids)),
        "normative_annex_count_exact": snapshot.normative_annex_count == 12,
        "source_inventory_count_exact": snapshot.source_inventory_count == 9,
        "execution_template_present": (SPEC_ROOT / "STEP_EXECUTION_COMPLIANCE_TEMPLATE.md").is_file(),
        "amendment_protocol_present": (SPEC_ROOT / "CONSTITUTION_AMENDMENT_PROTOCOL.md").is_file(),
    }
    return {
        "schema_version": "okcanvas-architecture-constitution-validation-v1",
        "validated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "snapshot": snapshot.to_public_dict(),
        "file_results": file_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        payload = validate()
    except Exception as exc:  # noqa: BLE001 - validator must produce bounded evidence
        payload = {
            "schema_version": "okcanvas-architecture-constitution-validation-v1",
            "state": "FAILED",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "checks": {},
            "passed_checks": 0,
            "total_checks": 0,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("state") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
