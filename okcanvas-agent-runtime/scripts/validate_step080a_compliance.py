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

DEFAULT_RECORD = ROOT / "docs/evidence/STEP080A_CONSTITUTION_COMPLIANCE.json"
STEP = "STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES"
VERSION = "2.60.1"
MINIMUM_SUCCESSOR_VERSION = (2, 61, 0)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("STEP compliance record must be a JSON object")
    return payload


def validate(path: Path = DEFAULT_RECORD) -> dict[str, Any]:
    payload = _load(path)
    summary = validate_step_compliance_record(payload)
    relocation_path = ROOT / "specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json"
    relocation = _load(relocation_path) if relocation_path.is_file() else {}
    historical_changed = tuple(str(item) for item in payload.get("changed_files", ()))
    removed_source = [item for item in historical_changed if item.startswith("src/okcanvas_agent_runtime/")]
    relocated_legacy = {
        str(item.get("legacy_path"))
        for item in relocation.get("python_relocations", []) + relocation.get("resource_relocations", [])
    }
    checks = {
        "historical_identity_exact": summary.step == STEP and summary.version == VERSION,
        "historical_gate_record_complete": summary.gate_result_count == 32,
        "historical_windows_gate_remains_pending": summary.pending_external_gate_count == 1,
        "current_step_is_explicit_successor": CURRENT_STEP.startswith("STEP")
        and CURRENT_STEP != STEP
        and tuple(int(item) for item in PROJECT_VERSION.split(".")) >= MINIMUM_SUCCESSOR_VERSION,
        "legacy_source_root_removed_by_successor": not ROOT.joinpath("src", "okcanvas_agent_runtime").exists(),
        "historical_removed_source_paths_relocated": bool(removed_source)
        and all(item in relocated_legacy for item in removed_source),
        "successor_relocation_manifest_complete": relocation.get("missing_relocation_count") == 0,
        "historical_record_retained_immutable": path.is_file()
        and payload.get("constitution_sha256")
        == "262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa",
    }
    state = "SUPERSEDED_BY_STEP081" if all(checks.values()) else "FAILED"
    return {
        "schema_version": "okcanvas-step080a-compliance-validation-v2",
        "state": state,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
        "summary": summary.to_public_dict(),
        "record_path": path.relative_to(ROOT).as_posix(),
        "superseding_step": CURRENT_STEP,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "SUPERSEDED_BY_STEP081" else 1


if __name__ == "__main__":
    raise SystemExit(main())
