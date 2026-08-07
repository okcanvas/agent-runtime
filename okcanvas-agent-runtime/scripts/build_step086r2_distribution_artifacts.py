from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

STEP = "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
VERSION = "2.66.2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inspect(path: Path, expected_root: str) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    roots = sorted({name.split("/", 1)[0] for name in names if name})
    forbidden = sorted(
        name for name in names
        if "__pycache__/" in name
        or name.endswith((".pyc", ".pyo"))
        or Path(name).name.startswith("--")
    )
    return {
        "filename": path.name,
        "sha256": _sha256(path),
        "entry_count": len(names),
        "roots": roots,
        "expected_root": expected_root,
        "forbidden_entries": forbidden,
    }


def _sidecar_exact(path: Path, digest: str) -> bool:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    return sidecar.is_file() and sidecar.read_text(encoding="utf-8") == f"{digest}  {path.name}\n"


def build(*, runtime: Path, configuration: Path, reference: Path, output: Path) -> dict[str, Any]:
    runtime_info = _inspect(runtime, "okcanvas-agent-runtime")
    config_info = _inspect(configuration, "okcanvas-agent-runtime-config")
    reference_info = _inspect(reference, "okcanvas-agent-runtime-reference")
    checks = {
        "runtime_exists": runtime.is_file(),
        "runtime_root_exact": runtime_info["roots"] == [runtime_info["expected_root"]],
        "runtime_forbidden_absent": not runtime_info["forbidden_entries"],
        "runtime_sidecar_exact": _sidecar_exact(runtime, runtime_info["sha256"]),
        "configuration_exists": configuration.is_file(),
        "configuration_root_exact": config_info["roots"] == [config_info["expected_root"]],
        "configuration_forbidden_absent": not config_info["forbidden_entries"],
        "configuration_sidecar_exact": _sidecar_exact(configuration, config_info["sha256"]),
        "reference_exists": reference.is_file(),
        "reference_root_exact": reference_info["roots"] == [reference_info["expected_root"]],
        "reference_forbidden_absent": not reference_info["forbidden_entries"],
        "reference_sidecar_exact": _sidecar_exact(reference, reference_info["sha256"]),
        "configuration_has_groupware_deployment_boundary": _zip_has(configuration, "okcanvas-agent-runtime-config/specs/groupware/deployment-boundary.json"),
        "configuration_has_groupware_provider_contract": _zip_has(configuration, "okcanvas-agent-runtime-config/specs/groupware/read-provider-contract.json"),
        "configuration_has_roles_header_contract": _zip_text_contains(configuration, "okcanvas-agent-runtime-config/specs/groupware/read-provider-contract.json", "X-OKCanvas-Roles"),
        "runtime_has_handoff": _zip_has(runtime, "okcanvas-agent-runtime/HANDOFF.md"),
        "runtime_has_windows_launcher": _zip_has(runtime, "okcanvas-agent-runtime/sh_run_step086r2_acceptance.cmd"),
        "runtime_has_strict_groupware_output_schema": _zip_has(runtime, "okcanvas-agent-runtime/specs/agents/groupware-read-agent/output.schema.json"),
        "runtime_filename_matches_current_sot": runtime.name == "okcanvas-agent-runtime-step086r2-delegated-role-header-and-external-connector-contract-closure.zip",
    }
    payload = {
        "schema_version": "okcanvas-step086r2-final-distribution-artifacts-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "runtime": runtime_info,
        "configuration": config_info,
        "reference": reference_info,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _zip_has(path: Path, name: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return name in archive.namelist()


def _zip_text_contains(path: Path, name: str, token: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return name in archive.namelist() and token in archive.read(name).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(
        runtime=args.runtime.resolve(),
        configuration=args.configuration.resolve(),
        reference=args.reference.resolve(),
        output=args.output.resolve(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
