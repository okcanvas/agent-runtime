from __future__ import annotations

import argparse
import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.application.ports import (
    EvaluationStorePort,
    GovernedRunAdmissionPort,
    RunSubmissionStorePort,
    ServiceResourceOwnershipStorePort,
    SessionRuntimePort,
    ToolApprovalStorePort,
)
from okcanvas_agent_runtime.bootstrap.storage_topology import (
    SQLiteStorageTopologySettings,
    build_sqlite_storage_topology,
)
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import (
    SQLiteSessionKeyRotationPolicyCatalog,
    SQLiteSessionPolicyCatalog,
)
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane

STEP = "STEP091B1_TYPED_PERSISTENCE_PORTS_AND_TRANSACTION_OWNERSHIP"
VERSION = "2.71.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091B1_DETERMINISTIC_ACCEPTANCE.json"
PARENT_PATH = ROOT / "docs/evidence/STEP090R1_DETERMINISTIC_ACCEPTANCE.json"
EXPECTED_PACKAGE_NAME = "okcanvas-agent-runtime-step091b1-typed-persistence-ports-and-transaction-ownership.zip"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _protocols_have_exact_signatures() -> bool:
    protocols = (
        RunSubmissionStorePort,
        GovernedRunAdmissionPort,
        ToolApprovalStorePort,
        ServiceResourceOwnershipStorePort,
        EvaluationStorePort,
        SessionRuntimePort,
    )
    for protocol in protocols:
        methods = [
            member
            for name, member in inspect.getmembers(protocol, inspect.isfunction)
            if not name.startswith("_")
        ]
        if not methods:
            return False
        for method in methods:
            kinds = {
                parameter.kind
                for parameter in inspect.signature(method).parameters.values()
            }
            if inspect.Parameter.VAR_POSITIONAL in kinds:
                return False
            if inspect.Parameter.VAR_KEYWORD in kinds:
                return False
    return True


