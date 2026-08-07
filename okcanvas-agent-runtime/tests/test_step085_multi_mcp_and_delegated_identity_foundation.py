from __future__ import annotations

import asyncio
import json
import hashlib
import shutil
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.mcp.clients import create_openai_mcp_runtime, remote_mcp_headers
from okcanvas_agent_runtime.adapters.storage.protected_payload import EncryptedFileProtectedPayloadStore, ProtectedPayloadKey
from okcanvas_agent_runtime.agent.mcp.definitions import MCPDefinitionContractError, MCPServerCatalog
from okcanvas_agent_runtime.application.mcp_access import (
    DelegatedMCPIdentity,
    MCPAccessCatalog,
    MCPAccessContractError,
    MCPPassiveHealthRegistry,
)
from okcanvas_agent_runtime.application.submissions.protected_payload import ProtectedPayloadContent
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

ROOT = Path(__file__).resolve().parents[1]
ENV = "OKCANVAS_MCP_SHARED_READ_BEARER"


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


def _project(tmp_path: Path, count: int = 2) -> Path:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    server_ids = [f"enterprise-read-{index}" for index in range(1, count + 1)]
    allowlist_path = project / "specs/mcp/allowlist.json"
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    allowlist["allowed_server_ids"].extend(server_ids)
    allowlist_path.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    refs = {
        "schema_version": "okcanvas-mcp-credential-references-v1",
        "references": [{
            "credential_ref": "shared-read-credential",
            "authorization_mode": "delegated-bearer-ref",
            "environment_variable": ENV,
        }],
    }
    (project / "specs/mcp/access/credential-references.json").write_text(
        json.dumps(refs, indent=2) + "\n", encoding="utf-8"
    )
    for server_id in server_ids:
        directory = project / "specs/mcp/servers" / server_id
        directory.mkdir()
        (directory / "server.json").write_text(
            json.dumps(_server(server_id), indent=2) + "\n", encoding="utf-8"
        )
    return project


def test_default_product_access_catalog_has_no_credential_values() -> None:
    catalog = MCPAccessCatalog(ROOT)
    assert catalog.policy.max_remote_servers_per_agent == 4
    assert all(item.credential_ref for item in catalog.secret_references.values())
    assert all(item.environment_variable for item in catalog.secret_references.values())
    public = catalog.to_public_dict()
    assert public["credential_values_exposed"] is False
    assert len(public["credential_references"]) == len(catalog.secret_references)
    assert all("environment_variable" in item for item in public["credential_references"])


def test_multi_remote_v3_catalog_and_delegated_binding(tmp_path: Path) -> None:
    project = _project(tmp_path)
    definitions = MCPServerCatalog(project).resolve_many(("enterprise-read-1", "enterprise-read-2"))
    assert len(definitions) == 2
    assert all(item.requires_delegated_identity for item in definitions)
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="alice", roles=("agent-user",)
    )
    bindings = MCPAccessCatalog(project).bind_many(definitions, identity)
    assert [item.server_id for item in bindings if item] == ["enterprise-read-1", "enterprise-read-2"]
    assert bindings[0] is not None
    assert bindings[0].url == "https://enterprise-read-1.example.invalid/tenants/tenant-a/mcp"
    assert bindings[0].identity_headers()["X-OKCanvas-Principal-ID"] == "alice"
    assert bindings[0].identity_headers()["X-OKCanvas-Roles"] == "agent-user"
    assert "secret" not in repr(bindings[0].to_public_dict())


def test_delegated_binding_fails_closed_for_missing_identity_role_or_secret_ref(tmp_path: Path) -> None:
    project = _project(tmp_path, count=1)
    definition = MCPServerCatalog(project).resolve("enterprise-read-1")
    access = MCPAccessCatalog(project)
    with pytest.raises(MCPAccessContractError, match="identity"):
        access.bind_many((definition,), None)
    denied = DelegatedMCPIdentity.create(tenant_id="tenant-a", principal_id="alice", roles=("other",))
    with pytest.raises(MCPAccessContractError, match="role"):
        access.bind_many((definition,), denied)
    missing = replace(definition, credential_ref="missing-reference")
    allowed = DelegatedMCPIdentity.create(tenant_id="tenant-a", principal_id="alice", roles=("agent-user",))
    with pytest.raises(MCPAccessContractError, match="credential"):
        access.bind_many((missing,), allowed)


def test_v3_rejects_more_than_four_remote_servers(tmp_path: Path) -> None:
    project = _project(tmp_path, count=5)
    with pytest.raises(MCPDefinitionContractError, match="at most four"):
        MCPServerCatalog(project).resolve_many(tuple(f"enterprise-read-{i}" for i in range(1, 6)))


