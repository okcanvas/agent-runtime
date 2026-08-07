from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.agent.tools.function import (
    FunctionToolApprovalMode,
    FunctionToolDefinitionNotFoundError,
    FunctionToolRuntimeCatalog,
    build_sdk_function_tool,
)


class _Step052CompatModelSettings:
    def __init__(self, **kwargs):
        self.values = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Step052CompatModelRetrySettings:
    def __init__(self, **kwargs):
        self.max_retries = kwargs.get("max_retries")
        self.policy = kwargs.get("policy")


def _install_step052_model_contract(fake_agents) -> None:
    fake_agents.ModelSettings = _Step052CompatModelSettings
    fake_agents.ModelRetrySettings = _Step052CompatModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_resolves_closed_function_tools() -> None:
    catalog = FunctionToolRuntimeCatalog(ROOT)
    runtimes = catalog.list_runtimes()
    assert [item.tool_id for item in runtimes] == [
        "local_text_fingerprint",
        "local_text_metrics",
        "project_readonly_inspect",
        "sandbox_project_readonly_inspect",
    ]
    fingerprint, metrics, project, sandbox_project = runtimes
    assert fingerprint.approval_mode is FunctionToolApprovalMode.NEVER
    assert metrics.approval_mode is FunctionToolApprovalMode.ALWAYS
    for runtime in runtimes:
        binding = runtime.to_binding_dict()
        assert binding["sdk_kind"] == "function_tool"
        expected_runtime_version = (
            "1.1.0" if runtime.tool_id == "project_readonly_inspect"
            else "1.0.0"
        )
        assert binding["runtime_version"] == expected_runtime_version
        for key in (
            "definition_sha256",
            "policy_sha256",
            "input_schema_sha256",
            "output_schema_sha256",
            "implementation_sha256",
        ):
            assert len(binding[key]) == 64
        assert runtime.read_only is True
        expected_filesystem = (
            "read-only" if runtime is project
            else "sandbox-read-only" if runtime is sandbox_project
            else "none"
        )
        assert runtime.filesystem_access == expected_filesystem
        assert runtime.network_access == "none"
        assert runtime.shell_access == "none"
        assert runtime.arguments_persisted is False
        assert runtime.result_persisted_in_events is False


def test_unknown_function_tool_fails_closed() -> None:
    with pytest.raises(FunctionToolDefinitionNotFoundError):
        FunctionToolRuntimeCatalog(ROOT).resolve("unknown_local_tool")


def test_sdk_factory_uses_strict_schema_tool_context_and_constant_approval(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_agents = types.ModuleType("agents")

    class FakeToolContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    def fake_function_tool(**kwargs):
        captured["decorator"] = kwargs

        def decorate(func):
            return SimpleNamespace(
                name=kwargs["name_override"],
                needs_approval=kwargs["needs_approval"],
                params_json_schema={"strict": kwargs["strict_mode"]},
                invoke=func,
            )

        return decorate

    fake_tool_context = types.ModuleType("agents.tool_context")
    fake_tool_context.ToolContext = FakeToolContext
    fake_agents.function_tool = fake_function_tool
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.tool_context", fake_tool_context)

    runtime = FunctionToolRuntimeCatalog(ROOT).resolve("local_text_fingerprint")
    execution_id = "execution_" + "a" * 32
    tool = build_sdk_function_tool(
        runtime,
        execution_id=execution_id,
        protected_text="hello 한글",
    )
    output = asyncio.run(
        tool.invoke(
            SimpleNamespace(context={"execution_id": execution_id}),
            execution_id,
        )
    )
    assert tool.name == "local_text_fingerprint"
    assert tool.needs_approval is False
    assert captured["decorator"]["strict_mode"] is True
    assert captured["decorator"]["failure_error_function"] is None
    assert output.sha256
    assert output.characters == len("hello 한글")
    assert output.utf8_bytes == len("hello 한글".encode("utf-8"))


def test_project_readonly_sdk_tool_uses_exact_configured_workspace(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    fake_agents = types.ModuleType("agents")

    class FakeToolContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    def fake_function_tool(**kwargs):
        captured["decorator"] = kwargs

        def decorate(func):
            return SimpleNamespace(
                name=kwargs["name_override"],
                needs_approval=kwargs["needs_approval"],
                params_json_schema={"strict": kwargs["strict_mode"]},
                invoke=func,
            )

        return decorate

    fake_tool_context = types.ModuleType("agents.tool_context")
    fake_tool_context.ToolContext = FakeToolContext
    fake_agents.function_tool = fake_function_tool
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.tool_context", fake_tool_context)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "router.py").write_text(
        "def register_health(app):\n    app.get('/healthz')\n", encoding="utf-8"
    )
    runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    execution_id = "execution_" + "b" * 32
    tool = build_sdk_function_tool(
        runtime,
        execution_id=execution_id,
        protected_text="Find the health route registration",
        workspace_root=tmp_path,
    )
    output = asyncio.run(
        tool.invoke(SimpleNamespace(context={"execution_id": execution_id}), execution_id)
    )
    assert tool.name == "project_readonly_inspect"
    assert tool.needs_approval is False
    assert output.inspected_files == ["src/router.py"]
    assert output.evidence[0].path == "src/router.py"
    assert str(tmp_path) not in output.model_dump_json()
