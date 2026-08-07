class GuardrailRuntimeError(RuntimeError):
    pass


class GuardrailDefinitionNotFoundError(GuardrailRuntimeError):
    pass


class GuardrailDefinitionContractError(GuardrailRuntimeError):
    pass


class GuardrailDefinitionIntegrityError(GuardrailRuntimeError):
    pass
