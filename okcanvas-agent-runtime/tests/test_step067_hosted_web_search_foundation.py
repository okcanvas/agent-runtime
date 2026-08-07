from __future__ import annotations

from tests.artifact_test_support import artifact_service, read_json_artifact

import asyncio
import json
import shutil
import sqlite3
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.agent.definitions import (
    AgentDefinitionCatalog,
    AgentDefinitionContractError,
)
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    HostedWebSearchResult,
    HostedWebSearchStatus,
    UsageSummary,
)
from okcanvas_agent_runtime.application.execution import (
    GenericAgentExecutionService,
    GenericGatewayRunResult,
    OpenAIGenericAgentGateway,
)
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.tools.hosted_search import (
    HostedWebSearchEvidence,
    HostedWebSearchEvidenceError,
    HostedWebSearchPolicyCatalog,
    HostedWebSearchSource,
    build_sdk_web_search_tool,
    extract_hosted_web_search_evidence,
    hosted_web_search_model_settings_kwargs,
    normalize_source_url,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

ROOT = Path(__file__).resolve().parents[1]


def _valid_items() -> list[dict[str, object]]:
    return [
        {
            "raw_item": {
                "id": "web_call_secret",
                "type": "web_search_call",
                "status": "completed",
                "action": {
                    "type": "search",
                    "query": "raw query must not persist",
                    "sources": [
                        {
                            "type": "url",
                            "url": (
                                "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
                                "?utm_source=test#section"
                            ),
                        },
                        {
                            "type": "url",
                            "url": "https://sub.developers.openai.com/api/docs/models/gpt-5.6-terra/",
                        },
                    ],
                },
            }
        },
        {
            "raw_item": {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Provider text must not be copied into evidence.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "GPT-5.6 Sol official model documentation",
                                "url": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
                            }
                        ],
                    }
                ],
            }
        },
    ]


def test_policy_and_runtime_binding_are_exact() -> None:
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    assert policy.tool_id == "web-search-v1"
    assert policy.allowed_domains == ("developers.openai.com",)
    assert policy.max_search_calls == 1
    assert policy.max_retrieved_sources == 8
    assert policy.max_citations == 8
    assert policy.response_include == ("web_search_call.action.sources",)
    assert policy.tool_choice == "required"
    assert policy.parallel_tool_calls is False
    assert policy.max_turns == 2
    definition = AgentDefinitionCatalog(ROOT).resolve("hosted-web-search-agent")
    assert definition.hosted_tools == ("web-search-v1",)
    assert definition.session_mode == "disabled"
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "hosted-web-search-execution-v1"
    assert len(binding.hosted_tools) == 1
    assert binding.hosted_tools[0]["policy_sha256"] == policy.policy_sha256
    assert binding.hosted_tool_runtime_sha256


def test_agent_catalog_rejects_hosted_tool_composition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    definition_path = project / "specs/agents/hosted-web-search-agent/definition.json"
    payload = json.loads(definition_path.read_text(encoding="utf-8"))
    payload["tools"] = ["local_text_metrics"]
    definition_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(AgentDefinitionContractError, match="isolated"):
        AgentDefinitionCatalog(project).resolve("hosted-web-search-agent")


def test_sdk_tool_and_model_settings_are_policy_owned(monkeypatch) -> None:
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    fake_agents = types.ModuleType("agents")

    class FakeWebSearchTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            self.name = "web_search"
            self.filters = SimpleNamespace(**kwargs["filters"])

    fake_agents.WebSearchTool = FakeWebSearchTool
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    tool = build_sdk_web_search_tool(policy)
    assert tool.name == "web_search"
    assert tool.user_location is None
    assert tool.search_context_size == "medium"
    assert tool.external_web_access is True
    allowed_domains = getattr(tool.filters, "allowed_domains", None)
    assert list(allowed_domains or ()) == ["developers.openai.com"]
    settings = hosted_web_search_model_settings_kwargs(policy)
    assert settings == {
        "reasoning": None,
        "response_include": ["web_search_call.action.sources"],
        "store": False,
        "tool_choice": "required",
        "parallel_tool_calls": False,
    }


