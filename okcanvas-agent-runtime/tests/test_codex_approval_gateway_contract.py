from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from okcanvas_agent_runtime.core.config import CodexWriteSettings
from okcanvas_agent_runtime.adapters.openai.runtime.codex_approval_gateway import OpenAICodexApprovalGateway


class FakeInterruption:
    name = "codex_workspace_write"
    call_id = "call-1"
    arguments = json.dumps({"execution_id": "execution-1"})


class FakeState:
    def __init__(self, context):
        self.context = context
        self.approved = False
        self.rejected = False

    def to_json(self, strict_context=False):
        assert strict_context is True
        return {"context": {"context": self.context}, "pending": True}

    def get_interruptions(self):
        return [FakeInterruption()]

    def approve(self, item):
        self.approved = True

    def reject(self, item, rejection_message=None):
        self.rejected = True
        assert rejection_message


class FakeResult:
    def __init__(self, *, context, interrupted, output=None):
        self.context_wrapper = SimpleNamespace(
            usage=SimpleNamespace(
                requests=1,
                input_tokens=5,
                output_tokens=1,
                total_tokens=6,
                input_tokens_details=SimpleNamespace(cached_tokens=2),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )
        )
        self.interruptions = [FakeInterruption()] if interrupted else []
        self.last_response_id = "resp-1"
        self.final_output = output
        self._state = FakeState(context)

    def to_state(self):
        return self._state


def test_gateway_builds_one_approval_tool_and_serializes_state(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            captured["model_settings"] = kwargs

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunContextWrapper:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

    def fake_tool(**kwargs):
        captured["tool_config"] = kwargs

        def decorate(fn):
            captured["tool_fn"] = fn
            return SimpleNamespace(name="codex_workspace_write")

        return decorate

    class FakeRunner:
        @classmethod
        async def run(cls, agent, input_value, **kwargs):
            captured.setdefault("runs", []).append((input_value, kwargs))
            if isinstance(input_value, FakeState):
                if input_value.approved:
                    ctx = SimpleNamespace(context=input_value.context)
                    output = await captured["tool_fn"](ctx, input_value.context["execution_id"])
                    return FakeResult(context=input_value.context, interrupted=False, output=output)
                return FakeResult(context=input_value.context, interrupted=False, output="rejected")
            return FakeResult(context=kwargs["context"], interrupted=True)

    class FakeRunState:
        @classmethod
        async def from_json(cls, agent, state_json, strict_context=False):
            assert strict_context is True
            return FakeState(state_json["context"]["context"])

    monkeypatch.setattr(
        OpenAICodexApprovalGateway,
        "_load_sdk",
        staticmethod(
            lambda: (
                FakeAgent,
                FakeModelSettings,
                FakeRunConfig,
                FakeRunner,
                FakeRunState,
                FakeRunContextWrapper,
                fake_tool,
                lambda: "trace-1",
                lambda key: captured.setdefault("key", key),
                "0.19.0",
            )
        ),
    )

    gateway = OpenAICodexApprovalGateway()
    settings = CodexWriteSettings(agent_model="agent", codex_model="codex", api_key="secret")
    context = {"execution_id": "execution-1"}
    calls = []

    async def executor(ctx):
        calls.append(ctx)
        return {"state": "SUCCEEDED"}

    prepared = asyncio.run(gateway.prepare(settings=settings, context=context, executor=executor))
    assert prepared.tool_name == "codex_workspace_write"
    assert calls == []
    assert captured["tool_config"]["needs_approval"] is True
    assert captured["agent"]["tool_use_behavior"] == "stop_on_first_tool"
    assert captured["model_settings"]["tool_choice"] == "required"
    assert captured["run_config"]["trace_include_sensitive_data"] is False

    approved = asyncio.run(
        gateway.resume(
            settings=settings,
            state_json=prepared.state_json,
            decision="APPROVE",
            executor=executor,
        )
    )
    assert approved.remaining_interruptions == 0
    assert calls == [context]
