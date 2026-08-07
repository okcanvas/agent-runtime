from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class NestedResultNormalization:
    """Product-owned normalized Child Agent result and bounded public evidence."""

    output: BaseModel
    metadata: dict[str, object]
