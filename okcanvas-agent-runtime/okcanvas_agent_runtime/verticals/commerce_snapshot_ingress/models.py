from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.application.submissions import RunSubmissionSourceBinding


@dataclass(frozen=True)
class CommerceSnapshotAdapterDefinition:
    schema_version: str
    adapter_id: str
    version: str
    name: str
    kind: str
    base_url_env: str
    credential_env: str
    auth_scheme: str
    method: str
    path_template: str
    loopback_only: bool
    follow_redirects: bool
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_response_bytes: int
    max_items: int
    max_retry_attempts: int
    definition_sha256: str
    definition_path: Path

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "version": self.version,
            "name": self.name,
            "kind": self.kind,
            "auth_scheme": self.auth_scheme,
            "method": self.method,
            "path_template": self.path_template,
            "loopback_only": self.loopback_only,
            "follow_redirects": self.follow_redirects,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "read_timeout_seconds": self.read_timeout_seconds,
            "max_response_bytes": self.max_response_bytes,
            "max_items": self.max_items,
            "max_retry_attempts": self.max_retry_attempts,
            "definition_sha256": self.definition_sha256,
        }


@dataclass(frozen=True)
class CommerceSnapshotAcquisition:
    canonical_request: str
    source_binding: RunSubmissionSourceBinding
