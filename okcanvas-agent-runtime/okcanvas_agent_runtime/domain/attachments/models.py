from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AttachmentInputKind = Literal["input_file", "input_image"]
AttachmentMediaType = Literal["application/pdf", "image/png", "image/jpeg"]


@dataclass(frozen=True)
class AttachmentMetadata:
    filename: str
    media_type: AttachmentMediaType
    input_kind: AttachmentInputKind
    content_sha256: str
    byte_length: int
    page_count: int | None = None
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttachmentRecord:
    record_ref: str
    record_type: Literal["slot", "bound"]
    file_sha256: str
    envelope_byte_length: int
    key_id: str
    created_at: str
    expires_at: str | None
    submission_id: str | None
    metadata: AttachmentMetadata

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-local-attachment-record-v1",
            "attachment_id": self.record_ref,
            "state": "UPLOADED" if self.record_type == "slot" else "BOUND",
            "filename": self.metadata.filename,
            "media_type": self.metadata.media_type,
            "input_kind": self.metadata.input_kind,
            "content_sha256": self.metadata.content_sha256,
            "byte_length": self.metadata.byte_length,
            "page_count": self.metadata.page_count,
            "width": self.metadata.width,
            "height": self.metadata.height,
            "expires_at": self.expires_at,
            "raw_bytes_persisted_in_events": False,
            "raw_bytes_persisted_in_artifacts": False,
        }


@dataclass(frozen=True)
class ProtectedAttachmentBinding:
    attachment_ref: str
    encrypted_file_sha256: str
    encrypted_byte_length: int
    encryption_key_id: str
    metadata: AttachmentMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-protected-attachment-binding-v1",
            "attachment_ref": self.attachment_ref,
            "encrypted_file_sha256": self.encrypted_file_sha256,
            "encrypted_byte_length": self.encrypted_byte_length,
            "encryption_key_id": self.encryption_key_id,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProtectedAttachmentBinding":
        expected = {
            "schema_version",
            "attachment_ref",
            "encrypted_file_sha256",
            "encrypted_byte_length",
            "encryption_key_id",
            "metadata",
        }
        if set(payload) != expected or payload.get("schema_version") != "okcanvas-protected-attachment-binding-v1":
            raise ValueError("Protected attachment binding fields are invalid")
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Protected attachment metadata is invalid")
        return cls(
            attachment_ref=str(payload["attachment_ref"]),
            encrypted_file_sha256=str(payload["encrypted_file_sha256"]),
            encrypted_byte_length=int(payload["encrypted_byte_length"]),
            encryption_key_id=str(payload["encryption_key_id"]),
            metadata=AttachmentMetadata(**metadata),
        )


@dataclass(frozen=True)
class PreparedLocalAttachment:
    metadata: AttachmentMetadata
    data: bytes = field(repr=False)

    def to_evidence_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-local-attachment-evidence-v1",
            **self.metadata.to_dict(),
            "raw_bytes_persisted": False,
            "remote_url_used": False,
            "provider_file_id_used": False,
        }
