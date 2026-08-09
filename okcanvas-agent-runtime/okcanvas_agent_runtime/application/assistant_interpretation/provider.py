from __future__ import annotations

from typing import Protocol, runtime_checkable

from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.domain.sessions.context_focus import SessionContextFocusRecord

from .models import GroundedInterpretationContext


@runtime_checkable
class GroundedInterpretationContextProvider(Protocol):
    async def build(
        self,
        *,
        utterance: str,
        delegated_identity: DelegatedMCPIdentity | None,
        session_focus: SessionContextFocusRecord | None,
    ) -> GroundedInterpretationContext: ...
