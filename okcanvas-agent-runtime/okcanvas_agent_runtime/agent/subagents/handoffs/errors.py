class NativeHandoffError(RuntimeError):
    pass


class NativeHandoffPolicyError(NativeHandoffError):
    pass


class NativeHandoffContractError(NativeHandoffError):
    pass
