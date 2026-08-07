from __future__ import annotations


class AgentDefinitionError(ValueError):
    """Base failure for immutable declarative Agent definitions."""


class AgentDefinitionNotFoundError(AgentDefinitionError):
    pass


class AgentDefinitionIntegrityError(AgentDefinitionError):
    pass


class AgentDefinitionContractError(AgentDefinitionError):
    pass
