from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.persistence.service_ownership import SQLiteServiceResourceOwnershipStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.assistant_routing.grounded_delegation import (
    grounded_structured_delegation_context,
)
from okcanvas_agent_runtime.application.submissions import (
    RunSubmissionAuthorityError,
    RunSubmissionBoundaryService,
    RunSubmissionOwnershipTransition,
    SQLiteRunSubmissionStore,
)
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

ROOT = Path(__file__).resolve().parents[1]
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_ID = "session_" + "b" * 32


def _grounded_request() -> str:
    routing = {
        "schema_version": "okcanvas-assistant-routing-context-v2",
        "request_class": "ANSWER",
        "side_effect": "NONE",
        "status": "EXECUTABLE",
        "required_capabilities": [],
        "matched_rule_id": "default-general-answer-v1",
        "selected_agent_definition_id": "organization-assistant-session-agent",
        "grounded_structured_delegation": grounded_structured_delegation_context(),
    }
    return (
        "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
        + json.dumps(routing, ensure_ascii=False, sort_keys=True)
        + "\n\nUSER REQUEST:\n"
        + "김민수 연락처 알려줘"
    )


def _boundary(tmp_path: Path):
    product = SQLiteProductStore(tmp_path / "product.sqlite3")
    product.initialize()
    SQLiteServiceResourceOwnershipStore(tmp_path / "product.sqlite3").initialize()
    store = SQLiteRunSubmissionStore(tmp_path / "product.sqlite3")
    store.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT),
        store=store,
        protected_payload_store=payloads,
    )
    definition = boundary._agents.resolve("organization-assistant-session-agent")
    binding = boundary._runtime_bindings.resolve(definition)

    class FakeSessionRuntime:
        def validate_binding(self, *, session_id, definition, runtime_binding_sha256):
            assert session_id == SESSION_ID
            assert runtime_binding_sha256 == binding.runtime_binding_sha256
            return object()

    boundary._sessions = FakeSessionRuntime()
    return boundary, payloads


def test_grounded_root_preserves_authenticated_delegated_identity_before_legacy_child_selection(
    tmp_path: Path,
) -> None:
    boundary, payloads = _boundary(tmp_path)
    request = _grounded_request()
    # The legacy cross-domain selector has no required capability here. STEP096B still needs
    # delegated identity so the turn-local hint plane and later lazy child admission can operate.
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="organization-assistant-session-agent",
        request=request,
        model="gpt-test",
        idempotency_key="step096br1r2-grounded-identity-0001",
        session_id=SESSION_ID,
        ownership_transition=RunSubmissionOwnershipTransition(
            tenant_id="tenant-a",
            principal_id="user-001",
            roles=("agent-user",),
        ),
    )
    payload = payloads.read(
        decision.protected_payload_ref or "",
        expected_file_sha256=decision.protected_payload_sha256 or "",
        expected_byte_length=decision.protected_payload_byte_length or 0,
    )
    identity = payload.delegated_mcp_identity
    assert identity is not None
    assert identity.tenant_id == "tenant-a"
    assert identity.principal_id == "user-001"
    assert identity.roles == ("agent-user",)


def test_grounded_root_requires_authenticated_principal_for_delegated_identity(tmp_path: Path) -> None:
    boundary, _payloads = _boundary(tmp_path)
    with pytest.raises(
        RunSubmissionAuthorityError,
        match="grounded Session read requires an authenticated service principal",
    ):
        boundary.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="organization-assistant-session-agent",
            request=_grounded_request(),
            model="gpt-test",
            idempotency_key="step096br1r2-grounded-identity-0002",
            session_id=SESSION_ID,
            ownership_transition=None,
        )


def test_hint_provider_reports_identity_unavailable_without_exposing_diagnostic_to_model() -> None:
    from okcanvas_agent_runtime.adapters.mcp.organization_interpretation_hints import (
        OrganizationGroundedInterpretationContextProvider,
    )
    import asyncio

    context = asyncio.run(
        OrganizationGroundedInterpretationContextProvider(ROOT).build(
            utterance="김민수 연락처 알려줘",
            delegated_identity=None,
            session_focus=None,
        )
    )
    assert context.organization_hints.state.value == "UNAVAILABLE"
    assert context.organization_hints.diagnostic_code == "DELEGATED_IDENTITY_UNAVAILABLE"
    assert "diagnostic_code" not in context.organization_hints.to_model_dict()
