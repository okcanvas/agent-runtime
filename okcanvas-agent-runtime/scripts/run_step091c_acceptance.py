from __future__ import annotations

import argparse
import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.adapters.persistence.postgresql import (
    PostgreSQLConnectionSettings,
    PostgreSQLProductStore,
    PostgreSQLRunSubmissionStore,
    PostgreSQLServiceResourceOwnershipStore,
)
from okcanvas_agent_runtime.application.ports import GovernedRunAdmissionPort, RunSubmissionStorePort
from okcanvas_agent_runtime.application.artifacts import ArtifactBlobStorePort, ArtifactService
from okcanvas_agent_runtime.adapters.storage.artifacts import (
    LocalFilesystemArtifactBlobStore, ObjectStorageArtifactBlobStore, ObjectStorageArtifactSettings
)
from okcanvas_agent_runtime.bootstrap.storage_topology import StorageTopology
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY"
VERSION = "2.73.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091C_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP091B2_DETERMINISTIC_ACCEPTANCE.json"
EXPECTED_PACKAGE_NAME = "okcanvas-agent-runtime-step091c-artifact-blob-store-and-object-storage-boundary.zip"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _method_surface(cls: type) -> set[str]:
    return {name for name, member in inspect.getmembers(cls, inspect.isfunction) if not name.startswith("_")}


def _postgresql_topology_contract() -> dict[str, object]:
    settings = PostgreSQLConnectionSettings("postgresql://runtime:secret@db.example/okcanvas")
    product = PostgreSQLProductStore(settings, connect_factory=lambda _: None)
    submission = PostgreSQLRunSubmissionStore(settings, connect_factory=lambda _: None)
    ownership = PostgreSQLServiceResourceOwnershipStore(settings, connect_factory=lambda _: None)
    placeholder = object()
    topology = StorageTopology(
        schema_version="okcanvas-storage-topology-v1",
        backend_id="postgresql-hybrid-v1",
        transaction_owner_id="postgresql-product-submission-governed-admission-v1",
        product_store=product,
        submission_store=submission,
        governed_admission=submission,
        tool_approval_store=placeholder,
        ownership_store=ownership,
        evaluation_store=placeholder,
        session_runtime=placeholder,
        artifact_blob_store=LocalFilesystemArtifactBlobStore(ROOT / ".local/acceptance-artifacts"),
    ).validate()
    return {
        "backend_id": topology.backend_id,
        "transaction_owner_id": topology.transaction_owner_id,
        "submission_and_admission_same_object": topology.submission_store is topology.governed_admission,
        "dsn_sha256": settings.dsn_sha256,
        "dsn_redacted": "secret" not in repr(settings) and "db.example" not in repr(settings),
    }


