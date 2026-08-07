from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

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
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.approvals.models import (
    ToolApprovalDecision,
    ToolApprovalState,
)
from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase, EvaluationResult
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.submissions.models import (
    ProtectedPayloadRetentionState,
    RunExecutionOwnershipTransition,
    RunSubmissionDecision,
    RunSubmissionExecutionMode,
    RunSubmissionRecordState,
)
from okcanvas_agent_runtime.bootstrap.storage_topology import (
    PostgreSQLHybridStorageTopologySettings,
    SQLiteStorageTopologySettings,
    build_postgresql_hybrid_storage_topology,
    build_sqlite_storage_topology,
)
from okcanvas_agent_runtime.domain.runs.models import EventSource
from okcanvas_agent_runtime.domain.sessions import (
    SessionBusyError,
    SessionHistoryKey,
    SQLiteSessionKeyRotationPolicyCatalog,
    SQLiteSessionPolicyCatalog,
)

STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"
VERSION = "2.74.1"
LIVE_DSN_ENV = "OKCANVAS_POSTGRESQL_LIVE_DSN"
LIVE_CONFIRM_ENV = "OKCANVAS_POSTGRESQL_LIVE_CONFIRM"
LIVE_CONFIRM_VALUE = "CREATE_AND_DROP_ISOLATED_TEST_SCHEMA"
SCHEMA_PREFIX = "okcanvas_step091b3r1_"
SHA = "a" * 64
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
EXPECTED_TABLES = {
    "agent_invocation",
    "artifact",
    "evaluation_baseline",
    "evaluation_result",
    "evaluation_suite_member",
    "evaluation_suite_run",
    "governed_tool_approval",
    "product_session",
    "product_session_key_rotation",
    "run",
    "run_event",
    "run_submission_preflight",
    "schema_migration",
    "service_resource_owner",
    "task",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _default_output() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return ROOT.parents[1] / f"step091b3r1-postgresql-live-{stamp}.json"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _schema_name() -> str:
    return f"{SCHEMA_PREFIX}{uuid.uuid4().hex[:16]}"


def _safe_failure(code: str, *, started_at: str, checks: dict[str, bool] | None = None) -> dict[str, Any]:
    checks = checks or {}
    return {
        "schema_version": "okcanvas-step091b3r1-real-postgresql-live-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "FAILED",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "failure_code": code,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "limitations": {
            "production_database_migration_executed": False,
            "distributed_session_history_implemented": False,
            "object_storage_live_server_executed": False,
            "api_worker_physical_split_implemented": False,
        },
    }


