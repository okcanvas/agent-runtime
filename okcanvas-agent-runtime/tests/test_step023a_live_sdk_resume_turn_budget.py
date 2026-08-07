from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.approvals import gateway as gateway_module
from okcanvas_agent_runtime.application.approvals.gateway import (
    LOCAL_TOOL_APPROVAL_MAX_TURNS,
    OpenAILocalToolApprovalGateway,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeRunContextWrapper:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls


class _FakeRunHooks:
    pass


class _FakeModelSettings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeRunConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeState:
    def to_json(self, *, strict_context: bool):
        assert strict_context is True
        return {"max_turns": LOCAL_TOOL_APPROVAL_MAX_TURNS, "current_turn": 1}


class _FakeResult:
    interruptions = [SimpleNamespace(name="local_text_metrics", call_id="call_1", arguments='{"execution_id":"execution_11111111111111111111111111111111"}')]
    last_response_id = "resp_1"
    context_wrapper = SimpleNamespace(
        usage=SimpleNamespace(
            requests=1,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            input_tokens_details=None,
            output_tokens_details=None,
        )
    )

    def to_state(self):
        return _FakeState()


class _FakeRunner:
    captured_max_turns = None

    @staticmethod
    async def run(_agent, _input, **kwargs):
        _FakeRunner.captured_max_turns = kwargs["max_turns"]
        return _FakeResult()


def _fake_tool(**_kwargs):
    def decorate(function):
        return function

    return decorate


def test_live_sdk_prepare_budget_covers_interruption_and_resume(monkeypatch) -> None:
    sdk = (
        _FakeAgent,
        _FakeModelSettings,
        _FakeRunConfig,
        _FakeRunHooks,
        _FakeRunner,
        object,
        lambda: "trace_1",
        lambda _key: None,
        "0.19.0",
    )
    monkeypatch.setattr(OpenAILocalToolApprovalGateway, "_load", staticmethod(lambda: sdk))
    monkeypatch.setattr(
        gateway_module,
        "build_sdk_function_tool",
        lambda runtime, **_kwargs: SimpleNamespace(name=runtime.tool_id),
    )
    definition = AgentDefinitionCatalog(ROOT).resolve("local-text-metrics-agent")

    async def sink(_event):
        return None

    async def executor():
        return {
            "sha256": "0" * 64,
            "utf8_bytes": 1,
            "characters": 1,
            "words": 1,
            "lines": 1,
        }

    result = asyncio.run(
        OpenAILocalToolApprovalGateway().prepare(
            definition=definition,
            execution_id="execution_11111111111111111111111111111111",
            run_id="run_1",
            settings=RuntimeSettings(model="acceptance-model", api_key="not-a-real-key"),
            lifecycle_sink=sink,
            executor=executor,
        )
    )

    assert LOCAL_TOOL_APPROVAL_MAX_TURNS == 2
    assert _FakeRunner.captured_max_turns == 2
    assert result.state_json["max_turns"] == 2
    assert result.state_json["current_turn"] == 1


def _load_acceptance_script():
    path = ROOT / "scripts" / "run_step020_acceptance.py"
    spec = importlib.util.spec_from_file_location("run_step020_acceptance_for_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decision_child_always_writes_failure_result(tmp_path: Path) -> None:
    module = _load_acceptance_script()
    (tmp_path / "prepare-result.json").write_text("{}", encoding="utf-8")

    exit_code = module.child_decide(tmp_path, "APPROVE", live=False)

    assert exit_code == 1
    payload = json.loads((tmp_path / "decision-result.json").read_text(encoding="utf-8"))
    assert payload["state"] == "FAILED"
    assert payload["error_type"] == "KeyError"
    assert "traceback" in payload


def test_missing_child_result_preserves_redacted_process_diagnostics(tmp_path: Path, monkeypatch) -> None:
    module = _load_acceptance_script()
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-api-key")
    process = subprocess.CompletedProcess(
        args=["python"],
        returncode=1,
        stdout="stdout super-secret-api-key",
        stderr="stderr super-secret-api-key",
    )

    with pytest.raises(RuntimeError, match="without decision-result.json"):
        module._require_child_result(tmp_path, "decision-result.json", process, "decision")

    evidence = json.loads((tmp_path / "decision-child-process.json").read_text(encoding="utf-8"))
    assert evidence["return_code"] == 1
    assert "super-secret-api-key" not in json.dumps(evidence)
    assert "[REDACTED]" in evidence["stdout"]


def test_reference_confirms_runstate_preserves_turn_budget() -> None:
    run_source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/run.py"
    ).read_text(encoding="utf-8")
    state_source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py"
    ).read_text(encoding="utf-8")

    assert "max_turns = run_state._max_turns" in run_source
    assert '"max_turns": self._max_turns' in state_source
    assert '"current_turn": self._current_turn' in state_source


def test_runtime_baseline_exposes_fix_without_claiming_live_acceptance() -> None:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.governed_local_tool_resume_turn_budget == 2
    assert info.governed_local_tool_resume_turn_budget_fix_implemented is True
    assert info.acceptance_child_process_diagnostics_implemented is True
    assert info.local_approval_operator_windows_live_accepted is True
    assert info.governed_local_tool_approval_live_sdk_accepted is True
