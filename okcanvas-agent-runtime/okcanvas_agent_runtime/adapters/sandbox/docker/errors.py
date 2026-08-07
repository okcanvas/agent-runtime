class SandboxRuntimeError(ValueError):
    """The Product-owned Sandbox Runtime contract or execution is invalid."""


class SandboxRuntimePolicyError(SandboxRuntimeError):
    """The immutable Sandbox policy is outside the closed Product contract."""


class SandboxProviderContractError(SandboxRuntimeError):
    """The immutable Sandbox provider contract is outside the closed Product contract."""


class SandboxExecutionDisabledError(SandboxRuntimeError):
    """Agent Sandbox execution is not enabled."""


class SandboxDockerError(SandboxRuntimeError):
    """A Product-owned Docker lifecycle operation failed safely.

    Raw Docker arguments, output, paths, image references, source text and secrets are
    intentionally excluded.  The bounded fields below are stable Product evidence.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        operation: str | None = None,
        return_code: int | None = None,
        stderr_category: str | None = None,
        output_truncated: bool = False,
        cleanup_attempted: bool | None = None,
        cleanup_completed: bool | None = None,
        orphan_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.operation = operation
        self.return_code = return_code
        self.stderr_category = stderr_category
        self.output_truncated = bool(output_truncated)
        self.cleanup_attempted = cleanup_attempted
        self.cleanup_completed = cleanup_completed
        self.orphan_count = orphan_count

    def attach_cleanup(
        self,
        *,
        cleanup_attempted: bool,
        cleanup_completed: bool,
        orphan_count: int | None,
    ) -> "SandboxDockerError":
        self.cleanup_attempted = bool(cleanup_attempted)
        self.cleanup_completed = bool(cleanup_completed)
        self.orphan_count = orphan_count
        return self
