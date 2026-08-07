from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.provider_identity.errors import ProviderIdentifierPolicyError
from okcanvas_agent_runtime.agent.model.provider_identity.models import ProviderIdentifierPolicy


class ProviderIdentifierPolicyCatalog:
    """Load the single OpenAI provider-identifier minimization policy."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/openai-provider-identifier-policy.json"

    def resolve(self) -> ProviderIdentifierPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise ProviderIdentifierPolicyError("OpenAI provider-identifier policy is missing or unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderIdentifierPolicyError(
                "OpenAI provider-identifier policy could not be decoded"
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderIdentifierPolicyError("OpenAI provider-identifier policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "persist_response_id",
            "persist_request_id",
            "persist_identifier_presence",
        }
        if set(payload) != expected:
            raise ProviderIdentifierPolicyError("OpenAI provider-identifier policy fields are not exact")
        if payload["schema_version"] != "okcanvas-openai-provider-identifier-policy-v1":
            raise ProviderIdentifierPolicyError("Unsupported OpenAI provider-identifier policy schema")
        if payload["policy_id"] != "local-openai-provider-identifier-minimization-v1":
            raise ProviderIdentifierPolicyError("STEP055 permits only the identifier-minimization policy")
        version = payload["version"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise ProviderIdentifierPolicyError("OpenAI provider-identifier policy version is invalid")
        if payload["persist_response_id"] is not False:
            raise ProviderIdentifierPolicyError("OpenAI response IDs must not be persisted")
        if payload["persist_request_id"] is not False:
            raise ProviderIdentifierPolicyError("OpenAI request IDs must not be persisted")
        if payload["persist_identifier_presence"] is not True:
            raise ProviderIdentifierPolicyError("Only identifier presence evidence must remain enabled")
        canonical = self._canonical(payload)
        return ProviderIdentifierPolicy(
            schema_version=payload["schema_version"],
            policy_id=payload["policy_id"],
            version=version,
            persist_response_id=False,
            persist_request_id=False,
            persist_identifier_presence=True,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
