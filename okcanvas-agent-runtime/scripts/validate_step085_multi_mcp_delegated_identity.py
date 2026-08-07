from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPDefinitionContractError, MCPServerCatalog
from okcanvas_agent_runtime.application.mcp_access import (
    DelegatedMCPIdentity,
    MCPAccessCatalog,
    MCPAccessContractError,
    MCPPassiveHealthRegistry,
)
from okcanvas_agent_runtime.application.submissions.protected_payload import ProtectedPayloadContent
from okcanvas_agent_runtime.adapters.storage.protected_payload import EncryptedFileProtectedPayloadStore, ProtectedPayloadKey
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION"
VERSION = "2.65.0"
ENV_NAME = "OKCANVAS_STEP085_SHARED_READ_BEARER"


def _server(server_id: str, role: str = "agent-user") -> dict[str, object]:
    return {
        "schema_version": "okcanvas-mcp-server-v3",
        "server_id": server_id,
        "version": "1.0.0",
        "name": server_id.replace("-", " ").title(),
        "kind": "remote-streamable-http",
        "endpoint_mode": "tenant-template",
        "url_template": f"https://{server_id}.example.invalid/tenants/{{tenant_id}}/mcp",
        "authorization_mode": "delegated-bearer-ref",
        "credential_ref": "shared-read-credential",
        "required_roles": [role],
        "allowed_tools": ["search_records", "read_record"],
        "read_only": True,
        "cache_tools_list": True,
        "connect_timeout_seconds": 10.0,
        "cleanup_timeout_seconds": 5.0,
        "tool_timeout_seconds": 15.0,
        "http_timeout_seconds": 15.0,
        "sse_read_timeout_seconds": 120.0,
        "max_retry_attempts": 0,
        "retry_backoff_seconds_base": 1.0,
        "max_result_chars": 24000,
        "health_mode": "passive",
        "circuit_breaker_failure_threshold": 2,
        "circuit_breaker_reset_seconds": 30.0,
    }


