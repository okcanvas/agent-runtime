from __future__ import annotations

from dataclasses import dataclass

from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteErrorCode


@dataclass
class CodexWriteFailure(Exception):
    code: CodexWriteErrorCode
    public_message: str
    retryable: bool = False
    detail_type: str | None = None

    def __str__(self) -> str:
        return self.public_message
