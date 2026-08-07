from __future__ import annotations
from tests.artifact_test_support import artifact_service

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]
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
        raise AssertionError("terminal outcome reconciliation must not invoke the gateway")


def _app(tmp_path: Path, gateway: NeverGateway):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
    )


def _seed_terminal_without_observer(app, tmp_path: Path, *, case: str, status: RunStatus):
    boundary = app.state.governed_submission_boundary
    submissions = app.state.run_submission_store
    product = app.state.product_store
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request=f"STEP035 {case} terminal before lifecycle observer",
        model="acceptance-model",
        idempotency_key=f"step035-terminal-{case}-0001",
    )
    bound = submissions.create_governed_task_run(decision.submission_id)
    claim = submissions.claim_execution(
        decision.submission_id,
        owner_id=f"previous-local-process-step035-{case}",
        lease_seconds=30,
        max_attempts=3,
    )
    assert claim is not None
    assert submissions.begin_execution(decision.submission_id, claim_token=claim.token)

    if status is RunStatus.SUCCEEDED:
        artifact = artifact_service(product, tmp_path / "artifacts").create_json(
            run_id=bound.run_id or "",
            artifact_type="agent.final-output",
            payload={"result": "ok"},
        )
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
    return decision, bound, claim


def test_terminal_outcomes_reconcile_retention_without_reexecution(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    with TestClient(app) as client:
        success = _seed_terminal_without_observer(
            app, tmp_path, case="success", status=RunStatus.SUCCEEDED
        )
        failed = _seed_terminal_without_observer(
            app, tmp_path, case="failed", status=RunStatus.FAILED
        )
        cancelled = _seed_terminal_without_observer(
            app, tmp_path, case="cancelled", status=RunStatus.CANCELLED
        )

        response = client.post(
            "/v1/run-submissions/reconcile-terminal-outcomes",
            headers=HEADERS,
            json={"confirmation": CONFIRMATION},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["scanned"] == 3
        assert result["reconciled"] == 3
        assert result["deleted"] == 1
        assert result["retained"] == 2
        assert result["failed"] == 0

        submissions = app.state.run_submission_store
        product = app.state.product_store
        success_decision = submissions.get(success[0].submission_id)
        failed_decision = submissions.get(failed[0].submission_id)
        cancelled_decision = submissions.get(cancelled[0].submission_id)

        assert success_decision.state.value == "EXECUTION_SUCCEEDED"
        assert success_decision.payload_retention_state.value == "DELETED"
        assert success_decision.protected_payload_persisted is False
        assert failed_decision.state.value == "EXECUTION_FAILED"
        assert failed_decision.payload_retention_state.value == "RETAINED"
        assert failed_decision.payload_delete_after is not None
        assert cancelled_decision.state.value == "EXECUTION_CANCELLED"
        assert cancelled_decision.payload_retention_state.value == "RETAINED"
        assert cancelled_decision.payload_delete_after is not None

        for _decision, bound, claim in (success, failed, cancelled):
            events = product.list_events(bound.run_id or "")
            assert [e.event_type for e in events].count("payload.retention.applied") == 1
            assert submissions.execution_fence_active(
                _decision.submission_id, claim_token=claim.token
            ) is False

        payload_files = list((tmp_path / "protected-payloads").glob("payload_*.json"))
        assert len(payload_files) == 2

        replay = client.post(
            "/v1/run-submissions/reconcile-terminal-outcomes",
            headers=HEADERS,
            json={"confirmation": CONFIRMATION},
        )
        assert replay.status_code == 200
        assert replay.json()["scanned"] == 0
        assert replay.json()["reconciled"] == 0

    assert gateway.calls == 0


def test_partial_success_retention_is_finished_and_event_is_not_duplicated(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    with TestClient(app) as client:
        decision, bound, _claim = _seed_terminal_without_observer(
            app, tmp_path, case="partial-success", status=RunStatus.SUCCEEDED
        )
        submissions = app.state.run_submission_store
        submissions.terminalize(
            decision.submission_id,
            run_status="SUCCEEDED",
            payload_delete_after="2000-01-01T00:00:00Z",
            retention_reason="successful-run-immediate-cleanup",
        )

        first = client.post(
            "/v1/run-submissions/reconcile-terminal-outcomes",
            headers=HEADERS,
            json={"confirmation": CONFIRMATION},
        )
        assert first.status_code == 200
        assert first.json()["reconciled"] == 1
        assert submissions.get(decision.submission_id).payload_retention_state.value == "DELETED"
        events = app.state.product_store.list_events(bound.run_id or "")
        assert [e.event_type for e in events].count("payload.retention.applied") == 1

        second = client.post(
            "/v1/run-submissions/reconcile-terminal-outcomes",
            headers=HEADERS,
            json={"confirmation": CONFIRMATION},
        )
        assert second.status_code == 200
        assert second.json()["reconciled"] == 0
        events = app.state.product_store.list_events(bound.run_id or "")
        assert [e.event_type for e in events].count("payload.retention.applied") == 1


def test_current_process_terminal_started_row_is_not_reconciled(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    with TestClient(app) as client:
        boundary = app.state.governed_submission_boundary
        submissions = app.state.run_submission_store
        product = app.state.product_store
        decision = boundary.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="STEP035 current process terminal race",
            model="acceptance-model",
            idempotency_key="step035-current-terminal-0001",
        )
        bound = submissions.create_governed_task_run(decision.submission_id)
        claim = submissions.claim_execution(
            decision.submission_id,
            owner_id=app.state.governed_submission_execution.owner_id,
            lease_seconds=30,
            max_attempts=3,
        )
        assert claim is not None
        assert submissions.begin_execution(decision.submission_id, claim_token=claim.token)
        product.transition_run(
            bound.run_id or "",
            RunStatus.FAILED,
            event_type="run.failed",
            payload={"code": "CONTROLLED_FAILURE"},
        )
        product.transition_task(bound.task_id or "", TaskStatus.FAILED)

        response = client.post(
            "/v1/run-submissions/reconcile-terminal-outcomes",
            headers=HEADERS,
            json={"confirmation": CONFIRMATION},
        )
        assert response.status_code == 200
        assert response.json()["scanned"] == 0
        assert submissions.get(decision.submission_id).state.value == "EXECUTION_STARTED"
