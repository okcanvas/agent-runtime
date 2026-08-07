from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicy

from okcanvas_agent_runtime.agent.model.routing.models import ResolvedModelRoute


class PinnedOpenAIResponsesProvider:
    """Lazy product-owned provider wrapper for one immutable SDK OpenAI route.

    STEP052 also owns retry authority. The underlying AsyncOpenAI client is constructed with
    max_retries=0, while Runner receives explicit zero-retry settings. This prevents hidden
    provider retries, Runner retries, and the SDK conversation-locked compatibility retry path.
    """

    def __init__(
        self,
        *,
        route: ResolvedModelRoute,
        retry_policy: ModelRetryPolicy,
        api_key: str,
    ) -> None:
        self.route = route
        self.retry_policy = retry_policy
        self._api_key = api_key
        self._delegate: Any | None = None
        self.closed = False

    def _provider(self) -> Any:
        if self._delegate is None:
            from agents import OpenAIProvider
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self.route.policy.base_url,
                max_retries=self.retry_policy.provider_managed_max_retries,
            )
            self._delegate = OpenAIProvider(
                openai_client=client,
                use_responses=True,
                use_responses_websocket=False,
                strict_feature_validation=True,
            )
        return self._delegate

    def get_model(self, model_name: str | None) -> Any:
        if self.closed:
            raise RuntimeError("Model provider is already closed")
        if model_name != self.route.model_id:
            raise RuntimeError("SDK requested a model outside the immutable route")
        return self._provider().get_model(model_name)

    async def aclose(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._delegate is not None:
            close = getattr(self._delegate, "aclose", None)
            if callable(close):
                await close()
