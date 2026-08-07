from __future__ import annotations

from tests.artifact_test_support import artifact_service

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import (
    AgentDefinitionCatalog,
    AgentDefinitionContractError,
    AgentDefinitionIntegrityError,
)

ROOT = Path(__file__).resolve().parents[1]


def test_resolves_immutable_coding_agent_definition() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("coding-agent")
    assert definition.agent_id == "coding-agent"
    assert definition.version == "1.0.0"
    assert definition.tools == ()
    assert definition.handoffs == ()
    assert definition.session_mode == "disabled"
    assert definition.output_contract == "CodingAgentResult"
    assert len(definition.definition_sha256) == 64
    assert "This STEP has no tools" in definition.instructions


def test_definition_digest_changes_when_instruction_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    catalog = AgentDefinitionCatalog(project)
    before = catalog.resolve("coding-agent").definition_sha256
    instructions = project / "specs/agents/coding-agent/instructions.md"
    instructions.write_text(instructions.read_text(encoding="utf-8") + "\nExtra rule.\n", encoding="utf-8")
    after = catalog.resolve("coding-agent").definition_sha256
    assert before != after


def test_definition_rejects_traversal_filename(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    path = project / "specs/agents/coding-agent/definition.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["instructions_file"] = "../README.md"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AgentDefinitionContractError):
        AgentDefinitionCatalog(project).resolve("coding-agent")


def test_definition_rejects_symlinked_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    instructions = project / "specs/agents/coding-agent/instructions.md"
    target = tmp_path / "outside.md"
    target.write_text("outside", encoding="utf-8")
    instructions.unlink()
    try:
        instructions.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(AgentDefinitionIntegrityError):
        AgentDefinitionCatalog(project).resolve("coding-agent")


def test_execution_rejects_schema_drift_before_product_state(tmp_path: Path) -> None:
    import asyncio
    from okcanvas_agent_runtime.core.config import RuntimeSettings
    from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, GenericExecutionErrorCode
    from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore

    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    schema = project / "specs/agents/coding-agent/output.schema.json"
    payload = json.loads(schema.read_text(encoding="utf-8"))
    payload["title"] = "DriftedContract"
    schema.write_text(json.dumps(payload), encoding="utf-8")

    class NeverGateway:
        async def run(self, **kwargs):
            raise AssertionError("Gateway must not be called")

    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    envelope = asyncio.run(
        GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(project),
            definitions=AgentDefinitionCatalog(project),
            store=store,
            gateway=NeverGateway(),
            artifact_root=tmp_path / "artifacts",
            artifact_service=artifact_service(store, tmp_path / "artifacts"),
        ).run(
            agent_definition_id="coding-agent",
            request="work",
            settings=RuntimeSettings(model="model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.error and envelope.error.code is GenericExecutionErrorCode.AGENT_DEFINITION_INVALID
    with store._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0


def test_definition_rejects_symlinked_file_even_when_target_stays_inside_definition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    directory = project / "specs/agents/coding-agent"
    target = directory / "alternate.md"
    target.write_text("safe-looking inside target", encoding="utf-8")
    instructions = directory / "instructions.md"
    instructions.unlink()
    try:
        instructions.symlink_to(target.name)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(AgentDefinitionIntegrityError):
        AgentDefinitionCatalog(project).resolve("coding-agent")


def test_session_agent_accepts_exact_always_approval_tool() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("session-approval-agent")
    assert definition.session_mode == "sqlite-v1"
    assert definition.tools == ("local_text_metrics",)
    assert definition.mcp_servers == ()
    assert definition.handoffs == ()
    assert definition.agent_tools == ()
    assert definition.workspace_access == "none"


def test_session_agent_rejects_nonapproval_function_tool(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    path = project / "specs/agents/session-approval-agent/definition.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tools"] = ["local_text_fingerprint"]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(AgentDefinitionContractError):
        AgentDefinitionCatalog(project).resolve("session-approval-agent")
