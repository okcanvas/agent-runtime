from __future__ import annotations

from okcanvas_agent_runtime.adapters.sandbox.docker.errors import SandboxExecutionDisabledError
from okcanvas_agent_runtime.adapters.sandbox.docker.models import SandboxRuntimeFoundation


class SandboxRuntimeService:
    """Expose Sandbox metadata and distinguish provider lifecycle from Agent execution."""

    def __init__(self, foundation: SandboxRuntimeFoundation) -> None:
        self.foundation = foundation

    def public_metadata(self) -> dict[str, object]:
        return self.foundation.to_public_dict()

    def require_provider_lifecycle(self) -> None:
        if not self.foundation.policy.provider_lifecycle_enabled:
            raise SandboxExecutionDisabledError("Product Docker provider lifecycle is disabled")

    def require_agent_execution(self, workspace_access: str) -> None:
        if not self.foundation.policy.agent_execution_enabled:
            raise SandboxExecutionDisabledError("Product Sandbox Agent execution is disabled")
        if workspace_access not in self.foundation.policy.active_workspace_access_modes:
            raise SandboxExecutionDisabledError("Requested Sandbox workspace mode is inactive")
        if workspace_access != "sandbox-readonly-v1":
            raise SandboxExecutionDisabledError("STEP075 permits read-only Sandbox workspace access only")
