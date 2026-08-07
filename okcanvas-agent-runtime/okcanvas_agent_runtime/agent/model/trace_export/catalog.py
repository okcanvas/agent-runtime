from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.model.trace_export.errors import TraceExportPolicyError
from okcanvas_agent_runtime.agent.model.trace_export.models import TraceExportPolicy


class TraceExportPolicyCatalog:
    """Load the single provider trace-export-disabled policy."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/openai-trace-export-policy.json"

    def resolve(self) -> TraceExportPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise TraceExportPolicyError("OpenAI trace-export policy is missing or unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TraceExportPolicyError("OpenAI trace-export policy could not be decoded") from exc
        if not isinstance(payload, dict):
            raise TraceExportPolicyError("OpenAI trace-export policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "sdk_tracing_disabled",
            "provider_trace_export_enabled",
            "trace_include_sensitive_data",
            "persist_local_trace_id",
        }
        if set(payload) != expected:
            raise TraceExportPolicyError("OpenAI trace-export policy fields are not exact")
        if payload["schema_version"] != "okcanvas-openai-trace-export-policy-v1":
            raise TraceExportPolicyError("Unsupported OpenAI trace-export policy schema")
        if payload["policy_id"] != "local-openai-trace-export-disabled-v1":
            raise TraceExportPolicyError("STEP072 permits only the trace-export-disabled policy")
        version = payload["version"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise TraceExportPolicyError("OpenAI trace-export policy version is invalid")
        if payload["sdk_tracing_disabled"] is not True:
            raise TraceExportPolicyError("OpenAI Agents SDK tracing must be explicitly disabled")
        if payload["provider_trace_export_enabled"] is not False:
            raise TraceExportPolicyError("Provider trace export must remain disabled")
        if payload["trace_include_sensitive_data"] is not False:
            raise TraceExportPolicyError("Trace-sensitive data must remain disabled")
        if payload["persist_local_trace_id"] is not True:
            raise TraceExportPolicyError("Product-local trace ID persistence must remain enabled")
        canonical = self._canonical(payload)
        return TraceExportPolicy(
            schema_version=payload["schema_version"],
            policy_id=payload["policy_id"],
            version=version,
            sdk_tracing_disabled=True,
            provider_trace_export_enabled=False,
            trace_include_sensitive_data=False,
            persist_local_trace_id=True,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
