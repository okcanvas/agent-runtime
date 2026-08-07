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
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step035-admin-key-123456"
SUBMITTER_KEY = "step035-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
CONFIRMATION = "RECONCILE_TERMINAL_RUN_OUTCOMES_AFTER_PROCESS_RESTART"


class NeverGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("STEP035 must not invoke the model gateway")


def _count(database: Path, table: str) -> int:
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def _seed(app, artifact_root: Path, *, case_id: str, status: RunStatus):
    boundary = app.state.governed_submission_boundary
    submissions = app.state.run_submission_store
    product = app.state.product_store
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request=f"STEP035 {case_id} terminal outcome before completion observer",
        model="acceptance-model",
        idempotency_key=f"step035-{case_id}-terminal-0001",
    )
    bound = submissions.create_governed_task_run(decision.submission_id)
    claim = submissions.claim_execution(
        decision.submission_id,
        owner_id=f"previous-local-process-step035-{case_id}",
        lease_seconds=30,
        max_attempts=3,
    )
    assert claim is not None
    assert submissions.begin_execution(decision.submission_id, claim_token=claim.token)

    artifact_id = None
    if status is RunStatus.SUCCEEDED:
        path = artifact_root / f"{case_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"result":"ok"}', encoding="utf-8")
        artifact = product.register_artifact(
            run_id=bound.run_id or "",
            artifact_type="agent.final-output",
            path=path,
            media_type="application/json",
        )
        artifact_id = artifact.artifact_id
        product.append_event(
            bound.run_id or "",
            event_type="artifact.created",
            source=EventSource.RUNTIME,
            payload={"artifact_id": artifact.artifact_id},
            require_active_run=True,
        )
        product.transition_run(
            bound.run_id or "",
            RunStatus.SUCCEEDED,
            event_type="run.completed",
            payload={"artifact_id": artifact.artifact_id},
        )
        product.transition_task(bound.task_id or "", TaskStatus.SUCCEEDED)
    elif status is RunStatus.FAILED:
        product.transition_run(
            bound.run_id or "",
            RunStatus.FAILED,
            event_type="run.failed",
            payload={"code": "CONTROLLED_FAILURE", "retryable": False},
        )
        product.transition_task(bound.task_id or "", TaskStatus.FAILED)
    else:
        product.transition_run(
            bound.run_id or "",
            RunStatus.CANCELLED,
            event_type="run.cancelled",
            payload={"reason": "controlled-cancel"},
        )
        product.transition_task(bound.task_id or "", TaskStatus.CANCELLED)
    return {
        "case_id": case_id,
        "status": status,
        "decision": decision,
        "bound": bound,
        "claim": claim,
        "artifact_id": artifact_id,
    }


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP035", output=output) as workspace:
        database = workspace.scratch_dir / "product.sqlite3"
        evaluation_db = workspace.scratch_dir / "evaluation.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        artifact_root = workspace.scratch_dir / "artifacts"
        gateway = NeverGateway()
        app = create_app(
            project_root=ROOT,
            product_db=database,
            artifact_root=artifact_root,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=gateway,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=payload_root,
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(app) as client:
            cases = [
                _seed(app, artifact_root, case_id="succeeded", status=RunStatus.SUCCEEDED),
                _seed(app, artifact_root, case_id="failed", status=RunStatus.FAILED),
                _seed(app, artifact_root, case_id="cancelled", status=RunStatus.CANCELLED),
            ]
            submissions = app.state.run_submission_store
            product = app.state.product_store
            candidates_before = submissions.list_terminal_outcome_reconciliation_candidates(
                current_owner_id=app.state.governed_submission_execution.owner_id
            )
            response = client.post(
                "/v1/run-submissions/reconcile-terminal-outcomes",
                headers=HEADERS,
                json={"confirmation": CONFIRMATION},
            )
            response_payload = response.json()

            case_results = []
            for case in cases:
                decision = submissions.get(case["decision"].submission_id)
                bound = case["bound"]
                events = product.list_events(bound.run_id or "")
                retention_events = [
                    event for event in events if event.event_type == "payload.retention.applied"
                ]
                case_results.append(
                    {
                        "case_id": case["case_id"],
                        "product_status": case["status"].value,
                        "submission_state": decision.state.value,
                        "payload_retention_state": decision.payload_retention_state.value,
                        "payload_retention_reason": decision.payload_retention_reason,
                        "payload_delete_after": decision.payload_delete_after,
                        "claim_cleared": decision.claim_owner_id is None,
                        "generation_active": submissions.execution_fence_active(
                            decision.submission_id, claim_token=case["claim"].token
                        ),
                        "retention_event_count": len(retention_events),
                        "retention_event": (
                            retention_events[0].payload if retention_events else None
                        ),
                        "artifact_id": case["artifact_id"],
                        "submission_id": decision.submission_id,
                        "task_id": bound.task_id,
                        "run_id": bound.run_id,
                    }
                )

            replay = client.post(
                "/v1/run-submissions/reconcile-terminal-outcomes",
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
            "evaluations": _count(evaluation_db, "evaluation_result"),
        }
        by_id = {item["case_id"]: item for item in case_results}
        checks = {
            "three_previous_process_terminal_outcomes_detected": len(candidates_before) == 3,
            "reconciliation_returned_200": response.status_code == 200,
            "three_outcomes_reconciled": response_payload.get("scanned") == 3
            and response_payload.get("reconciled") == 3
            and response_payload.get("failed") == 0,
            "success_submission_terminalized": by_id["succeeded"]["submission_state"]
            == "EXECUTION_SUCCEEDED",
            "failed_submission_terminalized": by_id["failed"]["submission_state"]
            == "EXECUTION_FAILED",
            "cancelled_submission_terminalized": by_id["cancelled"]["submission_state"]
            == "EXECUTION_CANCELLED",
            "success_payload_deleted": response_payload.get("deleted") == 1
            and by_id["succeeded"]["payload_retention_state"] == "DELETED",
            "failed_payload_retained": by_id["failed"]["payload_retention_state"]
            == "RETAINED"
            and by_id["failed"]["payload_delete_after"] is not None,
            "cancelled_payload_retained": by_id["cancelled"]["payload_retention_state"]
            == "RETAINED"
            and by_id["cancelled"]["payload_delete_after"] is not None,
            "retained_count_exact": response_payload.get("retained") == 2,
            "one_retention_event_per_run": all(
                item["retention_event_count"] == 1 for item in case_results
            ),
            "success_retention_event_exact": by_id["succeeded"]["retention_event"]
            == {"state": "DELETED", "reason": "successful-run"},
            "failure_retention_events_exact": all(
                by_id[key]["retention_event"].get("state") == "RETAINED"
                and by_id[key]["retention_event"].get("reason")
                == "terminal-failure-investigation-window"
                and by_id[key]["retention_event"].get("delete_after")
                for key in ("failed", "cancelled")
            ),
            "all_claims_cleared": all(item["claim_cleared"] for item in case_results),
            "all_previous_generations_fenced": all(
                item["generation_active"] is False for item in case_results
            ),
            "reexecution_never_attempted": gateway.calls == 0,
            "existing_task_run_counts_preserved": final_counts["tasks"] == 3
            and final_counts["runs"] == 3
            and final_counts["submissions"] == 3,
            "success_artifact_preserved_without_new_evaluation": final_counts["artifacts"] == 1
            and final_counts["evaluations"] == 0
            and by_id["succeeded"]["artifact_id"] is not None,
            "only_failed_and_cancelled_payloads_remain": len(payload_files) == 2,
            "reconciliation_replay_is_noop": replay.status_code == 200
            and replay_payload.get("scanned") == 0
            and replay_payload.get("reconciled") == 0,
            "references_unchanged": references_before == references_after,
        }
        state = "PASSED" if all(checks.values()) else "FAILED"
        summary = {
            "schema_version": "okcanvas-step035-acceptance-v1",
            "state": state,
            "checks": checks,
            "reconciliation": response_payload,
            "replay": replay_payload,
            "case_results": case_results,
            "final_counts": final_counts,
            "gateway_call_count": gateway.calls,
            "protected_payload_file_count": len(payload_files),
        }
        final = workspace.finalize(summary)
        print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if final.get("state") == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP035_ACCEPTANCE.json")
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
