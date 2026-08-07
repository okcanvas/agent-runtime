from __future__ import annotations

from okcanvas_agent_runtime.agent.model.response_storage.models import ResponseStoragePolicy


def build_sdk_response_storage_model_settings_kwargs(
    policy: ResponseStoragePolicy,
) -> dict[str, object]:
    """Return the explicit SDK ModelSettings value that disables Responses storage."""

    if policy.response_store_requested:
        raise ValueError("OpenAI Responses storage must remain disabled")
    return {"store": False}
