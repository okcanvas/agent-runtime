from __future__ import annotations

from okcanvas_agent_runtime.domain.sessions.context_focus import SessionContextFocusRecord

from .models import GroundedSessionEntityHint, GroundedSessionFocusHint


def project_session_focus(
    focus: SessionContextFocusRecord | None,
    *,
    max_candidates: int = 5,
) -> GroundedSessionFocusHint:
    if focus is None:
        return GroundedSessionFocusHint(state="EMPTY")
    candidates = tuple(
        GroundedSessionEntityHint(
            entity_type=item.entity_type,
            label=item.label,
            qualifiers=item.qualifiers,
            reference_token=(
                "SESSION_FOCUS"
                if focus.active_entity is item
                else f"SESSION_FOCUS_CANDIDATE_{index + 1}"
            ),
        )
        for index, item in enumerate(focus.candidates[:max_candidates])
    )
    active = candidates[0] if focus.active_entity is not None and candidates else None
    return GroundedSessionFocusHint(
        state=focus.state.value,
        active_entity=active,
        candidates=candidates,
        candidate_count=len(focus.candidates),
    )
