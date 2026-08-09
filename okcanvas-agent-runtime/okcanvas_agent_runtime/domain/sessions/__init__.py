"""Lazy public facade for okcanvas_agent_runtime/domain/sessions."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'BoundedEncryptedCompactionSession': ('okcanvas_agent_runtime.domain.sessions.compaction', 'BoundedEncryptedCompactionSession'),
    'CompactionEventSink': ('okcanvas_agent_runtime.domain.sessions.compaction', 'CompactionEventSink'),
    'select_compaction_candidate_items': ('okcanvas_agent_runtime.domain.sessions.compaction', 'select_compaction_candidate_items'),
    'SQLiteSessionApprovalPolicy': ('okcanvas_agent_runtime.domain.sessions.approval_policy', 'SQLiteSessionApprovalPolicy'),
    'SQLiteSessionApprovalPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.approval_policy', 'SQLiteSessionApprovalPolicyCatalog'),
    'SQLiteSessionAgentToolPolicy': ('okcanvas_agent_runtime.domain.sessions.agent_tool_policy', 'SQLiteSessionAgentToolPolicy'),
    'SQLiteSessionAgentToolPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.agent_tool_policy', 'SQLiteSessionAgentToolPolicyCatalog'),
    'SQLiteSessionHandoffPolicy': ('okcanvas_agent_runtime.domain.sessions.handoff_policy', 'SQLiteSessionHandoffPolicy'),
    'SQLiteSessionHandoffPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.handoff_policy', 'SQLiteSessionHandoffPolicyCatalog'),
    'SQLiteSessionGuardrailPolicy': ('okcanvas_agent_runtime.domain.sessions.guardrail_policy', 'SQLiteSessionGuardrailPolicy'),
    'SQLiteSessionGuardrailPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.guardrail_policy', 'SQLiteSessionGuardrailPolicyCatalog'),
    'SQLiteSessionMCPPolicy': ('okcanvas_agent_runtime.domain.sessions.mcp_policy', 'SQLiteSessionMCPPolicy'),
    'SQLiteSessionMCPPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.mcp_policy', 'SQLiteSessionMCPPolicyCatalog'),
    'ProductSessionRecord': ('okcanvas_agent_runtime.domain.sessions.models', 'ProductSessionRecord'),
    'ProductSessionState': ('okcanvas_agent_runtime.domain.sessions.models', 'ProductSessionState'),
    'SQLiteSessionPolicy': ('okcanvas_agent_runtime.domain.sessions.models', 'SQLiteSessionPolicy'),
    'SessionContextFocusState': ('okcanvas_agent_runtime.domain.sessions.context_focus', 'SessionContextFocusState'),
    'SessionContextEntityRef': ('okcanvas_agent_runtime.domain.sessions.context_focus', 'SessionContextEntityRef'),
    'SessionContextFocusObservation': ('okcanvas_agent_runtime.domain.sessions.context_focus', 'SessionContextFocusObservation'),
    'SessionContextFocusRecord': ('okcanvas_agent_runtime.domain.sessions.context_focus', 'SessionContextFocusRecord'),
    'SQLiteSessionPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.policy', 'SQLiteSessionPolicyCatalog'),
    'SQLiteSessionRuntimeService': ('okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service', 'SQLiteSessionRuntimeService'),
    'SQLiteSessionKeyRotationPolicy': ('okcanvas_agent_runtime.domain.sessions.rotation_policy', 'SQLiteSessionKeyRotationPolicy'),
    'SQLiteSessionKeyRotationPolicyCatalog': ('okcanvas_agent_runtime.domain.sessions.rotation_policy', 'SQLiteSessionKeyRotationPolicyCatalog'),
    'SessionKeyRotationResult': ('okcanvas_agent_runtime.adapters.persistence.sessions.rotation', 'SessionKeyRotationResult'),
    'SQLiteSessionHistoryRotator': ('okcanvas_agent_runtime.adapters.persistence.sessions.rotation', 'SQLiteSessionHistoryRotator'),
    'SessionHistoryKey': ('okcanvas_agent_runtime.adapters.storage.session_history', 'SessionHistoryKey'),
    'StrictEncryptedSession': ('okcanvas_agent_runtime.adapters.storage.session_history', 'StrictEncryptedSession'),
    'generate_session_history_key': ('okcanvas_agent_runtime.adapters.storage.session_history', 'generate_session_history_key'),
    'SessionRuntimeError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionRuntimeError'),
    'SessionPolicyError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionPolicyError'),
    'SessionConfigurationError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionConfigurationError'),
    'SessionNotFound': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionNotFound'),
    'SessionStateError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionStateError'),
    'SessionBusyError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionBusyError'),
    'SessionIntegrityError': ('okcanvas_agent_runtime.domain.sessions.errors', 'SessionIntegrityError'),
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
