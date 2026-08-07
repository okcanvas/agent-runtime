from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.adapters.storage.artifacts import LocalFilesystemArtifactBlobStore
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.domain.runs.models import ArtifactRecord
from okcanvas_agent_runtime.domain.runs.ports import ProductStore


def artifact_service(store: ProductStore, root: Path) -> ArtifactService:
    return ArtifactService(
        product_store=store,
        blob_store=LocalFilesystemArtifactBlobStore(root),
    )


def persist_json_artifact(
    store: ProductStore,
    root: Path,
    *,
    run_id: str,
    artifact_type: str,
    payload: dict[str, Any],
) -> ArtifactRecord:
    return artifact_service(store, root).create_json(
        run_id=run_id,
        artifact_type=artifact_type,
        payload=payload,
    )


def read_json_artifact(store: ProductStore, root: Path, artifact_id: str) -> dict[str, Any]:
    _, payload = artifact_service(store, root).read_json(artifact_id)
    return payload


def local_blob_path(root: Path, storage_ref: str) -> Path:
    prefix = "local-artifact-v1://"
    assert storage_ref.startswith(prefix)
    return (root / storage_ref[len(prefix):]).resolve()


def tamper_local_artifact(store: ProductStore, root: Path, artifact_id: str, data: bytes) -> None:
    artifact = store.get_artifact(artifact_id)
    local_blob_path(root, artifact.storage_path).write_bytes(data)
