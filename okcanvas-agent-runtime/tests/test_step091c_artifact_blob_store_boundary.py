from __future__ import annotations

from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.artifacts import (
    LocalFilesystemArtifactBlobStore,
    ObjectStorageArtifactBlobStore,
    ObjectStorageArtifactSettings,
)
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.bootstrap.storage_topology import (
    SQLiteStorageTopologySettings,
    build_sqlite_storage_topology,
)
from okcanvas_agent_runtime.domain.runs import ArtifactIntegrityError
from okcanvas_agent_runtime.domain.sessions import (
    SQLiteSessionKeyRotationPolicyCatalog,
    SQLiteSessionPolicyCatalog,
)

ROOT = Path(__file__).resolve().parents[1]


class MemoryObjectClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str, dict[str, str]]] = {}

    def put_object(self, *, bucket, key, data, content_type, metadata):
        self.objects[(bucket, key)] = (bytes(data), content_type, dict(metadata))

    def get_object(self, *, bucket, key):
        try:
            return self.objects[(bucket, key)][0]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc

    def head_object(self, *, bucket, key):
        try:
            data, content_type, metadata = self.objects[(bucket, key)]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc
        return {
            "content_length": len(data),
            "content_type": content_type,
            "metadata": metadata,
        }

    def delete_object(self, *, bucket, key):
        return self.objects.pop((bucket, key), None) is not None


def _running_run(store: SQLiteProductStore) -> str:
    task = store.create_task(
        task_type="TEST",
        input_sha256="a" * 64,
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    return run.run_id


def test_local_blob_store_uses_opaque_ref_and_detects_tampering(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    blobs = LocalFilesystemArtifactBlobStore(tmp_path / "artifacts")
    service = ArtifactService(product_store=store, blob_store=blobs)
    artifact = service.create_json(
        run_id=_running_run(store),
        artifact_type="agent.final-output",
        payload={"status": "PASS"},
    )
    assert artifact.storage_path.startswith("local-artifact-v1://")
    _, payload = service.read_json(artifact.artifact_id)
    assert payload == {"status": "PASS"}
    relative = artifact.storage_path.removeprefix("local-artifact-v1://")
    (tmp_path / "artifacts" / relative).write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError) as caught:
        service.verify(artifact.artifact_id)
    assert caught.value.details["reason"] == "mismatch"


def test_object_storage_adapter_round_trip_scope_and_integrity(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    client = MemoryObjectClient()
    blobs = ObjectStorageArtifactBlobStore(
        ObjectStorageArtifactSettings(bucket="runtime-artifacts", prefix="tenant-a"),
        client,
    )
    service = ArtifactService(product_store=store, blob_store=blobs)
    artifact = service.create_json(
        run_id=_running_run(store),
        artifact_type="agent.final-output",
        payload={"status": "PASS"},
    )
    assert artifact.storage_path.startswith("object-artifact-v1://runtime-artifacts/tenant-a/")
    assert service.read_json(artifact.artifact_id)[1] == {"status": "PASS"}
    with pytest.raises(ArtifactIntegrityError):
        blobs.read(
            artifact.storage_path.replace("runtime-artifacts", "other-bucket"),
            expected_sha256=artifact.sha256,
            expected_byte_length=artifact.byte_length,
        )
    bucket, key = blobs._parse_reference(artifact.storage_path)
    data, content_type, metadata = client.objects[(bucket, key)]
    client.objects[(bucket, key)] = (data + b"x", content_type, metadata)
    with pytest.raises(ArtifactIntegrityError) as caught:
        service.read_bytes(artifact.artifact_id)
    assert caught.value.details["reason"] == "mismatch"


def test_metadata_failure_compensates_written_blob(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    blobs = LocalFilesystemArtifactBlobStore(tmp_path / "artifacts")
    service = ArtifactService(product_store=store, blob_store=blobs)
    with pytest.raises(Exception):
        service.create_json(
            run_id="run_missing",
            artifact_type="agent.final-output",
            payload={"status": "PASS"},
            artifact_id="artifact_compensated",
        )
    assert not any((tmp_path / "artifacts").rglob("artifact_compensated.blob"))


def test_storage_topology_owns_blob_store(tmp_path: Path) -> None:
    topology = build_sqlite_storage_topology(
        SQLiteStorageTopologySettings(
            product_db=tmp_path / "product.sqlite3",
            evaluation_db=tmp_path / "evaluation.sqlite3",
            session_root=tmp_path / "sessions",
            artifact_root=tmp_path / "artifacts",
            session_policy=SQLiteSessionPolicyCatalog(ROOT).resolve(),
            session_history_key=None,
            session_history_previous_key=None,
            session_key_rotation_policy=SQLiteSessionKeyRotationPolicyCatalog(ROOT).resolve(),
        )
    )
    assert topology.artifact_blob_store.backend_id == "local-filesystem-artifact-v1"
