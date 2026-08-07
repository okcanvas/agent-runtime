from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.agent.model.retry.models import ModelRetryPolicy


def build_sdk_model_retry_settings(policy: ModelRetryPolicy) -> Any:
    """Build the installed-SDK explicit zero-retry settings.

    Supplying max_retries=0 disables Runner retries and the SDK's legacy conversation-locked
    compatibility retry path. The never policy makes the authority explicit rather than relying on
    an absent/default callback.
    """

    from agents import ModelRetrySettings, retry_policies

    return ModelRetrySettings(
        max_retries=policy.runner_managed_max_retries,
        policy=retry_policies.never(),
    )
