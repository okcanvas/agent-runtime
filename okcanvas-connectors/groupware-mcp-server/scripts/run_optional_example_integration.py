from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = (
    ROOT.parents[1]
    / "okcanvas-connector-examples"
    / "groupware"
    / "groupware-api-fake"
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groupware_mcp_server.app import create_app
from groupware_mcp_server.config import Settings
from groupware_mcp_server.identity import DelegatedIdentity


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
    raise RuntimeError("Groupware API fake example did not become ready")


def _headers(identity: DelegatedIdentity) -> dict[str, str]:
    return {
        "Authorization": "Bearer connector-secret",
        "X-OKCanvas-Tenant-ID": identity.tenant_id,
        "X-OKCanvas-Principal-ID": identity.principal_id,
        "X-OKCanvas-Roles": ",".join(identity.roles),
        "X-OKCanvas-Delegation-ID": identity.delegation_id,
        "Accept": "application/json, text/event-stream",
    }


async def run(example_root: Path) -> dict[str, object]:
    build = subprocess.run(
        ["npm", "run", "build"], cwd=example_root, text=True, capture_output=True, check=False
    )
    if build.returncode != 0:
        raise RuntimeError(build.stdout + build.stderr)
    port = _free_port()
    env = dict(os.environ)
    env.update({"PORT": str(port), "HOST": "127.0.0.1"})
    process = subprocess.Popen(
        ["node", "dist/src/main.js"],
        cwd=example_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        await _wait_ready(base_url)
        settings = Settings(
            connector_bearer="connector-secret",
            groupware_base_url=base_url,
            groupware_api_bearer="example-groupware-api-token",
            http_timeout_seconds=2,
        )
        app = create_app(settings)
        identity = DelegatedIdentity.create(
            tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user")
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://connector"
        ) as connector, httpx.AsyncClient(base_url=base_url) as fake:
            call = await connector.post(
                "/tenants/tenant-a/mcp",
                headers=_headers(identity),
                json={
                    "jsonrpc": "2.0",
                    "id": "call-001",
                    "method": "tools/call",
                    "params": {
                        "name": "search_notices",
                        "arguments": {"query": "maintenance", "limit": 5},
                        "_meta": {"request_id": "run-001-tool-001"},
                    },
                },
            )
            call_payload = call.json()
            structured = call_payload["result"]["structuredContent"]
            requests_payload = (await fake.get("/_fake/requests")).json()
            await fake.put(
                "/_fake/faults",
                json={"operation": "mail.search", "mode": "PERMISSION_DENIED", "count": 1},
            )
            denied = await connector.post(
                "/tenants/tenant-a/mcp",
                headers=_headers(identity),
                json={
                    "jsonrpc": "2.0",
                    "id": "call-002",
                    "method": "tools/call",
                    "params": {"name": "search_mail", "arguments": {"limit": 5}},
                },
            )
            denied_payload = denied.json()["result"]["structuredContent"]
        captured = requests_payload["requests"][0]
        checks = {
            "real_connector_mcp_call_passed": call.status_code == 200
            and call_payload["result"]["isError"] is False,
            "example_groupware_api_reached": captured["path"] == "/api/v1/notices/search",
            "delegated_identity_forwarded": captured["tenant_id"] == "tenant-a"
            and captured["principal_id"] == "user-001"
            and captured["roles"] == ["agent-user", "employee"]
            and captured["delegation_id"] == identity.delegation_id,
            "request_id_forwarded": captured["request_id"] == "run-001-tool-001",
            "authorization_value_not_captured": captured["authorization_present"] is True
            and captured["authorization_value_recorded"] is False
            and "example-groupware-api-token" not in json.dumps(requests_payload),
            "result_normalized": structured["tool_name"] == "search_notices"
            and structured["mutated"] is False
            and structured["records"][0]["record_id"] == "notice-001",
            "fault_mapped_by_real_connector": denied_payload["error_code"]
            == "GROUPWARE_PERMISSION_DENIED"
            and denied_payload["retryable"] is False,
        }
        return {
            "schema_version": "okcanvas-groupware-connector-example-integration-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "passed_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks),
            "connector_step": "CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE",
            "example_step": "EXAMPLE_STEP001_GROUPWARE_API_FAKE_TEMPLATE",
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    example = Path(os.environ.get("OKCANVAS_GROUPWARE_EXAMPLE_ROOT", str(DEFAULT_EXAMPLE))).resolve()
    payload = asyncio.run(run(example))
    output = ROOT / "docs/evidence/CONNECTOR_STEP001R1_OPTIONAL_EXAMPLE_INTEGRATION.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
