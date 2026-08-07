from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
if str(ROOT_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(ROOT_BOOTSTRAP))

from scripts.validate_windows_subprocess_portability import ROOT, validate as validate_base

STEP = "STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION"
VERSION = "2.64.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP084_WINDOWS_SUBPROCESS_PORTABILITY_VALIDATION.json"


def validate(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    base = validate_base(ROOT)
    acceptance = (ROOT / "scripts/run_step084_acceptance.py").read_text(encoding="utf-8")
    non_python = (ROOT / "scripts/validate_step084_non_python.py").read_text(encoding="utf-8")
    organization_context = (ROOT / "scripts/validate_step084_organization_context.py").read_text(encoding="utf-8")
    checks = dict(base["checks"])
    checks.update(
        {
            "step084_acceptance_uses_portable_validators": "validate_distribution" in acceptance
            and "validate_execution_plane" in acceptance,
            "step084_non_python_uses_npm_pack_helper": "run_npm_pack(CLI_ROOT)" in non_python
            and 'run_command(["npm", "run", "check"], CLI_ROOT)' in non_python,
            "step084_organization_validator_bootstraps_repository_root": "sys.path.insert(0, str(ROOT))" in organization_context
            and "ROOT = Path(__file__).resolve().parents[1]" in organization_context,
        }
    )
    payload = {
        "schema_version": "okcanvas-step084-windows-subprocess-portability-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "violations": base["violations"],
        "base_validation": base,
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
