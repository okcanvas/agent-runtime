from __future__ import annotations

import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.agent.model.trace_export import (
    TraceExportPolicyCatalog,
    TraceExportPolicyError,
    build_sdk_trace_run_config_kwargs,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "specs/runtime/openai-trace-export-policy.json"
RUN_CONFIG_FILES = (
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/openai_runtime.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/runtime/codex_approval_gateway.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/runtime/codex_gateway.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/runtime/codex_write_gateway.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/runtime/openai_gateway.py"),
    legacy_source_contract(ROOT, "okcanvas_agent_runtime/tool_approval/gateway.py"),
)


def test_trace_export_policy_is_exact_and_runtime_kwargs_disable_sdk_tracing() -> None:
    policy = TraceExportPolicyCatalog(ROOT).resolve()
    assert policy.schema_version == "okcanvas-openai-trace-export-policy-v1"
    assert policy.policy_id == "local-openai-trace-export-disabled-v1"
    assert policy.version == "1.0.0"
    assert policy.sdk_tracing_disabled is True
    assert policy.provider_trace_export_enabled is False
    assert policy.trace_include_sensitive_data is False
    assert policy.persist_local_trace_id is True
    assert len(policy.policy_sha256) == 64
    assert build_sdk_trace_run_config_kwargs(policy) == {
        "tracing_disabled": True,
        "trace_include_sensitive_data": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("sdk_tracing_disabled", False),
        ("provider_trace_export_enabled", True),
        ("trace_include_sensitive_data", True),
        ("persist_local_trace_id", False),
    ),
)
def test_trace_export_policy_fails_closed_on_forbidden_mutation(
    tmp_path: Path, field: str, value: object
) -> None:
    project = tmp_path / "project"
    target = project / "specs/runtime"
    target.mkdir(parents=True)
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload[field] = value
    (target / POLICY_PATH.name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(TraceExportPolicyError):
        TraceExportPolicyCatalog(project).resolve()


def test_runtime_binding_binds_trace_export_policy_and_runtime() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("skill-document-review-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.trace_export_policy["policy_id"] == "local-openai-trace-export-disabled-v1"
    assert binding.trace_export_policy["sdk_tracing_disabled"] is True
    assert binding.trace_export_policy["provider_trace_export_enabled"] is False
    assert binding.trace_export_policy["persist_local_trace_id"] is True
    assert len(binding.trace_export_runtime_sha256) == 64
    fingerprint = binding.to_fingerprint_dict()
    assert fingerprint["trace_export_policy"] == binding.trace_export_policy
    assert fingerprint["trace_export_runtime_sha256"] == binding.trace_export_runtime_sha256


def test_every_sdk_runconfig_path_uses_the_bound_trace_export_policy() -> None:
    for path in RUN_CONFIG_FILES:
        source = path.read_text(encoding="utf-8")
        assert "TraceExportPolicyCatalog" in source, path
        assert "build_sdk_trace_run_config_kwargs" in source, path
        assert "trace_run_config_settings" in source, path
        assert "**trace_run_config_settings" in source, path
        assert "provider_trace_export_enabled" in source, path


def test_step071_windows_live_closure_and_step072_runtime_flags_are_exact() -> None:
    summary = json.loads(
        (ROOT / "docs/evidence/STEP071_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["state"] == "WINDOWS_LIVE_ACCEPTED"
    assert summary["deterministic_passed_checks"] == 28
    assert summary["live_passed_checks"] == 28
    assert summary["model"] == "gpt-4.1"
    assert summary["model_calls"] == 1
    assert summary["usage"]["total_tokens"] == 1145
    assert summary["security"]["undeclared_capability_events"] == 0
    assert summary["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert "Tracing client error 400" in summary["observed_non_fatal_sdk_diagnostic"]

    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_skill_live_provider_accepted is True
    assert info.openai_trace_export_policy_implemented is True
    assert info.openai_agents_sdk_tracing_disabled is True
    assert info.openai_provider_trace_export_enabled is False
    assert info.product_local_trace_id_persisted is True
    assert info.openai_trace_export_deterministic_accepted is True
    assert info.openai_trace_export_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"
