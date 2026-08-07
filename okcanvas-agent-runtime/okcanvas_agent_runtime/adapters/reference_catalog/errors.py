from __future__ import annotations


class ReferenceCatalogError(RuntimeError):
    """Base error for immutable reference catalog operations."""

    code = "REFERENCE_CATALOG_ERROR"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ReferenceManifestError(ReferenceCatalogError):
    code = "REFERENCE_MANIFEST_ERROR"


class ReferenceNotFoundError(ReferenceCatalogError):
    code = "REFERENCE_NOT_FOUND"


class ReferenceIntegrityError(ReferenceCatalogError):
    code = "REFERENCE_INTEGRITY_ERROR"


class ReferencePathError(ReferenceCatalogError):
    code = "REFERENCE_PATH_ERROR"


class ReferenceContentError(ReferenceCatalogError):
    code = "REFERENCE_CONTENT_ERROR"


class ReferenceQueryError(ReferenceCatalogError):
    code = "REFERENCE_QUERY_ERROR"
