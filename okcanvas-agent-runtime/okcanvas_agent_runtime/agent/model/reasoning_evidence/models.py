from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReasoningEvidencePolicy:
    schema_version: str
    policy_id: str
    version: str
    reasoning_summary_requested: bool
    response_include: tuple[str, ...]
    persist_reasoning_content: bool
    persist_reasoning_summary: bool
    persist_reasoning_item_ids: bool
    persist_reasoning_provider_data: bool
    persist_reasoning_token_count: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "reasoning_summary_requested": self.reasoning_summary_requested,
            "response_include": list(self.response_include),
            "persist_reasoning_content": self.persist_reasoning_content,
            "persist_reasoning_summary": self.persist_reasoning_summary,
            "persist_reasoning_item_ids": self.persist_reasoning_item_ids,
            "persist_reasoning_provider_data": self.persist_reasoning_provider_data,
            "persist_reasoning_token_count": self.persist_reasoning_token_count,
            "policy_sha256": self.policy_sha256,
        }
