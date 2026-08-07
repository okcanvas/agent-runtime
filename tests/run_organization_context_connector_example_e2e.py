from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from workspace_process import prepare_invocation, resolve_executable, write_json_stdout


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_ready(httpx: object, base_url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            response = await httpx.AsyncClient().get(f"{base_url}/healthz")
            if response.status_code == 200:
                return
        except Exception:
            pass
        await asyncio.sleep(0.05)
    raise RuntimeError("Organization Context Example did not become ready")


def connector_headers(identity: object) -> dict[str, str]:
    return {
        "Authorization": "Bearer connector-secret",
        "X-OKCanvas-Tenant-ID": identity.tenant_id,
        "X-OKCanvas-Principal-ID": identity.principal_id,
        "X-OKCanvas-Roles": ",".join(identity.roles),
        "X-OKCanvas-Delegation-ID": identity.delegation_id,
        "Accept": "application/json, text/event-stream",
    }


def product_headers(identity: object, *, admin: bool = False) -> dict[str, str]:
    roles = tuple(sorted(set((*identity.roles, "admin")))) if admin else identity.roles
    return {
        "Authorization": "Bearer example-organization-context-api-token",
        "Content-Type": "application/json",
        "X-Tenant-ID": identity.tenant_id,
        "X-Principal-ID": identity.principal_id,
        "X-Principal-Roles": ",".join(roles),
        "X-Organization-Unit-ID": "department.strategy-planning" if admin else "department.human-resources",
        "X-Delegation-ID": identity.delegation_id,
        "X-Request-ID": "product-admin-request",
    }


async def call_tool(connector: object, identity: object, call_id: str, name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = await connector.post(
        "/tenants/tenant-a/mcp",
        headers=connector_headers(identity),
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments, "_meta": {"request_id": f"run-002-{call_id}"}},
        },
    )
    payload = response.json()
    return {"status": response.status_code, "payload": payload, "structured": payload["result"]["structuredContent"]}


