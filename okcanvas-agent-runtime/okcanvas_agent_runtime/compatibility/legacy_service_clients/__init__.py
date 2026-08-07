"""Compatibility facade for the removed service_clients package."""
from okcanvas_agent_runtime.transport.service.rest.auth import (
    ServiceClientAuthenticator,
    ServiceClientTokenRegistry,
)
from okcanvas_agent_runtime.core.service_identity import ServiceClientRole, ServicePrincipal
from okcanvas_agent_runtime.adapters.persistence.service_ownership import (
    SQLiteServiceResourceOwnershipStore,
    ServiceResourceOwner,
)

__all__ = [
    "ServiceClientAuthenticator",
    "ServiceClientTokenRegistry",
    "ServiceClientRole",
    "ServicePrincipal",
    "SQLiteServiceResourceOwnershipStore",
    "ServiceResourceOwner",
]
