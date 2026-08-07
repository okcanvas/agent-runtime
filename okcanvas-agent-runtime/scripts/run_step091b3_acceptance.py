from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.adapters.persistence.postgresql import (
    PostgreSQLConnectionSettings,
    PostgreSQLEvaluationStore,
    PostgreSQLProductStore,
    PostgreSQLRunSubmissionStore,
    PostgreSQLServiceResourceOwnershipStore,
    PostgreSQLSessionMetadataRuntimeService,
    PostgreSQLToolApprovalStore,
)
from okcanvas_agent_runtime.adapters.storage.artifacts import LocalFilesystemArtifactBlobStore
from okcanvas_agent_runtime.adapters.storage.session_history import SessionHistoryKey
from okcanvas_agent_runtime.bootstrap.storage_topology import StorageTopology
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionPolicyCatalog
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP091B3_POSTGRESQL_APPROVAL_EVALUATION_AND_SESSION_METADATA"
VERSION = "2.74.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091B3_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP091C_DETERMINISTIC_ACCEPTANCE.json"
EXPECTED_PACKAGE_NAME = "okcanvas-agent-runtime-step091b3-postgresql-approval-evaluation-and-session-metadata.zip"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _topology_contract() -> dict[str, object]:
    settings = PostgreSQLConnectionSettings("postgresql://runtime:secret@db.example/okcanvas")
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    key = SessionHistoryKey.from_text(
        base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
    )
    product = PostgreSQLProductStore(settings, connect_factory=lambda _: None)
    submission = PostgreSQLRunSubmissionStore(settings, connect_factory=lambda _: None)
    ownership = PostgreSQLServiceResourceOwnershipStore(settings, connect_factory=lambda _: None)
    approval = PostgreSQLToolApprovalStore(settings, connect_factory=lambda _: None)
    evaluation = PostgreSQLEvaluationStore(settings, connect_factory=lambda _: None)
    session = PostgreSQLSessionMetadataRuntimeService(
        settings,
        ROOT / ".local/acceptance-session-history",
        policy,
        key,
        connect_factory=lambda _: None,
    )
    topology = StorageTopology(
        schema_version="okcanvas-storage-topology-v1",
        backend_id="postgresql-hybrid-v1",
        transaction_owner_id="postgresql-product-submission-governed-admission-v1",
        product_store=product,
        submission_store=submission,
        governed_admission=submission,
        tool_approval_store=approval,
        ownership_store=ownership,
        evaluation_store=evaluation,
        session_runtime=session,
        artifact_blob_store=LocalFilesystemArtifactBlobStore(
            ROOT / ".local/acceptance-artifacts"
        ),
    ).validate()
    stores = (
        topology.product_store,
        topology.submission_store,
        topology.ownership_store,
        topology.tool_approval_store,
        topology.evaluation_store,
        topology.session_runtime,
    )
    return {
        "backend_id": topology.backend_id,
        "transaction_owner_id": topology.transaction_owner_id,
        "dsn_digests": sorted({store.settings.dsn_sha256 for store in stores}),
        "approval_store": type(topology.tool_approval_store).__name__,
        "evaluation_store": type(topology.evaluation_store).__name__,
        "session_runtime": type(topology.session_runtime).__name__,
        "session_metadata_backend_id": session.metadata_backend_id,
        "session_history_backend_id": session.history_backend_id,
        "dsn_redacted": "secret" not in repr(settings) and "db.example" not in repr(settings),
    }


