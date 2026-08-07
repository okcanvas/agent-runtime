from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRetryPolicy:
    schema_version: str
    policy_id: str
    version: str
    runner_managed_max_retries: int
    provider_managed_max_retries: int
    retryable_categories: tuple[str, ...]
    conversation_locked_compatibility_retries: bool
    automatic_model_fallback: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "runner_managed_max_retries": self.runner_managed_max_retries,
            "provider_managed_max_retries": self.provider_managed_max_retries,
            "retryable_categories": list(self.retryable_categories),
            "conversation_locked_compatibility_retries": (
                self.conversation_locked_compatibility_retries
            ),
            "automatic_model_fallback": self.automatic_model_fallback,
            "policy_sha256": self.policy_sha256,
        }
