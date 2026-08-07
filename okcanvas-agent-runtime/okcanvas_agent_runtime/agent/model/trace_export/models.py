from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceExportPolicy:
    schema_version: str
    policy_id: str
    version: str
    sdk_tracing_disabled: bool
    provider_trace_export_enabled: bool
    trace_include_sensitive_data: bool
    persist_local_trace_id: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "sdk_tracing_disabled": self.sdk_tracing_disabled,
            "provider_trace_export_enabled": self.provider_trace_export_enabled,
            "trace_include_sensitive_data": self.trace_include_sensitive_data,
            "persist_local_trace_id": self.persist_local_trace_id,
            "policy_sha256": self.policy_sha256,
        }
