from __future__ import annotations


class ProtectedPayloadError(RuntimeError):
    code = "PROTECTED_PAYLOAD_ERROR"


class ProtectedPayloadKeyError(ProtectedPayloadError):
    code = "PROTECTED_PAYLOAD_KEY_INVALID"


class ProtectedPayloadIntegrityError(ProtectedPayloadError):
    code = "PROTECTED_PAYLOAD_INTEGRITY_FAILED"


class ProtectedPayloadNotFound(ProtectedPayloadError):
    code = "PROTECTED_PAYLOAD_NOT_FOUND"


class ProtectedPayloadPathError(ProtectedPayloadError):
    code = "PROTECTED_PAYLOAD_PATH_INVALID"
