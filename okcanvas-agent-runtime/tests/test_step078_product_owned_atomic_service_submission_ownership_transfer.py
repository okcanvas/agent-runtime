from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.transport.common.errors import ControlAPIError
from okcanvas_agent_runtime.transport.service.models import ServicePrincipal, ServiceClientRole

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
ALICE_TOKEN = "step078-alice-service-token-123456"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step078-alice",
                "token_sha256": _sha(ALICE_TOKEN),
                "tenant_id": "tenant-a",
                "principal_id": "alice",
                "roles": ["agent-user"],
            }
        ],
    },
    sort_keys=True,
)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ALICE_TOKEN}"}


def _zip_bytes(value: int = 12) -> bytes:
    stream = io.BytesIO()
    info = zipfile.ZipInfo("src/inventory.py", date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(info, f"SAFETY_STOCK = {value}\n")
    return stream.getvalue()


class NoopGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP078 ownership tests must not call the model gateway")


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step078-local-admin-key-123456",
        gateway=NoopGateway(),
        run_submitter_key="step078-local-submitter-key-123456",
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )


def _upload_snapshot(client: TestClient) -> str:
    response = client.post(
        "/v1/service/project-snapshots",
        headers={
            **_headers(),
            "X-OKCanvas-Project-Snapshot-Filename": "project.zip",
        },
        content=_zip_bytes(),
    )
    assert response.status_code == 201, response.text
    return response.json()["project_snapshot_id"]


def _preflight(client: TestClient, snapshot_id: str, key: str) -> dict:
    response = client.post(
        "/v1/service/run-submissions/preflight",
        headers=_headers(),
        json={
            "agent_definition_id": "sandbox-readonly-coding-agent",
            "input": "Inspect the exact constant.",
            "model": "gpt-4.1",
            "project_snapshot_id": snapshot_id,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _rows(database: Path, query: str) -> list[sqlite3.Row]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def test_service_preflight_uses_atomic_store_transition_not_post_commit_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        snapshot_id = _upload_snapshot(client)
        original_register = app.state.service_resource_ownership.register

        def reject_old_submission_path(*, principal, resource_type, resource_id):
            if resource_type == "submission":
                raise RuntimeError("post-commit submission ownership path must not run")
            return original_register(
                principal=principal,
                resource_type=resource_type,
                resource_id=resource_id,
            )

        monkeypatch.setattr(app.state.service_resource_ownership, "register", reject_old_submission_path)
        decision = _preflight(client, snapshot_id, "step078-atomic-success-0001")

    owners = [dict(row) for row in _rows(
        tmp_path / "product.sqlite3",
        "SELECT resource_type,resource_id,tenant_id,principal_id FROM service_resource_owner ORDER BY resource_type,resource_id",
    )]
    assert owners == [{
        "resource_type": "submission",
        "resource_id": decision["submission_id"],
        "tenant_id": "tenant-a",
        "principal_id": "alice",
    }]
    assert app.state.project_snapshot_store.slot_exists(snapshot_id) is False


def test_atomic_transition_failure_rolls_back_submission_payload_bound_snapshot_and_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)

        def fail_transition(*_args, **_kwargs):
            raise RuntimeError("injected atomic ownership transition failure")

        monkeypatch.setattr(app.state.run_submission_store, "_apply_ownership_transition", fail_transition)
        response = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(),
            json={
                "agent_definition_id": "sandbox-readonly-coding-agent",
                "input": "Inspect.",
                "model": "gpt-4.1",
                "project_snapshot_id": snapshot_id,
                "idempotency_key": "step078-atomic-failure-0001",
            },
        )
        assert response.status_code == 500

    assert _rows(tmp_path / "product.sqlite3", "SELECT * FROM run_submission_preflight") == []
    assert _rows(tmp_path / "product.sqlite3", "SELECT * FROM service_resource_owner") == []
    assert list((tmp_path / "protected-payloads").glob("*.json")) == []
    assert list((tmp_path / "protected-project-snapshots" / "slots").glob("*.json")) == []
    assert list((tmp_path / "protected-project-snapshots" / "bound").glob("*.json")) == []


def test_idempotent_binary_replay_releases_replacement_slot_and_preserves_submission_owner(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        first_slot = _upload_snapshot(client)
        first = _preflight(client, first_slot, "step078-idempotent-replay-0001")
        second_slot = _upload_snapshot(client)
        second = _preflight(client, second_slot, "step078-idempotent-replay-0001")

    assert second["submission_id"] == first["submission_id"]
    assert second["replayed"] is True
    assert app.state.project_snapshot_store.slot_exists(second_slot) is False
    owners = [dict(row) for row in _rows(
        tmp_path / "product.sqlite3",
        "SELECT resource_type,resource_id,tenant_id,principal_id FROM service_resource_owner ORDER BY resource_type,resource_id",
    )]
    assert owners == [{
        "resource_type": "submission",
        "resource_id": first["submission_id"],
        "tenant_id": "tenant-a",
        "principal_id": "alice",
    }]


def test_failed_cleanup_never_releases_another_principals_ingress_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(tmp_path)
    bob = ServicePrincipal(
        tenant_id="tenant-b",
        principal_id="bob",
        roles=(ServiceClientRole.AGENT_USER,),
        token_id="step078-bob",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot_id = _upload_snapshot(client)
        ownership = app.state.service_resource_ownership
        ownership.release_if_exists(
            resource_type="project-snapshot-slot", resource_id=snapshot_id
        )
        ownership.register(
            principal=bob,
            resource_type="project-snapshot-slot",
            resource_id=snapshot_id,
        )
        original_require = ownership.require_principal

        def allow_stale_authorization(*, principal, resource_type, resource_id):
            if resource_type == "project-snapshot-slot" and resource_id == snapshot_id:
                return None
            return original_require(
                principal=principal,
                resource_type=resource_type,
                resource_id=resource_id,
            )

        monkeypatch.setattr(ownership, "require_principal", allow_stale_authorization)
        response = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(),
            json={
                "agent_definition_id": "sandbox-readonly-coding-agent",
                "input": "Inspect.",
                "model": "gpt-4.1",
                "project_snapshot_id": snapshot_id,
                "idempotency_key": "step078-foreign-owner-0001",
            },
        )
        assert response.status_code == 409

    owner = app.state.service_resource_ownership.get(
        resource_type="project-snapshot-slot", resource_id=snapshot_id
    )
    assert owner.tenant_id == "tenant-b"
    assert owner.principal_id == "bob"
    assert _rows(tmp_path / "product.sqlite3", "SELECT * FROM run_submission_preflight") == []
    assert list((tmp_path / "protected-payloads").glob("*.json")) == []
    assert list((tmp_path / "protected-project-snapshots" / "bound").glob("*.json")) == []
