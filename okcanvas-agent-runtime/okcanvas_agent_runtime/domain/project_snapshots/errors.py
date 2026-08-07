from __future__ import annotations


class ProjectSnapshotError(RuntimeError):
    pass


class ProjectSnapshotPolicyError(ProjectSnapshotError):
    pass


class ProjectSnapshotValidationError(ProjectSnapshotError):
    pass


class ProjectSnapshotIntegrityError(ProjectSnapshotError):
    pass


class ProjectSnapshotNotFound(ProjectSnapshotError):
    pass
