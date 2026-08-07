from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests import test_step078_product_owned_atomic_service_submission_ownership_transfer as step078

_app = step078._app
_headers = step078._headers
_preflight = step078._preflight
_upload_snapshot = step078._upload_snapshot
ServiceClientRole = step078.ServiceClientRole
ServicePrincipal = step078.ServicePrincipal


def _rows(database: Path, query: str) -> list[dict[str, object]]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(query).fetchall()]
    finally:
        connection.close()


def _confirm(client: TestClient, submission: dict[str, object]):
    return client.post(
        f"/v1/service/run-submissions/{submission['submission_id']}/confirm",
        headers=_headers(),
        json={"confirmation": submission["confirmation_challenge"]},
    )


def test_confirm_creates_task_run_and_owners_without_post_commit_register(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)
        submission = _preflight(client, snapshot_id, "step079-atomic-success-0001")
        original_register = app.state.service_resource_ownership.register

        def reject_old_execution_owner_path(*, principal, resource_type, resource_id):
            if resource_type in {"task", "run"}:
                raise RuntimeError("post-commit Task/Run ownership path must not run")
            return original_register(
                principal=principal,
                resource_type=resource_type,
                resource_id=resource_id,
            )

        monkeypatch.setattr(
            app.state.service_resource_ownership,
            "register",
            reject_old_execution_owner_path,
        )
        response = _confirm(client, submission)
        assert response.status_code == 202, response.text
        payload = response.json()

    owners = _rows(
        tmp_path / "product.sqlite3",
        "SELECT resource_type,resource_id,tenant_id,principal_id "
        "FROM service_resource_owner ORDER BY resource_type,resource_id",
    )
    assert owners == [
        {
            "resource_type": "run",
            "resource_id": payload["run_id"],
            "tenant_id": "tenant-a",
            "principal_id": "alice",
        },
        {
            "resource_type": "submission",
            "resource_id": submission["submission_id"],
            "tenant_id": "tenant-a",
            "principal_id": "alice",
        },
        {
            "resource_type": "task",
            "resource_id": payload["task_id"],
            "tenant_id": "tenant-a",
            "principal_id": "alice",
        },
    ]


def test_execution_ownership_failure_rolls_back_task_run_and_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)
        submission = _preflight(client, snapshot_id, "step079-atomic-failure-0001")

        def fail_transition(*_args, **_kwargs):
            raise RuntimeError("injected Task/Run ownership transition failure")

        monkeypatch.setattr(
            app.state.run_submission_store,
            "_apply_execution_ownership_transition",
            fail_transition,
        )
        response = _confirm(client, submission)
        assert response.status_code == 500

    assert _rows(tmp_path / "product.sqlite3", "SELECT * FROM task") == []
    assert _rows(tmp_path / "product.sqlite3", "SELECT * FROM run") == []
    decisions = _rows(
        tmp_path / "product.sqlite3",
        "SELECT state,task_id,run_id FROM run_submission_preflight",
    )
    assert decisions == [{"state": "READY_FOR_CONFIRMATION", "task_id": None, "run_id": None}]
    owners = _rows(
        tmp_path / "product.sqlite3",
        "SELECT resource_type,resource_id,tenant_id,principal_id FROM service_resource_owner",
    )
    assert owners == [
        {
            "resource_type": "submission",
            "resource_id": submission["submission_id"],
            "tenant_id": "tenant-a",
            "principal_id": "alice",
        }
    ]


def test_confirm_replay_repairs_missing_task_run_owner_rows(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)
        submission = _preflight(client, snapshot_id, "step079-replay-repair-0001")
        first = _confirm(client, submission)
        assert first.status_code == 202, first.text
        first_payload = first.json()
        app.state.service_resource_ownership.release_if_exists(
            resource_type="task",
            resource_id=first_payload["task_id"],
        )
        app.state.service_resource_ownership.release_if_exists(
            resource_type="run",
            resource_id=first_payload["run_id"],
        )
        replay = _confirm(client, submission)
        assert replay.status_code == 202, replay.text
        replay_payload = replay.json()
        assert replay_payload["task_id"] == first_payload["task_id"]
        assert replay_payload["run_id"] == first_payload["run_id"]
        assert replay_payload["replayed"] is True

    for resource_type, resource_id in (
        ("task", first_payload["task_id"]),
        ("run", first_payload["run_id"]),
    ):
        owner = app.state.service_resource_ownership.get(
            resource_type=resource_type,
            resource_id=resource_id,
        )
        assert owner.tenant_id == "tenant-a"
        assert owner.principal_id == "alice"


def test_foreign_existing_task_run_owner_causes_atomic_conflict_without_owner_theft(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    bob = ServicePrincipal(
        tenant_id="tenant-b",
        principal_id="bob",
        roles=(ServiceClientRole.AGENT_USER,),
        token_id="step079-bob",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)
        submission = _preflight(client, snapshot_id, "step079-foreign-owner-0001")
        decision = app.state.run_submission_store.create_governed_task_run(
            submission["submission_id"]
        )
        assert decision.task_id is not None
        assert decision.run_id is not None
        app.state.service_resource_ownership.register(
            principal=bob,
            resource_type="task",
            resource_id=decision.task_id,
        )
        app.state.service_resource_ownership.register(
            principal=bob,
            resource_type="run",
            resource_id=decision.run_id,
        )
        response = _confirm(client, submission)
        assert response.status_code == 409

    for resource_type, resource_id in (
        ("task", decision.task_id),
        ("run", decision.run_id),
    ):
        owner = app.state.service_resource_ownership.get(
            resource_type=resource_type,
            resource_id=resource_id,
        )
        assert owner.tenant_id == "tenant-b"
        assert owner.principal_id == "bob"
