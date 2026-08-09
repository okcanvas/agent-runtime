from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_step096a_static_contract import STEP, VERSION, validate

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP096A_DETERMINISTIC_ACCEPTANCE.json"

FOCUSED_TESTS = (
    "tests/test_step096a_grounded_llm_interpretation_context_shadow.py",
    "tests/test_generic_mcp_gateway_contract.py",
    "tests/test_mcp_factory_contract.py",
    "tests/test_step085_multi_mcp_and_delegated_identity_foundation.py",
    "tests/test_step087r1_live_agent_tool_turn_budget_closure.py",
    "tests/test_step088r1_organization_context_bounded_response_diagnostics.py",
    "tests/test_step090_organization_context_ambiguous_result_normalization.py",
    "tests/test_step091_organization_context_mcp_output_adapter_and_tool_choice.py",
    "tests/test_step093r1_relation_route_protocol_and_live_failure_fence.py",
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) > 1:
        raise SystemExit("run_step096a_acceptance accepts at most one output path")
    output = Path(args[0]).resolve() if args else OUTPUT_DEFAULT
    static = validate()
    compile_result = _run([sys.executable, "-m", "compileall", "-q", "okcanvas_agent_runtime", "okcanvas_agent_protocols"])
    pytest_result = _run([sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS])
    checks = {
        "step096a_static_contract": static["state"] == "PASSED",
        "python_compileall": compile_result.returncode == 0,
        "focused_regression_pytest": pytest_result.returncode == 0,
        "focused_regression_exact_pass_count": "48 passed" in pytest_result.stdout,
        "windows_live_not_claimed": True,
        "broad_historical_suite_not_claimed": True,
    }
    payload = {
        "schema_version": "okcanvas-step096a-deterministic-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "static": static,
        "focused_pytest": {
            "returncode": pytest_result.returncode,
            "summary": pytest_result.stdout.strip().splitlines()[-1] if pytest_result.stdout.strip() else "",
            "stderr_present": bool(pytest_result.stderr.strip()),
        },
        "compileall_returncode": compile_result.returncode,
        "windows_live": "NOT_RUN",
        "broad_regression": "NOT_CLAIMED_HISTORICAL_STALE_TESTS_RECORDED_SEPARATELY",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "state": payload["state"],
        "passed_checks": payload["passed_checks"],
        "total_checks": payload["total_checks"],
        "focused_pytest": payload["focused_pytest"]["summary"],
    }, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