async def execute(connector_root: Path, example_root: Path) -> dict[str, object]:
    if str(connector_root) not in sys.path:
        sys.path.insert(0, str(connector_root))

    import httpx
    from organization_context_mcp_server.app import create_app
    from organization_context_mcp_server.config import Settings
    from organization_context_mcp_server.identity import DelegatedIdentity

    node = resolve_executable("node")
    npm = resolve_executable("npm")
    npm_invocation, npm_shell = prepare_invocation(npm, ["run", "build"])
    try:
        build = subprocess.run(
            npm_invocation,
            cwd=example_root,
            text=True,
            capture_output=True,
            check=False,
            shell=npm_shell,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("organization context example build exceeded 60 seconds") from exc
    if build.returncode != 0:
        raise RuntimeError(build.stdout + build.stderr)

    port = free_port()
    environment = dict(os.environ)
    environment.update({"PORT": str(port), "HOST": "127.0.0.1"})
    process = subprocess.Popen(
        [node, "dist/src/main.js"],
        cwd=example_root,
        env=environment,
        text=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        await wait_ready(httpx, base_url)
        settings = Settings("connector-secret", base_url, "example-organization-context-api-token", 2, 0)
        app = create_app(settings)
        identity = DelegatedIdentity.create(tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://connector") as connector, httpx.AsyncClient(base_url=base_url) as fake:
            employee = await call_tool(connector, identity, "call-001", "resolve_organization_context", {"query": "플랫폼팀 김민수 선임", "entity_types": ["EMPLOYEE"]})
            same_name = await call_tool(connector, identity, "call-002", "resolve_organization_context", {"query": "김민수", "entity_types": ["EMPLOYEE"]})
            clients = await call_tool(connector, identity, "call-003", "resolve_organization_context", {"query": "한빛", "entity_types": ["CLIENT"]})
            search = await call_tool(connector, identity, "call-004", "search_organization_context", {"query": "", "entity_types": ["PRODUCT"], "limit": 20})
            client = await call_tool(connector, identity, "call-005", "get_organization_entity", {"entity_type": "CLIENT", "entity_id": "client-0042"})
            glossary = await call_tool(connector, identity, "call-006", "resolve_organization_terms", {"query": "PI", "organization_unit_id": "department.human-resources", "limit": 10})
            state_before = await call_tool(connector, identity, "call-007", "get_organization_catalog_state", {})
            create_body = {
                "term_id": "term.okr", "tenant_id": "tenant-a", "canonical_name": "목표 및 핵심 결과", "definition": "조직 목표 관리 방식",
                "classification": "STRATEGY", "status": "ACTIVE", "visible_to_roles": ["agent-user", "employee", "manager", "admin"],
                "aliases": [{"value": "OKR", "organization_unit_id": None, "locale": "ko-KR"}],
                "bindings": [{"system_id": "strategy", "capability_id": "objectives.read", "entity_type": "OBJECTIVE", "default_operation": "READ", "risk_level": "LOW"}],
                "source": {"reference": "org://tenant-a/strategy/okr", "version": "1", "approved_by": "strategy-admin"},
            }
            created_response = await fake.post("/api/v1/admin/glossary/terms", headers=product_headers(identity, admin=True), json=create_body)
            created = created_response.json()
            changed = await call_tool(connector, identity, "call-008", "get_organization_changes", {"after_revision": 500, "limit": 20})
            resolved_new = await call_tool(connector, identity, "call-009", "resolve_organization_terms", {"query": "OKR", "organization_unit_id": "department.strategy-planning"})
            requests_payload = (await fake.get("/_fake/requests")).json()
            await fake.put("/_fake/faults", json={"operation": "context.resolve", "mode": "PERMISSION_DENIED", "count": 1})
            denied = await call_tool(connector, identity, "call-010", "resolve_organization_context", {"query": "김민수", "entity_types": ["EMPLOYEE"]})

        employee_structured = employee["structured"]
        same_name_structured = same_name["structured"]
        clients_structured = clients["structured"]
        search_structured = search["structured"]
        client_structured = client["structured"]
        glossary_structured = glossary["structured"]
        state_structured = state_before["structured"]
        change_structured = changed["structured"]
        new_structured = resolved_new["structured"]
        denied_structured = denied["structured"]
        product_requests = [item for item in requests_payload["requests"] if item["path"].startswith("/api/v1/")]
        first = product_requests[0]
        state_record = state_structured["records"][0]
        client_record = client_structured["records"][0]
        checks = {
            "real_connector_mcp_call_passed": employee["status"] == 200 and employee["payload"]["result"]["isError"] is False,
            "example_product_api_reached": first["path"] == "/api/v1/context/resolve",
            "delegated_identity_forwarded": first["tenant_id"] == "tenant-a" and first["principal_id"] == "user-001" and first["roles"] == ["agent-user", "employee"] and first["delegation_id"] == identity.delegation_id,
            "request_id_forwarded": first["request_id"] == "run-002-call-001",
            "authorization_value_not_captured": first["authorization_present"] is True and first["authorization_value_recorded"] is False and "example-organization-context-api-token" not in json.dumps(requests_payload),
            "json_reference_dataset_counts_observed": state_record["dataset_counts"]["departments"] == 13 and state_record["dataset_counts"]["positions"] == 12 and state_record["dataset_counts"]["employees"] == 48 and state_record["dataset_counts"]["products"] == 120 and state_record["dataset_counts"]["clients"] == 120 and state_record["dataset_counts"]["glossary"] == 80 and state_record["dataset_counts"]["relations"] == 893,
            "production_db_sot_observed": state_record["production_sot"] == "DATABASE" and state_record["example_sot"] == "COMMITTED_JSON_FIXTURES" and state_record["fixture_valid"] is True,
            "employee_context_resolved": employee_structured["resolved"] is True and employee_structured["records"][0]["entity_id"] == "employee-0017",
            "bounded_exact_resolution_observed": employee_structured.get("response_shape") == "TOP_SCORE_CANDIDATES_WITH_DETAILS" and employee_structured.get("returned_count") == 1 and employee_structured.get("candidate_count", 0) > employee_structured.get("returned_count", 0) and len(json.dumps(employee_structured, ensure_ascii=False)) < 32000,
            "compact_search_response_observed": search_structured.get("response_shape") == "RANKED_ENTITY_SUMMARIES" and search_structured.get("returned_count") == 20 and search_structured.get("truncated") is True and all("record" not in item and "relations" not in item for item in search_structured.get("records", [])) and len(json.dumps(search_structured, ensure_ascii=False)) < 32000,
            "same_name_ambiguity_preserved": same_name_structured["ambiguous"] is True and [item["entity_id"] for item in same_name_structured["records"][:2]] == ["employee-0017", "employee-0034"],
            "similar_client_ambiguity_preserved": clients_structured["ambiguous"] is True and len(clients_structured["records"]) >= 4,
            "entity_relationships_normalized": any(item["relation_type"] == "EMPLOYEE_MANAGES_CLIENT" for item in client_record["relations"]) and any(item["relation_type"] == "CLIENT_USES_PRODUCT" for item in client_record["relations"]),
            "glossary_compatibility_retained": glossary_structured["resolved"] is True and glossary_structured["records"][0]["term_id"] == "term.performance-index",
            "catalog_revision_observed": state_structured["catalog_revision"] == 500,
            "mutable_product_change_visible_through_read_only_connector": created_response.status_code == 201 and created["catalog_revision"] == 501 and change_structured["changes"][0]["change_type"] == "CREATE" and new_structured["records"][0]["term_id"] == "term.okr",
            "fault_mapped_by_real_connector": denied["payload"]["result"]["isError"] is True and denied_structured["error_code"] == "ORGANIZATION_CONTEXT_PERMISSION_DENIED" and denied_structured["retryable"] is False,
        }
        return {
            "schema_version": "okcanvas-organization-context-connector-example-integration-v3",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "passed_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks),
            "connector_step": "CONNECTOR_ORGANIZATION_CONTEXT_STEP002R2_BOUNDED_CONTEXT_RESPONSE_ALIGNMENT",
            "example_step": "EXAMPLE_ORGANIZATION_CONTEXT_STEP002R2_REFERENCE_RELATION_FACT_CONSISTENCY_CLOSURE",
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connector-root", type=Path, required=True)
    parser.add_argument("--example-root", type=Path, required=True)
    args = parser.parse_args()
    payload = asyncio.run(execute(args.connector_root.resolve(), args.example_root.resolve()))
    write_json_stdout(payload)
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
