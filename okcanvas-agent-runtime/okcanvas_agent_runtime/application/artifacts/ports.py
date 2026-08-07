from __future__ import annotations

from typing import Protocol, runtime_checkable

from okcanvas_agent_runtime.application.artifacts.models import ArtifactBlobContent, ArtifactBlobRecord


@runtime_checkable
class ArtifactBlobStorePort(Protocol):
    """Binary Artifact storage independent from Product metadata persistence."""

    @property
    def backend_id(self) -> str: ...

    def initialize(self) -> None: ...

    def put(
        self,
        *,
        run_id: str,
        artifact_id: str,
        artifact_type: str,
        media_type: str,
        data: bytes,
    ) -> ArtifactBlobRecord: ...

    def read(
        self,
        storage_ref: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> ArtifactBlobContent: ...

    def verify(
        self,
        storage_ref: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> ArtifactBlobRecord: ...

    def delete(self, storage_ref: str) -> bool: ...

    def exists(self, storage_ref: str) -> bool: ...
