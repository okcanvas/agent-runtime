class InvocationScopeError(RuntimeError):
    pass


class InvocationPolicyError(InvocationScopeError):
    pass


class InvocationGraphError(InvocationScopeError):
    pass


class InvocationStateError(InvocationScopeError):
    pass


class InvocationWorkspaceError(InvocationScopeError):
    pass
