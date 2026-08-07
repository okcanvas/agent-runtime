from __future__ import annotations

import asyncio
import json
import os
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT.parents[1] / "okcanvas-connector-examples" / "organization-context" / "organization-context-api-fake"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organization_context_mcp_server.app import create_app
from organization_context_mcp_server.config import Settings
from organization_context_mcp_server.identity import DelegatedIdentity


def _resolve_executable(name: str) -> str:
    candidates = [name]
    if os.name == "nt" and Path(name).suffix == "":
        candidates.extend([f"{name}.cmd", f"{name}.exe", f"{name}.bat"])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return str(Path(resolved).resolve())
    raise FileNotFoundError(f"required executable was not found on PATH: {name}")


def _prepare_invocation(executable: str, arguments: list[str]) -> tuple[list[str] | str, bool]:
    command = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(command), True
    return command, False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_ready(base_url: str) -> None:
    deadline = time.monotonic() + 10
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"{base_url}/healthz", timeout=0.5)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)
    raise RuntimeError("Organization Context API example did not become ready")


def _headers(identity: DelegatedIdentity) -> dict[str, str]:
    return {
        "Authorization": "Bearer connector-secret",
        "X-OKCanvas-Tenant-ID": identity.tenant_id,
        "X-OKCanvas-Principal-ID": identity.principal_id,
        "X-OKCanvas-Roles": ",".join(identity.roles),
        "X-OKCanvas-Delegation-ID": identity.delegation_id,
        "Accept": "application/json, text/event-stream",
    }


def _product_headers(identity: DelegatedIdentity, *, admin: bool = False) -> dict[str, str]:
    roles = tuple(sorted(set((*identity.roles, "admin")))) if admin else identity.roles
    return {
        "Authorization": "Bearer example-organization-context-api-token",
        "Content-Type": "application/json",
        "X-Tenant-ID": identity.tenant_id,
        "X-Principal-ID": identity.principal_id,
        "X-Principal-Roles": ",".join(roles),
        "X-Organization-Unit-ID": "strategy" if admin else "hr",
        "X-Delegation-ID": DelegatedIdentity.create(tenant_id=identity.tenant_id, principal_id=identity.principal_id, roles=roles).delegation_id,
        "X-Request-ID": "product-admin-request",
    }


