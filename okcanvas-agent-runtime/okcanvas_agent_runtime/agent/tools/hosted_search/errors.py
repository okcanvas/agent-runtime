from __future__ import annotations


class HostedWebSearchError(RuntimeError):
    """Base error for the product-owned hosted Web Search boundary."""


class HostedWebSearchPolicyError(HostedWebSearchError):
    """Raised when the immutable hosted Web Search policy is missing or invalid."""


class HostedWebSearchEvidenceError(HostedWebSearchError):
    """Raised when SDK output does not satisfy the hosted Web Search evidence contract."""
