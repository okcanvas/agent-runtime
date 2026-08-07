from __future__ import annotations

from tests.artifact_test_support import artifact_service

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import base64
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    GovernedLifecyclePolicy,
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_KEY = "step019-admin-key-123456789"
SUBMITTER_KEY = "step019-submitter-key-123456789"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}


class NeverGateway:
    async def run(self, **_kwargs):  # pragma: no cover - recovery unit test never calls it
        raise AssertionError("gateway must not be called")


class FailingGateway:
    async def run(self, **_kwargs):
        raise RuntimeError("controlled failure")


class CapturingScheduler:
    def __init__(self) -> None:
        self.prepared = []

    async def schedule_prepared(self, *, prepared, settings):
        self.prepared.append((prepared, settings))
        return object()


def _direct_services(tmp_path: Path, *, owner_id: str, scheduler: CapturingScheduler):
    product_db = tmp_path / "product.sqlite3"
    product = SQLiteProductStore(product_db)
    product.initialize()
    submissions = SQLiteRunSubmissionStore(product_db)
    submissions.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "payloads", ProtectedPayloadKey.from_text(PAYLOAD_KEY)
    )
    payloads.initialize()
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT), store=submissions, protected_payload_store=payloads
    )
    execution = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=product,
        gateway=NeverGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(product, tmp_path / "artifacts"),
    )
    governed = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=scheduler,
        owner_id=owner_id,
        lifecycle_policy=GovernedLifecyclePolicy(
            claim_lease_seconds=5,
            max_claim_attempts=3,
            failed_payload_retention_days=7,
        ),
    )
    return product, submissions, payloads, boundary, governed


def test_stale_claim_recovery_rotates_generation_and_fences_old_task(tmp_path: Path) -> None:
    first_scheduler = CapturingScheduler()
    product, submissions, _payloads, boundary, first = _direct_services(
        tmp_path, owner_id="owner-one", scheduler=first_scheduler
    )
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="recover this governed request",
        model="test-model",
        idempotency_key="step019-recovery-idempotency",
    )
    settings = RuntimeSettings(model="test-model", api_key="test-key")

    import asyncio

    initial = asyncio.run(
        first.confirm_and_schedule(
            submission_id=decision.submission_id,
            confirmation=decision.confirmation_challenge or "",
            settings=settings,
        )
    )
    assert initial.scheduled is True
    assert len(first_scheduler.prepared) == 1
    old_prepared, _ = first_scheduler.prepared[0]

    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    connection = sqlite3.connect(tmp_path / "product.sqlite3")
    try:
        connection.execute(
            "UPDATE run_submission_preflight SET claim_expires_at = ? WHERE submission_id = ?",
            (past, decision.submission_id),
        )
        connection.commit()
    finally:
        connection.close()

    second_scheduler = CapturingScheduler()
    _, _, _, _, second = _direct_services(
        tmp_path, owner_id="owner-two", scheduler=second_scheduler
    )
    recovered = asyncio.run(
        second.recover_stale(settings_factory=lambda _decision: settings)
    )
    assert recovered.recovered == 1
    assert recovered.submission_ids == (decision.submission_id,)
    assert len(second_scheduler.prepared) == 1
    new_prepared, _ = second_scheduler.prepared[0]

    assert old_prepared.start_execution is not None
    assert new_prepared.start_execution is not None
    assert old_prepared.start_execution() is False
    assert new_prepared.start_execution() is True
    assert product.get_run(initial.run_id).status.value == "RUNNING"
    current = submissions.get(decision.submission_id)
    assert current.state.value == "EXECUTION_STARTED"
    assert current.claim_attempts == 2
    assert current.recovery_count == 1


def test_failed_run_retains_payload_then_explicit_cleanup_deletes_it(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=FailingGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
    )
    with TestClient(app) as client:
        preflight = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "coding-agent",
                "input": "controlled failure payload",
                "model": "test-model",
                "idempotency_key": "step019-failure-retention",
            },
        ).json()
        confirmed = client.post(
            f"/v1/run-submissions/{preflight['submission_id']}/confirm",
            headers=HEADERS,
            json={"confirmation": preflight["confirmation_challenge"]},
        ).json()

        import time

        deadline = time.monotonic() + 3
        detail = None
        while time.monotonic() < deadline:
            detail = client.get(
                f"/v1/run-submissions/{preflight['submission_id']}",
                headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
            ).json()
            if detail["state"] == "EXECUTION_FAILED":
                break
            time.sleep(0.02)
        assert detail is not None
        assert detail["state"] == "EXECUTION_FAILED"
        assert detail["payload_retention_state"] == "RETAINED"
        assert detail["payload_delete_after"] is not None
        payload_path = tmp_path / "payloads" / f"{preflight['protected_payload_ref']}.json"
        assert payload_path.is_file()

        past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        connection = sqlite3.connect(tmp_path / "product.sqlite3")
        try:
            connection.execute(
                "UPDATE run_submission_preflight SET payload_delete_after = ? WHERE submission_id = ?",
                (past, preflight["submission_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        cleanup = client.post(
            "/v1/protected-payloads/cleanup-expired", headers=HEADERS
        )
        assert cleanup.status_code == 200
        assert cleanup.json()["deleted"] == 1
        assert not payload_path.exists()
        final = client.get(
            f"/v1/run-submissions/{preflight['submission_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
        ).json()
        assert final["payload_retention_state"] == "DELETED"
        assert final["payload_deleted_at"] is not None
        assert confirmed["run_id"] == final["run_id"]


def test_unconfirmed_payload_expires_without_creating_task_or_run(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=NeverGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
    )
    with TestClient(app) as client:
        preflight = client.post(
            "/v1/run-submissions/preflight",
            headers=HEADERS,
            json={
                "agent_definition_id": "coding-agent",
                "input": "unconfirmed expiring payload",
                "model": "test-model",
                "idempotency_key": "step019-unconfirmed-retention",
            },
        ).json()
        path = tmp_path / "payloads" / f"{preflight['protected_payload_ref']}.json"
        assert path.is_file()
        connection = sqlite3.connect(tmp_path / "product.sqlite3")
        try:
            connection.execute(
                "UPDATE run_submission_preflight SET payload_delete_after = ? WHERE submission_id = ?",
                ("2000-01-01T00:00:00Z", preflight["submission_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        result = client.post("/v1/protected-payloads/cleanup-expired", headers=HEADERS)
        assert result.status_code == 200
        assert result.json()["deleted"] == 1
        assert not path.exists()

    connection = sqlite3.connect(tmp_path / "product.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 0
    finally:
        connection.close()


def test_recovery_and_cleanup_require_submitter_authority(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=NeverGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
    )
    with TestClient(app) as client:
        admin_only = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
        recovery = client.post("/v1/run-submissions/recover-stale", headers=admin_only)
        cleanup = client.post("/v1/protected-payloads/cleanup-expired", headers=admin_only)
    assert recovery.status_code == 403
    assert cleanup.status_code == 403
