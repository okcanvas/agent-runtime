from __future__ import annotations


class CommerceSnapshotIngressError(RuntimeError):
    code = "COMMERCE_SNAPSHOT_INGRESS_ERROR"
    retryable = False


class CommerceSnapshotDefinitionError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_DEFINITION_INVALID"


class CommerceSnapshotConfigurationError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_SOURCE_NOT_CONFIGURED"


class CommerceSnapshotRequestError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_REQUEST_INVALID"


class CommerceSnapshotUnavailableError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_SOURCE_UNAVAILABLE"
    retryable = True


class CommerceSnapshotAuthenticationError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_SOURCE_AUTH_FAILED"


class CommerceSnapshotResponseError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_RESPONSE_REJECTED"


class CommerceSnapshotTooLargeError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_RESPONSE_TOO_LARGE"


class CommerceSnapshotValidationError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_INVALID"


class CommerceSnapshotIdentityMismatchError(CommerceSnapshotValidationError):
    code = "COMMERCE_SNAPSHOT_IDENTITY_MISMATCH"


class CommerceSnapshotReplayIntegrityError(CommerceSnapshotIngressError):
    code = "COMMERCE_SNAPSHOT_REPLAY_INTEGRITY_FAILED"