def test_url_normalization_is_strict_and_canonical() -> None:
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    assert normalize_source_url(
        "https://DEVELOPERS.OPENAI.COM/api/docs/models/gpt-5.6-sol/?x=1#y",
        policy,
    ) == "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
    with pytest.raises(HostedWebSearchEvidenceError, match="domain policy"):
        normalize_source_url("https://example.com/docs/page", policy)
    with pytest.raises(HostedWebSearchEvidenceError, match="path"):
        normalize_source_url("https://developers.openai.com/assets/logo.svg", policy)
    with pytest.raises(HostedWebSearchEvidenceError, match="domain policy"):
        normalize_source_url("https://user@developers.openai.com/api/docs/models/x", policy)


def test_source_evidence_separates_retrieved_and_cited_sources() -> None:
    policy = HostedWebSearchPolicyCatalog(ROOT).resolve()
    evidence = extract_hosted_web_search_evidence(_valid_items(), policy)
    assert evidence.search_call_count == 1
    assert evidence.retrieved_source_count == 2
    assert evidence.citation_count == 1
    assert evidence.sources[0].url == (
        "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
    )
    assert evidence.sources[0].cited is True
    assert evidence.sources[0].citation_count == 1
    assert evidence.sources[1].cited is False
    payload = evidence.to_artifact_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "raw query must not persist" not in encoded
    assert "Provider text must not be copied" not in encoded
    assert "web_call_secret" not in encoded
    assert payload["raw_query_persisted"] is False
    assert payload["raw_content_persisted"] is False
    assert payload["provider_call_id_persisted"] is False


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda items: items.append(
                {"raw_item": {"type": "file_search_call", "status": "completed"}}
            ),
            "File Search",
        ),
        (
            lambda items: items[1]["raw_item"]["content"][0].update(annotations=[]),  # type: ignore[index]
            "no inline citation",
        ),
        (
            lambda items: items[0]["raw_item"]["action"]["sources"].append(  # type: ignore[index]
                {"type": "url", "url": "https://example.com/docs/page"}
            ),
            "domain policy",
        ),
        (
            lambda items: items[0]["raw_item"].update(status="in_progress"),  # type: ignore[index]
            "did not complete",
        ),
    ],
)
def test_source_evidence_fails_closed(mutator, message: str) -> None:
    items = _valid_items()
    mutator(items)
    with pytest.raises(HostedWebSearchEvidenceError, match=message):
        extract_hosted_web_search_evidence(items, HostedWebSearchPolicyCatalog(ROOT).resolve())


def test_structured_output_rejects_model_owned_urls() -> None:
    with pytest.raises(ValueError, match="Product source evidence"):
        HostedWebSearchResult(
            status=HostedWebSearchStatus.ANSWERED,
            answer="See https://developers.openai.com/api/docs/models/x",
            unverified=[],
        )


class _CompatModelSettings:
    def __init__(self, **kwargs):
        self.values = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class _CompatModelRetrySettings:
    def __init__(self, **kwargs):
        self.max_retries = kwargs.get("max_retries")
        self.policy = kwargs.get("policy")


