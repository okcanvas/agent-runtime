from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from scripts.node_acceptance import run_command, run_node_tests, run_npm_pack, validate_committed_typescript_release
from scripts.verify_no_reference_imports import find_violations

STEP = "STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION"
VERSION = "2.61.4"
DEFAULT_OUTPUT = ROOT / "docs/evidence/STEP081D_NON_PYTHON_VALIDATION.json"


def validate(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    node_root = ROOT / "clients/cli"
    node_release_ok, node_release_output = validate_committed_typescript_release(node_root)
    node_ok, node_output = run_node_tests(node_root)
    npm_pack_ok, npm_pack_output = run_npm_pack(node_root)
    reference_results = ReferenceCatalogService(ROOT).verify_all()
    direct_violations = find_violations(ROOT)
    checks = {
        "node_release_manifest_passed": node_release_ok,
        "node_tests_passed": node_ok,
        "npm_pack_dry_run_passed": npm_pack_ok,
        "reference_integrity_passed": len(reference_results) == 4 and all(item.verified for item in reference_results),
        "direct_reference_imports_absent": not direct_violations,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step081d-non-python-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        **checks,
        "reference_result_count": len(reference_results),
        "reference_results": [item.to_dict() for item in reference_results],
        "direct_reference_import_violations": direct_violations,
        "node_release_output": node_release_output,
        "node_test_output": node_output,
        "npm_pack_output": npm_pack_output,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = validate()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
