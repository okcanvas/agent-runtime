"""Lazy public facade for okcanvas_agent_runtime/application/submissions."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'GovernedExecutionLifecycleService': ('okcanvas_agent_runtime.application.submissions.lifecycle', 'GovernedExecutionLifecycleService'),
    'GovernedLifecyclePolicy': ('okcanvas_agent_runtime.application.submissions.lifecycle', 'GovernedLifecyclePolicy'),
    'GovernedLifecyclePolicyCatalog': ('okcanvas_agent_runtime.application.submissions.lifecycle', 'GovernedLifecyclePolicyCatalog'),
    'GovernedReadOnlyRunSubmissionService': ('okcanvas_agent_runtime.application.submissions.execution', 'GovernedReadOnlyRunSubmissionService'),
    'GovernedRunSubmissionResult': ('okcanvas_agent_runtime.application.submissions.models', 'GovernedRunSubmissionResult'),
    'OrphanedRunReconciliationResult': ('okcanvas_agent_runtime.application.submissions.models', 'OrphanedRunReconciliationResult'),
    'ExecutionClaim': ('okcanvas_agent_runtime.application.submissions.models', 'ExecutionClaim'),
    'ProtectedPayloadRetentionState': ('okcanvas_agent_runtime.application.submissions.models', 'ProtectedPayloadRetentionState'),
    'RecoveryResult': ('okcanvas_agent_runtime.application.submissions.models', 'RecoveryResult'),
    'RetentionCleanupResult': ('okcanvas_agent_runtime.application.submissions.models', 'RetentionCleanupResult'),
    'TerminalOutcomeReconciliationResult': ('okcanvas_agent_runtime.application.submissions.models', 'TerminalOutcomeReconciliationResult'),
    'RunSubmissionAuthorityError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionAuthorityError'),
    'RunSubmissionBoundaryService': ('okcanvas_agent_runtime.application.submissions.service', 'RunSubmissionBoundaryService'),
    'RunSubmissionConfirmationError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionConfirmationError'),
    'RunSubmissionDecision': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionDecision'),
    'RunSubmissionError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionError'),
    'RunSubmissionExecutionMode': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionExecutionMode'),
    'RunExecutionOwnershipTransition': ('okcanvas_agent_runtime.application.submissions.models', 'RunExecutionOwnershipTransition'),
    'RunSubmissionIdempotencyConflict': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionIdempotencyConflict'),
    'RunSubmissionOwnershipTransition': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionOwnershipTransition'),
    'RunSubmissionIntegrityError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionIntegrityError'),
    'RunSubmissionNotFound': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionNotFound'),
    'RunSubmissionPolicy': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionPolicy'),
    'RunSubmissionPolicyCatalog': ('okcanvas_agent_runtime.application.submissions.policy', 'RunSubmissionPolicyCatalog'),
    'RunSubmissionPolicyError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionPolicyError'),
    'RunSubmissionRecordState': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionRecordState'),
    'RunSubmissionSourceBinding': ('okcanvas_agent_runtime.application.submissions.models', 'RunSubmissionSourceBinding'),
    'RunSubmissionStateError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionStateError'),
    'RunSubmissionValidationError': ('okcanvas_agent_runtime.application.submissions.errors', 'RunSubmissionValidationError'),
    'SQLiteRunSubmissionStore': ('okcanvas_agent_runtime.adapters.persistence.run_submission', 'SQLiteRunSubmissionStore'),
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
