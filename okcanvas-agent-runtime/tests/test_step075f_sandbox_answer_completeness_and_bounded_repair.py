from __future__ import annotations

from types import SimpleNamespace

from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.application.execution.sandbox_answer_completeness import (
    assess_sandbox_answer_completeness,
    build_sandbox_answer_repair_prompt,
    find_sandbox_tool_output,
)
from okcanvas_agent_runtime.agent.tools.function.models import SandboxProjectReadonlyInspectOutput


LIVE_REQUEST = (
    "Find where calculate_reorder is implemented, explain its exact reorder formula, "
    "and cite the supporting file and line evidence."
)


def _tool_output() -> SandboxProjectReadonlyInspectOutput:
    return SandboxProjectReadonlyInspectOutput.model_validate(
        {
            "workspace_label": "bounded-project",
            "snapshot_sha256": "a" * 64,
            "files_considered": 3,
            "bytes_considered": 128,
            "inspected_files": ["src/inventory.py"],
            "evidence": [
                {
                    "path": "src/inventory.py",
                    "line_start": 1,
                    "line_end": 4,
                    "excerpt": (
                        "SAFETY_STOCK = 12\n\n"
                        "def calculate_reorder(on_hand: int, forecast: int) -> int:\n"
                        "    return max(0, forecast + SAFETY_STOCK - on_hand)"
                    ),
                }
            ],
            "evidence_characters": 128,
            "query_terms_considered": 4,
            "truncated": False,
            "workspace_access": "sandbox-readonly-v1",
            "workspace_materialized": True,
            "docker_call_count": 9,
            "selected_file_hashes_verified": True,
            "cleanup_state": "COMPLETED",
            "orphan_count": 0,
            "image_binding_sha256": "b" * 64,
            "network_mode": "none",
            "shell_enabled": False,
            "apply_patch_enabled": False,
        },
        strict=True,
    )


def _draft() -> CodingAgentResult:
    return CodingAgentResult.model_validate(
        {
            "status": "PASS",
            "summary": "The function uses a standard reorder calculation.",
            "findings": [
                {
                    "severity": "INFO",
                    "confidence": "CONFIRMED",
                    "title": "Reorder calculation",
                    "detail": "calculate_reorder uses max(0, ...) to avoid negative values.",
                    "evidence": ["src/inventory.py lines 1-4"],
                }
            ],
            "unverified": ["src/inventory.py"],
        }
    )


def _complete() -> CodingAgentResult:
    return CodingAgentResult.model_validate(
        {
            "status": "PASS",
            "summary": (
                "src/inventory.py lines 1-4 defines SAFETY_STOCK = 12 and "
                "calculate_reorder as max(0, forecast + SAFETY_STOCK - on_hand)."
            ),
            "findings": [
                {
                    "severity": "INFO",
                    "confidence": "CONFIRMED",
                    "title": "Exact reorder formula",
                    "detail": (
                        "calculate_reorder returns "
                        "max(0, forecast + SAFETY_STOCK - on_hand), with SAFETY_STOCK = 12."
                    ),
                    "evidence": ["src/inventory.py lines 1-4"],
                }
            ],
            "unverified": [],
        }
    )


def test_live_draft_requires_bounded_repair() -> None:
    assessment = assess_sandbox_answer_completeness(
        request=LIVE_REQUEST,
        output=_draft(),
        tool_output=_tool_output(),
    )
    assert assessment.repair_required is True
    assert assessment.issue_codes == (
        "EXACT_EVIDENCE_FRAGMENT_MISSING",
        "EVIDENCE_BACKED_PATH_MARKED_UNVERIFIED",
    )
    assert assessment.required_fragments == (
        "calculate_reorder",
        "max(0, forecast + SAFETY_STOCK - on_hand)",
        "SAFETY_STOCK = 12",
    )


def test_exact_complete_answer_passes_without_repair() -> None:
    assessment = assess_sandbox_answer_completeness(
        request=LIVE_REQUEST,
        output=_complete(),
        tool_output=_tool_output(),
    )
    assert assessment.complete is True
    assert assessment.repair_required is False
    assert assessment.issue_codes == ()




