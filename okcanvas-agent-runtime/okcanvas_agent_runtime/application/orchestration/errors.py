class BoundedOrchestrationError(RuntimeError):
    pass


class BoundedOrchestrationPolicyError(BoundedOrchestrationError):
    pass


class BoundedOrchestrationContractError(BoundedOrchestrationError):
    pass
