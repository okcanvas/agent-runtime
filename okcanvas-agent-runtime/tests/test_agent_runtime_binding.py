from __future__ import annotations

from tests.artifact_test_support import artifact_service

import asyncio
import base64
import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog, GenericAgentExecutionService
from okcanvas_agent_runtime.application.execution.output_registry import OutputContractRuntime
from okcanvas_agent_runtime.application.execution import output_registry
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    RunSubmissionIdempotencyConflict,
    RunSubmissionIntegrityError,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class NeverGateway:
    async def run(self, **_kwargs):
        raise AssertionError("model gateway must not be called")


class CapturingScheduler:
    def __init__(self) -> None:
        self.calls = 0

    async def schedule_prepared(self, *, prepared, settings):
        self.calls += 1
        return object()


def _project_copy(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    return project


def _services(tmp_path: Path, project: Path):
    db = tmp_path / "product.sqlite3"
    product = SQLiteProductStore(db)
    product.initialize()
    submissions = SQLiteRunSubmissionStore(db)
    submissions.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "payloads", ProtectedPayloadKey.from_text(KEY)
    )
    payloads.initialize()
    definitions = AgentDefinitionCatalog(project)
    execution = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog((definitions).project_root),
        definitions=definitions,
        store=product,
        gateway=NeverGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(product, tmp_path / "artifacts"),
    )
    scheduler = CapturingScheduler()
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
        project_root=str(project),
        store=submissions,
        protected_payload_store=payloads,
    )
    governed = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
        project_root=str(project),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=scheduler,
    )
    return product, submissions, payloads, boundary, governed, scheduler


def test_runtime_bindings_cover_generic_mcp_and_local_tool_paths() -> None:
    catalog = AgentRuntimeBindingCatalog(ROOT)
    definitions = AgentDefinitionCatalog(ROOT)
    coding = catalog.resolve(definitions.resolve("coding-agent"))
    reference = catalog.resolve(definitions.resolve("reference-research-agent"))
    local_tool = catalog.resolve(definitions.resolve("local-text-metrics-agent"))

    assert coding.execution_path == "generic-agent-execution-v1"
    assert coding.mcp_servers == ()
    assert coding.local_tools == ()
    assert reference.execution_path == "generic-agent-execution-v1"
    assert len(reference.mcp_servers) == 1
    assert reference.mcp_servers[0]["server_id"] == "reference-catalog"
    assert len(reference.mcp_servers[0]["definition_sha256"]) == 64
    assert len(reference.mcp_servers[0]["module_sha256"]) == 64
    assert local_tool.execution_path == "governed-function-tool-approval-v1"
    assert local_tool.local_tools[0]["tool_id"] == "local_text_metrics"
    assert len(local_tool.local_tools[0]["policy_sha256"]) == 64
    assert len(local_tool.local_tools[0]["implementation_sha256"]) == 64
    assert len({coding.runtime_binding_sha256, reference.runtime_binding_sha256, local_tool.runtime_binding_sha256}) == 3


def test_preflight_binds_runtime_sha_to_ledger_fingerprint_and_payload(tmp_path: Path) -> None:
    project = _project_copy(tmp_path)
    _, submissions, payloads, boundary, _, _ = _services(tmp_path / "state", project)
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="bind this Runtime behavior",
        model="test-model",
        idempotency_key="step033-runtime-binding-0001",
    )
    expected = AgentRuntimeBindingCatalog(project).resolve(
        AgentDefinitionCatalog(project).resolve("coding-agent")
    )
    assert decision.runtime_binding_sha256 == expected.runtime_binding_sha256
    assert len(decision.runtime_binding_sha256) == 64
    stored = submissions.get(decision.submission_id)
    assert stored.runtime_binding_sha256 == decision.runtime_binding_sha256
    payload = payloads.read(
        decision.protected_payload_ref or "",
        expected_file_sha256=decision.protected_payload_sha256 or "",
        expected_byte_length=decision.protected_payload_byte_length or 0,
    )
    assert payload.runtime_binding_sha256 == decision.runtime_binding_sha256


