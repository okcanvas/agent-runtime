from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing.cross_domain_session import (
    CrossDomainSessionContractError,
    CrossDomainSessionDelegationCatalog,
)
from okcanvas_agent_runtime.application.submissions.service import RunSubmissionBoundaryService

ROOT = Path(__file__).resolve().parents[1]


def _request(*capabilities: str) -> str:
    payload = {
        "status": "EXECUTABLE",
        "selected_agent_definition_id": "organization-assistant-session-agent",
        "required_capabilities": list(capabilities),
    }
    return (
        "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        + "\n\nUSER REQUEST:\nfixture"
    )


def test_submission_preflight_uses_unified_cross_domain_owner_not_legacy_groupware_owner() -> None:
    source = inspect.getsource(RunSubmissionBoundaryService.preflight)
    assert "CrossDomainSessionDelegationCatalog" in source
    assert "cross_domain_binding.target_for_request(normalized)" in source
    assert "mcp_server_ids.append(cross_domain_target.mcp_server_id)" in source
    assert "GroupwareSessionDelegationCatalog" not in source
    assert "requires_groupware_session_delegation" not in source


def test_submission_target_is_exactly_one_mcp_from_immutable_routing_context() -> None:
    root = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    binding = CrossDomainSessionDelegationCatalog(ROOT).resolve(root)
    organization = binding.target_for_request(_request("organization-context-read-v1"))
    groupware = binding.target_for_request(_request("groupware-read-v1"))
    assert organization is not None
    assert organization.domain == "ORGANIZATION_CONTEXT"
    assert organization.mcp_server_id == "organization-context-read"
    assert groupware is not None
    assert groupware.domain == "GROUPWARE"
    assert groupware.mcp_server_id == "groupware-read"


def test_submission_target_rejects_two_delegated_read_domains_in_one_turn() -> None:
    root = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    binding = CrossDomainSessionDelegationCatalog(ROOT).resolve(root)
    with pytest.raises(CrossDomainSessionContractError, match="Exactly one delegated read domain"):
        binding.target_for_request(_request("organization-context-read-v1", "groupware-read-v1"))