def _write(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _decision(token: str, *, approval_required: bool = False) -> RunSubmissionDecision:
    submission_id = f"submission-{token}"
    return RunSubmissionDecision(
        submission_id=submission_id,
        state=RunSubmissionRecordState.READY_FOR_CONFIRMATION,
        execution_mode=RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION,
        policy_id="policy-step091b3r1-live",
        policy_version="1.0.0",
        policy_sha256=SHA,
        authority_scope="READ_ONLY",
        agent_definition_id="agent-step091b3r1-live",
        agent_definition_version="1.0.0",
        agent_definition_sha256=SHA,
        runtime_binding_sha256=SHA,
        session_id=None,
        model="postgresql-live-test",
        input_sha256=_sha(f"input:{token}"),
        request_fingerprint_sha256=_sha(f"request:{token}"),
        idempotency_key_sha256=_sha(f"idempotency:{token}"),
        source_adapter_id=None,
        source_adapter_version=None,
        source_adapter_definition_sha256=None,
        source_request_sha256=None,
        source_snapshot_sha256=None,
        source_acquired_at=None,
        project_snapshot_sha256=None,
        project_snapshot_archive_sha256=None,
        project_snapshot_file_count=None,
        project_snapshot_total_bytes=None,
        confirmation_challenge="confirmed",
        approval_required=approval_required,
        executable_now=True,
        protected_payload_persisted=True,
        protected_payload_ref=f"payload-{token}",
        protected_payload_sha256=_sha(f"payload:{token}"),
        protected_payload_key_id="key-step091b3r1-live",
        protected_payload_byte_length=10,
        task_id=None,
        run_id=None,
        confirmed_at=None,
        payload_consumed_at=None,
        scheduled_at=None,
        claim_owner_id=None,
        claim_acquired_at=None,
        claim_expires_at=None,
        claim_attempts=0,
        recovery_count=0,
        last_recovered_at=None,
        execution_started_at=None,
        execution_completed_at=None,
        payload_retention_state=ProtectedPayloadRetentionState.ACTIVE,
        payload_delete_after=None,
        payload_deleted_at=None,
        payload_retention_reason=None,
        reasons=("step091b3r1-real-postgresql-live",),
        created_at=_utc_now(),
    )


def _require_environment() -> tuple[str | None, str | None]:
    dsn = os.environ.get(LIVE_DSN_ENV, "").strip()
    if not dsn:
        return None, "POSTGRESQL_LIVE_DSN_MISSING"
    if os.environ.get(LIVE_CONFIRM_ENV, "").strip() != LIVE_CONFIRM_VALUE:
        return None, "POSTGRESQL_LIVE_CONFIRMATION_MISSING"
    try:
        PostgreSQLConnectionSettings(dsn)
    except ValueError:
        return None, "POSTGRESQL_LIVE_DSN_INVALID"
    return dsn, None


def _load_psycopg() -> tuple[Any, Any]:
    try:
        import psycopg  # type: ignore[import-not-found]
        from psycopg import sql  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("POSTGRESQL_DRIVER_UNAVAILABLE") from exc
    return psycopg, sql


def _connect_factory(psycopg: Any, sql: Any, schema: str) -> Callable[[PostgreSQLConnectionSettings], Any]:
    def connect(settings: PostgreSQLConnectionSettings) -> Any:
        raw = psycopg.connect(
            settings.dsn,
            connect_timeout=settings.connect_timeout_seconds,
            application_name=settings.application_name,
        )
        raw.autocommit = True
        with raw.cursor() as cursor:
            cursor.execute(
                sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(schema))
            )
        return raw

    return connect


def _schema_tables(admin: Any, schema: str) -> set[str]:
    with admin.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
            (schema,),
        )
        return {str(row[0]) for row in cursor.fetchall()}


def _database_identity(admin: Any) -> dict[str, Any]:
    with admin.cursor() as cursor:
        cursor.execute(
            "SELECT current_setting('server_version_num'), current_database(), current_user"
        )
        row = cursor.fetchone()
    return {
        "server_version_num": int(row[0]),
        "database_name_sha256": _sha(str(row[1])),
        "database_user_sha256": _sha(str(row[2])),
    }


