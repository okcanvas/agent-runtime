from __future__ import annotations

import hashlib

from okcanvas_agent_runtime.agent.tools.function.models import LocalTextFingerprintOutput, LocalTextMetricsOutput, ProjectEvidenceOutput, ProjectReadonlyInspectOutput, SandboxProjectReadonlyInspectOutput


_MAX_TEXT_CHARS = 1_000_000


def _validate_text(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Protected local text must be a non-empty non-NUL string")
    if len(value) > _MAX_TEXT_CHARS:
        raise ValueError("Protected local text exceeds the bounded Tool input")
    return value


def local_text_fingerprint(value: str) -> LocalTextFingerprintOutput:
    text = _validate_text(value)
    encoded = text.encode("utf-8")
    return LocalTextFingerprintOutput(
        sha256=hashlib.sha256(encoded).hexdigest(),
        utf8_bytes=len(encoded),
        characters=len(text),
    )


def local_text_metrics(value: str) -> LocalTextMetricsOutput:
    text = _validate_text(value)
    fingerprint = local_text_fingerprint(text)
    return LocalTextMetricsOutput(
        sha256=fingerprint.sha256,
        utf8_bytes=fingerprint.utf8_bytes,
        characters=fingerprint.characters,
        words=len(text.split()),
        lines=len(text.splitlines()) or 1,
    )


def __getattr__(name: str):
    # Compatibility only: concrete workspace/Docker implementations live in Adapters.
    if name in {"project_readonly_inspect", "sandbox_project_readonly_inspect"}:
        from importlib import import_module
        return getattr(
            import_module("okcanvas_agent_runtime.adapters.workspace.tool_inspection"),
            name,
        )
    raise AttributeError(name)


__all__ = [
    "local_text_fingerprint",
    "local_text_metrics",
    "project_readonly_inspect",
    "sandbox_project_readonly_inspect",
]
