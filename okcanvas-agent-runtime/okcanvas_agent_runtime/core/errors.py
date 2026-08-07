from __future__ import annotations

from dataclasses import dataclass

from okcanvas_agent_runtime.core.contracts import RuntimeErrorCode


@dataclass
class RuntimeFailure(Exception):
    code: RuntimeErrorCode
    public_message: str
    retryable: bool = False
    detail_type: str | None = None

    def __str__(self) -> str:
        return self.public_message
