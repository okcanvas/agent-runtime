from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
import time
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.domain.project_snapshots import (
    ProjectSnapshotIntegrityError,
    ProjectSnapshotPolicyCatalog,
    ProjectSnapshotValidationError,
    materialize_project_snapshot,
    validate_project_snapshot_zip,
)
from okcanvas_agent_runtime.adapters.storage.project_snapshots import EncryptedProjectSnapshotStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
ALICE_TOKEN = "step076-alice-service-token-123456"
BOB_TOKEN = "step076-bob-service-token-12345678"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step076-alice",
                "token_sha256": _sha(ALICE_TOKEN),
                "tenant_id": "tenant-a",
                "principal_id": "alice",
                "roles": ["agent-user"],
            },
            {
                "token_id": "step076-bob",
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


def _zip_bytes(files: dict[str, bytes | str]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content.encode("utf-8") if isinstance(content, str) else content)
    return stream.getvalue()


class SnapshotGateway:
    def __init__(self) -> None:
        self.snapshot_sha256: str | None = None
        self.archive: bytes | None = None

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink, project_snapshot=None):
        assert project_snapshot is not None
        self.snapshot_sha256 = project_snapshot.metadata.snapshot_sha256
        self.archive = project_snapshot.archive
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step076"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="Immutable project snapshot inspected.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=8, output_tokens=4, total_tokens=12),
            trace_id="trace_step076",
            response_id="resp_step076",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path, gateway: SnapshotGateway):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step076-local-admin-key-123456",
        gateway=gateway,
        run_submitter_key="step076-local-submitter-key-123456",
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )


