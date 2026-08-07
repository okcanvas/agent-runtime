from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderIdentifierPolicy:
    schema_version: str
    policy_id: str
    version: str
    persist_response_id: bool
    persist_request_id: bool
    persist_identifier_presence: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "persist_response_id": self.persist_response_id,
            "persist_request_id": self.persist_request_id,
            "persist_identifier_presence": self.persist_identifier_presence,
            "policy_sha256": self.policy_sha256,
        }
