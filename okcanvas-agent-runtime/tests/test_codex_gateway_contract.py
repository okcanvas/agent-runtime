import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyResult
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings
from okcanvas_agent_runtime.adapters.evidence import JsonlEventJournal
from okcanvas_agent_runtime.adapters.openai.runtime.codex_gateway import OpenAICodexReadOnlyGateway
import okcanvas_agent_runtime.adapters.openai.runtime.codex_gateway as gateway_module
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness


def test_codex_gateway_uses_official_experimental_contract(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    fake_codex = types.ModuleType("agents.extensions.experimental.codex")

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            captured["model_settings"] = kwargs

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeCodexOptions:
        def __init__(self, **kwargs):
            captured["codex_options"] = kwargs

    class FakeThreadOptions:
        def __init__(self, **kwargs):
            captured["thread_options"] = kwargs

    class FakeTurnOptions:
        def __init__(self, **kwargs):
            captured["turn_options"] = kwargs

    class FakeTurnCompletedEvent:
        def __init__(self):
            self.type = "turn.completed"
            self.usage = SimpleNamespace(
                input_tokens=30,
                cached_input_tokens=4,
                output_tokens=9,
            )

        def as_dict(self):
            return {
                "type": self.type,
                "usage": {
                    "input_tokens": 30,
                    "cached_input_tokens": 4,
                    "output_tokens": 9,
                },
            }

    def fake_codex_tool(**kwargs):
        captured["tool"] = kwargs
        return SimpleNamespace(name="codex_engineer", callback=kwargs["on_stream"])

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, context, max_turns, run_config):
            captured["request"] = request
            captured["context_before"] = dict(context)
            captured["max_turns"] = max_turns
            tool = captured["tool"]
            await tool["on_stream"](SimpleNamespace(event=FakeTurnCompletedEvent()))
            context["codex_thread_id_engineer"] = "thread_resumed"
            usage = SimpleNamespace(
                requests=2,
                input_tokens=11,
                output_tokens=6,
                total_tokens=17,
                input_tokens_details=SimpleNamespace(cached_tokens=1),
                output_tokens_details=SimpleNamespace(reasoning_tokens=2),
            )
            output = CodexReadOnlyResult(
                summary="Found the pricing defect.",
                inspected_files=["src/inventory/pricing.py"],
                commands_observed=["rg quantity"],
                findings=[],
                unverified=[],
            )

            class FakeResult:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_codex"

                def final_output_as(self, cls, raise_if_incorrect_type=False):
                    assert cls is CodexReadOnlyResult
                    assert raise_if_incorrect_type is True
                    return output

            return FakeResult()

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_codex"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    fake_codex.CodexOptions = FakeCodexOptions
    fake_codex.ThreadOptions = FakeThreadOptions
    fake_codex.TurnCompletedEvent = FakeTurnCompletedEvent
    fake_codex.TurnOptions = FakeTurnOptions
    fake_codex.codex_tool = fake_codex_tool

    monkeypatch.setenv("UNRELATED_SECRET", "must-not-reach-codex")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-in-inherited-env")
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.extensions", types.ModuleType("agents.extensions"))
    monkeypatch.setitem(
        sys.modules, "agents.extensions.experimental", types.ModuleType("agents.extensions.experimental")
    )
    monkeypatch.setitem(sys.modules, "agents.extensions.experimental.codex", fake_codex)
    monkeypatch.setattr(
        gateway_module,
        "inspect_codex_readiness",
        lambda settings: CodexReadiness(
            ready=True,
            sdk_installed=True,
            sdk_version="0.19.0",
            codex_cli_installed=True,
            codex_cli_path="/fake/codex",
            codex_cli_version="codex-cli 1.2.3",
            agent_model_configured=True,
            codex_model_configured=True,
            api_key_configured=True,
            experimental_codex_importable=True,
            issues=(),
        ),
    )
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    journal = JsonlEventJournal(tmp_path / "events.jsonl")
    result = asyncio.run(
        OpenAICodexReadOnlyGateway().run(
            request="Inspect the defect without modifications.",
            run_id="run_fixed",
            settings=CodexReadOnlySettings(
                agent_model="agent-model",
                codex_model="codex-model",
                api_key="hidden-key",
                codex_path="/fake/codex",
            ),
            workspace=tmp_path,
            existing_thread_id="thread_existing",
            journal=journal,
        )
    )

    assert captured["api_key"] == "hidden-key"
    assert captured["agent"]["model"] == "agent-model"
    assert captured["agent"]["handoffs"] == []
    assert captured["agent"]["output_type"] is CodexReadOnlyResult
    assert captured["model_settings"]["tool_choice"] == "required"
    assert captured["tool"]["name"] == "codex_engineer"
    assert captured["codex_options"]["api_key"] == "hidden-key"
    assert "OPENAI_API_KEY" not in captured["codex_options"]["env"]
    assert "UNRELATED_SECRET" not in captured["codex_options"]["env"]
    assert captured["codex_options"]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert captured["tool"]["sandbox_mode"] == "read-only"
    assert captured["tool"]["working_directory"] == str(tmp_path)
    assert captured["tool"]["skip_git_repo_check"] is False
    assert captured["tool"]["use_run_context_thread_id"] is True
    assert captured["thread_options"]["model"] == "codex-model"
    assert captured["thread_options"]["network_access_enabled"] is False
    assert captured["thread_options"]["web_search_enabled"] is False
    assert captured["thread_options"]["approval_policy"] == "never"
    assert captured["run_config"]["trace_include_sensitive_data"] is False
    assert captured["context_before"]["codex_thread_id_engineer"] == "thread_existing"
    assert result.thread_id == "thread_resumed"
    assert result.codex_usage.input_tokens == 30
    assert result.codex_usage.cached_input_tokens == 4
    assert result.codex_usage.output_tokens == 9
    assert result.agent_usage.total_tokens == 17
    assert journal.count == 1
