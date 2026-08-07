from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.routing.errors import ModelRouteDeniedError, ModelRoutingPolicyError
from okcanvas_agent_runtime.agent.model.routing.models import ModelRoutingPolicy, ResolvedModelRoute


_EXPECTED_SCHEMA = "okcanvas-model-routing-policy-v1"
_EXPECTED_PROVIDER = "openai"
_EXPECTED_ADAPTER = "agents.models.openai_provider.OpenAIProvider"
_EXPECTED_API = "responses"
_EXPECTED_TRANSPORT = "http"
_EXPECTED_BASE_URL = "https://api.openai.com/v1"


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ModelRoutingPolicyCatalog:
    """Load the single product-owned OpenAI Responses/HTTP route.

    STEP051 intentionally does not implement a provider matrix or fallback chain. A selected
    model remains per-Run input, but the provider, API, transport and endpoint are immutable.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "runtime" / "model-routing-policy.json"

    def resolve(self) -> ModelRoutingPolicy:
        path = self.path
        if path.is_symlink() or not path.is_file():
            raise ModelRoutingPolicyError("Model routing policy is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRoutingPolicyError("Model routing policy is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ModelRoutingPolicyError("Model routing policy must be an object")
        required = {
            "schema_version",
            "policy_id",
            "version",
            "provider_id",
            "provider_adapter",
            "api",
            "transport",
            "base_url",
            "model_id_pattern",
            "allow_provider_prefixes",
            "automatic_fallback",
            "fallback_model_ids",
            "trace_include_sensitive_data",
        }
        if set(payload) != required:
            raise ModelRoutingPolicyError("Model routing policy fields are not exact")
        if payload["schema_version"] != _EXPECTED_SCHEMA:
            raise ModelRoutingPolicyError("Unsupported model routing policy schema")
        if payload["provider_id"] != _EXPECTED_PROVIDER:
            raise ModelRoutingPolicyError("STEP051 permits only the OpenAI provider")
        if payload["provider_adapter"] != _EXPECTED_ADAPTER:
            raise ModelRoutingPolicyError("STEP051 requires the installed SDK OpenAIProvider")
        if payload["api"] != _EXPECTED_API or payload["transport"] != _EXPECTED_TRANSPORT:
            raise ModelRoutingPolicyError("STEP051 requires Responses over HTTP")
        if payload["base_url"] != _EXPECTED_BASE_URL:
            raise ModelRoutingPolicyError("STEP051 requires the official OpenAI API base URL")
        if payload["allow_provider_prefixes"] is not False:
            raise ModelRoutingPolicyError("STEP051 forbids provider-prefixed model routes")
        if payload["automatic_fallback"] is not False or payload["fallback_model_ids"] != []:
            raise ModelRoutingPolicyError("STEP051 forbids automatic model fallback")
        if payload["trace_include_sensitive_data"] is not False:
            raise ModelRoutingPolicyError("STEP051 requires sensitive trace data to be disabled")
        for key in ("policy_id", "version", "model_id_pattern"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ModelRoutingPolicyError(f"{key} must be a non-empty string")
        try:
            re.compile(payload["model_id_pattern"])
        except re.error as exc:
            raise ModelRoutingPolicyError("Model ID pattern is invalid") from exc
        return ModelRoutingPolicy(
            schema_version=payload["schema_version"],
            policy_id=payload["policy_id"],
            version=payload["version"],
            provider_id=payload["provider_id"],
            provider_adapter=payload["provider_adapter"],
            api=payload["api"],
            transport=payload["transport"],
            base_url=payload["base_url"],
            model_id_pattern=payload["model_id_pattern"],
            allow_provider_prefixes=payload["allow_provider_prefixes"],
            automatic_fallback=payload["automatic_fallback"],
            fallback_model_ids=tuple(payload["fallback_model_ids"]),
            trace_include_sensitive_data=payload["trace_include_sensitive_data"],
            policy_sha256=_canonical_sha(payload),
        )

    def resolve_model(self, model: str | None) -> ResolvedModelRoute:
        if model is None or not model.strip():
            raise ModelRouteDeniedError("A concrete model is required by the model route policy")
        normalized = model.strip()
        policy = self.resolve()
        if "/" in normalized or not re.fullmatch(policy.model_id_pattern, normalized):
            raise ModelRouteDeniedError(
                "Model ID is outside the immutable OpenAI Responses route"
            )
        return ResolvedModelRoute(policy=policy, model_id=normalized)
