from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.retry.errors import ModelRetryPolicyError
from okcanvas_agent_runtime.agent.model.retry.models import ModelRetryPolicy


class ModelRetryPolicyCatalog:
    """Load one exact zero-retry policy for the immutable OpenAI route.

    STEP052 deliberately disables both provider-managed and Runner-managed retries. The installed
    SDK's conversation-locked compatibility path is also disabled by the explicit zero retry
    budget. A future bounded retry step requires separate replay and side-effect evidence.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/model-retry-policy.json"

    def resolve(self) -> ModelRetryPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise ModelRetryPolicyError("Model retry policy is missing or unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRetryPolicyError("Model retry policy could not be decoded") from exc
        if not isinstance(payload, dict):
            raise ModelRetryPolicyError("Model retry policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "runner_managed_max_retries",
            "provider_managed_max_retries",
            "retryable_categories",
            "conversation_locked_compatibility_retries",
            "automatic_model_fallback",
        }
        if set(payload) != expected:
            raise ModelRetryPolicyError("Model retry policy fields are not exact")
        if payload["schema_version"] != "okcanvas-model-retry-policy-v1":
            raise ModelRetryPolicyError("Unsupported model retry policy schema")
        if payload["policy_id"] != "local-openai-zero-retry-v1":
            raise ModelRetryPolicyError("STEP052 permits only the zero-retry policy")
        version = payload["version"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise ModelRetryPolicyError("Model retry policy version is invalid")
        if payload["runner_managed_max_retries"] != 0:
            raise ModelRetryPolicyError("Runner-managed model retries must be disabled")
        if payload["provider_managed_max_retries"] != 0:
            raise ModelRetryPolicyError("Provider-managed model retries must be disabled")
        if payload["retryable_categories"] != []:
            raise ModelRetryPolicyError("STEP052 has no retryable model error categories")
        if payload["conversation_locked_compatibility_retries"] is not False:
            raise ModelRetryPolicyError("Conversation-locked compatibility retries are disabled")
        if payload["automatic_model_fallback"] is not False:
            raise ModelRetryPolicyError("Automatic model fallback remains disabled")
        canonical = self._canonical(payload)
        return ModelRetryPolicy(
            schema_version=payload["schema_version"],
            policy_id=payload["policy_id"],
            version=payload["version"],
            runner_managed_max_retries=payload["runner_managed_max_retries"],
            provider_managed_max_retries=payload["provider_managed_max_retries"],
            retryable_categories=tuple(payload["retryable_categories"]),
            conversation_locked_compatibility_retries=payload[
                "conversation_locked_compatibility_retries"
            ],
            automatic_model_fallback=payload["automatic_model_fallback"],
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
