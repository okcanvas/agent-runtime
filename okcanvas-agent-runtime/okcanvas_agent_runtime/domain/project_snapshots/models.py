from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ProjectSnapshotFile:
    path: str
    sha256: str
    byte_length: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectSnapshotMetadata:
    filename: str
    archive_sha256: str
    archive_byte_length: int
    snapshot_sha256: str
    file_count: int
    total_bytes: int
    files: tuple[ProjectSnapshotFile, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "archive_sha256": self.archive_sha256,
            "archive_byte_length": self.archive_byte_length,
            "snapshot_sha256": self.snapshot_sha256,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "files": [item.to_dict() for item in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectSnapshotMetadata":
        expected = {
            "filename", "archive_sha256", "archive_byte_length", "snapshot_sha256",
            "file_count", "total_bytes", "files",
        }
        if set(payload) != expected or not isinstance(payload.get("files"), list):
            raise ValueError("Project snapshot metadata fields are invalid")
        return cls(
            filename=str(payload["filename"]),
            archive_sha256=str(payload["archive_sha256"]),
            archive_byte_length=int(payload["archive_byte_length"]),
            snapshot_sha256=str(payload["snapshot_sha256"]),
            file_count=int(payload["file_count"]),
            total_bytes=int(payload["total_bytes"]),
            files=tuple(ProjectSnapshotFile(**item) for item in payload["files"]),
        )


@dataclass(frozen=True)
class ProjectSnapshotRecord:
    record_ref: str
    record_type: Literal["slot", "bound"]
    file_sha256: str
    envelope_byte_length: int
    key_id: str
    created_at: str
    expires_at: str | None
    submission_id: str | None
    metadata: ProjectSnapshotMetadata

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-project-snapshot-record-v1",
            "project_snapshot_id": self.record_ref,
            "state": "UPLOADED" if self.record_type == "slot" else "BOUND",
            "filename": self.metadata.filename,
            "archive_sha256": self.metadata.archive_sha256,
            "archive_byte_length": self.metadata.archive_byte_length,
            "snapshot_sha256": self.metadata.snapshot_sha256,
            "file_count": self.metadata.file_count,
            "total_bytes": self.metadata.total_bytes,
            "expires_at": self.expires_at,
            "raw_archive_persisted_in_events": False,
            "raw_archive_persisted_in_artifacts": False,
        }


@dataclass(frozen=True)
class ProtectedProjectSnapshotBinding:
    project_snapshot_ref: str
    encrypted_file_sha256: str
    encrypted_byte_length: int
    encryption_key_id: str
    filename: str
    archive_sha256: str
    archive_byte_length: int
    snapshot_sha256: str
    file_count: int
    total_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-protected-project-snapshot-binding-v1",
            "project_snapshot_ref": self.project_snapshot_ref,
            "encrypted_file_sha256": self.encrypted_file_sha256,
            "encrypted_byte_length": self.encrypted_byte_length,
            "encryption_key_id": self.encryption_key_id,
            "filename": self.filename,
            "archive_sha256": self.archive_sha256,
            "archive_byte_length": self.archive_byte_length,
            "snapshot_sha256": self.snapshot_sha256,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProtectedProjectSnapshotBinding":
        expected = {
            "schema_version", "project_snapshot_ref", "encrypted_file_sha256",
            "encrypted_byte_length", "encryption_key_id", "filename", "archive_sha256",
            "archive_byte_length", "snapshot_sha256", "file_count", "total_bytes",
        }
        if set(payload) != expected or payload.get("schema_version") != "okcanvas-protected-project-snapshot-binding-v1":
            raise ValueError("Protected project snapshot binding fields are invalid")
        return cls(
            project_snapshot_ref=str(payload["project_snapshot_ref"]),
            encrypted_file_sha256=str(payload["encrypted_file_sha256"]),
            encrypted_byte_length=int(payload["encrypted_byte_length"]),
            encryption_key_id=str(payload["encryption_key_id"]),
            filename=str(payload["filename"]),
            archive_sha256=str(payload["archive_sha256"]),
            archive_byte_length=int(payload["archive_byte_length"]),
            snapshot_sha256=str(payload["snapshot_sha256"]),
            file_count=int(payload["file_count"]),
            total_bytes=int(payload["total_bytes"]),
        )


@dataclass(frozen=True)
class PreparedProjectSnapshot:
    metadata: ProjectSnapshotMetadata
    archive: bytes = field(repr=False)

    def to_evidence_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-project-snapshot-evidence-v1",
            "snapshot_sha256": self.metadata.snapshot_sha256,
            "archive_sha256": self.metadata.archive_sha256,
            "archive_byte_length": self.metadata.archive_byte_length,
            "file_count": self.metadata.file_count,
            "total_bytes": self.metadata.total_bytes,
            "raw_archive_persisted": False,
            "host_path_persisted": False,
        }
