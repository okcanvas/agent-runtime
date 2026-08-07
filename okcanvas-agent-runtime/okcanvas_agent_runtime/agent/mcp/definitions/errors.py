from __future__ import annotations


class MCPDefinitionError(RuntimeError):
    """Base error for product-owned MCP server definitions."""


class MCPDefinitionNotFoundError(MCPDefinitionError):
    pass


class MCPDefinitionContractError(MCPDefinitionError):
    pass


class MCPDefinitionIntegrityError(MCPDefinitionError):
    pass
