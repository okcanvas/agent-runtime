from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from okcanvas_agent_runtime.domain.sessions.errors import SessionConfigurationError, SessionIntegrityError
from okcanvas_agent_runtime.domain.sessions.models import SQLiteSessionPolicy

CompactionEventSink = Callable[[str, dict[str, Any]], Awaitable[None]]
CompactorFactory = Callable[[], Any]


def select_compaction_candidate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match the pinned SDK 0.19.0 compaction-candidate contract.

    User messages and already compacted items do not count toward the automatic trigger.
    """

    def is_user_message(item: dict[str, Any]) -> bool:
        if item.get("type") == "message":
            return item.get("role") == "user"
        return item.get("role") == "user" and "content" in item

    return [
        item
        for item in items
        if not (is_user_message(item) or item.get("type") == "compaction")
    ]


class BoundedEncryptedCompactionSession:
    """Governed post-commit facade over the pinned SDK compaction session.

    The wrapped SDK session stores only STEP063 encrypted envelopes. Compaction sends
    locally decrypted input with ``store=False``, never uses ``previous_response_id``,
    enforces a bounded item ceiling, verifies a strict reduction, restores the exact
    pre-compaction history on replacement failure, and emits metadata-only lifecycle
    events. This facade is intentionally not passed to ``Runner``.
    """

    def __init__(
        self,
        *,
        session_id: str,
        encrypted_storage_session: Any,
        compactor_factory: CompactorFactory,
        policy: SQLiteSessionPolicy,
        event_sink: CompactionEventSink | None = None,
    ) -> None:
        if not policy.compaction_enabled:
            raise SessionConfigurationError("Session compaction policy is not enabled")
        self.session_id = session_id
        self.encrypted_storage_session = encrypted_storage_session
        self.compactor_factory = compactor_factory
        self.policy = policy
        self.event_sink = event_sink

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_sink is None:
            return
        await self.event_sink(
            event_type,
            {
                "session_id": self.session_id,
                "compaction_policy_id": self.policy.policy_id,
                "compaction_policy_sha256": self.policy.policy_sha256,
                "compaction_mode": self.policy.compaction_mode,
                "compaction_provider": self.policy.compaction_provider,
                "compaction_api": self.policy.compaction_api,
                "compaction_model": self.policy.compaction_model,
                "history_persisted_in_product_events": False,
                **payload,
            },
        )

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        return await self.encrypted_storage_session.get_items(limit)

    async def add_items(self, items: list[Any]) -> None:
        await self.encrypted_storage_session.add_items(items)

    async def pop_item(self) -> dict[str, Any] | None:
        return await self.encrypted_storage_session.pop_item()

    async def clear_session(self) -> None:
        await self.encrypted_storage_session.clear_session()

    async def _restore_exact_history(self, before: list[dict[str, Any]]) -> None:
        try:
            current = await self.encrypted_storage_session.get_items()
            if current == before:
                return
            await self.encrypted_storage_session.clear_session()
            if before:
                await self.encrypted_storage_session.add_items(list(before))
            restored = await self.encrypted_storage_session.get_items()
        except Exception as exc:
            raise SessionIntegrityError(
                "Session compaction failed and exact history restore could not complete"
            ) from exc
        if restored != before:
            raise SessionIntegrityError(
                "Session compaction failed and exact history restore did not match"
            )

    async def run_compaction(self, args: dict[str, Any] | None = None) -> bool:
        requested = dict(args or {})
        if requested.get("compaction_mode") not in (None, "auto", "input"):
            raise SessionIntegrityError("Session compaction mode must remain input-only")
        if requested.get("store") not in (None, False):
            raise SessionIntegrityError("Session compaction cannot enable provider response storage")
        if requested.get("response_id") is not None:
            raise SessionIntegrityError("Session compaction cannot accept a provider response ID")

        before = await self.encrypted_storage_session.get_items()
        candidates = select_compaction_candidate_items(before)
        force = bool(requested.get("force", False))
        if len(before) > self.policy.compaction_max_input_items:
            await self._emit(
                "session.compaction.failed",
                {
                    "reason": "INPUT_ITEM_LIMIT_EXCEEDED",
                    "input_item_count": len(before),
                    "candidate_item_count": len(candidates),
                    "max_input_items": self.policy.compaction_max_input_items,
                },
            )
            raise SessionIntegrityError("Session history exceeds bounded compaction input limit")
        if not force and len(candidates) < self.policy.compaction_trigger_candidate_items:
            return False

        await self._emit(
            "session.compaction.started",
            {
                "input_item_count": len(before),
                "candidate_item_count": len(candidates),
                "trigger_candidate_items": self.policy.compaction_trigger_candidate_items,
                "max_input_items": self.policy.compaction_max_input_items,
                "provider_request_count": 1,
                "provider_token_usage_recorded": False,
            },
        )
        try:
            sdk_compaction_session = self.compactor_factory()
            await sdk_compaction_session.run_compaction(
                {
                    "force": True,
                    "compaction_mode": "input",
                    "store": False,
                }
            )
            after = await self.encrypted_storage_session.get_items()
            if not after or len(after) >= len(before):
                await self._restore_exact_history(before)
                raise SessionIntegrityError(
                    "Session compaction replacement must be a non-empty strict item reduction"
                )
        except Exception as exc:
            try:
                await self._restore_exact_history(before)
            except SessionIntegrityError as restore_error:
                await self._emit(
                    "session.compaction.failed",
                    {
                        "reason": type(restore_error).__name__,
                        "input_item_count": len(before),
                        "candidate_item_count": len(candidates),
                        "exact_history_restored": False,
                    },
                )
                raise restore_error from exc
            await self._emit(
                "session.compaction.failed",
                {
                    "reason": type(exc).__name__,
                    "input_item_count": len(before),
                    "candidate_item_count": len(candidates),
                    "exact_history_restored": True,
                },
            )
            raise

        return True

    def close(self) -> None:
        close = getattr(self.encrypted_storage_session, "close", None)
        if callable(close):
            close()
