from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, IntegrityContractError
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step034-admin-key-123456"
SUBMITTER_KEY = "step034-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
CONFIRMATION = "RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART"


class NeverGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("STEP034 reconciliation must not call the model gateway")


def _count(database: Path, table: str) -> int:
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP034", output=output) as workspace:
        database = workspace.scratch_dir / "product.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        artifact_root = workspace.scratch_dir / "artifacts"
        gateway = NeverGateway()
        app = create_app(
            project_root=ROOT,
            product_db=database,
            artifact_root=artifact_root,
            evaluation_db=workspace.scratch_dir / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            gateway=gateway,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=payload_root,
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(app) as client:
            boundary = app.state.governed_submission_boundary
            submissions = app.state.run_submission_store
            product = app.state.product_store
            current_owner = app.state.governed_submission_execution.owner_id

            decision = boundary.preflight(
                authority_scope="LOCAL_RUN_SUBMITTER",
                agent_definition_id="coding-agent",
                request="STEP034 reconcile previous process orphan without reexecution",
                model="acceptance-model",
                idempotency_key="step034-orphaned-running-acceptance-0001",
            )
            bound = submissions.create_governed_task_run(decision.submission_id)
            previous_owner = "previous-local-process-step034"
            claim = submissions.claim_execution(
                decision.submission_id,
                owner_id=previous_owner,
                lease_seconds=30,
                max_attempts=3,
            )
            assert claim is not None
            started = submissions.begin_execution(
                decision.submission_id, claim_token=claim.token
            )
            fence_before = submissions.execution_fence_active(
                decision.submission_id, claim_token=claim.token
            )
            candidates_before = submissions.list_orphaned_running(
                current_owner_id=current_owner
            )

            response = client.post(
                "/v1/run-submissions/reconcile-orphaned-running",
                headers=HEADERS,
                json={"confirmation": CONFIRMATION},
            )
            response_payload = response.json()

            updated = submissions.get(decision.submission_id)
            task = product.get_task(bound.task_id or "")
            run = product.get_run(bound.run_id or "")
            events = product.list_events(bound.run_id or "")
            event_types = [item.event_type for item in events]
            failure_event = next(item for item in events if item.event_type == "run.failed")

            fence_after = submissions.execution_fence_active(
                decision.submission_id, claim_token=claim.token
            )
            late_event_blocked = False
            late_metadata_blocked = False
            late_artifact_blocked = False
            try:
                product.append_event(
                    bound.run_id or "",
                    event_type="model.completed",
                    source=EventSource.RUNTIME,
                    payload={"late": True},
                    require_active_run=True,
                )
            except IntegrityContractError:
                late_event_blocked = True
            try:
                product.update_run_execution_metadata(
                    bound.run_id or "",
                    trace_id="late-trace",
                    input_tokens=1,
                    output_tokens=1,
                    total_tokens=2,
                )
            except IntegrityContractError:
                late_metadata_blocked = True
            late_path = artifact_root / "late-output.json"
            late_path.parent.mkdir(parents=True, exist_ok=True)
            late_path.write_text('{"late":true}', encoding="utf-8")
            try:
                product.register_artifact(
                    run_id=bound.run_id or "",
                    artifact_type="agent.final-output",
                    path=late_path,
                    media_type="application/json",
                )
            except ArtifactIntegrityError:
                late_artifact_blocked = True

            replay = client.post(
                "/v1/run-submissions/reconcile-orphaned-running",
                headers=HEADERS,
                json={"confirmation": CONFIRMATION},
            )
            replay_payload = replay.json()

        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        payload_files = list(payload_root.glob("payload_*.json"))
        final_counts = {
            "tasks": _count(database, "task"),
            "runs": _count(database, "run"),
            "events": _count(database, "run_event"),
            "artifacts": _count(database, "artifact"),
            "submissions": _count(database, "run_submission_preflight"),
            "evaluations": _count(workspace.scratch_dir / "evaluation.sqlite3", "evaluation_result"),
        }
        checks = {
            "previous_process_execution_started": started is True,
            "previous_generation_fence_active_before_reconcile": fence_before is True,
            "different_owner_started_run_detected": len(candidates_before) == 1,
            "reconciliation_returned_200": response.status_code == 200,
            "one_orphan_scanned_and_reconciled": response_payload.get("scanned") == 1
            and response_payload.get("reconciled") == 1
            and response_payload.get("failed") == 0,
            "same_task_and_run_terminalized": response_payload.get("submission_ids")
            == [decision.submission_id]
            and response_payload.get("run_ids") == [bound.run_id],
            "task_failed_exactly": task.status is TaskStatus.FAILED,
            "run_failed_exactly": run.status is RunStatus.FAILED,
            "submission_failed_and_claim_cleared": updated.state.value == "EXECUTION_FAILED"
            and updated.claim_owner_id is None,
            "orphan_event_sequence_exact": event_types[-3:]
            == ["run.execution.orphaned", "run.failed", "payload.retention.applied"],
            "process_loss_failure_contract_exact": failure_event.payload.get("code")
            == "PROCESS_LOSS_RECONCILED"
            and failure_event.payload.get("retryable") is False,
            "reexecution_never_attempted": gateway.calls == 0,
            "previous_generation_fenced_after_reconcile": fence_after is False,
            "late_lifecycle_event_blocked": late_event_blocked,
            "late_execution_metadata_blocked": late_metadata_blocked,
            "late_artifact_registration_blocked": late_artifact_blocked,
            "no_artifact_or_evaluation_created": final_counts["artifacts"] == 0
            and final_counts["evaluations"] == 0,
            "failed_payload_retained_for_investigation": updated.payload_retention_state.value
            == "RETAINED"
            and updated.payload_retention_reason == "process-loss-investigation-window"
            and updated.payload_delete_after is not None
            and len(payload_files) == 1,
            "reconciliation_replay_is_noop": replay.status_code == 200
            and replay_payload.get("scanned") == 0
            and replay_payload.get("reconciled") == 0,
            "references_unchanged": references_before == references_after,
        }
        state = "PASSED" if all(checks.values()) else "FAILED"
        summary = {
            "schema_version": "okcanvas-step034-acceptance-v1",
            "state": state,
            "checks": checks,
            "reconciliation": response_payload,
            "replay": replay_payload,
            "submission": {
                "submission_id": decision.submission_id,
                "task_id": bound.task_id,
                "run_id": bound.run_id,
                "state": updated.state.value,
                "payload_retention_state": updated.payload_retention_state.value,
            },
            "failure": {
                "code": failure_event.payload.get("code"),
                "retryable": failure_event.payload.get("retryable"),
                "event_types": event_types,
            },
            "fence": {
                "active_before": fence_before,
                "active_after": fence_after,
                "late_event_blocked": late_event_blocked,
                "late_metadata_blocked": late_metadata_blocked,
                "late_artifact_blocked": late_artifact_blocked,
            },
            "gateway_call_count": gateway.calls,
            "protected_payload_file_count": len(payload_files),
            "final_counts": final_counts,
        }
        final = workspace.finalize(summary)
        print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if final.get("state") == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP034_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
