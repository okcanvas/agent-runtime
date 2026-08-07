from __future__ import annotations

import asyncio
import json
import sys
import types
from functools import wraps
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import (
    BoundedEncryptedCompactionSession,
    SQLiteSessionPolicyCatalog,
    SQLiteSessionRuntimeService,
    SessionHistoryKey,
    SessionIntegrityError,
    StrictEncryptedSession,
    select_compaction_candidate_items,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = SessionHistoryKey.from_text("11" * 32)


def _async_test(function):
    """Run one async test without requiring an ambient pytest async plugin."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class FakeSDKCompactionSession:
    def __init__(
        self,
        *,
        session_id: str,
        underlying_session,
        client,
        model: str,
        compaction_mode: str,
        should_trigger_compaction,
    ) -> None:
        self.session_id = session_id
        self.underlying_session = underlying_session
        self.client = client
        self.model = model
        self.compaction_mode = compaction_mode
        self.should_trigger_compaction = should_trigger_compaction

    async def get_items(self, limit: int | None = None):
        return await self.underlying_session.get_items(limit)

    async def add_items(self, items):
        await self.underlying_session.add_items(items)

    async def pop_item(self):
        return await self.underlying_session.pop_item()

    async def clear_session(self):
        await self.underlying_session.clear_session()

    async def run_compaction(self, args=None):
        items = await self.get_items()
        result = await self.client.responses.compact(model=self.model, input=items)
        await self.clear_session()
        if result.output:
            await self.add_items(list(result.output))


class MemorySession:
    def __init__(self) -> None:
        self.items: list[dict] = []
        self.closed = False

    async def get_items(self, limit: int | None = None):
        values = list(self.items)
        return values if limit is None else values[-limit:]

    async def add_items(self, items):
        self.items.extend(items)

    async def pop_item(self):
        return self.items.pop() if self.items else None

    async def clear_session(self):
        self.items.clear()

    def close(self) -> None:
        self.closed = True


def _history(candidate_count: int) -> list[dict]:
    values: list[dict] = []
    for index in range(candidate_count):
        values.append({"role": "user", "content": f"question-{index}"})
        values.append(
            {
                "type": "message",
                "role": "assistant",
                "content": f"answer-{index}",
            }
        )
    return values


def _session(*, output: list[dict], policy=None):
    storage = MemorySession()
    encrypted = StrictEncryptedSession(session_id="session_test", underlying_session=storage, key=KEY)
    response = SimpleNamespace(output=output)
    client = MagicMock()
    client.responses.compact = AsyncMock(return_value=response)
    resolved = policy or SQLiteSessionPolicyCatalog(ROOT).resolve()
    upstream = FakeSDKCompactionSession(
        session_id="session_test",
        underlying_session=encrypted,
        client=client,
        model=resolved.compaction_model,
        compaction_mode="input",
        should_trigger_compaction=lambda context: len(context["compaction_candidate_items"])
        >= resolved.compaction_trigger_candidate_items,
    )
    events: list[tuple[str, dict]] = []

    async def sink(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    wrapper = BoundedEncryptedCompactionSession(
        session_id="session_test",
        encrypted_storage_session=encrypted,
        compactor_factory=lambda: upstream,
        policy=resolved,
        event_sink=sink,
    )
    return wrapper, storage, client, events


def test_step064_policy_is_exact_and_store_false() -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    assert policy.schema_version == "okcanvas-sqlite-session-policy-v3"
    assert policy.policy_id == "local-strict-encrypted-compacted-sqlite-session-v1"
    assert policy.version == "3.0.0"
    assert policy.compaction_enabled is True
    assert policy.compaction_mode == "INPUT_ONLY"
    assert policy.compaction_provider == "openai"
    assert policy.compaction_api == "responses.compact"
    assert policy.compaction_model == "gpt-4.1"
    assert policy.compaction_trigger_candidate_items == 10
    assert policy.compaction_max_input_items == 256
    assert policy.compaction_store is False
    assert policy.compaction_previous_response_id_allowed is False
    assert policy.compaction_automatic is True
    assert policy.compaction_restore_previous_on_failure is True
    assert policy.compaction_raw_history_in_events is False
    assert policy.encryption_enabled is True


def test_candidate_selection_matches_pinned_sdk_contract() -> None:
    items = [
        {"role": "user", "content": "easy user"},
        {"type": "message", "role": "user", "content": "typed user"},
        {"type": "message", "role": "assistant", "content": "assistant"},
        {"type": "compaction", "summary": "old"},
        {"type": "function_call_output", "output": "ok"},
    ]
    selected = select_compaction_candidate_items(items)
    assert selected == [items[2], items[4]]


@_async_test
async def test_compaction_uses_input_mode_preserves_encryption_and_emits_metadata_only() -> None:
    wrapper, storage, client, events = _session(
        output=[{"type": "message", "role": "assistant", "content": "compacted"}]
    )
    await wrapper.add_items(_history(10))
    await wrapper.run_compaction({"store": False})

    items = await wrapper.get_items()
    assert items == [{"type": "message", "role": "assistant", "content": "compacted"}]
    assert len(storage.items) == 1
    raw = json.dumps(storage.items, sort_keys=True)
    assert "question-0" not in raw
    assert "answer-0" not in raw
    assert "compacted" not in raw
    assert storage.items[0]["__okcanvas_session_encrypted__"] == 1

    kwargs = client.responses.compact.await_args.kwargs
    assert kwargs["model"] == "gpt-4.1"
    assert kwargs["input"] == _history(10)
    assert "previous_response_id" not in kwargs
    assert [name for name, _ in events] == ["session.compaction.started"]
    assert all("history" not in payload for _, payload in events)
    assert events[0][1]["input_item_count"] == 20
    assert events[0][1]["provider_request_count"] == 1
    assert events[0][1]["provider_token_usage_recorded"] is False


@_async_test
async def test_below_threshold_does_not_call_compaction_api() -> None:
    wrapper, _, client, events = _session(
        output=[{"type": "message", "role": "assistant", "content": "unused"}]
    )
    await wrapper.add_items(_history(9))
    await wrapper.run_compaction({"store": False})
    client.responses.compact.assert_not_awaited()
    assert len(await wrapper.get_items()) == 18
    assert events == []


@_async_test
async def test_input_bound_fails_closed_without_provider_call() -> None:
    policy = replace(SQLiteSessionPolicyCatalog(ROOT).resolve(), compaction_max_input_items=2)
    wrapper, _, client, events = _session(
        output=[{"type": "message", "role": "assistant", "content": "unused"}],
        policy=policy,
    )
    await wrapper.add_items(_history(2))
    with pytest.raises(SessionIntegrityError, match="bounded compaction input limit"):
        await wrapper.run_compaction({"force": True, "store": False})
    client.responses.compact.assert_not_awaited()
    assert [name for name, _ in events] == ["session.compaction.failed"]


@_async_test
async def test_non_reducing_output_restores_exact_plaintext_history() -> None:
    before = _history(10)
    wrapper, _, _, events = _session(output=list(before))
    await wrapper.add_items(before)
    with pytest.raises(SessionIntegrityError, match="strict item reduction"):
        await wrapper.run_compaction({"store": False})
    assert await wrapper.get_items() == before
    assert [name for name, _ in events] == [
        "session.compaction.started",
        "session.compaction.failed",
    ]


def test_runtime_builds_pinned_sdk_compaction_facade_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeSQLiteSession(MemorySession):
        def __init__(self, session_id: str, db_path) -> None:
            super().__init__()
            self.session_id = session_id
            self.db_path = db_path

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str, base_url: str, max_retries: int) -> None:
            self.api_key = api_key
            self.base_url = base_url + "/" if not base_url.endswith("/") else base_url
            self.max_retries = max_retries
            self.responses = SimpleNamespace(compact=AsyncMock())

    agents_module = types.ModuleType("agents")
    agents_module.SQLiteSession = FakeSQLiteSession
    agents_module.OpenAIResponsesCompactionSession = FakeSDKCompactionSession
    openai_module = types.ModuleType("openai")
    openai_module.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, "agents", agents_module)
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(tmp_path / "sessions", policy, history_key=KEY)
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    session = runtime._compaction_session(
        record.session_id,
        compaction_api_key="sk-test-only",
        compaction_event_sink=None,
    )
    try:
        assert isinstance(session, BoundedEncryptedCompactionSession)
        compactor = session.compactor_factory()
        assert compactor.model == "gpt-4.1"
        assert compactor.compaction_mode == "input"
        assert str(compactor.client.base_url) == "https://api.openai.com/v1/"
        assert compactor.client.max_retries == 0
    finally:
        session.close()


@_async_test
async def test_provider_response_id_is_rejected_before_any_compaction_call() -> None:
    wrapper, _, client, events = _session(
        output=[{"type": "message", "role": "assistant", "content": "unused"}]
    )
    await wrapper.add_items(_history(10))
    with pytest.raises(SessionIntegrityError, match="provider response ID"):
        await wrapper.run_compaction({"response_id": "resp_forbidden", "store": False})
    client.responses.compact.assert_not_awaited()
    assert events == []


@_async_test
async def test_post_commit_compaction_holds_database_lease_and_updates_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(tmp_path / "sessions", policy, history_key=KEY)
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_compaction",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=record.session_id,
        run_id="run_compaction",
        committed=True,
        item_count=20,
    )

    class StubCompactionSession:
        closed = False

        async def run_compaction(self, args):
            assert args == {"store": False}
            leased = runtime.get(record.session_id)
            assert leased.active_run_id == "run_compaction"
            with pytest.raises(Exception, match="active Turn"):
                runtime.acquire_turn(
                    session_id=record.session_id,
                    run_id="run_other",
                    definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
            return True

        async def get_items(self):
            return [{"type": "message", "role": "assistant", "content": "summary"}]

        def close(self):
            self.closed = True

    stub = StubCompactionSession()
    monkeypatch.setattr(runtime, "_compaction_session", lambda *args, **kwargs: stub)
    events: list[tuple[str, dict]] = []

    async def sink(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    compacted = await runtime.compact_after_committed_turn(
        session_id=record.session_id,
        run_id="run_compaction",
        compaction_api_key="sk-test-only",
        compaction_event_sink=sink,
    )
    assert compacted is True
    current = runtime.get(record.session_id)
    assert current.active_run_id is None
    assert current.turn_count == 1
    assert current.item_count == 1
    assert stub.closed is True
    assert [name for name, _ in events] == ["session.compaction.completed"]
    assert events[0][1]["history_persisted_in_product_events"] is False


@_async_test
async def test_post_commit_compaction_failure_releases_lease_without_changing_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(tmp_path / "sessions", policy, history_key=KEY)
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    record = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.acquire_turn(
        session_id=record.session_id,
        run_id="run_failure",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=record.session_id,
        run_id="run_failure",
        committed=True,
        item_count=20,
    )

    class FailingCompactionSession:
        closed = False

        async def run_compaction(self, args):
            assert runtime.get(record.session_id).active_run_id == "run_failure"
            raise SessionIntegrityError("provider failure after exact restore")

        def close(self):
            self.closed = True

    stub = FailingCompactionSession()
    monkeypatch.setattr(runtime, "_compaction_session", lambda *args, **kwargs: stub)
    compacted = await runtime.compact_after_committed_turn(
        session_id=record.session_id,
        run_id="run_failure",
        compaction_api_key="sk-test-only",
    )
    assert compacted is False
    current = runtime.get(record.session_id)
    assert current.active_run_id is None
    assert current.turn_count == 1
    assert current.item_count == 20
    assert stub.closed is True


def test_compaction_is_post_commit_and_never_inserted_into_runner() -> None:
    execution_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(
        encoding="utf-8"
    )
    gateway_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(
        encoding="utf-8"
    )
    approval_source = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/tool_approval/service.py")).read_text(
        encoding="utf-8"
    )
    release_index = execution_source.index("session_record = self._sessions.release_turn(")
    compact_index = execution_source.index("await self._sessions.compact_after_committed_turn(")
    complete_index = execution_source.index("RunStatus.SUCCEEDED", compact_index)
    assert release_index < compact_index < complete_index
    assert "BoundedEncryptedCompactionSession" not in gateway_source
    assert "session_runtime.sdk_session(session_id)" in gateway_source
    assert approval_source.count("await self._sessions.compact_after_committed_turn(") == 2
