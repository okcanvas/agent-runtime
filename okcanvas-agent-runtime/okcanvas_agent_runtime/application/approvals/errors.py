class ToolApprovalError(RuntimeError):
    code = "TOOL_APPROVAL_ERROR"


class ToolApprovalNotFound(ToolApprovalError):
    code = "TOOL_APPROVAL_NOT_FOUND"


class ToolApprovalStateError(ToolApprovalError):
    code = "TOOL_APPROVAL_STATE_ERROR"


class ToolApprovalIntegrityError(ToolApprovalError):
    code = "TOOL_APPROVAL_INTEGRITY_ERROR"


class ToolApprovalConfirmationError(ToolApprovalError):
    code = "TOOL_APPROVAL_CONFIRMATION_MISMATCH"
