from __future__ import annotations

from okcanvas_agent_runtime.agent.model.trace_export.models import TraceExportPolicy


def build_sdk_trace_run_config_kwargs(policy: TraceExportPolicy) -> dict[str, object]:
    """Return explicit SDK RunConfig values that prevent provider trace export."""

    if not policy.sdk_tracing_disabled or policy.provider_trace_export_enabled:
        raise ValueError("OpenAI provider trace export must remain disabled")
    if policy.trace_include_sensitive_data:
        raise ValueError("Trace-sensitive data must remain disabled")
    return {
        "tracing_disabled": True,
        "trace_include_sensitive_data": False,
    }
