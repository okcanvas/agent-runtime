"""Transport-neutral application boundary errors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApplicationBoundaryError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


# Historical name retained while canonical ownership moves out of Transport.
ControlAPIError = ApplicationBoundaryError

__all__ = ["ApplicationBoundaryError", "ControlAPIError"]
