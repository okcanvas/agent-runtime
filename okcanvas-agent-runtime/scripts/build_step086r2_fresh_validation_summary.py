from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

STEP = "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
VERSION = "2.66.2"
ARCHIVE_ROOT = "okcanvas-agent-runtime"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, candidate_zip: Path, extracted_root: Path, fresh_python_regression: Path, fresh_acceptance: Path, output: Path) -> dict[str, Any]:
    evidence_root = extracted_root / "docs/evidence"
    evidence = {
        "fresh_python_regression": _load(fresh_python_regression),
        "fresh_acceptance": _load(fresh_acceptance),
        "architecture": _load(evidence_root / "STEP086R2_ARCHITECTURE_VALIDATION.json"),
        "connector": _load(evidence_root / "STEP086R2_CONNECTOR_CONTRACT_VALIDATION.json"),
        "execution_plane": _load(evidence_root / "STEP086R2_EXECUTION_PLANE_VALIDATION.json"),
        "distribution": _load(evidence_root / "STEP086R2_DISTRIBUTION_VALIDATION.json"),
        "acceptance": _load(evidence_root / "STEP086R2_ACCEPTANCE.json"),
        "portability": _load(evidence_root / "STEP086R2_WINDOWS_SUBPROCESS_PORTABILITY_VALIDATION.json"),
        "non_python": _load(evidence_root / "STEP086R2_NON_PYTHON_VALIDATION.json"),
        "installation": _load(evidence_root / "STEP086R2_INSTALLATION_VALIDATION.json"),
        "python_regression": _load(evidence_root / "STEP086R2_PYTHON_REGRESSION.json"),
        "compliance": _load(evidence_root / "STEP086R2_COMPLIANCE_VALIDATION.json"),
    }
    with zipfile.ZipFile(candidate_zip) as archive:
        names = archive.namelist()
        roots = sorted({name.split("/", 1)[0] for name in names if name})
        forbidden = sorted(
            name
            for name in names
            if "__pycache__/" in name
            or name.endswith((".pyc", ".pyo"))
            or "/.pytest_cache/" in name
            or Path(name).name.startswith("--")
            or "/docs/evidence/step086r2-local/" in name
        )
        missing_or_mismatched: list[str] = []
        for name in names:
            if name.endswith("/"):
                continue
            relative = Path(name).relative_to(ARCHIVE_ROOT)
            extracted = extracted_root / relative
            if not extracted.is_file() or hashlib.sha256(archive.read(name)).hexdigest() != _sha256(extracted):
                missing_or_mismatched.append(name)
    handoff_text = (extracted_root / "HANDOFF.md").read_text(encoding="utf-8")
    retained_handoff_identities = (
        "document-review-v1",
        "local_text_fingerprint",
        "local_text_metrics",
        "project_readonly_inspect",
        "sandbox_project_readonly_inspect",
        "reference-catalog",
        "GroupwareReadResult",
        "external-connector-service",
        "groupware-action-agent",
    )
    checks = {
        "candidate_exists": candidate_zip.is_file(),
        "handoff_retained_product_identities_exact": all(
            identity in handoff_text for identity in retained_handoff_identities
        ),
        "single_archive_root_exact": roots == [ARCHIVE_ROOT],
        "forbidden_entries_absent": not forbidden,
        "extracted_root_exact": extracted_root.name == ARCHIVE_ROOT and extracted_root.is_dir(),
        "extracted_payload_exact": not missing_or_mismatched,
        "architecture_passed": evidence["architecture"].get("state") == "PASSED"
        and evidence["architecture"].get("passed_checks") == evidence["architecture"].get("total_checks") == 40,
        "connector_contract_passed": evidence["connector"].get("state") == "PASSED"
        and evidence["connector"].get("passed_checks") == evidence["connector"].get("total_checks") == 11,
        "execution_plane_passed": evidence["execution_plane"].get("state") == "PASSED"
        and evidence["execution_plane"].get("passed_checks") == evidence["execution_plane"].get("total_checks") == 13,
        "distribution_passed": evidence["distribution"].get("state") == "PASSED"
        and evidence["distribution"].get("passed_checks") == evidence["distribution"].get("total_checks") == 14,
        "acceptance_passed": evidence["acceptance"].get("state") == "PASSED"
        and evidence["acceptance"].get("passed_checks") == evidence["acceptance"].get("total_checks") == 15,
        "portability_passed": evidence["portability"].get("state") == "PASSED"
        and evidence["portability"].get("passed_checks") == evidence["portability"].get("total_checks") == 10,
        "non_python_passed": evidence["non_python"].get("state") == "PASSED"
        and evidence["non_python"].get("node_passed_count") == evidence["non_python"].get("node_test_count") == 14
        and evidence["non_python"].get("reference_result_count") == 4
        and evidence["non_python"].get("npm_pack_entry_count") == 23,
        "installation_passed": evidence["installation"].get("state") == "PASSED"
        and evidence["installation"].get("passed_checks") == evidence["installation"].get("total_checks") == 16
        and evidence["installation"].get("wheel_payload_file_count") == 351,
        "python_regression_passed": evidence["python_regression"].get("state") == "PASSED"
        and evidence["python_regression"].get("passed_tests") == evidence["python_regression"].get("total_tests") == 979
        and evidence["python_regression"].get("failed_tests") == 0
        and evidence["python_regression"].get("error_tests") == 0
        and evidence["python_regression"].get("skipped_tests") == 0,
        "compliance_passed": evidence["compliance"].get("state") == "PASSED"
        and evidence["compliance"].get("passed_checks") == evidence["compliance"].get("total_checks") == 16
        and not evidence["compliance"].get("unregistered_changed_files")
        and not evidence["compliance"].get("stale_declared_changed_files"),
        "fresh_python_regression_passed": evidence["fresh_python_regression"].get("state") == "PASSED"
        and evidence["fresh_python_regression"].get("passed_tests") == evidence["fresh_python_regression"].get("total_tests") == 979
        and evidence["fresh_python_regression"].get("failed_tests") == 0
        and evidence["fresh_python_regression"].get("error_tests") == 0
        and evidence["fresh_python_regression"].get("skipped_tests") == 0,
        "fresh_acceptance_passed": evidence["fresh_acceptance"].get("state") == "PASSED"
        and evidence["fresh_acceptance"].get("passed_checks") == evidence["fresh_acceptance"].get("total_checks") == 15,
    }
    payload = {
        "schema_version": "okcanvas-step086r2-final-fresh-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "candidate": {
            "filename": candidate_zip.name,
            "sha256": _sha256(candidate_zip),
            "entry_count": len(names),
            "archive_roots": roots,
            "forbidden_entries": forbidden,
        },
        "extracted_payload_mismatches": missing_or_mismatched,
        "evidence": evidence,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--extracted-root", type=Path, required=True)
    parser.add_argument("--fresh-python-regression", type=Path, required=True)
    parser.add_argument("--fresh-acceptance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(
        candidate_zip=args.candidate_zip.resolve(),
        extracted_root=args.extracted_root.resolve(),
        fresh_python_regression=args.fresh_python_regression.resolve(),
        fresh_acceptance=args.fresh_acceptance.resolve(),
        output=args.output.resolve(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