def test_non_exact_request_does_not_require_exact_formula_fragments() -> None:
    output = CodingAgentResult.model_validate(
        {
            "status": "PASS",
            "summary": "The implementation is in src/inventory.py.",
            "findings": [
                {
                    "severity": "INFO",
                    "confidence": "CONFIRMED",
                    "title": "Implementation located",
                    "detail": "The function uses a bounded non-negative calculation.",
                    "evidence": ["src/inventory.py lines 1-4"],
                }
            ],
            "unverified": [],
        }
    )
    assessment = assess_sandbox_answer_completeness(
        request="Review calculate_reorder and identify its implementation file.",
        output=output,
        tool_output=_tool_output(),
    )
    assert assessment.exactness_requested is False
    assert assessment.complete is True
    assert assessment.repair_required is False

def test_repair_prompt_contains_bounded_evidence_but_no_capability_grant() -> None:
    assessment = assess_sandbox_answer_completeness(
        request=LIVE_REQUEST,
        output=_draft(),
        tool_output=_tool_output(),
    )
    prompt = build_sandbox_answer_repair_prompt(
        request=LIVE_REQUEST,
        draft=_draft(),
        tool_output=_tool_output(),
        assessment=assessment,
    )
    assert "SAFETY_STOCK = 12" in prompt
    assert "max(0, forecast + SAFETY_STOCK - on_hand)" in prompt
    assert "Do not call tools" in prompt
    assert "unverified" in prompt


def test_tool_output_is_recovered_only_from_one_exact_typed_item() -> None:
    output = _tool_output()
    assert find_sandbox_tool_output([SimpleNamespace(output=output)]) == output
    assert find_sandbox_tool_output([SimpleNamespace(output=output), SimpleNamespace(output=output)]) is None
    assert find_sandbox_tool_output([]) is None


def test_gateway_completes_incomplete_sandbox_answer_without_model_or_tool_reexecution(monkeypatch) -> None:
    import asyncio
    import sys
    import types
    from pathlib import Path

    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.core.config import RuntimeSettings
    from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
    from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
    from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

    root = Path(__file__).resolve().parents[1]
    captured: dict[str, object] = {"calls": 0, "events": [], "agents": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agents"].append(kwargs)
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, **kwargs):
            captured["calls"] = int(captured["calls"]) + 1
            call = int(captured["calls"])
            hooks = kwargs["hooks"]
            if hasattr(hooks, "on_agent_start"):
                await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(),
                agent,
                SimpleNamespace(response_id=f"resp_{call}", request_id=f"req_{call}", output=[1]),
            )
            output = _draft()
            if hasattr(hooks, "on_agent_end"):
                await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=1,
                input_tokens=10 * call,
                output_tokens=5 * call,
                total_tokens=15 * call,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )
            return SimpleNamespace(
                context_wrapper=SimpleNamespace(usage=usage),
                last_response_id=f"resp_{call}",
                new_items=[SimpleNamespace(output=_tool_output())] if call == 1 else [],
                raw_responses=[],
                final_output_as=lambda output_type, raise_if_incorrect_type=False: output,
            )

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelSettings
    fake_agents.retry_policies = types.SimpleNamespace(never=lambda: (lambda _context: False))
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_step075f"
    fake_agents.set_default_openai_key = lambda value: None
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(
        gateway_module,
        "build_sdk_function_tool",
        lambda runtime, **kwargs: SimpleNamespace(name=runtime.tool_id),
    )

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway(
            readonly_workspace_root=str(root),
            sandbox_readonly_image="busybox:1.36",
        ).run(
            definition=AgentDefinitionCatalog(root).resolve("sandbox-readonly-coding-agent"),
            request=LIVE_REQUEST,
            run_id="run_step075f",
            settings=RuntimeSettings(model="gpt-4.1", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )

    assert captured["calls"] == 1
    assessment = assess_sandbox_answer_completeness(
        request=LIVE_REQUEST, output=result.output, tool_output=_tool_output()
    )
    assert assessment.complete is True
    assert result.output.unverified == []
    serialized = result.output.model_dump_json()
    assert "max(0, forecast + SAFETY_STOCK - on_hand)" in serialized
    assert "SAFETY_STOCK = 12" in serialized
    assert result.usage.requests == 1
    assert result.usage.total_tokens == 15
    assert result.response_id is None
    events = [event.event_type for event in captured["events"]]
    assert events.count("agent.output.completeness.checked") == 1
    assert events.count("agent.output.completion.started") == 1
    assert events.count("agent.output.completion.completed") == 1
    assert events.count("agent.output.repair.started") == 0
    assert events.count("agent.output.repair.completed") == 0
    assert events.count("tool.started") == 0
    assert len(captured["agents"]) == 1