def _upload(client: TestClient, token: str, archive: bytes, filename: str = "project.zip") -> dict:
    response = client.post(
        "/v1/service/project-snapshots",
        headers={
            **_headers(token),
            "X-OKCanvas-Project-Snapshot-Filename": filename,
        },
        content=archive,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _preflight(client: TestClient, token: str, snapshot_id: str, key: str) -> dict:
    response = client.post(
        "/v1/service/run-submissions/preflight",
        headers=_headers(token),
        json={
            "agent_definition_id": "sandbox-readonly-coding-agent",
            "input": "Inspect the exact formula and constant.",
            "model": "gpt-4.1",
            "project_snapshot_id": snapshot_id,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _wait_terminal(client: TestClient, token: str, run_id: str) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"/v1/service/runs/{run_id}", headers=_headers(token))
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("STEP076 run did not become terminal")


def test_snapshot_policy_rejects_traversal_symlink_collision_and_bounds() -> None:
    policy = ProjectSnapshotPolicyCatalog(ROOT).resolve()
    with pytest.raises(ProjectSnapshotValidationError):
        validate_project_snapshot_zip(_zip_bytes({"../escape.py": "x"}), "project.zip", policy)

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        info = zipfile.ZipInfo("link.py")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "target.py")
    with pytest.raises(ProjectSnapshotValidationError):
        validate_project_snapshot_zip(stream.getvalue(), "project.zip", policy)

    with pytest.raises(ProjectSnapshotValidationError):
        validate_project_snapshot_zip(
            _zip_bytes({"src/Case.py": "x", "src/case.py": "y"}),
            "project.zip",
            policy,
        )

    tiny = replace(policy, max_file_bytes=3, max_total_bytes=3)
    with pytest.raises(ProjectSnapshotValidationError):
        validate_project_snapshot_zip(_zip_bytes({"a.txt": "four"}), "project.zip", tiny)


def test_encrypted_snapshot_binding_tamper_detection_and_materialization_cleanup(tmp_path: Path) -> None:
    policy = ProjectSnapshotPolicyCatalog(ROOT).resolve()
    store = EncryptedProjectSnapshotStore(
        tmp_path / "snapshots",
        ProtectedPayloadKey.from_text(PAYLOAD_KEY),
        policy,
    )
    archive = _zip_bytes({"src/inventory.py": "SAFETY_STOCK = 12\n", "README.md": "safe\n"})
    slot = store.create_slot(archive, "project.zip")
    bound, binding = store.bind_slot(slot.record_ref, "submission_" + "1" * 32)
    prepared = store.read_bound(binding, "submission_" + "1" * 32)
    assert prepared.metadata.snapshot_sha256 == slot.metadata.snapshot_sha256

    temporary_parent = tmp_path / "materialized"
    with materialize_project_snapshot(prepared, temporary_parent=temporary_parent) as root:
        materialized_root = root
        assert (root / "src" / "inventory.py").read_text(encoding="utf-8") == "SAFETY_STOCK = 12\n"
    assert not materialized_root.exists()

    path = tmp_path / "snapshots" / "bound" / f"{bound.record_ref}.json"
    raw = bytearray(path.read_bytes())
    raw[-10] ^= 1
    path.write_bytes(bytes(raw))
    with pytest.raises(ProjectSnapshotIntegrityError):
        store.read_bound(binding, "submission_" + "1" * 32)


def test_service_snapshot_is_principal_scoped_fingerprinted_and_deleted_after_success(tmp_path: Path) -> None:
    gateway = SnapshotGateway()
    archive = _zip_bytes(
        {
            "src/inventory.py": (
                "SAFETY_STOCK = 12\n\n"
                "def calculate_reorder(on_hand: int, forecast: int) -> int:\n"
                "    return max(0, forecast + SAFETY_STOCK - on_hand)\n"
            )
        }
    )
    with TestClient(_app(tmp_path, gateway)) as client:
        capabilities = client.get("/v1/service/capabilities", headers=_headers(ALICE_TOKEN)).json()
        assert capabilities["project_snapshot_ingress_configured"] is True
        assert capabilities["project_snapshot_api"] == "/v1/service/project-snapshots"
        assert capabilities["next_selected_step"] == "UNSELECTED_PENDING_USER_SELECTION"

        missing = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(ALICE_TOKEN),
            json={
                "agent_definition_id": "sandbox-readonly-coding-agent",
                "input": "Inspect.",
                "model": "gpt-4.1",
                "idempotency_key": "step076-missing-snapshot-0001",
            },
        )
        assert missing.status_code == 422

        upload = _upload(client, ALICE_TOKEN, archive)
        denied = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(BOB_TOKEN),
            json={
                "agent_definition_id": "sandbox-readonly-coding-agent",
                "input": "Inspect.",
                "model": "gpt-4.1",
                "project_snapshot_id": upload["project_snapshot_id"],
                "idempotency_key": "step076-cross-tenant-denied-0001",
            },
        )
        assert denied.status_code == 404

        submission = _preflight(
            client,
            ALICE_TOKEN,
            upload["project_snapshot_id"],
            "step076-snapshot-run-0000001",
        )
        assert submission["project_snapshot_sha256"] == upload["snapshot_sha256"]
        assert submission["project_snapshot_archive_sha256"] == upload["archive_sha256"]
        assert submission["project_snapshot_file_count"] == 1
        assert submission["project_snapshot_total_bytes"] > 0
        assert list((tmp_path / "protected-project-snapshots" / "slots").glob("*.json")) == []
        assert len(list((tmp_path / "protected-project-snapshots" / "bound").glob("*.json"))) == 1

        confirmation = client.post(
            f"/v1/service/run-submissions/{submission['submission_id']}/confirm",
            headers=_headers(ALICE_TOKEN),
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert confirmation.status_code == 202, confirmation.text
        run_id = confirmation.json()["run_id"]
        terminal = _wait_terminal(client, ALICE_TOKEN, run_id)
        assert terminal["status"] == "SUCCEEDED"
        assert gateway.snapshot_sha256 == upload["snapshot_sha256"]
        assert gateway.archive == archive

        artifacts = client.get(
            f"/v1/service/runs/{run_id}/artifacts", headers=_headers(ALICE_TOKEN)
        ).json()
        assert {item["artifact_type"] for item in artifacts["artifacts"]} == {
            "agent.project-snapshot-evidence",
            "agent.final-output",
        }
        evidence_summary = next(
            item for item in artifacts["artifacts"]
            if item["artifact_type"] == "agent.project-snapshot-evidence"
        )
        evidence = client.get(
            f"/v1/service/runs/{run_id}/artifacts/{evidence_summary['artifact_id']}",
            headers=_headers(ALICE_TOKEN),
        ).json()["content"]
        assert evidence["snapshot_sha256"] == upload["snapshot_sha256"]
        assert evidence["raw_archive_persisted"] is False
        assert evidence["host_path_persisted"] is False
        assert list((tmp_path / "protected-project-snapshots" / "bound").glob("*.json")) == []


def test_snapshot_identity_changes_submission_fingerprint(tmp_path: Path) -> None:
    gateway = SnapshotGateway()
    with TestClient(_app(tmp_path, gateway)) as client:
        first = _upload(client, ALICE_TOKEN, _zip_bytes({"src/a.py": "VALUE = 1\n"}), "one.zip")
        second = _upload(client, ALICE_TOKEN, _zip_bytes({"src/a.py": "VALUE = 2\n"}), "two.zip")
        one = _preflight(client, ALICE_TOKEN, first["project_snapshot_id"], "step076-fingerprint-one-0001")
        two = _preflight(client, ALICE_TOKEN, second["project_snapshot_id"], "step076-fingerprint-two-0001")
        assert one["project_snapshot_sha256"] != two["project_snapshot_sha256"]
        assert one["request_fingerprint_sha256"] != two["request_fingerprint_sha256"]
