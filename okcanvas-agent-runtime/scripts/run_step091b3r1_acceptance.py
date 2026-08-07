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

STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"
VERSION = "2.74.1"
PARENT_PATH = ROOT / "docs/evidence/STEP091B3_DETERMINISTIC_ACCEPTANCE.json"
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP091B3R1_DETERMINISTIC_ACCEPTANCE.json"


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
    registry = validate_registry()
    architecture = validate_architecture()

    focused_ok, focused_output = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step091b3r1_real_postgresql_live_acceptance_gate.py",
            "tests/test_step091b3_postgresql_approval_evaluation_and_session_metadata.py",
            "tests/test_step091b2_postgresql_product_and_submission_atomic_store.py",
            "tests/test_step091c_artifact_blob_store_boundary.py",
            "tests/test_step091b1_typed_persistence_ports_and_transaction_ownership.py",
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

    live_source = (ROOT / "scripts/run_step091b3r1_postgresql_live_acceptance.py").read_text(
        encoding="utf-8"
    )
    live_launcher = (ROOT / "sh_run_step091b3r1_postgresql_live_acceptance.cmd").read_text(
        encoding="utf-8"
    )
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    topology = (ROOT / "okcanvas_agent_runtime/bootstrap/storage_topology.py").read_text(
        encoding="utf-8"
    )
    driver = (
        ROOT / "okcanvas_agent_runtime/adapters/persistence/postgresql/driver.py"
    ).read_text(encoding="utf-8")

    checks = {
        "identity_exact": CURRENT_STEP == STEP and PROJECT_VERSION == VERSION,
        "step091b3_parent_retained": parent.get("state") == "PASSED"
        and parent.get("passed_checks") == parent.get("total_checks") == 22,
        "real_postgresql_live_harness_present": all(
            token in live_source
            for token in (
                "psycopg.connect",
                "CREATE SCHEMA",
                "DROP SCHEMA IF EXISTS",
                "SET search_path",
                "REAL_POSTGRESQL_ISOLATED_SCHEMA_LIVE_GATE",
            )
        ),
        "live_dsn_requires_dedicated_environment": all(
            token in live_source
            for token in (
                'LIVE_DSN_ENV = "OKCANVAS_POSTGRESQL_LIVE_DSN"',
                'LIVE_CONFIRM_ENV = "OKCANVAS_POSTGRESQL_LIVE_CONFIRM"',
                'LIVE_CONFIRM_VALUE = "CREATE_AND_DROP_ISOLATED_TEST_SCHEMA"',
            )
        ),
        "live_schema_isolated_and_cleanup_mandatory": all(
            token in live_source
            for token in (
                "SCHEMA_PREFIX",
                "isolated_schema_created",
                "isolated_schema_cleanup_succeeded",
                "DROP SCHEMA IF EXISTS",
            )
        ),
        "live_admission_concurrency_and_atomicity_covered": all(
            token in live_source
            for token in (
                "concurrent_admission_is_idempotent",
                "governed_admission_rolls_back_atomically",
                "RunExecutionOwnershipTransition",
            )
        ),
        "live_event_sequence_concurrency_covered": all(
            token in live_source
            for token in (
                "concurrent_event_sequences_are_contiguous",
                "ThreadPoolExecutor",
                "append_event",
            )
        ),
        "live_approval_resume_fence_covered": all(
            token in live_source
            for token in (
                "approval_state_machine_and_resume_fence_live",
                "begin_tool_execution",
                "tool_execution_count=1",
            )
        ),
        "live_evaluation_round_trip_covered": "evaluation_round_trip_live" in live_source,
        "live_session_row_lock_and_restart_covered": all(
            token in live_source
            for token in (
                "session_active_run_row_lock_live",
                "session_metadata_survives_service_restart",
                "SessionBusyError",
            )
        ),
        "live_sqlite_default_retention_covered": "sqlite_default_topology_retained" in live_source,
        "live_evidence_is_secret_safe_by_construction": all(
            token in live_source
            for token in (
                "dsn_sha256",
                "database_name_sha256",
                "database_user_sha256",
                'failure_code = f"POSTGRESQL_LIVE_ACCEPTANCE_{type(exc).__name__.upper()}"',
            )
        ),
        "postgresql_optional_dependency_declared": 'postgresql = ["psycopg[binary]>=3.2,<4"]'
        in pyproject,
        "postgresql_row_lock_translation_retained": "FOR UPDATE" in driver
        and "pg_advisory_xact_lock" in driver,
        "postgresql_topology_same_dsn_validation_retained": "must share one DSN" in topology,
        "windows_live_launcher_present": "run_step091b3r1_postgresql_live_acceptance.py"
        in live_launcher
        and "python_bytecode_isolation.py" in live_launcher,
        "launcher_registry_current_exact": registry.get("state") == "PASSED"
        and registry.get("current_step") == STEP
        and registry.get("current_step_token") == "091B3R1"
        and registry.get("current_record_count") == 4,
        "architecture_regression_passed": architecture.get("state") == "PASSED"
        and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "package_identity_exact": PACKAGE_STEP == STEP
        and DEFAULT_OUTPUT.name
        == "okcanvas-agent-runtime-step091b3r1-real-postgresql-live-acceptance-gate.zip",
    }
    payload = {
        "schema_version": "okcanvas-step091b3r1-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_REAL_POSTGRESQL_LIVE_GATE_READINESS",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "step091b3_parent": parent,
        "launcher_registry": registry,
        "architecture_validation": architecture,
        "focused_output": focused_output,
        "compile_output": compile_output,
        "limitations": {
            "real_postgresql_server_executed": False,
            "postgresql_live_gate_implemented": True,
            "production_database_migration_executed": False,
            "distributed_session_history_implemented": False,
            "object_storage_live_server_executed": False,
            "api_worker_physical_split_implemented": False,
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
