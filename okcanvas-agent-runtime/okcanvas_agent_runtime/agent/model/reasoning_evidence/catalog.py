from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.reasoning_evidence.errors import ReasoningEvidencePolicyError
from okcanvas_agent_runtime.agent.model.reasoning_evidence.models import ReasoningEvidencePolicy


class ReasoningEvidencePolicyCatalog:
    """Load the single reasoning-evidence minimization policy."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/reasoning-evidence-policy.json"

    def resolve(self) -> ReasoningEvidencePolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise ReasoningEvidencePolicyError("Reasoning evidence policy is missing or unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReasoningEvidencePolicyError("Reasoning evidence policy could not be decoded") from exc
        if not isinstance(payload, dict):
            raise ReasoningEvidencePolicyError("Reasoning evidence policy must be an object")
        expected = {
            "schema_version", "policy_id", "version", "reasoning_summary_requested",
            "response_include", "persist_reasoning_content", "persist_reasoning_summary",
            "persist_reasoning_item_ids", "persist_reasoning_provider_data",
            "persist_reasoning_token_count",
        }
        if set(payload) != expected:
            raise ReasoningEvidencePolicyError("Reasoning evidence policy fields are not exact")
        if payload["schema_version"] != "okcanvas-reasoning-evidence-policy-v1":
            raise ReasoningEvidencePolicyError("Unsupported reasoning evidence policy schema")
        if payload["policy_id"] != "local-openai-reasoning-evidence-minimization-v1":
            raise ReasoningEvidencePolicyError("STEP053 permits only the minimization policy")
        version = payload["version"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise ReasoningEvidencePolicyError("Reasoning evidence policy version is invalid")
        exact_false = (
            "reasoning_summary_requested", "persist_reasoning_content",
            "persist_reasoning_summary", "persist_reasoning_item_ids",
            "persist_reasoning_provider_data",
        )
        if any(payload[name] is not False for name in exact_false):
            raise ReasoningEvidencePolicyError("Reasoning content and identity persistence must be disabled")
        if payload["response_include"] != []:
            raise ReasoningEvidencePolicyError("Additional reasoning response includes are forbidden")
        if payload["persist_reasoning_token_count"] is not True:
            raise ReasoningEvidencePolicyError("Only the non-content reasoning token count is retained")
        canonical = self._canonical(payload)
        return ReasoningEvidencePolicy(
            schema_version=payload["schema_version"], policy_id=payload["policy_id"],
            version=version, reasoning_summary_requested=False, response_include=(),
            persist_reasoning_content=False, persist_reasoning_summary=False,
            persist_reasoning_item_ids=False, persist_reasoning_provider_data=False,
            persist_reasoning_token_count=True,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
