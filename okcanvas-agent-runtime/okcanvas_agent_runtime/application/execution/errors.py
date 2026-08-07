from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.core.contracts import UsageSummary

from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode


class GenericExecutionFailure(RuntimeError):
    def __init__(
        self,
        code: GenericExecutionErrorCode,
        public_message: str,
        *,
        retryable: bool = False,
        detail_type: str | None = None,
        usage: UsageSummary | None = None,
        trace_id: str | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.retryable = retryable
        self.detail_type = detail_type
        self.usage = usage
        self.trace_id = trace_id
        self.diagnostic = dict(diagnostic) if diagnostic is not None else None