async def _call(connector: httpx.AsyncClient, identity: DelegatedIdentity, call_id: str, name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = await connector.post(
        "/tenants/tenant-a/mcp", headers=_headers(identity),
        json={"jsonrpc": "2.0", "id": call_id, "method": "tools/call", "params": {"name": name, "arguments": arguments, "_meta": {"request_id": f"run-001-{call_id}"}}},
    )
    payload = response.json()
    return {"status": response.status_code, "payload": payload, "structured": payload["result"]["structuredContent"]}


async def run(example_root: Path) -> dict[str, object]:
    node = _resolve_executable("node")
    npm = _resolve_executable("npm")
    npm_invocation, npm_shell = _prepare_invocation(npm, ["run", "build"])
    build = subprocess.run(npm_invocation, cwd=example_root, text=True, capture_output=True, check=False, shell=npm_shell)
    if build.returncode != 0:
        raise RuntimeError(build.stdout + build.stderr)
    port = _free_port()
    env = dict(os.environ)
    env.update({"PORT": str(port), "HOST": "127.0.0.1"})
    process = subprocess.Popen([node, "dist/src/main.js"], cwd=example_root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_url = f"http://127.0.0.1:{port}"
    try:
        await _wait_ready(base_url)
        settings = Settings("connector-secret", base_url, "example-organization-context-api-token", 2, 0)
        app = create_app(settings)
        identity = DelegatedIdentity.create(tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://connector") as connector, httpx.AsyncClient(base_url=base_url) as fake:
            resolved = await _call(connector, identity, "call-001", "resolve_organization_terms", {"query": "PI", "organization_unit_id": "hr", "limit": 10})
            ambiguous = await _call(connector, identity, "call-002", "resolve_organization_terms", {"query": "PI", "limit": 10})
            state_before = await _call(connector, identity, "call-003", "get_organization_catalog_state", {})
            create_body = {
                "term_id": "term.okr", "tenant_id": "tenant-a", "canonical_name": "목표 및 핵심 결과", "definition": "조직 목표 관리 방식",
                "classification": "STRATEGY", "status": "ACTIVE", "visible_to_roles": ["agent-user", "employee", "manager", "admin"],
                "aliases": [{"value": "OKR", "organization_unit_id": None, "locale": "ko-KR"}],
                "bindings": [{"system_id": "strategy", "capability_id": "objectives.read", "entity_type": "OBJECTIVE", "default_operation": "READ", "risk_level": "LOW"}],
                "source": {"reference": "org://tenant-a/strategy/okr", "version": "1", "approved_by": "strategy-admin"},
            }
            created_response = await fake.post("/api/v1/admin/glossary/terms", headers=_product_headers(identity, admin=True), json=create_body)
            created = created_response.json()
            changed = await _call(connector, identity, "call-004", "get_organization_changes", {"after_revision": 3, "limit": 20})
            resolved_new = await _call(connector, identity, "call-005", "resolve_organization_terms", {"query": "OKR", "organization_unit_id": "strategy"})
            requests_payload = (await fake.get("/_fake/requests")).json()
            await fake.put("/_fake/faults", json={"operation": "glossary.resolve", "mode": "PERMISSION_DENIED", "count": 1})
            denied = await _call(connector, identity, "call-006", "resolve_organization_terms", {"query": "연차"})
        resolve_structured = resolved["structured"]
        ambiguous_structured = ambiguous["structured"]
        state_structured = state_before["structured"]
        change_structured = changed["structured"]
        new_structured = resolved_new["structured"]
        denied_structured = denied["structured"]
        assert isinstance(resolve_structured, dict)
        assert isinstance(ambiguous_structured, dict)
        assert isinstance(state_structured, dict)
        assert isinstance(change_structured, dict)
        assert isinstance(new_structured, dict)
        assert isinstance(denied_structured, dict)
        product_requests = [item for item in requests_payload["requests"] if item["path"].startswith("/api/v1/")]
        first = product_requests[0]
        checks = {
            "real_connector_mcp_call_passed": resolved["status"] == 200 and resolved["payload"]["result"]["isError"] is False,
            "example_product_api_reached": first["path"] == "/api/v1/glossary/resolve",
            "delegated_identity_forwarded": first["tenant_id"] == "tenant-a" and first["principal_id"] == "user-001" and first["roles"] == ["agent-user", "employee"] and first["organization_unit_id"] == "hr",
            "request_id_forwarded": first["request_id"] == "run-001-call-001",
            "authorization_value_not_captured": first["authorization_present"] is True and first["authorization_value_recorded"] is False and "example-organization-context-api-token" not in json.dumps(requests_payload),
            "department_scoped_resolution_normalized": resolve_structured["resolved"] is True and resolve_structured["records"][0]["term_id"] == "term.performance-index",
            "ambiguity_preserved_without_guessing": ambiguous_structured["ambiguous"] is True and len(ambiguous_structured["records"]) == 2,
            "catalog_revision_observed": state_structured["catalog_revision"] == 3,
            "mutable_product_change_visible_through_read_only_connector": created_response.status_code == 201 and created["catalog_revision"] == 4 and change_structured["changes"][0]["change_type"] == "CREATE" and new_structured["records"][0]["term_id"] == "term.okr",
            "fault_mapped_by_real_connector": denied["payload"]["result"]["isError"] is True and denied_structured["error_code"] == "ORGANIZATION_CONTEXT_PERMISSION_DENIED" and denied_structured["retryable"] is False,
        }
        return {
            "schema_version": "okcanvas-organization-context-connector-example-integration-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "passed_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks),
            "connector_step": "CONNECTOR_ORGANIZATION_CONTEXT_STEP001R1_GROUPWARE_ACCEPTANCE_PATTERN_ALIGNMENT",
            "example_step": "EXAMPLE_ORGANIZATION_CONTEXT_STEP001R1_GROUPWARE_CONSTRUCTION_GUIDE_PATTERN_ALIGNMENT",
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    example = Path(os.environ.get("OKCANVAS_ORGANIZATION_CONTEXT_EXAMPLE_ROOT", str(DEFAULT_EXAMPLE))).resolve()
    payload = asyncio.run(run(example))
    output = ROOT / "docs/evidence/CONNECTOR_ORGANIZATION_CONTEXT_STEP001R1_OPTIONAL_EXAMPLE_INTEGRATION.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
