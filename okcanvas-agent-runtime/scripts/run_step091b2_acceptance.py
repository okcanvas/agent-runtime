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
from okcanvas_agent_runtime.bootstrap.storage_topology import StorageTopology
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE"
VERSION = "2.72.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091B2_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP091B1_DETERMINISTIC_ACCEPTANCE.json"
EXPECTED_PACKAGE_NAME = "okcanvas-agent-runtime-step091b2-postgresql-product-and-submission-atomic-store.zip"


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
    ).validate()
    return {
        "backend_id": topology.backend_id,
        "transaction_owner_id": topology.transaction_owner_id,
        "submission_and_admission_same_object": topology.submission_store is topology.governed_admission,
        "dsn_sha256": settings.dsn_sha256,
        "dsn_redacted": "secret" not in repr(settings) and "db.example" not in repr(settings),
    }


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started = _now()
    info = RuntimeInfo()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    topology = _postgresql_topology_contract()

    print("[STEP091B2] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP091B2] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP091B2] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP091B2] architecture", file=sys.stderr, flush=True)
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    print("[STEP091B2] focused-regression", file=sys.stderr, flush=True)
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step091b2_postgresql_product_and_submission_atomic_store.py",
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
    print("[STEP091B2] compileall", file=sys.stderr, flush=True)
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

    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "step091b1_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == parent.get("total_checks") == 25,
        "postgresql_optional_dependency_declared": 'postgresql = ["psycopg[binary]>=3.2,<4"]' in pyproject,
        "postgresql_driver_loaded_lazily": "import psycopg" in driver_source and not driver_source.lstrip().startswith("import psycopg"),
        "postgresql_dsn_redacted": topology["dsn_redacted"] is True and len(str(topology["dsn_sha256"])) == 64,
        "postgresql_product_surface_complete": _method_surface(PostgreSQLProductStore) >= _method_surface(__import__("okcanvas_agent_runtime.adapters.persistence.product.sqlite_store", fromlist=["SQLiteProductStore"]).SQLiteProductStore),
        "postgresql_submission_ports_conform": isinstance(PostgreSQLRunSubmissionStore(PostgreSQLConnectionSettings("postgresql://runtime:secret@db.example/okcanvas"), connect_factory=lambda _: None), RunSubmissionStorePort) and isinstance(PostgreSQLRunSubmissionStore(PostgreSQLConnectionSettings("postgresql://runtime:secret@db.example/okcanvas"), connect_factory=lambda _: None), GovernedRunAdmissionPort),
        "postgresql_topology_identity_exact": topology["backend_id"] == "postgresql-hybrid-v1" and topology["transaction_owner_id"] == "postgresql-product-submission-governed-admission-v1",
        "postgresql_submission_and_admission_same_owner": topology["submission_and_admission_same_object"] is True,
        "governed_admission_atomic_sql_retained": all(
            token in sqlite_submission_source
            for token in ("INSERT INTO task", "INSERT INTO run", "INSERT INTO run_event", "UPDATE run_submission_preflight")
        ) and "class PostgreSQLRunSubmissionStore(SQLiteRunSubmissionStore)" in submission_source,
        "submission_row_lock_present": "FOR UPDATE" in submission_source,
        "idempotency_advisory_lock_present": "pg_advisory_xact_lock" in driver_source,
        "run_event_owner_lock_present": "SELECT run_id FROM run WHERE run_id = ? FOR UPDATE" in product_source and "SELECT run_id FROM run WHERE run_id = ? FOR UPDATE" in submission_source,
        "postgresql_same_dsn_validation_present": "must share one DSN" in topology_source,
        "bootstrap_postgresql_opt_in_present": "postgresql-hybrid-v1" in bootstrap_source and "OKCANVAS_POSTGRESQL_DSN" in bootstrap_source and "OKCANVAS_PRODUCT_STORE_BACKEND" in bootstrap_source,
        "sqlite_default_retained": 'product_store_backend: str = "sqlite-local-v1"' in bootstrap_source,
        "artifact_blob_storage_deferred": "ArtifactBlobStorePort" not in topology_source,
        "session_evaluation_approval_remain_local": all(token in topology_source for token in ("SQLiteToolApprovalStore", "SQLiteEvaluationStore", "SQLiteSessionRuntimeService")),
        "step082b_execution_plane_retained": execution.get("state") == "PASSED" and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED" and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0 and architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED" and registry.get("current_step") == STEP and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP and DEFAULT_OUTPUT.name == EXPECTED_PACKAGE_NAME,
    }
    payload = {
        "schema_version": "okcanvas-step091b2-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_POSTGRESQL_PRODUCT_SUBMISSION_ATOMIC_STORE_GATE",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091b1_parent": parent,
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
            "artifact_blob_store_implemented": False,
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
    args = parser.parse_args(argv)
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