def test_gateway_constructs_hosted_tool_and_extracts_sdk_evidence(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeWebSearchTool:
        def __init__(self, **kwargs):
            captured["web_tool"] = kwargs
            self.name = "web_search"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(
            cls,
            agent,
            request,
            *,
            max_turns,
            hooks,
            run_config,
            error_handlers=None,
            session,
        ):
            captured["request"] = request
            captured["max_turns"] = max_turns
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(),
                agent,
                SimpleNamespace(response_id="resp_secret", request_id="req_secret", output=[]),
            )
            output = HostedWebSearchResult(
                status=HostedWebSearchStatus.ANSWERED,
                answer="The official documentation describes the requested model.",
                unverified=[],
            )
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=2,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_secret"
                new_items = _valid_items()

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is HostedWebSearchResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.WebSearchTool = FakeWebSearchTool
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = _CompatModelSettings
    fake_agents.ModelRetrySettings = _CompatModelRetrySettings
    fake_agents.retry_policies = SimpleNamespace(never=lambda: (lambda _context: False))
    fake_agents.gen_trace_id = lambda: "trace_hosted_search"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve("hosted-web-search-agent"),
            request="Compare the official model documentation.",
            run_id="run_hosted_search",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert captured["max_turns"] == 2
    assert captured["web_tool"] == {
        "user_location": None,
        "filters": {"allowed_domains": ["developers.openai.com"]},
        "search_context_size": "medium",
        "external_web_access": True,
    }
    agent_settings = captured["agent"]["model_settings"].values  # type: ignore[index]
    run_settings = captured["run_config"]["model_settings"].values  # type: ignore[index]
    for values in (agent_settings, run_settings):
        assert values["tool_choice"] == "required"
        assert values["parallel_tool_calls"] is False
        assert values["store"] is False
        assert values["response_include"] == ["web_search_call.action.sources"]
    assert result.hosted_search_evidence is not None
    assert result.hosted_search_evidence.retrieved_source_count == 2
    event_types = [event.event_type for event in captured["events"]]  # type: ignore[index]
    assert event_types[-1] == "hosted.web_search.completed"
    assert "raw query must not persist" not in repr(captured["events"])
    assert "hidden-key" not in repr(captured["events"])
    assert "hidden-key" not in repr(captured["run_config"])


class _HostedSearchGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        assert definition.agent_id == "hosted-web-search-agent"
        return GenericGatewayRunResult(
            output=HostedWebSearchResult(
                status=HostedWebSearchStatus.ANSWERED,
                answer="The official documentation supports the answer.",
                unverified=[],
            ),
            usage=UsageSummary(requests=2, input_tokens=20, output_tokens=10, total_tokens=30),
            trace_id="trace_hosted_search",
            response_id=None,
            sdk_version="0.19.0",
            hosted_search_evidence=HostedWebSearchEvidence(
                policy_id="official-openai-docs-web-search-v1",
                policy_sha256=HostedWebSearchPolicyCatalog(ROOT).resolve().policy_sha256,
                search_call_count=1,
                retrieved_source_count=1,
                citation_count=1,
                sources=(
                    HostedWebSearchSource(
                        url="https://developers.openai.com/api/docs/models/gpt-5.6-sol",
                        title="GPT-5.6 Sol",
                        cited=True,
                        citation_count=1,
                    ),
                ),
            ),
        )


def test_execution_persists_final_and_separate_hosted_search_evidence(tmp_path: Path) -> None:
    database = tmp_path / "product.sqlite3"
    store = SQLiteProductStore(database)
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=_HostedSearchGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(store, tmp_path / "artifacts"),
    )
    request = "SECRET QUERY TEXT THAT MUST NOT ENTER PRODUCT EVIDENCE"
    envelope = asyncio.run(
        service.run(
            agent_definition_id="hosted-web-search-agent",
            request=request,
            settings=RuntimeSettings(model="test-model", api_key="secret-key"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "SUCCEEDED"
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT artifact_id, artifact_type FROM artifact WHERE run_id = ? ORDER BY artifact_type",
            (envelope.run_id,),
        ).fetchall()
    assert [row[1] for row in rows] == [
        "agent.final-output",
        "agent.hosted-search-evidence",
    ]
    payloads = {
        artifact_type: read_json_artifact(store, tmp_path / "artifacts", artifact_id)
        for artifact_id, artifact_type in rows
    }
    assert "url" not in payloads["agent.final-output"]
    evidence = payloads["agent.hosted-search-evidence"]
    assert evidence["retrieved_source_count"] == 1
    assert evidence["sources"][0]["url"].startswith("https://developers.openai.com/")
    assert request not in json.dumps(evidence)
    events = store.list_events(envelope.run_id)
    event_text = json.dumps([event.payload for event in events], ensure_ascii=False)
    assert request not in event_text
    assert "secret-key" not in event_text