def test_factory_builds_two_remote_servers_with_delegated_headers(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    definitions = MCPServerCatalog(project).resolve_many(("enterprise-read-1", "enterprise-read-2"))
    identity = DelegatedMCPIdentity.create(tenant_id="tenant-a", principal_id="alice", roles=("agent-user",))
    bindings = MCPAccessCatalog(project).bind_many(definitions, identity)
    monkeypatch.setenv(ENV, "secret-token")
    captured: dict[str, object] = {"remotes": []}
    agents_mcp = types.ModuleType("agents.mcp")
    agents_mcp_util = types.ModuleType("agents.mcp.util")

    class FakeRemote:
        def __init__(self, **kwargs):
            captured["remotes"].append(kwargs)
            self.name = kwargs["name"]
            self.cached_tools = None
        async def connect(self): return None
        async def cleanup(self): return None
        async def list_tools(self, *args, **kwargs): return []
        async def call_tool(self, *args, **kwargs):
            return types.SimpleNamespace(model_dump_json=lambda: '{"ok":true}')

    class FakeManager:
        def __init__(self, servers, **kwargs):
            captured["manager"] = {"servers": servers, **kwargs}
            self.active_servers = list(servers)

    agents_mcp.MCPServerStdio = object
    agents_mcp.MCPServerStreamableHttp = FakeRemote
    agents_mcp.MCPServerManager = FakeManager
    agents_mcp_util.create_static_tool_filter = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "agents.mcp", agents_mcp)
    monkeypatch.setitem(sys.modules, "agents.mcp.util", agents_mcp_util)

    runtime = create_openai_mcp_runtime(
        definitions, project_root=project, access_bindings=bindings,
        health_registry=MCPPassiveHealthRegistry(),
    )
    assert len(runtime.servers) == 2
    assert captured["manager"]["connect_in_parallel"] is True
    headers = captured["remotes"][0]["params"]["headers"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["X-OKCanvas-Tenant-ID"] == "tenant-a"
    assert headers["X-OKCanvas-Principal-ID"] == "alice"
    assert headers["X-OKCanvas-Roles"] == "agent-user"
    assert headers["X-OKCanvas-Delegation-ID"].startswith("delegation_")
    assert "secret-token" not in repr(definitions[0].to_public_dict())


def test_passive_circuit_opens_after_threshold() -> None:
    registry = MCPPassiveHealthRegistry()
    registry.record_failure("server", threshold=2, reset_seconds=30.0)
    registry.require_available("server")
    registry.record_failure("server", threshold=2, reset_seconds=30.0)
    with pytest.raises(RuntimeError, match="open"):
        registry.require_available("server")
    registry.record_success("server")
    registry.require_available("server")


def test_protected_payload_round_trip_preserves_delegated_identity(tmp_path: Path) -> None:
    identity = DelegatedMCPIdentity.create(tenant_id="tenant-a", principal_id="alice", roles=("agent-user",))
    content = ProtectedPayloadContent(
        submission_id="submission_" + "1" * 32,
        agent_definition_id="agent",
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
    store = EncryptedFileProtectedPayloadStore(
        tmp_path / "payloads", ProtectedPayloadKey.from_text("11" * 32)
    )
    record = store.write(content)
    restored = store.read(
        record.payload_ref,
        expected_file_sha256=record.file_sha256,
        expected_byte_length=record.byte_length,
    )
    assert restored.delegated_mcp_identity == identity


def test_runtime_binding_selects_v3_multi_remote_delegated_execution_path(tmp_path: Path) -> None:
    project = _project(tmp_path)
    base = AgentDefinitionCatalog(project).resolve("reference-research-agent")
    definition = replace(
        base,
        agent_id="enterprise-read-agent",
        name="Enterprise Read Agent",
        mcp_servers=("enterprise-read-1", "enterprise-read-2"),
    )
    binding = AgentRuntimeBindingCatalog(project).resolve(definition)
    assert binding.execution_path == "multi-remote-mcp-delegated-identity-execution-v1"
    assert len(binding.mcp_servers) == 2
    assert {item["credential_ref"] for item in binding.mcp_servers} == {"shared-read-credential"}
    assert {item["required_roles"] for item in binding.mcp_servers} == {"agent-user"}
    assert all(item["endpoint_mode"] == "tenant-template" for item in binding.mcp_servers)
    assert "secret-token" not in repr(binding.to_fingerprint_dict())


def test_step085_local_evidence_is_excluded_from_product_inventory() -> None:
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES, included_relative_path
    relative = Path("docs/evidence/step085-local/python-regression/chunk-000-019.txt")
    assert ("docs", "evidence", "step085-local") in EXCLUDED_PREFIXES
    assert included_relative_path(relative) is False
    assert "docs/evidence/step085-local/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_source_packager_rejects_option_like_output() -> None:
    from scripts.package_source import main
    with pytest.raises(SystemExit, match="positional output path"):
        main(["--output", "candidate.zip"])
    for residue in ("--output", "--help", "--output.sha256", "--help.sha256"):
        assert not (ROOT / residue).exists()
