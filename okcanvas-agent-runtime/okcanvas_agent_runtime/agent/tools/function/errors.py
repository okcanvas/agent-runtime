from __future__ import annotations


class FunctionToolRuntimeError(RuntimeError):
    """Base error for the product-owned local Function Tool Runtime."""


class FunctionToolDefinitionNotFoundError(FunctionToolRuntimeError):
    pass


class FunctionToolDefinitionContractError(FunctionToolRuntimeError):
    pass


class FunctionToolDefinitionIntegrityError(FunctionToolRuntimeError):
    pass


class FunctionToolExecutionError(FunctionToolRuntimeError):
    pass
