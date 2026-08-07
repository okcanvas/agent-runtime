from __future__ import annotations

from dataclasses import asdict, dataclass

from okcanvas_agent_runtime.core.runtime_info.validation import ValidationRuntimeInfoFields


@dataclass(frozen=True)
class RuntimeInfo(ValidationRuntimeInfoFields):
    """Flat public runtime capability contract assembled from feature-group field modules."""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = ["RuntimeInfo"]
