from __future__ import annotations

from dataclasses import dataclass

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyErrorCode


@dataclass
class CodexReadOnlyFailure(Exception):
    code: CodexReadOnlyErrorCode
    public_message: str
    retryable: bool = False
    detail_type: str | None = None

    def __str__(self) -> str:
        return self.public_message