def _fixture(count: int = 2) -> Path:
    root = Path(tempfile.mkdtemp(prefix="okcanvas-step085-mcp-"))
    shutil.copytree(ROOT / "specs", root / "specs")
    server_ids = [f"enterprise-read-{index}" for index in range(1, count + 1)]
    allowlist_path = root / "specs/mcp/allowlist.json"
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    allowlist["allowed_server_ids"].extend(server_ids)
    allowlist_path.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    refs = {
        "schema_version": "okcanvas-mcp-credential-references-v1",
        "references": [{
            "credential_ref": "shared-read-credential",
            "authorization_mode": "delegated-bearer-ref",
            "environment_variable": ENV_NAME,
        }],
    }
    (root / "specs/mcp/access/credential-references.json").write_text(
        json.dumps(refs, indent=2) + "\n", encoding="utf-8"
    )
    for server_id in server_ids:
        directory = root / "specs/mcp/servers" / server_id
        directory.mkdir()
        (directory / "server.json").write_text(
            json.dumps(_server(server_id), indent=2) + "\n", encoding="utf-8"
        )
    return root


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    default_access = MCPAccessCatalog(ROOT)
    fixture = _fixture(2)
    definitions = MCPServerCatalog(fixture).resolve_many(("enterprise-read-1", "enterprise-read-2"))
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="alice", roles=("agent-user", "agent-user")
    )
    bindings = MCPAccessCatalog(fixture).bind_many(definitions, identity)
    base = AgentDefinitionCatalog(fixture).resolve("reference-research-agent")
    binding = AgentRuntimeBindingCatalog(fixture).resolve(
        replace(base, agent_id="enterprise-read-agent", name="Enterprise Read Agent", mcp_servers=("enterprise-read-1", "enterprise-read-2"))
    )
    missing_identity_blocked = False
    role_blocked = False
    count_blocked = False
    try:
        MCPAccessCatalog(fixture).bind_many(definitions, None)
    except MCPAccessContractError:
        missing_identity_blocked = True
    try:
        denied = DelegatedMCPIdentity.create(tenant_id="tenant-a", principal_id="alice", roles=("other",))
        MCPAccessCatalog(fixture).bind_many(definitions, denied)
    except MCPAccessContractError:
        role_blocked = True
    too_many = _fixture(5)
    try:
        MCPServerCatalog(too_many).resolve_many(tuple(f"enterprise-read-{i}" for i in range(1, 6)))
    except MCPDefinitionContractError:
        count_blocked = True
    health = MCPPassiveHealthRegistry()
    health.record_failure("enterprise-read-1", threshold=2, reset_seconds=30.0)
    health.record_failure("enterprise-read-1", threshold=2, reset_seconds=30.0)
    circuit_opened = False
    try:
        health.require_available("enterprise-read-1")
    except RuntimeError:
        circuit_opened = True
    protected = ProtectedPayloadContent(
        submission_id="submission_" + "1" * 32,
        agent_definition_id="enterprise-read-agent",
        agent_definition_version="1.0.0",
        agent_definition_sha256="a" * 64,
        runtime_binding_sha256="b" * 64,
        session_id=None,
        model="gpt-4.1",
        request="read",
        input_sha256=hashlib.sha256(b"read").hexdigest(),
        request_fingerprint_sha256="d" * 64,
        created_at="2026-08-04T00:00:00Z",
        delegated_mcp_identity=identity,
    )
    payload_root = Path(tempfile.mkdtemp(prefix="okcanvas-step085-payload-"))
    store = EncryptedFileProtectedPayloadStore(payload_root, ProtectedPayloadKey.from_text("11" * 32))
    record = store.write(protected)
    restored = store.read(record.payload_ref, expected_file_sha256=record.file_sha256, expected_byte_length=record.byte_length)
    public = default_access.to_public_dict()
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "runtime_info_foundation_exact": info.multi_mcp_foundation_implemented is True
        and info.multi_mcp_max_remote_servers_per_agent == 4
        and info.delegated_mcp_identity_implemented is True,
        "default_credentials_empty": default_access.secret_references == {},
        "credential_values_never_public": public["credential_values_exposed"] is False,
        "v3_multi_remote_resolved": len(definitions) == 2 and all(item.requires_delegated_identity for item in definitions),
        "tenant_endpoint_binding_exact": bindings[0] is not None
        and bindings[0].url == "https://enterprise-read-1.example.invalid/tenants/tenant-a/mcp",
        "delegated_headers_exact": bindings[0] is not None
        and set(bindings[0].identity_headers()) == {
            "X-OKCanvas-Tenant-ID", "X-OKCanvas-Principal-ID", "X-OKCanvas-Roles", "X-OKCanvas-Delegation-ID"
        },
        "identity_fingerprint_deterministic": identity.delegation_id.startswith("delegation_")
        and identity.roles == ("agent-user",),
        "missing_identity_fails_closed": missing_identity_blocked,
        "missing_role_fails_closed": role_blocked,
        "remote_count_bounded": count_blocked,
        "runtime_binding_execution_path_exact": binding.execution_path == "multi-remote-mcp-delegated-identity-execution-v1",
        "runtime_binding_has_two_servers": len(binding.mcp_servers) == 2,
        "runtime_binding_has_no_secret_values": ENV_NAME not in repr(binding.to_fingerprint_dict())
        and "secret-token" not in repr(binding.to_fingerprint_dict()),
        "passive_circuit_opens": circuit_opened,
        "delegated_identity_protected_roundtrip": restored.delegated_mcp_identity == identity,
        "protected_payload_schema_v6": info.delegated_mcp_identity_protected_payload_schema == "okcanvas-protected-payload-content-v6",
        "mcp_write_remains_disabled": info.delegated_mcp_write_enabled is False,
        "oauth_refresh_not_claimed": info.delegated_mcp_oauth_refresh_enabled is False,
        "external_endpoints_not_configured": info.delegated_mcp_external_endpoints_configured is False,
        "tool_search_remains_disabled": info.organization_assistant_tool_search_runtime_enabled is False
        and info.organization_assistant_programmatic_tool_calling_runtime_enabled is False,
        "next_step_exact": info.next_selected_step == "STEP086_GROUPWARE_READ_ONLY_VERTICAL",
    }
    return {
        "schema_version": "okcanvas-step085-multi-mcp-delegated-identity-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "default_access_catalog": public,
        "bound_servers": [item.to_public_dict() for item in bindings if item is not None],
        "runtime_binding": {
            "execution_path": binding.execution_path,
            "mcp_server_count": len(binding.mcp_servers),
            "runtime_binding_sha256": binding.runtime_binding_sha256,
        },
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