def run(output: Path, *, emit_stdout: bool = True, focused_evidence: Path | None = None) -> int:
    started = _now()
    info = RuntimeInfo()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    topology = _topology_contract()

    print("[STEP091B3] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP091B3] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP091B3] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP091B3] architecture", file=sys.stderr, flush=True)
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    print("[STEP091B3] focused-regression", file=sys.stderr, flush=True)
    if focused_evidence is None:
        focused_ok, focused_output = run_command(
            [
                sys.executable, "-m", "pytest", "-q",
                "tests/test_step091b3_postgresql_approval_evaluation_and_session_metadata.py",
                "tests/test_step091c_artifact_blob_store_boundary.py",
                "tests/test_step091b2_postgresql_product_and_submission_atomic_store.py",
                "tests/test_governed_local_tool_approval.py",
                "tests/test_tool_approval_inbox.py",
                "tests/test_evaluation_service.py",
                "tests/test_evaluation_suite_service.py",
                "tests/test_recorded_run_evaluation_service.py",
                "tests/test_sqlite_session_runtime.py",
                "tests/test_step063_strict_encrypted_sqlite_session_history.py",
                "tests/test_step064_bounded_encrypted_sqlite_session_compaction.py",
                "tests/test_step065_session_history_key_rotation.py",
                "tests/test_step091b1_typed_persistence_ports_and_transaction_ownership.py",
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
    print("[STEP091B3] compileall", file=sys.stderr, flush=True)
    compile_ok, compile_output = run_command(
        [
            sys.executable, "-m", "compileall", "-q",
            "okcanvas_agent_runtime", "okcanvas_agent_protocols",
            "okcanvas_agent_clients", "scripts", "tests",
        ],
        ROOT,
    )

    topology_source = (ROOT / "okcanvas_agent_runtime/bootstrap/storage_topology.py").read_text(encoding="utf-8")
    driver_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/driver.py").read_text(encoding="utf-8")
    approval_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/tool_approval.py").read_text(encoding="utf-8")
    evaluation_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/evaluation_store.py").read_text(encoding="utf-8")
    session_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/session_runtime.py").read_text(encoding="utf-8")
    sqlite_session_source = (ROOT / "okcanvas_agent_runtime/adapters/persistence/sessions/runtime_service.py").read_text(encoding="utf-8")
    artifact_source = (ROOT / "okcanvas_agent_runtime/application/artifacts/service.py").read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "step091c_parent_retained": parent.get("state") == "PASSED" and parent.get("passed_checks") == parent.get("total_checks") == 26,
        "postgresql_metadata_stores_share_one_dsn": topology["dsn_digests"] and len(topology["dsn_digests"]) == 1,
        "postgresql_tool_approval_implemented": topology["approval_store"] == "PostgreSQLToolApprovalStore" and "class PostgreSQLToolApprovalStore" in approval_source,
        "approval_product_transaction_domain_retained": all(token in approval_source for token in ("SQLiteToolApprovalStore", "postgresql_connection")) and "GOVERNED_TOOL_APPROVAL" in driver_source,
        "postgresql_evaluation_implemented": topology["evaluation_store"] == "PostgreSQLEvaluationStore" and "class PostgreSQLEvaluationStore" in evaluation_source,
        "postgresql_session_metadata_implemented": topology["session_runtime"] == "PostgreSQLSessionMetadataRuntimeService" and "class PostgreSQLSessionMetadataRuntimeService" in session_source,
        "session_history_remains_encrypted_local_sqlite": topology["session_history_backend_id"] == "encrypted-local-sqlite-history-v1" and "self.history_db" in sqlite_session_source,
        "session_metadata_row_locking_present": "PRODUCT_SESSION WHERE SESSION_ID" in driver_source,
        "approval_row_locking_present": "GOVERNED_TOOL_APPROVAL WHERE APPROVAL_ID" in driver_source,
        "run_event_sequence_locking_retained": "MAX(SEQUENCE)" in driver_source,
        "postgresql_topology_uses_metadata_stores": all(token in topology_source for token in ("PostgreSQLToolApprovalStore", "PostgreSQLEvaluationStore", "PostgreSQLSessionMetadataRuntimeService")),
        "sqlite_default_topology_retained": all(token in topology_source for token in ("SQLiteToolApprovalStore", "SQLiteEvaluationStore", "SQLiteSessionRuntimeService")),
        "artifact_blob_boundary_retained": "self._blobs.put" in artifact_source and parent.get("checks", {}).get("artifact_blob_port_typed") is True,
        "dsn_redaction_retained": topology["dsn_redacted"] is True,
        "step082b_execution_plane_retained": execution.get("state") == "PASSED" and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED" and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0 and architecture.get("state") == "PASSED" and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED" and registry.get("current_step") == STEP and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP and DEFAULT_OUTPUT.name == EXPECTED_PACKAGE_NAME,
    }
    payload = {
        "schema_version": "okcanvas-step091b3-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_POSTGRESQL_APPROVAL_EVALUATION_AND_SESSION_METADATA_GATE",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091c_parent": parent,
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
            "postgresql_tool_approval_implemented": True,
            "postgresql_evaluation_implemented": True,
            "postgresql_session_metadata_implemented": True,
            "session_history_backend": "encrypted-local-sqlite-history-v1",
            "distributed_session_history_implemented": False,
            "object_storage_live_server_executed": False,
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
