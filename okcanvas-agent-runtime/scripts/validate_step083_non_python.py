from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.node_acceptance import run_command, run_npm_pack
from scripts.verify_no_reference_imports import find_violations

STEP = "STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION"
VERSION = "2.63.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP083_NON_PYTHON_VALIDATION.json"
CLI_ROOT = ROOT / "clients/cli"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _reference_result_count(output: str) -> int:
    match = re.search(r"PASS reference baseline: (\d+)/(\d+)", output)
    if not match or match.group(1) != match.group(2):
        return 0
    return int(match.group(1))


def _node_counts(output: str) -> tuple[int, int]:
    tests = re.search(r"# tests (\d+)", output)
    passed = re.search(r"# pass (\d+)", output)
    return (int(tests.group(1)) if tests else 0, int(passed.group(1)) if passed else 0)


def validate(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    started = _now()
    node_ok, node_output = run_command(["npm", "run", "check"], CLI_ROOT)
    reference_ok, reference_output = run_command([sys.executable, "scripts/verify_reference.py"], ROOT)
    direct_violations = find_violations(ROOT)
    pack_ok, pack_output = run_npm_pack(CLI_ROOT)
    try:
        pack_payload = json.loads(pack_output) if pack_ok else []
    except json.JSONDecodeError:
        pack_payload = []
    node_tests, node_passed = _node_counts(node_output)
    reference_count = _reference_result_count(reference_output)
    pack_entry_count = int(pack_payload[0].get("entryCount", 0)) if len(pack_payload) == 1 else 0
    checks = {
        "node_check_passed": node_ok,
        "node_tests_exact": node_tests == node_passed == 14,
        "reference_integrity_passed": reference_ok,
        "reference_result_count_exact": reference_count == 4,
        "direct_reference_imports_absent": not direct_violations,
        "npm_pack_passed": pack_ok,
        "npm_pack_single_package": len(pack_payload) == 1,
        "npm_pack_entry_count_exact": pack_entry_count == 23,
    }
    payload = {
        "schema_version": "okcanvas-step083-non-python-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "node_test_count": node_tests,
        "node_passed_count": node_passed,
        "reference_result_count": reference_count,
        "direct_reference_import_violations": direct_violations,
        "npm_pack_entry_count": pack_entry_count,
        "npm_pack_payload": pack_payload,
        "outputs": {"node": node_output, "reference": reference_output, "npm_pack": pack_output},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    result = validate(args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
