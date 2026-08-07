from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    commands = {
        "compileall": [sys.executable, "-m", "compileall", "-q", "groupware_mcp_server", "tests", "scripts"],
        "pytest": [sys.executable, "-m", "pytest", "-q"],
    }
    results: dict[str, object] = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        results[name] = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    runtime_contract = json.loads((ROOT / "contracts/runtime-provider-contract.json").read_text(encoding="utf-8"))
    connector_binding = json.loads((ROOT / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    checks = {
        "runtime_contract_v2_exact": runtime_contract.get("schema_version") == "okcanvas-groupware-read-provider-contract-v2"
        and runtime_contract.get("external_connector_project_path") == "okcanvas-connectors/groupware-mcp-server"
        and runtime_contract.get("credential_reference_transmitted") is False,
        "connector_binding_contract_exact": connector_binding.get("required_role") == "agent-user"
        and connector_binding.get("credential_reference_transmitted") is False,
        "compileall_passed": results["compileall"]["returncode"] == 0,
        "pytest_passed": results["pytest"]["returncode"] == 0,
        "fake_mode_absent": "FAKE_MODE" not in "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "groupware_mcp_server").rglob("*.py")
        ),
        "async_test_runner_dependency_closed": all(
            token not in "\n".join(
                path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py")
            )
            for token in ("pytest.mark.asyncio", "pytest_asyncio")
        ),
        "read_tools_exact": all(
            token in (ROOT / "groupware_mcp_server/mcp_protocol.py").read_text(encoding="utf-8")
            for token in ("search_notices", "search_mail", "list_calendar_events")
        ),
    }
    payload = {
        "schema_version": "okcanvas-groupware-connector-step001r1-acceptance-v1",
        "step": "CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE",
        "version": "0.1.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "processes": results,
    }
    output = ROOT / "docs/evidence/CONNECTOR_STEP001R1_ACCEPTANCE.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
