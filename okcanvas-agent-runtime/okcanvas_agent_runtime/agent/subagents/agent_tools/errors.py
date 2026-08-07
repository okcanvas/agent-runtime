class AgentToolError(RuntimeError):
    pass


class AgentToolPolicyError(AgentToolError):
    pass


class AgentToolContractError(AgentToolError):
    pass
