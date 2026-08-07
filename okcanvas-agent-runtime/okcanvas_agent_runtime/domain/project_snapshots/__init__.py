"""Lazy public facade for okcanvas_agent_runtime/domain/project_snapshots."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    'ProjectSnapshotError': ('okcanvas_agent_runtime.domain.project_snapshots.errors', 'ProjectSnapshotError'),
    'ProjectSnapshotIntegrityError': ('okcanvas_agent_runtime.domain.project_snapshots.errors', 'ProjectSnapshotIntegrityError'),
    'ProjectSnapshotNotFound': ('okcanvas_agent_runtime.domain.project_snapshots.errors', 'ProjectSnapshotNotFound'),
    'ProjectSnapshotPolicyError': ('okcanvas_agent_runtime.domain.project_snapshots.errors', 'ProjectSnapshotPolicyError'),
    'ProjectSnapshotValidationError': ('okcanvas_agent_runtime.domain.project_snapshots.errors', 'ProjectSnapshotValidationError'),
    'PreparedProjectSnapshot': ('okcanvas_agent_runtime.domain.project_snapshots.models', 'PreparedProjectSnapshot'),
    'ProjectSnapshotFile': ('okcanvas_agent_runtime.domain.project_snapshots.models', 'ProjectSnapshotFile'),
    'ProjectSnapshotMetadata': ('okcanvas_agent_runtime.domain.project_snapshots.models', 'ProjectSnapshotMetadata'),
    'ProjectSnapshotRecord': ('okcanvas_agent_runtime.domain.project_snapshots.models', 'ProjectSnapshotRecord'),
    'ProtectedProjectSnapshotBinding': ('okcanvas_agent_runtime.domain.project_snapshots.models', 'ProtectedProjectSnapshotBinding'),
    'ProjectSnapshotPolicy': ('okcanvas_agent_runtime.domain.project_snapshots.policy', 'ProjectSnapshotPolicy'),
    'ProjectSnapshotPolicyCatalog': ('okcanvas_agent_runtime.domain.project_snapshots.policy', 'ProjectSnapshotPolicyCatalog'),
    'materialize_project_snapshot': ('okcanvas_agent_runtime.adapters.workspace.project_snapshot_materialization', 'materialize_project_snapshot'),
    'normalize_snapshot_filename': ('okcanvas_agent_runtime.domain.project_snapshots.validation', 'normalize_snapshot_filename'),
    'validate_project_snapshot_zip': ('okcanvas_agent_runtime.domain.project_snapshots.validation', 'validate_project_snapshot_zip'),
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
