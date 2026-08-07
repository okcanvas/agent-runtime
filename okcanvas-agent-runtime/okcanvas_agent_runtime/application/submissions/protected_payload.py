from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from okcanvas_agent_runtime.domain.attachments.models import ProtectedAttachmentBinding
from okcanvas_agent_runtime.domain.project_snapshots.models import ProtectedProjectSnapshotBinding
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity


@dataclass(frozen=True)
class ProtectedPayloadContent:
    submission_id: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    session_id: str | None
    model: str
    request: str
    input_sha256: str
    request_fingerprint_sha256: str
    created_at: str
    attachment: ProtectedAttachmentBinding | None = None
    project_snapshot: ProtectedProjectSnapshotBinding | None = None
    delegated_mcp_identity: DelegatedMCPIdentity | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["attachment"] = self.attachment.to_dict() if self.attachment is not None else None
        payload["project_snapshot"] = (
            self.project_snapshot.to_dict() if self.project_snapshot is not None else None
        )
        payload["delegated_mcp_identity"] = (
            self.delegated_mcp_identity.to_protected_dict() if self.delegated_mcp_identity is not None else None
        )
        return {
            "schema_version": "okcanvas-protected-payload-content-v6",
            **payload,
        }


@dataclass(frozen=True)
class ProtectedPayloadRecord:
    payload_ref: str
    file_sha256: str
    byte_length: int
    key_id: str
    algorithm: str
    created_at: str

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)
