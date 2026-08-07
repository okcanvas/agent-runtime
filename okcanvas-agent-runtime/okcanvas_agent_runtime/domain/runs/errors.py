from __future__ import annotations


class ProductStateError(RuntimeError):
    """Base error for durable OKCanvas product state."""

    code = "PRODUCT_STATE_ERROR"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class RecordNotFoundError(ProductStateError):
    code = "RECORD_NOT_FOUND"


class DuplicateRecordError(ProductStateError):
    code = "DUPLICATE_RECORD"


class InvalidStateTransitionError(ProductStateError):
    code = "INVALID_STATE_TRANSITION"


class IntegrityContractError(ProductStateError):
    code = "INTEGRITY_CONTRACT_ERROR"


class ArtifactIntegrityError(ProductStateError):
    code = "ARTIFACT_INTEGRITY_ERROR"
