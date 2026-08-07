from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.transport.common.errors import ControlAPIError

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
ALICE_TOKEN = "step077-alice-service-token-123456"
BOB_TOKEN = "step077-bob-service-token-12345678"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step077-alice",
                "token_sha256": _sha(ALICE_TOKEN),
                "tenant_id": "tenant-a",
                "principal_id": "alice",
                "roles": ["agent-user"],
            },
            {
                "token_id": "step077-bob",
                "token_sha256": _sha(BOB_TOKEN),
                "tenant_id": "tenant-b",
                "principal_id": "bob",
                "roles": ["agent-user"],
            },
        ],
    },
    sort_keys=True,
)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _zip_bytes(value: int = 12) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("src/inventory.py", f"SAFETY_STOCK = {value}\n")
    return stream.getvalue()


def _png_bytes(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


class NoopGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP077 slot lifecycle tests must not call the model gateway")


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step077-local-admin-key-123456",
        gateway=NoopGateway(),
        run_submitter_key="step077-local-submitter-key-123456",
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )


def _upload_snapshot(client: TestClient, token: str = ALICE_TOKEN) -> dict:
    response = client.post(
        "/v1/service/project-snapshots",
        headers={
            **_headers(token),
            "X-OKCanvas-Project-Snapshot-Filename": "project.zip",
        },
        content=_zip_bytes(),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload_attachment(client: TestClient, token: str = ALICE_TOKEN) -> dict:
    response = client.post(
        "/v1/service/local-attachments",
        headers={
            **_headers(token),
            "X-OKCanvas-Attachment-Filename": "image.png",
        },
        content=_png_bytes(),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_project_snapshot_store_reconciles_authenticated_expired_slots_before_upload(tmp_path: Path) -> None:
    app = _app(tmp_path)
    store = app.state.project_snapshot_store
    archive = _zip_bytes()
    metadata = store.create_slot(archive, "old.zip").metadata
    old_ref = next((tmp_path / "protected-project-snapshots" / "slots").glob("*.json")).stem
    store.delete(old_ref)
    store._write_record(
        record_ref=old_ref,
        record_type="slot",
        data=archive,
        metadata=metadata,
        created_at="1999-12-31T23:59:00Z",
        expires_at="2000-01-01T00:00:00Z",
        submission_id=None,
    )

    new_slot = store.create_slot(_zip_bytes(13), "new.zip")

    assert store.slot_exists(old_ref) is False
    assert store.slot_exists(new_slot.record_ref) is True


def test_service_delete_is_principal_scoped_for_snapshot_and_attachment_slots(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        snapshot = _upload_snapshot(client)
        attachment = _upload_attachment(client)

        denied_snapshot = client.delete(
            f"/v1/service/project-snapshots/{snapshot['project_snapshot_id']}",
            headers=_headers(BOB_TOKEN),
        )
        denied_attachment = client.delete(
            f"/v1/service/local-attachments/{attachment['attachment_id']}",
            headers=_headers(BOB_TOKEN),
        )
        assert denied_snapshot.status_code == 404
        assert denied_attachment.status_code == 404

        deleted_snapshot = client.delete(
            f"/v1/service/project-snapshots/{snapshot['project_snapshot_id']}",
            headers=_headers(ALICE_TOKEN),
        )
        deleted_attachment = client.delete(
            f"/v1/service/local-attachments/{attachment['attachment_id']}",
            headers=_headers(ALICE_TOKEN),
        )
        assert deleted_snapshot.status_code == 204
        assert deleted_attachment.status_code == 204
        assert app.state.project_snapshot_store.slot_exists(snapshot["project_snapshot_id"]) is False
        assert app.state.local_attachment_store.slot_exists(attachment["attachment_id"]) is False
        with pytest.raises(ControlAPIError):
            app.state.service_resource_ownership.get(
                resource_type="project-snapshot-slot",
                resource_id=snapshot["project_snapshot_id"],
            )
        with pytest.raises(ControlAPIError):
            app.state.service_resource_ownership.get(
                resource_type="attachment-slot",
                resource_id=attachment["attachment_id"],
            )


def test_upload_ownership_failure_compensates_encrypted_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(tmp_path)

    def fail_register(**_kwargs):
        raise RuntimeError("injected ownership failure")

    monkeypatch.setattr(app.state.service_resource_ownership, "register", fail_register)
    with TestClient(app, raise_server_exceptions=False) as client:
        snapshot = client.post(
            "/v1/service/project-snapshots",
            headers={
                **_headers(ALICE_TOKEN),
                "X-OKCanvas-Project-Snapshot-Filename": "project.zip",
            },
            content=_zip_bytes(),
        )
        attachment = client.post(
            "/v1/service/local-attachments",
            headers={
                **_headers(ALICE_TOKEN),
                "X-OKCanvas-Attachment-Filename": "image.png",
            },
            content=_png_bytes(),
        )
    assert snapshot.status_code == 500
    assert attachment.status_code == 500
    assert list((tmp_path / "protected-project-snapshots" / "slots").glob("*.json")) == []
    assert list((tmp_path / "protected-attachments" / "slots").glob("*.json")) == []


def test_preflight_reconciles_expired_slot_file_and_ownership_row(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        uploaded = _upload_snapshot(client)
        slot_ref = uploaded["project_snapshot_id"]
        store = app.state.project_snapshot_store
        record, data = store._read_record(slot_ref, expected_type="slot")
        store.delete(slot_ref)
        store._write_record(
            record_ref=slot_ref,
            record_type="slot",
            data=data,
            metadata=record.metadata,
            created_at="1999-12-31T23:59:00Z",
            expires_at="2000-01-01T00:00:00Z",
            submission_id=None,
        )

        response = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(ALICE_TOKEN),
            json={
                "agent_definition_id": "sandbox-readonly-coding-agent",
                "input": "Inspect.",
                "model": "gpt-4.1",
                "project_snapshot_id": slot_ref,
                "idempotency_key": "step077-expired-slot-0001",
            },
        )
        assert response.status_code == 404
        assert store.slot_exists(slot_ref) is False
        with pytest.raises(ControlAPIError):
            app.state.service_resource_ownership.get(
                resource_type="project-snapshot-slot",
                resource_id=slot_ref,
            )
