"""Lazy public facade for okcanvas_agent_runtime/domain/attachments."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'AttachmentError': ('okcanvas_agent_runtime.domain.attachments.errors', 'AttachmentError'),
    'AttachmentIntegrityError': ('okcanvas_agent_runtime.domain.attachments.errors', 'AttachmentIntegrityError'),
    'AttachmentNotFound': ('okcanvas_agent_runtime.domain.attachments.errors', 'AttachmentNotFound'),
    'AttachmentPolicyError': ('okcanvas_agent_runtime.domain.attachments.errors', 'AttachmentPolicyError'),
    'AttachmentValidationError': ('okcanvas_agent_runtime.domain.attachments.errors', 'AttachmentValidationError'),
    'AttachmentMetadata': ('okcanvas_agent_runtime.domain.attachments.models', 'AttachmentMetadata'),
    'AttachmentRecord': ('okcanvas_agent_runtime.domain.attachments.models', 'AttachmentRecord'),
    'PreparedLocalAttachment': ('okcanvas_agent_runtime.domain.attachments.models', 'PreparedLocalAttachment'),
    'ProtectedAttachmentBinding': ('okcanvas_agent_runtime.domain.attachments.models', 'ProtectedAttachmentBinding'),
    'LocalAttachmentPolicy': ('okcanvas_agent_runtime.domain.attachments.policy', 'LocalAttachmentPolicy'),
    'LocalAttachmentPolicyCatalog': ('okcanvas_agent_runtime.domain.attachments.policy', 'LocalAttachmentPolicyCatalog'),
    'MultimodalModelPolicy': ('okcanvas_agent_runtime.domain.attachments.model_policy', 'MultimodalModelPolicy'),
    'MultimodalModelPolicyCatalog': ('okcanvas_agent_runtime.domain.attachments.model_policy', 'MultimodalModelPolicyCatalog'),
    'normalize_filename': ('okcanvas_agent_runtime.domain.attachments.validation', 'normalize_filename'),
    'validate_local_attachment': ('okcanvas_agent_runtime.domain.attachments.validation', 'validate_local_attachment'),
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
