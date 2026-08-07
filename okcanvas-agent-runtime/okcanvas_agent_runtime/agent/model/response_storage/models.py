from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseStoragePolicy:
    schema_version: str
    policy_id: str
    version: str
    response_store_requested: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "response_store_requested": self.response_store_requested,
            "policy_sha256": self.policy_sha256,
        }
