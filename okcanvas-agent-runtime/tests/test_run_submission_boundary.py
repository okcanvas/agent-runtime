from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import base64
import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionContractError
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    RunSubmissionAuthorityError,
    RunSubmissionBoundaryService,
    RunSubmissionExecutionMode,
    RunSubmissionIdempotencyConflict,
    RunSubmissionPolicyCatalog,
    RunSubmissionValidationError,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
REQUEST = "STEP018 raw request sentinel that must never be persisted in SQLite or cleartext"
IDEMPOTENCY_KEY = "step018-idempotency-0001"
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


def _service(
    tmp_path: Path, project_root: Path = ROOT
) -> tuple[RunSubmissionBoundaryService, SQLiteRunSubmissionStore, EncryptedFileProtectedPayloadStore]:
    product = SQLiteProductStore(tmp_path / "product.sqlite3")
    product.initialize()
    store = SQLiteRunSubmissionStore(tmp_path / "product.sqlite3")
    store.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    return (
        RunSubmissionBoundaryService(
            runtime_bindings=AgentRuntimeBindingCatalog(str(project_root)),
            project_root=str(project_root), store=store, protected_payload_store=payloads
        ),
        store,
        payloads,
    )


def test_policy_has_fail_closed_defaults() -> None:
    policy = RunSubmissionPolicyCatalog(ROOT).resolve()
    assert policy.authority_scope == "LOCAL_RUN_SUBMITTER"
    assert policy.idempotency_required is True
    assert policy.read_only_execution_mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION
    assert policy.local_tool_execution_mode is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED
    assert policy.write_mcp_execution_mode is RunSubmissionExecutionMode.PROPOSAL_ONLY
    assert policy.direct_run_api_default_enabled is False
    assert policy.console_mutation_enabled is False
    assert policy.protected_payload_mode == "AES_256_GCM_FILE_V1"


def test_read_only_preflight_encrypts_payload_and_is_idempotent(tmp_path: Path) -> None:
    service, _, payloads = _service(tmp_path)
    first = service.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="reference-research-agent",
        request=REQUEST,
        model="gpt-test",
        idempotency_key=IDEMPOTENCY_KEY,
    )
    replay = service.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="reference-research-agent",
        request=REQUEST,
        model="gpt-test",
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert first.execution_mode is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION
    assert first.executable_now is True
    assert first.approval_required is False
    assert first.protected_payload_persisted is True
    assert first.protected_payload_ref
    assert first.confirmation_challenge
    assert service.confirmation_matches(first, first.confirmation_challenge) is True
    assert service.confirmation_matches(first, first.confirmation_challenge + "x") is False
    assert replay.submission_id == first.submission_id
    assert replay.replayed is True
    assert len(list(payloads.root.glob("payload_*.json"))) == 1

    database = (tmp_path / "product.sqlite3").read_bytes()
    encrypted = next(payloads.root.glob("payload_*.json")).read_bytes()
    assert REQUEST.encode() not in database
    assert REQUEST.encode() not in encrypted
    assert IDEMPOTENCY_KEY.encode() not in database
    assert KEY_TEXT.encode() not in database
    assert KEY_TEXT.encode() not in encrypted


def test_read_only_preflight_requires_concrete_model(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    with pytest.raises(RunSubmissionValidationError):
        service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="work",
            model=None,
            idempotency_key=IDEMPOTENCY_KEY,
        )


def test_idempotency_key_cannot_be_reused_for_different_fingerprint(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    service.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="first input",
        model="gpt-test",
        idempotency_key=IDEMPOTENCY_KEY,
    )
    with pytest.raises(RunSubmissionIdempotencyConflict):
        service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="different input",
            model="gpt-test",
            idempotency_key=IDEMPOTENCY_KEY,
        )


def test_read_only_admin_scope_does_not_grant_submission_authority(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    with pytest.raises(RunSubmissionAuthorityError):
        service.preflight(
            authority_scope="LOCAL_OPERATIONS_READER",
            agent_definition_id="coding-agent",
            request="work",
            model="gpt-test",
            idempotency_key=IDEMPOTENCY_KEY,
        )


def test_unregistered_local_tool_is_rejected_before_preflight(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    definition_path = project / "specs" / "agents" / "coding-agent" / "definition.json"
    payload = json.loads(definition_path.read_text(encoding="utf-8"))
    payload["tools"] = ["controlled_local_tool"]
    definition_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    service, store, payloads = _service(tmp_path / "state", project)
    with pytest.raises(AgentDefinitionContractError):
        service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="work",
            model=None,
            idempotency_key=IDEMPOTENCY_KEY,
        )
    import sqlite3
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0] == 0
    assert not payloads.root.exists() or not list(payloads.root.iterdir())


def test_invalid_submission_fails_before_ledger_or_payload_write(tmp_path: Path) -> None:
    service, _, payloads = _service(tmp_path)
    with pytest.raises(RunSubmissionValidationError):
        service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="\x00",
            model="gpt-test",
            idempotency_key="short",
        )
    import sqlite3

    connection = sqlite3.connect(tmp_path / "product.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0] == 0
    finally:
        connection.close()
    assert not payloads.root.exists() or not list(payloads.root.iterdir())
