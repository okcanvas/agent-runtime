from __future__ import annotations


class ModelRoutingError(RuntimeError):
    """Base error for immutable model routing policy failures."""


class ModelRoutingPolicyError(ModelRoutingError):
    """Raised when the product-owned routing policy is invalid or unsafe."""


class ModelRouteDeniedError(ModelRoutingError):
    """Raised when a requested model is outside the accepted route."""
