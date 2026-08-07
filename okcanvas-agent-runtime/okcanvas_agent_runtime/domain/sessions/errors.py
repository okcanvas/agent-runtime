class SessionRuntimeError(RuntimeError):
    code = "SESSION_RUNTIME_ERROR"


class SessionPolicyError(SessionRuntimeError):
    code = "SESSION_POLICY_INVALID"


class SessionConfigurationError(SessionRuntimeError):
    code = "SESSION_CONFIGURATION_INVALID"


class SessionNotFound(SessionRuntimeError):
    code = "SESSION_NOT_FOUND"


class SessionStateError(SessionRuntimeError):
    code = "SESSION_STATE_INVALID"


class SessionBusyError(SessionRuntimeError):
    code = "SESSION_BUSY"


class SessionIntegrityError(SessionRuntimeError):
    code = "SESSION_INTEGRITY_ERROR"
