from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.json_subprocess_validation import run_json_python_validator
from scripts.node_acceptance import run_command
from scripts.validate_acceptance_launcher_registry import validate as validate_registry
from scripts.validate_step082b_distribution import validate as validate_distribution
from scripts.validate_step082b_execution_plane import validate as validate_execution_plane
from scripts.validate_step084_organization_context import validate as validate_organization_context
from scripts.validate_step085_multi_mcp_delegated_identity import validate as validate_multi_mcp

STEP = "STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION"
VERSION = "2.65.0"
OUTPUT_DEFAULT = ROOT / "docs/evidence/step085-local/STEP085_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(output: Path) -> int:
    started = _now()
    info = RuntimeInfo()
    organization_context_raw = validate_organization_context()
    retained_org_checks = {
        key: value
        for key, value in organization_context_raw.get("checks", {}).items()
        if key not in {"identity_exact", "next_step_exact"}
    }
    organization_context = {
        **organization_context_raw,
        "schema_version": "okcanvas-step085-retained-step084-organization-context-v1",
        "state": "PASSED" if retained_org_checks and all(retained_org_checks.values()) else "FAILED",
        "checks": retained_org_checks,
        "passed_checks": sum(value is True for value in retained_org_checks.values()),
        "total_checks": len(retained_org_checks),
        "retained_from_step": "STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION",
    }
    multi_mcp = validate_multi_mcp()
    execution = validate_execution_plane()
    distribution = validate_distribution()
    registry = validate_registry()
    architecture, architecture_process = run_json_python_validator(
        root=ROOT, script=ROOT / "scripts/validate_step081_architecture.py"
    )
    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step085_multi_mcp_and_delegated_identity_foundation.py",
            "tests/test_step084_organization_knowledge_glossary_and_directory_foundation.py",
            "tests/test_step083_organization_assistant_main_agent_and_action_routing.py",
            "tests/test_baseline_version.py",
            "tests/test_runtime_info.py",
            "tests/test_step082b_coding_execution_plane_and_distribution_boundary.py",
            "tests/test_step081_windows_entrypoint_and_launcher_registry.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "okcanvas_agent_runtime",
            "okcanvas_agent_protocols",
            "okcanvas_agent_clients",
            "scripts",
            "tests",
        ],
        ROOT,
    )
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "multi_mcp_validation_passed": multi_mcp.get("state") == "PASSED"
        and multi_mcp.get("passed_checks") == multi_mcp.get("total_checks") == 22,
        "step084_organization_context_retained": organization_context.get("state") == "PASSED"
        and organization_context.get("passed_checks") == organization_context.get("total_checks") == 18,
        "step082b_execution_plane_retained": execution.get("state") == "PASSED"
        and execution.get("passed_checks") == execution.get("total_checks") == 13,
        "step082b_distribution_retained": distribution.get("state") == "PASSED"
        and distribution.get("passed_checks") == distribution.get("total_checks") == 14,
        "architecture_regression_passed": architecture_process.get("returncode") == 0
        and architecture.get("state") == "PASSED"
        and architecture.get("passed_checks") == architecture.get("total_checks") == 40,
        "launcher_registry_passed": registry.get("state") == "PASSED"
        and registry.get("current_step") == STEP
        and registry.get("current_record_count") == 2,
        "focused_regression_passed": focused_ok,
        "compileall_passed": compile_ok,
        "default_external_mcp_fails_closed": info.delegated_mcp_default_credential_reference_count == 0
        and info.delegated_mcp_external_endpoints_configured is False,
        "writes_and_automation_remain_unconfigured": info.delegated_mcp_write_enabled is False
        and info.organization_assistant_enterprise_write_configured is False
        and info.organization_assistant_durable_automation_configured is False,
        "next_step_exact": info.next_selected_step == "STEP086_GROUPWARE_READ_ONLY_VERTICAL",
    }
    payload = {
        "schema_version": "okcanvas-step085-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "multi_mcp_validation": multi_mcp,
        "organization_context_validation": organization_context,
        "execution_plane_validation": execution,
        "distribution_validation": distribution,
        "architecture_validation": architecture,
        "architecture_validation_process": architecture_process,
        "launcher_registry": registry,
        "focused_output": focused_output,
        "compile_output": compile_output,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