def run(output: Path, *, emit_stdout: bool = True, focused_evidence: Path | None = None) -> int:
    started = _now()
    info = RuntimeInfo()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    topology = _postgresql_topology_contract()

    print("[STEP091C] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP091C] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP091C] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP091C] architecture", file=sys.stderr, flush=True)
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    print("[STEP091C] focused-regression", file=sys.stderr, flush=True)
    if focused_evidence is None:
        focused_ok, focused_output = run_command(
            [
                sys.executable, "-m", "pytest", "-q",
                "tests/test_step091c_artifact_blob_store_boundary.py",
                "tests/test_step091b2_postgresql_product_and_submission_atomic_store.py",
                "tests/test_generic_agent_execution_service.py",
                "tests/test_recorded_run_evaluation_service.py",
                "tests/test_evaluation_suite_service.py",
                "tests/test_interactive_runner.py",
                "tests/test_step091b1_typed_persistence_ports_and_transaction_ownership.py",
                "tests/test_sqlite_product_store.py",
                "tests/test_run_submission_boundary.py",
                "tests/test_governed_run_submission_concurrency.py",
                "tests/test_governed_recovery_and_retention.py",
                "tests/test_run_execution_metadata.py",
                "tests/test_agent_invocation_scope.py",
                "tests/test_step082b_coding_execution_plane_and_distribution_boundary.py",
                "tests/test_step081_root_package_and_architecture_restructuring.py",
                "tests/test_baseline_version.py",
                "tests/test_runtime_info.py",
            ],
            ROOT,
        )
    else:
        supplied = json.loads(focused_evidence.read_text(encoding="utf-8"))
        focused_ok = supplied.get("state") == "PASSED" and supplied.get("exit_code") == 0
        focused_output = str(supplied.get("output", ""))
    print("[STEP091C] compileall", file=sys.stderr, flush=True)
    compile_ok, compile_output = run_command(
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
        ],
        ROOT,
    )

    driver_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/driver.py").read_text(encoding="utf-8")
    product_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/product_store.py").read_text(encoding="utf-8")
    submission_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/run_submission.py").read_text(encoding="utf-8")
    sqlite_submission_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/run_submission.py").read_text(encoding="utf-8")
    topology_source = (ROOT / "okcanvas_agent_runtime/bootstrap/storage_topology.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "okcanvas_agent_runtime/bootstrap/application.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    blob_port_source = (ROOT / "okcanvas_agent_runtime/application/artifacts/ports.py").read_text(encoding="utf-8")
    artifact_service_source = (ROOT / "okcanvas_agent_runtime/application/artifacts/service.py").read_text(encoding="utf-8")
    local_blob_source = (ROOT / "okcanvas_agent_runtime/adapters/storage/artifacts/local_filesystem.py").read_text(encoding="utf-8")
    object_blob_source = (ROOT / "okcanvas_agent_runtime/adapters/storage/artifacts/object_storage.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "okcanvas_agent_runtime/application/execution/service.py").read_text(encoding="utf-8")
    service_use_case_source = (ROOT / "okcanvas_agent_runtime/application/service/use_cases.py").read_text(encoding="utf-8")
    admin_use_case_source = (ROOT / "okcanvas_agent_runtime/application/admin/use_cases.py").read_text(encoding="utf-8")
    evaluation_source = (ROOT / "okcanvas_agent_runtime/application/evaluation/application.py").read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "step091b2_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == parent.get("total_checks") == 25,
        "postgresql_boundary_retained": topology["backend_id"] == "postgresql-hybrid-v1" and topology["transaction_owner_id"] == "postgresql-product-submission-governed-admission-v1",
        "artifact_blob_port_typed": "class ArtifactBlobStorePort(Protocol)" in blob_port_source and all(token in blob_port_source for token in ("def put(", "def read(", "def verify(", "def delete(", "def exists(")),
        "artifact_service_coordinates_blob_and_metadata": all(token in artifact_service_source for token in ("self._blobs.put", "self._products.register_artifact", "self._blobs.delete", "self._blobs.read")),
        "local_blob_reference_opaque": "local-artifact-v1://" in local_blob_source and "storage-reference-escape" in local_blob_source,
        "object_storage_reference_opaque": "object-artifact-v1" in object_blob_source and "storage-reference-scope-mismatch" in object_blob_source,
        "object_storage_sdk_neutral": "class ObjectStorageClient(Protocol)" in object_blob_source and "boto3" not in object_blob_source and "azure" not in object_blob_source,
        "product_store_metadata_only": "storage_ref: str" in (ROOT / "okcanvas_agent_runtime/domain/runs/ports.py").read_text(encoding="utf-8") and "path: Path" not in (ROOT / "okcanvas_agent_runtime/domain/runs/ports.py").read_text(encoding="utf-8"),
        "sqlite_product_store_no_blob_io": "resolved = path.expanduser" not in (ROOT / "okcanvas_agent_runtime/adapters/persistence/product/sqlite_store.py").read_text(encoding="utf-8") and "_file_integrity(path)" not in (ROOT / "okcanvas_agent_runtime/adapters/persistence/product/sqlite_store.py").read_text(encoding="utf-8"),
        "execution_uses_artifact_service": "self._artifact_service.create_json" in execution_source and "_write_json_atomic(" not in execution_source[execution_source.find("class GenericAgentExecutionService"):],
        "service_read_uses_artifact_service": "self._artifact_service.read_json" in service_use_case_source,
        "admin_read_uses_artifact_service": "self._artifact_service.read_json" in admin_use_case_source,
        "evaluation_uses_artifact_service": "self._artifact_service.read_bytes" in evaluation_source and "Path(artifact.storage_path)" not in evaluation_source,
        "topology_owns_blob_store": "artifact_blob_store: ArtifactBlobStorePort" in topology_source and "artifact_blob_store=artifact_blob_store" in topology_source,
        "bootstrap_blob_backend_explicit": all(token in bootstrap_source for token in ("local-filesystem-artifact-v1", "object-storage-artifact-v1", "OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND")),
        "local_artifact_default_retained": 'artifact_blob_store_backend: str = "local-filesystem-artifact-v1"' in bootstrap_source,
        "postgresql_optional_dependency_retained": 'postgresql = ["psycopg[binary]>=3.2,<4"]' in pyproject,
        "session_evaluation_approval_storage_retained": all(token in topology_source for token in ("SQLiteToolApprovalStore", "SQLiteEvaluationStore", "SQLiteSessionRuntimeService")),
        "step082b_execution_plane_retained": execution.get("state") == "PASSED" and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED" and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0 and architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED" and registry.get("current_step") == STEP and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP and DEFAULT_OUTPUT.name == EXPECTED_PACKAGE_NAME,
    }
    payload = {
        "schema_version": "okcanvas-step091c-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY_GATE",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091b2_parent": parent,
        "postgresql_topology_contract": topology,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "postgresql_adapter_implemented": True,
            "postgresql_live_server_executed": False,
            "artifact_blob_store_implemented": True,
            "object_storage_adapter_implemented": True,
            "object_storage_live_server_executed": False,
            "postgresql_session_implemented": False,
            "postgresql_evaluation_implemented": False,
            "distributed_worker_lease_implemented": False,
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
    parser.add_argument("--focused-evidence", type=Path)
    args = parser.parse_args(argv)
    return run(
        args.output.resolve(),
        emit_stdout=not args.quiet,
        focused_evidence=(args.focused_evidence.resolve() if args.focused_evidence else None),
    )


if __name__ == "__main__":
    raise SystemExit(main())
