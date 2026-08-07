"""Lazy public facade for tool-approval application services."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "EncryptedRunStateStore": ("okcanvas_agent_runtime.adapters.storage.run_state", "EncryptedRunStateStore"),
    "GovernedLocalToolApprovalService": ("okcanvas_agent_runtime.application.approvals.service", "GovernedLocalToolApprovalService"),
    "OpenAILocalToolApprovalGateway": ("okcanvas_agent_runtime.adapters.openai.local_tool_approval", "OpenAILocalToolApprovalGateway"),
    "SQLiteToolApprovalStore": ("okcanvas_agent_runtime.adapters.persistence.tool_approval", "SQLiteToolApprovalStore"),
    "ToolApprovalError": ("okcanvas_agent_runtime.application.approvals.errors", "ToolApprovalError"),
    "ToolApprovalDecision": ("okcanvas_agent_runtime.application.approvals.models", "ToolApprovalDecision"),
    "ToolApprovalConfirmationError": ("okcanvas_agent_runtime.application.approvals.errors", "ToolApprovalConfirmationError"),
    "decision_confirmation_challenge": ("okcanvas_agent_runtime.application.approvals.models", "decision_confirmation_challenge"),
    "ToolApprovalGateway": ("okcanvas_agent_runtime.application.approvals.gateway", "ToolApprovalGateway"),
    "ToolApprovalGatewayPrepare": ("okcanvas_agent_runtime.application.approvals.gateway", "ToolApprovalGatewayPrepare"),
    "ToolApprovalGatewayResume": ("okcanvas_agent_runtime.application.approvals.gateway", "ToolApprovalGatewayResume"),
    "ToolApprovalIntegrityError": ("okcanvas_agent_runtime.application.approvals.errors", "ToolApprovalIntegrityError"),
    "ToolApprovalNotFound": ("okcanvas_agent_runtime.application.approvals.errors", "ToolApprovalNotFound"),
    "ToolApprovalPrepareResult": ("okcanvas_agent_runtime.application.approvals.models", "ToolApprovalPrepareResult"),
    "ToolApprovalRecord": ("okcanvas_agent_runtime.application.approvals.models", "ToolApprovalRecord"),
    "ToolApprovalResumeResult": ("okcanvas_agent_runtime.application.approvals.models", "ToolApprovalResumeResult"),
    "ToolApprovalState": ("okcanvas_agent_runtime.application.approvals.models", "ToolApprovalState"),
    "ToolApprovalStateError": ("okcanvas_agent_runtime.application.approvals.errors", "ToolApprovalStateError"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = list(_EXPORTS)