def _topology_summary() -> dict[str, object]:
    with TemporaryDirectory(prefix="step091b1-") as directory:
        root = Path(directory)
        topology = build_sqlite_storage_topology(
            SQLiteStorageTopologySettings(
                product_db=root / "product.sqlite3",
                evaluation_db=root / "evaluation.sqlite3",
                session_root=root / "sessions",
                session_policy=SQLiteSessionPolicyCatalog(ROOT).resolve(),
                session_history_key=None,
                session_history_previous_key=None,
                session_key_rotation_policy=SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve(),
            )
        )
        return {
            "schema_version": topology.schema_version,
            "backend_id": topology.backend_id,
            "transaction_owner_id": topology.transaction_owner_id,
            "submission_and_admission_same_object": topology.submission_store
            is topology.governed_admission,
            "submission_port": isinstance(topology.submission_store, RunSubmissionStorePort),
            "admission_port": isinstance(topology.governed_admission, GovernedRunAdmissionPort),
            "approval_port": isinstance(topology.tool_approval_store, ToolApprovalStorePort),
            "ownership_port": isinstance(
                topology.ownership_store, ServiceResourceOwnershipStorePort
            ),
            "evaluation_port": isinstance(topology.evaluation_store, EvaluationStorePort),
            "session_port": isinstance(topology.session_runtime, SessionRuntimePort),
        }


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started = _now()
    info = RuntimeInfo()
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))
    topology = _topology_summary()

    print("[STEP091B1] execution-plane", file=sys.stderr, flush=True)
    execution = validate_execution_plane()
    print("[STEP091B1] distribution", file=sys.stderr, flush=True)
    distribution = validate_distribution()
    print("[STEP091B1] launcher-registry", file=sys.stderr, flush=True)
    registry = validate_registry()
    print("[STEP091B1] architecture", file=sys.stderr, flush=True)
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    print("[STEP091B1] focused-regression", file=sys.stderr, flush=True)
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step091b1_typed_persistence_ports_and_transaction_ownership.py",
            "tests/test_step078_product_owned_atomic_service_submission_ownership_transfer.py",
            "tests/test_run_submission_boundary.py",
            "tests/test_governed_run_submission_control_api.py",
            "tests/test_sqlite_product_store.py",
            "tests/test_sqlite_session_runtime.py",
            "tests/test_sqlite_session_approval_composition.py",
            "tests/test_recorded_run_evaluation_service.py",
            "tests/test_evaluation_service.py",
            "tests/test_generic_agent_execution_service.py",
            "tests/test_control_api.py",
            "tests/test_step082b_coding_execution_plane_and_distribution_boundary.py",
            "tests/test_step081_root_package_and_architecture_restructuring.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
        ],
        ROOT,
    )
    print("[STEP091B1] compileall", file=sys.stderr, flush=True)
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

    ports_source = (ROOT / "okcanvas_agent_runtime/application/ports/stores.py").read_text(
        encoding="utf-8"
    )
    execution_source = (
        ROOT / "okcanvas_agent_runtime/application/submissions/execution.py"
    ).read_text(encoding="utf-8")
    approval_source = (
        ROOT / "okcanvas_agent_runtime/application/approvals/service.py"
    ).read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "okcanvas_agent_runtime/bootstrap/application.py").read_text(
        encoding="utf-8"
    )
    topology_source = (
        ROOT / "okcanvas_agent_runtime/bootstrap/storage_topology.py"
    ).read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP
        and PROJECT_VERSION == info.version == VERSION,
        "step090r1_parent_retained": parent.get("state") == "PASSED"
        and parent.get("passed_checks") == parent.get("total_checks") == 25,
        "typed_ports_have_no_broad_variadic_signatures": _protocols_have_exact_signatures()
        and "*args: Any" not in ports_source
        and "**kwargs: Any" not in ports_source,
        "governed_admission_port_separated": "class GovernedRunAdmissionPort" in ports_source
        and "create_governed_task_run" not in RunSubmissionStorePort.__dict__
        and "create_governed_task_run" in GovernedRunAdmissionPort.__dict__,
        "submission_and_admission_same_transaction_owner": topology[
            "submission_and_admission_same_object"
        ]
        is True,
        "sqlite_topology_identity_exact": topology["schema_version"]
        == "okcanvas-storage-topology-v1"
        and topology["backend_id"] == "sqlite-local-v1"
        and topology["transaction_owner_id"]
        == "sqlite-run-submission-governed-admission-v1",
        "submission_port_runtime_conformance": topology["submission_port"] is True,
        "admission_port_runtime_conformance": topology["admission_port"] is True,
        "approval_port_runtime_conformance": topology["approval_port"] is True,
        "ownership_port_runtime_conformance": topology["ownership_port"] is True,
        "evaluation_port_runtime_conformance": topology["evaluation_port"] is True,
        "session_port_runtime_conformance": topology["session_port"] is True,
        "read_execution_uses_admission_dependency": "self._admission.create_governed_task_run"
        in execution_source,
        "approval_execution_uses_admission_dependency": "self._admission.create_governed_task_run"
        in approval_source,
        "bootstrap_uses_validated_topology_factory": "build_sqlite_storage_topology" in bootstrap_source
        and "app.state.storage_topology = topology" in bootstrap_source
        and "submission_store is not self.governed_admission" in topology_source,
        "sqlite_is_only_admitted_backend": "Only the retained SQLite local topology is admitted"
        in topology_source,
        "postgresql_not_implemented_yet": "PostgreSQL" not in topology_source,
        "artifact_semantics_unchanged": "ArtifactBlobStorePort" not in ports_source,
        "step082b_execution_plane_retained": execution.get("state") == "PASSED"
        and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED"
        and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0
        and architecture.get("state") == "PASSED"
        and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED"
        and registry.get("current_step") == STEP
        and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP
        and DEFAULT_OUTPUT.name == EXPECTED_PACKAGE_NAME,
    }
    payload = {
        "schema_version": "okcanvas-step091b1-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_TYPED_PERSISTENCE_PORT_AND_TRANSACTION_OWNERSHIP_GATE",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step090r1_parent": parent,
        "storage_topology": topology,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "postgresql_implemented": False,
            "artifact_blob_store_implemented": False,
            "distributed_worker_lease_implemented": False,
            "product_runtime_behavior_intentionally_changed": False,
            "windows_step091b1_executed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if emit_stdout:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