def _run_live(output: Path) -> int:
    started_at = _utc_now()
    dsn, readiness_error = _require_environment()
    if readiness_error is not None or dsn is None:
        payload = _safe_failure(readiness_error or "POSTGRESQL_LIVE_ENVIRONMENT_INVALID", started_at=started_at)
        _write(output, payload)
        return 2

    try:
        psycopg, sql = _load_psycopg()
    except RuntimeError as exc:
        payload = _safe_failure(str(exc), started_at=started_at)
        _write(output, payload)
        return 2

    settings = PostgreSQLConnectionSettings(
        dsn,
        connect_timeout_seconds=15,
        application_name="okcanvas-step091b3r1-live",
    )
    schema = _schema_name()
    checks: dict[str, bool] = {}
    cleanup_succeeded = False
    database_identity: dict[str, Any] = {}
    schema_tables: list[str] = []
    failure_code: str | None = None

    admin = None
    try:
        admin = psycopg.connect(
            settings.dsn,
            connect_timeout=settings.connect_timeout_seconds,
            application_name="okcanvas-step091b3r1-live-admin",
        )
        admin.autocommit = True
        database_identity = _database_identity(admin)
        checks["actual_postgresql_server_connected"] = database_identity["server_version_num"] > 0

        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        checks["isolated_schema_created"] = True

        connect_factory = _connect_factory(psycopg, sql, schema)
        token = uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix="okcanvas-step091b3r1-live-") as temp_name:
            temp = Path(temp_name)
            policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
            rotation_policy = SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve()
            history_key = SessionHistoryKey.from_text(KEY_TEXT)

            topology = build_postgresql_hybrid_storage_topology(
                PostgreSQLHybridStorageTopologySettings(
                    postgresql=settings,
                    local_control_db=temp / "unused-local-control.sqlite3",
                    evaluation_db=temp / "unused-evaluation.sqlite3",
                    session_root=temp / "sessions",
                    artifact_root=temp / "artifacts",
                    session_policy=policy,
                    session_history_key=history_key,
                    session_history_previous_key=None,
                    session_key_rotation_policy=rotation_policy,
                    connect_factory=connect_factory,
                )
            )
            checks["postgresql_hybrid_topology_initialized"] = topology.backend_id == "postgresql-hybrid-v1"
            digests = {
                store.settings.dsn_sha256
                for store in (
                    topology.product_store,
                    topology.submission_store,
                    topology.ownership_store,
                    topology.tool_approval_store,
                    topology.evaluation_store,
                    topology.session_runtime,
                )
            }
            checks["all_postgresql_metadata_stores_share_one_dsn"] = digests == {settings.dsn_sha256}

            schema_tables = sorted(_schema_tables(admin, schema))
            checks["all_expected_tables_created"] = EXPECTED_TABLES.issubset(schema_tables)

            product = topology.product_store
            submission = topology.submission_store
            approval = topology.tool_approval_store
            evaluation = topology.evaluation_store
            session_runtime = topology.session_runtime

            concurrent = _decision(f"{token}-concurrent")
            submission.register(concurrent)
            barrier = threading.Barrier(2)

            def admit_once() -> tuple[str, str]:
                local_store = PostgreSQLRunSubmissionStore(settings, connect_factory=connect_factory)
                barrier.wait(timeout=20)
                admitted = local_store.create_governed_task_run(
                    concurrent.submission_id,
                    ownership_transition=RunExecutionOwnershipTransition(
                        tenant_id="tenant-live", principal_id="principal-live"
                    ),
                )
                return str(admitted.task_id), str(admitted.run_id)

            with ThreadPoolExecutor(max_workers=2) as executor:
                admission_results = list(executor.map(lambda _: admit_once(), range(2)))
            checks["concurrent_admission_is_idempotent"] = len(set(admission_results)) == 1
            admitted_task_id, admitted_run_id = admission_results[0]
            checks["governed_admission_persisted_task_run"] = (
                product.get_task(admitted_task_id).status.value == "READY"
                and product.get_run(admitted_run_id).status.value == "CREATED"
            )
            owner = topology.ownership_store.get(resource_type="run", resource_id=admitted_run_id)
            checks["governed_admission_persisted_ownership"] = (
                owner.tenant_id == "tenant-live" and owner.principal_id == "principal-live"
            )

            before_task_total = product.list_tasks()[1]
            before_run_total = product.list_runs()[1]
            rollback_decision = _decision(f"{token}-rollback")
            submission.register(rollback_decision)
            try:
                with patch.object(
                    submission,
                    "_apply_execution_ownership_transition",
                    side_effect=RuntimeError("injected ownership failure"),
                ):
                    submission.create_governed_task_run(
                        rollback_decision.submission_id,
                        ownership_transition=RunExecutionOwnershipTransition(
                            tenant_id="tenant-live", principal_id="principal-live"
                        ),
                    )
            except RuntimeError:
                pass
            rollback_loaded = submission.get(rollback_decision.submission_id)
            checks["governed_admission_rolls_back_atomically"] = (
                rollback_loaded.task_id is None
                and rollback_loaded.run_id is None
                and product.list_tasks()[1] == before_task_total
                and product.list_runs()[1] == before_run_total
            )

            event_task = product.create_task(
                task_type="POSTGRESQL_LIVE",
                input_sha256=_sha(f"event-input:{token}"),
                agent_definition_id="agent-step091b3r1-live",
                agent_definition_version="1.0.0",
            )
            event_run = product.create_run(task_id=event_task.task_id)
            event_barrier = threading.Barrier(8)

            def append_event(index: int) -> int:
                local_product = PostgreSQLProductStore(settings, connect_factory=connect_factory)
                event_barrier.wait(timeout=20)
                return local_product.append_event(
                    event_run.run_id,
                    event_type=f"live.concurrent.{index}",
                    source=EventSource.RUNTIME,
                ).sequence

            with ThreadPoolExecutor(max_workers=8) as executor:
                appended_sequences = sorted(executor.map(append_event, range(8)))
            all_sequences = [event.sequence for event in product.list_events(event_run.run_id)]
            checks["concurrent_event_sequences_are_contiguous"] = (
                appended_sequences == list(range(2, 10)) and all_sequences == list(range(1, 10))
            )

            approval_decision = _decision(f"{token}-approval")
            submission.register(approval_decision)
            approval_admitted = submission.create_governed_task_run(approval_decision.submission_id)
            claim = submission.claim_execution(
                approval_decision.submission_id,
                owner_id="worker-step091b3r1-live",
                lease_seconds=60,
                max_attempts=3,
            )
            if claim is None or not submission.begin_execution(
                approval_decision.submission_id, claim_token=claim.token
            ):
                raise RuntimeError("approval admission could not begin")
            pending = approval.create_pending(
                approval_id=f"approval-{token}",
                submission_id=approval_decision.submission_id,
                task_id=str(approval_admitted.task_id),
                run_id=str(approval_admitted.run_id),
                tool_name="local_text_metrics",
                tool_call_id_sha256=_sha(f"tool-call:{token}"),
                arguments_sha256=_sha(f"arguments:{token}"),
                run_state_ref=f"run-state-{token}",
                run_state_sha256=_sha(f"run-state:{token}"),
                run_state_byte_length=128,
                run_state_key_id="key-step091b3r1-live",
                trace_id=None,
                response_id=None,
            )
            deciding, replayed, resume_token = approval.claim_decision(
                pending.approval_id, ToolApprovalDecision.APPROVE
            )
            first_execution = approval.begin_tool_execution(
                pending.approval_id, resume_token=str(resume_token)
            )
            second_execution = approval.begin_tool_execution(
                pending.approval_id, resume_token=str(resume_token)
            )
            completed = approval.finish(
                pending.approval_id,
                state=ToolApprovalState.SUCCEEDED,
                tool_execution_count=1,
            )
            approval_events = [
                event.event_type
                for event in product.list_events(str(approval_admitted.run_id))
            ]
            checks["approval_state_machine_and_resume_fence_live"] = (
                deciding.state is ToolApprovalState.APPROVING
                and replayed is False
                and bool(resume_token)
                and first_execution is True
                and second_execution is False
                and completed.state is ToolApprovalState.SUCCEEDED
                and approval_events[-4:]
                == [
                    "tool.approval.requested",
                    "run.interrupted",
                    "tool.approval.decided",
                    "run.resumed",
                ]
            )

            case = EvaluationCase(
                case_id=f"case-{token}",
                version="1.0.0",
                agent_definition_id="agent-step091b3r1-live",
                required_result={},
                forbidden_result={},
                required_tools=(),
                forbidden_tools=(),
                max_total_tokens=None,
                max_duration_ms=None,
                manifest_sha256=SHA,
            )
            result = EvaluationResult(
                evaluation_id=f"evaluation-{token}",
                case_id=case.case_id,
                case_version=case.version,
                subject_run_id=event_run.run_id,
                state="PASSED",
                checks={"live": True},
                metrics={"total_tokens": 12},
                failures=(),
                created_at=_utc_now(),
            )
            evaluation.save(
                case=case,
                envelope={
                    "agent_definition_id": case.agent_definition_id,
                    "runtime_binding_sha256": _sha(f"binding:{token}"),
                    "model": "postgresql-live-test",
                },
                result=result,
            )
            loaded_evaluation = evaluation.get(result.evaluation_id)
            checks["evaluation_round_trip_live"] = (
                loaded_evaluation["checks"] == {"live": True}
                and evaluation.statistics()["evaluation_total"] == 1
            )

            definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
            binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
            session_record = session_runtime.create(
                definition=definition,
                runtime_binding_sha256=binding.runtime_binding_sha256,
            )
            session_a = PostgreSQLSessionMetadataRuntimeService(
                settings,
                temp / "sessions",
                policy,
                history_key,
                key_rotation_policy=rotation_policy,
                connect_factory=connect_factory,
            )
            session_b = PostgreSQLSessionMetadataRuntimeService(
                settings,
                temp / "sessions",
                policy,
                history_key,
                key_rotation_policy=rotation_policy,
                connect_factory=connect_factory,
            )
            turn_barrier = threading.Barrier(2)

            def acquire(service: PostgreSQLSessionMetadataRuntimeService, run_id: str) -> tuple[str, str]:
                turn_barrier.wait(timeout=20)
                try:
                    record = service.acquire_turn(
                        session_id=session_record.session_id,
                        run_id=run_id,
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                    return "ACQUIRED", str(record.active_run_id)
                except SessionBusyError:
                    return "BUSY", run_id

            with ThreadPoolExecutor(max_workers=2) as executor:
                turn_results = list(
                    executor.map(
                        lambda item: acquire(*item),
                        ((session_a, f"run-{token}-a"), (session_b, f"run-{token}-b")),
                    )
                )
            acquired = [value for state, value in turn_results if state == "ACQUIRED"]
            busy = [value for state, value in turn_results if state == "BUSY"]
            checks["session_active_run_row_lock_live"] = len(acquired) == 1 and len(busy) == 1
            released = session_b.release_turn(
                session_id=session_record.session_id,
                run_id=acquired[0],
                succeeded=True,
                item_count=2,
            )
            restarted_session = PostgreSQLSessionMetadataRuntimeService(
                settings,
                temp / "sessions",
                policy,
                history_key,
                key_rotation_policy=rotation_policy,
                connect_factory=connect_factory,
            )
            persisted_session = restarted_session.get(session_record.session_id)
            checks["session_metadata_survives_service_restart"] = (
                released.turn_count == 1
                and released.item_count == 2
                and persisted_session.turn_count == 1
                and persisted_session.item_count == 2
                and persisted_session.active_run_id is None
            )
            checks["session_history_remains_local_encrypted_sqlite"] = (
                restarted_session.metadata_backend_id == "postgresql-session-metadata-v1"
                and restarted_session.history_backend_id == "encrypted-local-sqlite-history-v1"
                and restarted_session.history_db.parent == (temp / "sessions").resolve()
                and not restarted_session.catalog_db.exists()
            )

            restarted_product = PostgreSQLProductStore(settings, connect_factory=connect_factory)
            checks["product_rows_survive_store_restart"] = (
                restarted_product.get_task(admitted_task_id).task_id == admitted_task_id
                and restarted_product.get_run(admitted_run_id).run_id == admitted_run_id
            )

            sqlite_topology = build_sqlite_storage_topology(
                SQLiteStorageTopologySettings(
                    product_db=temp / "sqlite-default-product.sqlite3",
                    evaluation_db=temp / "sqlite-default-evaluation.sqlite3",
                    session_root=temp / "sqlite-default-sessions",
                    artifact_root=temp / "sqlite-default-artifacts",
                    session_policy=policy,
                    session_history_key=history_key,
                    session_history_previous_key=None,
                    session_key_rotation_policy=rotation_policy,
                )
            )
            checks["sqlite_default_topology_retained"] = sqlite_topology.backend_id == "sqlite-local-v1"
            checks["dsn_not_exposed_in_settings_repr"] = dsn not in repr(settings)

    except Exception as exc:  # live diagnostics intentionally secret-safe
        failure_code = f"POSTGRESQL_LIVE_ACCEPTANCE_{type(exc).__name__.upper()}"
    finally:
        if admin is not None:
            try:
                with admin.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                    )
                cleanup_succeeded = not _schema_tables(admin, schema)
            except Exception:
                cleanup_succeeded = False
            try:
                admin.close()
            except Exception:
                pass

    checks["isolated_schema_cleanup_succeeded"] = cleanup_succeeded
    state = "PASSED" if failure_code is None and checks and all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-step091b3r1-real-postgresql-live-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "REAL_POSTGRESQL_ISOLATED_SCHEMA_LIVE_GATE",
        "state": state,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "failure_code": failure_code,
        "postgresql": {
            **database_identity,
            "dsn_sha256": settings.dsn_sha256,
            "isolated_schema_name_sha256": _sha(schema),
            "expected_table_count": len(EXPECTED_TABLES),
            "observed_table_count": len(schema_tables),
        },
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "limitations": {
            "real_postgresql_server_executed": checks.get("actual_postgresql_server_connected") is True,
            "isolated_test_schema_only": True,
            "production_database_migration_executed": False,
            "distributed_session_history_implemented": False,
            "object_storage_live_server_executed": False,
            "api_worker_physical_split_implemented": False,
            "distributed_worker_lease_implemented": False,
        },
    }
    _write(output, payload)
    return 0 if state == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=_default_output())
    args = parser.parse_args(argv)
    return _run_live(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
