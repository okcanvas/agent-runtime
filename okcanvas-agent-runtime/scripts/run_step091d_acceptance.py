from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step081_architecture import validate as validate_architecture

STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
VERSION = "2.75.0"
PARENT_PATH = ROOT / "docs/evidence/STEP091B3R1_DETERMINISTIC_ACCEPTANCE.json"
POSTGRESQL_LIVE_PATH = ROOT / "docs/evidence/windows/STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE.json"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091D_DETERMINISTIC_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run(command: list[str]) -> tuple[bool, str]:
    process = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return process.returncode == 0, process.stdout


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started_at = _now()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    postgresql_live = json.loads(POSTGRESQL_LIVE_PATH.read_text(encoding="utf-8"))
    registry = validate_registry()
    architecture = validate_architecture()
    focused_ok, focused_output = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step091d_object_storage_deployment_composition_and_live_gate.py",
            "tests/test_step091c_artifact_blob_store_boundary.py",
            "tests/test_step091b3r1_real_postgresql_live_acceptance_gate.py",
            "tests/test_step091b3_postgresql_approval_evaluation_and_session_metadata.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
            "tests/test_packaging_policy.py",
            "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
        ]
    )
    compile_ok, compile_output = _run(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "okcanvas_agent_runtime",
            "okcanvas_agent_protocols",
            "okcanvas_agent_clients",
            "scripts",
            "tests",
        ]
    )

    client_source = (ROOT / "okcanvas_agent_runtime/adapters/storage/artifacts/s3_compatible.py").read_text(encoding="utf-8")
    generic_source = (ROOT / "okcanvas_agent_runtime/adapters/storage/artifacts/object_storage.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "okcanvas_agent_runtime/bootstrap/application.py").read_text(encoding="utf-8")
    live_source = (ROOT / "scripts/run_step091d_object_storage_live_acceptance.py").read_text(encoding="utf-8")
    live_launcher = (ROOT / "sh_run_step091d_object_storage_live_acceptance.cmd").read_text(encoding="utf-8")
    audit_source = (ROOT / "docs/audits/STEP091D_NEXT_BOUNDARY_READ_ONLY_AUDIT.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION,
        "step091b3r1_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == parent.get("total_checks") == 21,
        "real_postgresql_parent_live_retained": postgresql_live.get("state") == "PASSED" and postgresql_live.get("passed_checks") == postgresql_live.get("total_checks") == 19,
        "read_only_audit_selected_smaller_boundary": "Object Storage deployment composition + explicit real-server Live acceptance gate" in audit_source,
        "sdk_neutral_blob_adapter_retained": "class ObjectStorageClient(Protocol)" in generic_source and "boto3" not in generic_source,
        "s3_compatible_deployment_client_present": all(token in client_source for token in ("class Boto3S3CompatibleObjectStorageClient", "boto3.client", "signature_version=\"s3v4\"", "addressing_style")),
        "credentials_remain_sdk_chain_owned": "access_key" not in client_source.lower() and "secret_key" not in client_source.lower(),
        "environment_composition_injects_object_client": "_object_storage_client_from_environment(os.environ)" in bootstrap_source and "OKCANVAS_ARTIFACT_OBJECT_ENDPOINT_URL" in bootstrap_source and "OKCANVAS_ARTIFACT_OBJECT_ADDRESSING_STYLE" in bootstrap_source,
        "local_artifact_default_retained": 'artifact_blob_store_backend: str = "local-filesystem-artifact-v1"' in bootstrap_source,
        "object_storage_optional_dependency_declared": 'object-storage = ["boto3>=1.35,<2"]' in pyproject,
        "real_object_storage_live_harness_present": all(token in live_source for token in ("REAL_S3_COMPATIBLE_OBJECT_STORAGE_ISOLATED_PREFIX_LIVE_GATE", "CREATE_AND_DELETE_ISOLATED_TEST_PREFIX", "metadata_failure_compensates_object_live", "tracked_refs.append(compensation_ref)", "isolated_prefix_known_objects_cleanup_succeeded")),
        "live_bucket_not_created_or_deleted": '"bucket_creation_or_deletion_executed": False' in live_source,
        "live_evidence_secret_safe": all(token in live_source for token in ("bucket_sha256", "endpoint_url_sha256", '"credentials_persisted": False', '"secret_values_not_persisted"')),
        "windows_live_launcher_present": "run_step091d_object_storage_live_acceptance.py" in live_launcher and "python_bytecode_isolation.py" in live_launcher,
        "launcher_registry_current_exact": registry.get("state") == "PASSED" and registry.get("current_step") == STEP and registry.get("current_step_token") == "091D" and registry.get("current_record_count") == 4,
        "architecture_regression_passed": architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP and DEFAULT_OUTPUT.name == "okcanvas-agent-runtime-step091d-object-storage-deployment-composition-and-live-acceptance-gate.zip",
    }
    payload = {
        "schema_version": "okcanvas-step091d-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_GATE_READINESS",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091b3r1_parent": parent,
        "postgresql_live_parent": postgresql_live,
        "launcher_registry": registry,
        "architecture_validation": architecture,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "real_object_storage_server_executed": False,
            "real_object_storage_live_gate_implemented": True,
            "artifact_orphan_inventory_gc_implemented": False,
            "api_worker_physical_split_implemented": False,
            "distributed_worker_lease_implemented": False,
            "distributed_session_history_implemented": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if emit_stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
