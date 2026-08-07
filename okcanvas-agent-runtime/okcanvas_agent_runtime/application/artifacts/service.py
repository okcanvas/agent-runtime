from __future__ import annotations

import json
import uuid
from typing import Any

from okcanvas_agent_runtime.application.artifacts.ports import ArtifactBlobStorePort
from okcanvas_agent_runtime.domain.runs.models import ArtifactRecord
from okcanvas_agent_runtime.domain.runs.ports import ProductStore


class ArtifactService:
    """Coordinates blob persistence and Product Artifact metadata without sharing storage internals."""

    def __init__(self, *, product_store: ProductStore, blob_store: ArtifactBlobStorePort) -> None:
        self._products = product_store
        self._blobs = blob_store

    @property
    def blob_backend_id(self) -> str:
        return self._blobs.backend_id

    def create_json(
        self,
        *,
        run_id: str,
        artifact_type: str,
        payload: dict[str, Any],
        artifact_id: str | None = None,
    ) -> ArtifactRecord:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.create_bytes(
            run_id=run_id,
            artifact_type=artifact_type,
            media_type="application/json",
            data=data,
            artifact_id=artifact_id,
        )

    def create_bytes(
        self,
        *,
        run_id: str,
        artifact_type: str,
        media_type: str,
        data: bytes,
        artifact_id: str | None = None,
    ) -> ArtifactRecord:
        resolved_artifact_id = artifact_id or f"artifact_{uuid.uuid4().hex}"
        blob = self._blobs.put(
            run_id=run_id,
            artifact_id=resolved_artifact_id,
            artifact_type=artifact_type,
            media_type=media_type,
            data=data,
        )
        try:
            return self._products.register_artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                storage_ref=blob.storage_ref,
                sha256=blob.sha256,
                byte_length=blob.byte_length,
                media_type=media_type,
                artifact_id=resolved_artifact_id,
            )
        except Exception:
            self._blobs.delete(blob.storage_ref)
            raise

    def read_bytes(self, artifact_id: str) -> tuple[ArtifactRecord, bytes]:
        artifact = self._products.get_artifact(artifact_id)
        content = self._blobs.read(
            artifact.storage_path,
            expected_sha256=artifact.sha256,
            expected_byte_length=artifact.byte_length,
        )
        verified = self._products.verify_artifact(artifact_id)
        return verified, content.data

    def read_json(self, artifact_id: str) -> tuple[ArtifactRecord, dict[str, Any]]:
        artifact, data = self.read_bytes(artifact_id)
        parsed = json.loads(data.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Artifact content must be a JSON object")
        return artifact, parsed

    def verify(self, artifact_id: str) -> ArtifactRecord:
        artifact = self._products.get_artifact(artifact_id)
        self._blobs.verify(
            artifact.storage_path,
            expected_sha256=artifact.sha256,
            expected_byte_length=artifact.byte_length,
        )
        return self._products.verify_artifact(artifact_id)
