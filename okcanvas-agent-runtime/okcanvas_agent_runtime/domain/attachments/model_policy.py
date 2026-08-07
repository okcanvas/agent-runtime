from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.attachments.errors import AttachmentPolicyError


@dataclass(frozen=True)
class MultimodalModelPolicy:
    schema_version: str
    policy_id: str
    version: str
    provider_id: str
    api: str
    allowed_model_ids: tuple[str, ...]
    input_file: bool
    input_image: bool
    structured_output: bool
    store: bool
    policy_sha256: str

    def validate_model(self, model: str | None) -> str:
        normalized = model.strip() if model else ""
        if normalized not in self.allowed_model_ids:
            raise AttachmentPolicyError(
                "Local attachment execution requires an explicitly allowed multimodal model"
            )
        return normalized

    def to_binding_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "provider_id": self.provider_id,
            "api": self.api,
            "allowed_model_ids": list(self.allowed_model_ids),
            "input_file": self.input_file,
            "input_image": self.input_image,
            "structured_output": self.structured_output,
            "store": self.store,
            "policy_sha256": self.policy_sha256,
        }


class MultimodalModelPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "attachments" / "policies" / "multimodal-model-v1.json"

    def resolve(self) -> MultimodalModelPolicy:
        path = self.path.resolve()
        expected_parent = (self.project_root / "specs" / "attachments" / "policies").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise AttachmentPolicyError("Multimodal model policy is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentPolicyError("Multimodal model policy is invalid JSON") from exc
        expected = {
            "schema_version", "policy_id", "version", "provider_id", "api",
            "allowed_model_ids", "input_file", "input_image", "structured_output", "store",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise AttachmentPolicyError("Multimodal model policy fields are not exact")
        if payload["schema_version"] != "okcanvas-multimodal-model-policy-v1":
            raise AttachmentPolicyError("Unsupported multimodal model policy schema")
        if payload["policy_id"] != "openai-responses-local-pdf-image-model-v1" or payload["version"] != "1.0.0":
            raise AttachmentPolicyError("Multimodal model policy identity is invalid")
        if payload["provider_id"] != "openai" or payload["api"] != "responses":
            raise AttachmentPolicyError("STEP068 requires OpenAI Responses")
        if payload["allowed_model_ids"] != ["gpt-4.1"]:
            raise AttachmentPolicyError("STEP068 model allowlist is invalid")
        if payload["input_file"] is not True or payload["input_image"] is not True or payload["structured_output"] is not True or payload["store"] is not False:
            raise AttachmentPolicyError("Multimodal model capability flags are invalid")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        values = dict(payload)
        values["allowed_model_ids"] = tuple(payload["allowed_model_ids"])
        return MultimodalModelPolicy(
            **values,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
