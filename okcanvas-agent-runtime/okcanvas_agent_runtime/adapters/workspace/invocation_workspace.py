from __future__ import annotations

import re
from pathlib import Path

from okcanvas_agent_runtime.domain.invocations.errors import InvocationWorkspaceError

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")


class InvocationWorkspacePlanner:
    """Derive isolated workspace roots without creating or granting filesystem access."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()

    def preview_isolated_root(
        self,
        *,
        run_id: str,
        invocation_id: str,
        requested_root: str | Path | None = None,
    ) -> Path:
        if requested_root is not None:
            raise InvocationWorkspaceError(
                "Host workspace roots cannot be supplied by prompts, models, or Agent definitions"
            )
        if not _ID_RE.fullmatch(run_id) or not _ID_RE.fullmatch(invocation_id):
            raise InvocationWorkspaceError("Run and invocation IDs are invalid")
        candidate = (self.workspace_root / run_id / invocation_id).resolve()
        if self.workspace_root not in candidate.parents:
            raise InvocationWorkspaceError("Generated workspace root escaped its configured root")
        return candidate
