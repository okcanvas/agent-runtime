from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.response_storage.errors import ResponseStoragePolicyError
from okcanvas_agent_runtime.agent.model.response_storage.models import ResponseStoragePolicy


class ResponseStoragePolicyCatalog:
    """Load the single OpenAI Responses storage-disabled request policy."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/openai-response-storage-policy.json"

    def resolve(self) -> ResponseStoragePolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise ResponseStoragePolicyError("OpenAI response-storage policy is missing or unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResponseStoragePolicyError(
                "OpenAI response-storage policy could not be decoded"
            ) from exc
        if not isinstance(payload, dict):
            raise ResponseStoragePolicyError("OpenAI response-storage policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "response_store_requested",
        }
        if set(payload) != expected:
            raise ResponseStoragePolicyError("OpenAI response-storage policy fields are not exact")
        if payload["schema_version"] != "okcanvas-openai-response-storage-policy-v1":
            raise ResponseStoragePolicyError("Unsupported OpenAI response-storage policy schema")
        if payload["policy_id"] != "local-openai-response-storage-disabled-v1":
            raise ResponseStoragePolicyError("STEP054 permits only the storage-disabled policy")
        version = payload["version"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise ResponseStoragePolicyError("OpenAI response-storage policy version is invalid")
        if payload["response_store_requested"] is not False:
            raise ResponseStoragePolicyError("OpenAI Responses store must be explicitly disabled")
        canonical = self._canonical(payload)
        return ResponseStoragePolicy(
            schema_version=payload["schema_version"],
            policy_id=payload["policy_id"],
            version=version,
            response_store_requested=False,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
