"""Lazy public facade for okcanvas_agent_runtime/domain/invocations."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'AgentInvocationRecord': ('okcanvas_agent_runtime.domain.invocations.models', 'AgentInvocationRecord'),
    'ChildAgentEdge': ('okcanvas_agent_runtime.domain.invocations.models', 'ChildAgentEdge'),
    'ChildAgentGraphResolver': ('okcanvas_agent_runtime.agent.subagents.invocation_graph', 'ChildAgentGraphResolver'),
    'InvocationGraphError': ('okcanvas_agent_runtime.domain.invocations.errors', 'InvocationGraphError'),
    'InvocationKind': ('okcanvas_agent_runtime.domain.invocations.models', 'InvocationKind'),
    'InvocationPolicy': ('okcanvas_agent_runtime.domain.invocations.models', 'InvocationPolicy'),
    'InvocationPolicyCatalog': ('okcanvas_agent_runtime.domain.invocations.policy', 'InvocationPolicyCatalog'),
    'InvocationPolicyError': ('okcanvas_agent_runtime.domain.invocations.errors', 'InvocationPolicyError'),
    'InvocationScopeError': ('okcanvas_agent_runtime.domain.invocations.errors', 'InvocationScopeError'),
    'InvocationState': ('okcanvas_agent_runtime.domain.invocations.models', 'InvocationState'),
    'InvocationStateError': ('okcanvas_agent_runtime.domain.invocations.errors', 'InvocationStateError'),
    'InvocationWorkspaceError': ('okcanvas_agent_runtime.domain.invocations.errors', 'InvocationWorkspaceError'),
    'InvocationWorkspacePlanner': ('okcanvas_agent_runtime.adapters.workspace.invocation_workspace', 'InvocationWorkspacePlanner'),
    'WorkspaceAccess': ('okcanvas_agent_runtime.domain.invocations.models', 'WorkspaceAccess'),
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
