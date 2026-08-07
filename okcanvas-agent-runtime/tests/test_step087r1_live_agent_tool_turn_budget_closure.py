from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_live_groupware_agent_tool_turn_budgets_are_exact() -> None:
    catalog = AgentDefinitionCatalog(ROOT)
    root = catalog.resolve("organization-assistant-session-agent")
    child = catalog.resolve("groupware-read-agent")

    # Real OpenAI Agents execution needs one parent model turn to invoke the
    # child and one more parent model turn to produce the final output.  The
    # child similarly needs one MCP Tool turn and one final-output turn.
    assert root.max_turns == 2
    assert child.max_turns == 2
    assert root.session_mode == "sqlite-v1"
    assert child.session_mode == "disabled"


def test_groupware_child_live_tool_choice_is_required_in_gateway_source() -> None:
    source = (
        ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py"
    ).read_text(encoding="utf-8")
    assert 'delegated_session_binding is not None' in source
    assert 'child_agent_kwargs["model_settings"] = ModelSettings(' in source
    assert 'tool_choice="required"' in source
    assert 'child_agent_kwargs["reset_tool_choice"] = True' in source


def test_bundled_sdk_run_loop_proves_tool_calls_consume_turn_budget() -> None:
    source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/run.py"
    ).read_text(encoding="utf-8")
    assert "NextStepRunAgain" in source
    assert "current_turn += 1" in source
    assert "current_turn > max_turns" in source
    assert "MaxTurnsExceeded" in source


def test_runtime_info_exposes_live_turn_budget_closure_without_live_claim() -> None:
    info = RuntimeInfo()
    assert info.main_assistant_groupware_root_max_turns == 2
    assert info.main_assistant_groupware_child_max_turns == 2
    assert info.main_assistant_groupware_child_tool_choice_required is True
    assert info.main_assistant_groupware_live_agent_tool_turn_budget_closed is True
    assert info.main_assistant_groupware_live_openai_provider_verified is False


def test_environment_example_declares_live_openai_inputs_without_values() -> None:
    text = (ROOT / ".env.local.example").read_text(encoding="utf-8")
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    assert "OPENAI_API_KEY" in values
    assert "OKCANVAS_AGENT_MODEL" in values
    assert values["OPENAI_API_KEY"] == ""
    assert values["OKCANVAS_AGENT_MODEL"] == ""


def test_local_environment_loader_exports_only_source_and_loaded_key_names() -> None:
    source = (ROOT / "scripts/windows_entrypoint.py").read_text(encoding="utf-8")
    assert 'environment["OKCANVAS_LOCAL_ENV_SOURCE_NAME"]' in source
    assert 'environment["OKCANVAS_LOCAL_ENV_LOADED_KEYS"]' in source
    assert '",".join(sorted(local_values))' in source
    assert "OKCANVAS_LOCAL_ENV_VALUES" not in source
