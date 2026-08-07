from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.agent.model.provider_identity.models import ProviderIdentifierPolicy


def provider_identifier_presence(value: Any, policy: ProviderIdentifierPolicy) -> bool:
    """Return count-only identifier evidence without returning or serializing the identifier."""

    if not policy.persist_identifier_presence:
        return False
    return bool(value)


def minimize_provider_identifier(value: Any, policy: ProviderIdentifierPolicy) -> None:
    """Drop a provider identifier at the Product boundary."""

    del value
    if policy.persist_response_id or policy.persist_request_id:
        raise ValueError("Provider identifier persistence must remain disabled")
    return None
