from __future__ import annotations

import argparse
import json
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace

ROOT = Path(__file__).resolve().parents[1]
MIGRATED_SCRIPTS = (
    "verify_core_store.py",
    "run_step006_acceptance.py",
    "run_step007_acceptance.py",
    "run_step008_acceptance.py",
    "run_step009_acceptance.py",
    "run_step010_acceptance.py",
    "run_step011_acceptance.py",
    "run_step012_acceptance.py",
    "run_step013_acceptance.py",
    "run_step015_acceptance.py",
    "run_step016_acceptance.py",
)


def run_acceptance(output: Path) -> int:
    with AcceptanceWorkspace(step_id="STEP014", output=output) as outer:
        close_order: list[str] = []
        pass_output = outer.evidence_dir / "pass-summary.json"
        passing = AcceptanceWorkspace(
            step_id="STEP014-PASS",
            output=pass_output,
            base_dir=outer.scratch_dir,
            acceptance_id="passing-fixture",
            cleanup_delay_seconds=0,
        )
        passing.register_closer("first", lambda: close_order.append("first"))
        passing.register_closer("second", lambda: close_order.append("second"))
        pass_root = passing.root
        (passing.database_dir / "acceptance.sqlite3").write_bytes(b"fixture")
        passed = passing.finalize({"schema_version": "step014-pass-fixture-v1", "state": "PASSED"})

        fail_output = outer.evidence_dir / "fail-summary.json"
        failing = AcceptanceWorkspace(
            step_id="STEP014-FAIL",
            output=fail_output,
            base_dir=outer.scratch_dir,
            acceptance_id="failure-fixture",
        )
        fail_root = failing.root
        failed = failing.finalize({"schema_version": "step014-fail-fixture-v1", "state": "FAILED"})

        migrated = {}
        for script_name in MIGRATED_SCRIPTS:
            text = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
            migrated[script_name] = (
                "AcceptanceWorkspace" in text
                and "TemporaryDirectory" not in text
                and "tempfile.mkdtemp" not in text
            )

        pass_evidence = json.loads(pass_output.read_text(encoding="utf-8"))
        fail_evidence = json.loads(fail_output.read_text(encoding="utf-8"))
        checks = {
            "pass_workspace_removed": not pass_root.exists(),
            "pass_compact_evidence_exported": pass_output.is_file(),
            "pass_cleanup_completed": passed["acceptance_workspace"]["cleanup_state"] == "COMPLETED",
            "resources_closed_reverse_order": close_order == ["second", "first"],
            "failure_workspace_preserved": fail_root.is_dir(),
            "failure_exact_path_reported": failed["acceptance_workspace"]["preserved_path"] == str(fail_root),
            "failure_compact_evidence_exported": fail_output.is_file(),
            "failure_evidence_matches": fail_evidence["acceptance_workspace"]["preserved_path"] == str(fail_root),
            "pass_evidence_has_no_preserved_path": pass_evidence["acceptance_workspace"]["preserved_path"] is None,
            "acceptance_state_not_product_runtime": passed["acceptance_workspace"]["product_runtime_state"] is False,
            "deterministic_acceptance_scripts_migrated": all(migrated.values()),
            "legacy_live_acceptance_not_reclassified": all(
                "AcceptanceWorkspace" not in (ROOT / "scripts" / name).read_text(encoding="utf-8")
                for name in (
                    "run_step002_live_acceptance.py",
                    "run_step003_live_acceptance.py",
                    "run_step004_live_acceptance.py",
                )
            ),
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step014-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "migrated_scripts": migrated,
            "failure_fixture_preserved_path": str(fail_root),
        }
        payload = outer.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP014_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