def test_output_runtime_drift_conflicts_replay_and_blocks_confirmation(tmp_path: Path) -> None:
    project = _project_copy(tmp_path)
    product, _, _, boundary, governed, scheduler = _services(tmp_path / "state", project)
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="do not execute after runtime drift",
        model="test-model",
        idempotency_key="step033-output-drift-0001",
    )
    original = output_registry._OUTPUT_CONTRACTS["CodingAgentResult"]
    output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = OutputContractRuntime(
        contract_name="CodingAgentResult",
        output_type=CodingAgentResult,
        runtime_version="1.0.1",
        implementation_id="coding-agent-result-runtime-drift-fixture",
    )
    try:
        with pytest.raises(RunSubmissionIdempotencyConflict):
            boundary.preflight(
                authority_scope="LOCAL_RUN_SUBMITTER",
                agent_definition_id="coding-agent",
                request="do not execute after runtime drift",
                model="test-model",
                idempotency_key="step033-output-drift-0001",
            )
        with pytest.raises(RunSubmissionIntegrityError):
            asyncio.run(
                governed.confirm_and_schedule(
                    submission_id=decision.submission_id,
                    confirmation=decision.confirmation_challenge or "",
                    settings=RuntimeSettings(model="test-model", api_key="test-key"),
                )
            )
    finally:
        output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = original
    assert scheduler.calls == 0
    assert product.list_tasks(limit=10) == ([], 0)
    assert product.list_runs(limit=10) == ([], 0)


def test_mcp_definition_drift_blocks_confirmation_before_product_state(tmp_path: Path) -> None:
    project = _project_copy(tmp_path)
    product, _, _, boundary, governed, scheduler = _services(tmp_path / "state", project)
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="reference-research-agent",
        request="inspect immutable references",
        model="test-model",
        idempotency_key="step033-mcp-drift-0001",
    )
    server = project / "specs" / "mcp" / "servers" / "reference-catalog" / "server.json"
    payload = json.loads(server.read_text(encoding="utf-8"))
    payload["max_result_chars"] = int(payload["max_result_chars"]) - 1
    server.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(RunSubmissionIntegrityError):
        asyncio.run(
            governed.confirm_and_schedule(
                submission_id=decision.submission_id,
                confirmation=decision.confirmation_challenge or "",
                settings=RuntimeSettings(model="test-model", api_key="test-key"),
            )
        )
    assert scheduler.calls == 0
    assert product.list_tasks(limit=10) == ([], 0)
    assert product.list_runs(limit=10) == ([], 0)


def test_sqlite_session_approval_binding_is_exact_and_distinct() -> None:
    catalog = AgentRuntimeBindingCatalog(ROOT)
    definition = AgentDefinitionCatalog(ROOT).resolve("session-approval-agent")
    binding = catalog.resolve(definition)
    assert binding.execution_path == "sqlite-session-approval-execution-v1"
    assert len(binding.local_tools) == 1
    assert binding.local_tools[0]["tool_id"] == "local_text_metrics"
    assert binding.local_tools[0]["approval_mode"] == "ALWAYS"
    assert binding.session_policy is not None
    assert binding.session_policy["sqlite_session"]["session_mode"] == "sqlite-v1"
    assert binding.session_policy["approval_composition"]["approval_mode"] == "ALWAYS"
    assert binding.session_policy["approval_composition"]["hold_turn_lease_while_interrupted"] is True
    assert len(binding.session_runtime_sha256 or "") == 64


def test_session_approval_preflight_binds_session_into_encrypted_payload(tmp_path: Path, monkeypatch) -> None:
    import sys
    import types

    project = _project_copy(tmp_path)
    # The project copy includes the new Session+approval Agent and policy.
    _, submissions, payloads, boundary, _, _ = _services(tmp_path / "state", project)
    definition = AgentDefinitionCatalog(project).resolve("session-approval-agent")
    binding = AgentRuntimeBindingCatalog(project).resolve(definition)

    class FakeSessionRuntime:
        def validate_binding(self, *, session_id, definition, runtime_binding_sha256):
            assert session_id == "session_" + "a" * 32
            assert runtime_binding_sha256 == binding.runtime_binding_sha256
            return object()

    boundary._sessions = FakeSessionRuntime()
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="session-approval-agent",
        request="session approval encrypted identity",
        model="test-model",
        idempotency_key="step046-session-payload-0001",
        session_id="session_" + "a" * 32,
    )
    stored = submissions.get(decision.submission_id)
    assert stored.session_id == decision.session_id
    payload = payloads.read(
        decision.protected_payload_ref or "",
        expected_file_sha256=decision.protected_payload_sha256 or "",
        expected_byte_length=decision.protected_payload_byte_length or 0,
    )
    assert payload.session_id == decision.session_id
