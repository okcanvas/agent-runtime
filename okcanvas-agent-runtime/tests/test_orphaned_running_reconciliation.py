from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, IntegrityContractError

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step034-admin-key-123456"
SUBMITTER_KEY = "step034-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}


class NeverGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("orphan reconciliation must not invoke the model gateway")


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


def _seed_previous_process_started(app) -> tuple[object, object]:
    boundary = app.state.governed_submission_boundary
    submissions = app.state.run_submission_store
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="STEP034 previous process active execution",
        model="acceptance-model",
        idempotency_key="step034-orphaned-running-0001",
    )
    bound = submissions.create_governed_task_run(decision.submission_id)
    claim = submissions.claim_execution(
        decision.submission_id,
        owner_id="previous-local-process-step034",
        lease_seconds=30,
        max_attempts=3,
    )
    assert claim is not None
    assert submissions.begin_execution(decision.submission_id, claim_token=claim.token) is True
    assert submissions.execution_fence_active(
        decision.submission_id, claim_token=claim.token
    ) is True
    return bound, claim


def test_explicit_restart_reconciliation_fails_orphan_without_reexecution(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    with TestClient(app) as client:
        bound, claim = _seed_previous_process_started(app)
        response = client.post(
            "/v1/run-submissions/reconcile-orphaned-running",
            headers=HEADERS,
            json={"confirmation": "RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["scanned"] == 1
        assert result["reconciled"] == 1
        assert result["failed"] == 0
        assert result["submission_ids"] == [bound.submission_id]
        assert result["run_ids"] == [bound.run_id]

        product = app.state.product_store
        task = product.get_task(bound.task_id)
        run = product.get_run(bound.run_id)
        updated = app.state.run_submission_store.get(bound.submission_id)
        assert task.status is TaskStatus.FAILED
        assert run.status is RunStatus.FAILED
        assert updated.state.value == "EXECUTION_FAILED"
        assert updated.claim_owner_id is None
        assert updated.payload_retention_state.value == "RETAINED"
        assert updated.payload_retention_reason == "process-loss-investigation-window"
        assert updated.payload_delete_after is not None
        assert app.state.run_submission_store.execution_fence_active(
            bound.submission_id, claim_token=claim.token
        ) is False

        event_types = [item.event_type for item in product.list_events(bound.run_id)]
        assert event_types[-3:] == [
            "run.execution.orphaned",
            "run.failed",
            "payload.retention.applied",
        ]
        failure = product.list_events(bound.run_id)[-2]
        assert failure.payload["code"] == "PROCESS_LOSS_RECONCILED"
        assert failure.payload["retryable"] is False

        replay = client.post(
            "/v1/run-submissions/reconcile-orphaned-running",
            headers=HEADERS,
            json={"confirmation": "RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART"},
        )
        assert replay.status_code == 200
        assert replay.json()["scanned"] == 0
        assert replay.json()["reconciled"] == 0

    assert gateway.calls == 0


def test_late_previous_process_writes_are_fenced_after_reconciliation(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    with TestClient(app) as client:
        bound, claim = _seed_previous_process_started(app)
        response = client.post(
            "/v1/run-submissions/reconcile-orphaned-running",
            headers=HEADERS,
            json={"confirmation": "RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART"},
        )
        assert response.status_code == 200

        product = app.state.product_store
        with pytest.raises(IntegrityContractError):
            product.append_event(
                bound.run_id,
                event_type="model.completed",
                source=EventSource.RUNTIME,
                payload={"late": True},
                require_active_run=True,
            )
        with pytest.raises(IntegrityContractError):
            product.update_run_execution_metadata(
                bound.run_id,
                trace_id="late-trace",
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
            )
        with pytest.raises(ArtifactIntegrityError):
            product.register_artifact(
                run_id=bound.run_id,
                artifact_type="agent.final-output",
                storage_ref="local-artifact-v1://late-output.blob",
                sha256=hashlib.sha256(b'{"late":true}').hexdigest(),
                byte_length=len(b'{"late":true}'),
                media_type="application/json",
            )
        assert app.state.run_submission_store.execution_fence_active(
            bound.submission_id, claim_token=claim.token
        ) is False
        assert product.artifact_count() == 0


def test_same_process_started_run_is_not_an_orphan_candidate(tmp_path: Path) -> None:
    gateway = NeverGateway()
    app = _app(tmp_path, gateway)
    submissions = app.state.run_submission_store
    current_owner = app.state.governed_submission_execution.owner_id
    decision = app.state.governed_submission_boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="STEP034 current process execution",
        model="acceptance-model",
        idempotency_key="step034-current-running-0001",
    )
    submissions.create_governed_task_run(decision.submission_id)
    claim = submissions.claim_execution(
        decision.submission_id,
        owner_id=current_owner,
        lease_seconds=30,
        max_attempts=3,
    )
    assert claim is not None
    assert submissions.begin_execution(decision.submission_id, claim_token=claim.token)
    assert submissions.list_orphaned_running(current_owner_id=current_owner) == []
