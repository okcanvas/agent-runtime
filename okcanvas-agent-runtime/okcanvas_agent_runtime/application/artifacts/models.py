from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactBlobRecord:
    storage_ref: str
    sha256: str
    byte_length: int
    media_type: str


@dataclass(frozen=True)
class ArtifactBlobContent:
    record: ArtifactBlobRecord
    data: bytes
