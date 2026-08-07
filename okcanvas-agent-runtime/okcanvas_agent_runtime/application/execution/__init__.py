"""Lazy public facade for okcanvas_agent_runtime/application/execution."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'AgentRuntimeBinding': ('okcanvas_agent_runtime.bootstrap.runtime_binding', 'AgentRuntimeBinding'),
    'AgentRuntimeBindingCatalog': ('okcanvas_agent_runtime.bootstrap.runtime_binding', 'AgentRuntimeBindingCatalog'),
    'GatewayLifecycleEvent': ('okcanvas_agent_runtime.application.execution.contracts', 'GatewayLifecycleEvent'),
    'GenericAgentExecutionService': ('okcanvas_agent_runtime.application.execution.service', 'GenericAgentExecutionService'),
    'GenericAgentGateway': ('okcanvas_agent_runtime.application.execution.gateway', 'GenericAgentGateway'),
    'GenericExecutionEnvelope': ('okcanvas_agent_runtime.application.execution.contracts', 'GenericExecutionEnvelope'),
    'GenericExecutionError': ('okcanvas_agent_runtime.application.execution.contracts', 'GenericExecutionError'),
    'GenericExecutionErrorCode': ('okcanvas_agent_runtime.application.execution.contracts', 'GenericExecutionErrorCode'),
    'GenericExecutionFailure': ('okcanvas_agent_runtime.application.execution.errors', 'GenericExecutionFailure'),
    'GenericGatewayRunResult': ('okcanvas_agent_runtime.application.execution.contracts', 'GenericGatewayRunResult'),
    'LifecycleSink': ('okcanvas_agent_runtime.application.execution.gateway', 'LifecycleSink'),
    'OpenAIGenericAgentGateway': ('okcanvas_agent_runtime.adapters.openai.generic_gateway', 'OpenAIGenericAgentGateway'),
    'OutputContractRuntime': ('okcanvas_agent_runtime.application.execution.output_registry', 'OutputContractRuntime'),
    'list_output_contracts': ('okcanvas_agent_runtime.application.execution.output_registry', 'list_output_contracts'),
    'resolve_output_contract': ('okcanvas_agent_runtime.application.execution.output_registry', 'resolve_output_contract'),
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
