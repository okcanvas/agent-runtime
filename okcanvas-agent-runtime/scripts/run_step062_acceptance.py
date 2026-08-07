from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import run_command, run_node_tests, validate_committed_typescript_release

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP062_ACCEPTANCE.json"
ROOT_AGENT = "bounded-orchestration-manager-agent"
CHILDREN = [
    "bounded-orchestration-architecture-agent",
    "bounded-orchestration-risk-agent",
]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value



def run(output: Path) -> int:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
    from okcanvas_agent_runtime.application.admin.projections import agent_definition_summary
    from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationPolicyCatalog
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve(ROOT_AGENT)
    children = [definitions.resolve(item) for item in CHILDREN]
    policy = BoundedOrchestrationPolicyCatalog(ROOT).resolve()
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)
    public = agent_definition_summary(root)
    step061 = _load_json(ROOT / "docs/evidence/STEP061_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json")

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_bounded_multi_agent_orchestration.py",
            "tests/test_step062_bounded_multi_agent_orchestration_baseline.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts/run_step062_acceptance.py"],
        ROOT,
    )
    cli_root = ROOT / "clients/cli"
    node_build_ok, node_build_output = validate_committed_typescript_release(cli_root)
    node_test_ok, node_test_output = run_node_tests(cli_root)

    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    openai_runtime = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/orchestration/openai_runtime.py")).read_text(
        encoding="utf-8"
    )
    runtime_service = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(
        encoding="utf-8"
    )
    invocation_service = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/invocations/service.py")).read_text(
        encoding="utf-8"
    )
    control_contract = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/control_api/contracts.py")).read_text(
        encoding="utf-8"
    )
    cli_render = (ROOT / "clients/cli/src/render.ts").read_text(encoding="utf-8")
    baseline = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")

    required_docs = [
        ROOT / "docs/plans/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION.md",
        ROOT / "docs/reference/STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP061_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    root_schema = _load_json(
        ROOT / "specs/agents/bounded-orchestration-manager-agent/output.schema.json"
    )
    child_schemas = [
        _load_json(ROOT / "specs/agents" / item / "output.schema.json") for item in CHILDREN
    ]

    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.43.1"
            and info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"
            and 'PROJECT_VERSION = "2.43.1"' in baseline
            and 'CURRENT_STEP = "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"' in baseline
        ),
        "step061_windows_live_closure_exact": (
            step061.get("state") == "PASSED"
            and step061.get("passed_checks") == 20
            and step061.get("total_checks") == 20
            and step061.get("classified_example_count") == 212
            and step061.get("next_selected_step")
            == "STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION"
            and info.sdk_examples_coverage_matrix_windows_live_accepted is True
        ),
        "runtime_info_step062_flags_exact": (
            info.bounded_multi_agent_orchestration_implemented is True
            and info.bounded_multi_agent_orchestration_child_count == 2
            and info.bounded_multi_agent_orchestration_max_parallelism == 2
            and info.bounded_multi_agent_orchestration_max_depth == 1
            and info.bounded_multi_agent_orchestration_root_model_calls == 0
            and info.bounded_multi_agent_orchestration_deterministic_accepted is True
            and info.bounded_multi_agent_orchestration_windows_live_accepted is True
        ),
        "policy_identity_and_sha_exact": (
            policy.policy_id == "default-bounded-multi-agent-orchestration"
            and policy.version == "1.0.0"
            and len(policy.policy_sha256) == 64
        ),
        "policy_bounds_exact": (
            policy.child_count == 2
            and policy.max_parallelism == 2
            and policy.max_depth == 1
            and policy.failure_mode == "ALL_REQUIRED_FAIL_FAST"
            and policy.cancellation_mode == "CANCEL_PENDING_SIBLINGS"
            and policy.aggregation_mode == "DECLARATION_ORDER_STRUCTURED"
        ),
        "root_graph_exact": list(root.orchestration_children) == CHILDREN,
        "root_capability_boundary_exact": (
            root.output_contract == "BoundedOrchestrationResult"
            and not root.tools
            and not root.mcp_servers
            and not root.handoffs
            and not root.agent_tools
            and not root.guardrails
            and root.session_mode == "disabled"
            and root.workspace_access == "none"
        ),
        "children_terminal_language_only_exact": all(
            item.output_contract == "CodingAgentResult"
            and not item.tools
            and not item.mcp_servers
            and not item.handoffs
            and not item.agent_tools
            and not item.orchestration_children
            and not item.guardrails
            and item.session_mode == "disabled"
            and item.workspace_access == "none"
            for item in children
        ),
        "output_schemas_strict_and_exact": (
            root_schema.get("additionalProperties") is False
            and root_schema.get("title") == "BoundedOrchestrationResult"
            and all(schema.get("additionalProperties") is False for schema in child_schemas)
            and all(schema.get("title") == "CodingAgentResult" for schema in child_schemas)
        ),
        "runtime_binding_path_exact": binding.execution_path
        == "bounded-multi-agent-orchestration-v1",
        "runtime_binding_policy_bound": (
            binding.orchestration_policy is not None
            and binding.orchestration_policy.get("policy_sha256") == policy.policy_sha256
            and len(binding.orchestration_runtime_sha256 or "") == 64
            and len(binding.runtime_binding_sha256) == 64
        ),
        "runtime_binding_child_order_exact": (
            [item.get("ordinal") for item in binding.child_agents] == [1, 2]
            and [item.get("child_agent_id") for item in binding.child_agents] == CHILDREN
        ),
        "runtime_binding_child_shas_present": all(
            len(str(item.get("child_definition_sha256", ""))) == 64
            and len(str(item.get("child_runtime_binding_sha256", ""))) == 64
            for item in binding.child_agents
        ),
        "direct_parallel_runner_path_present": (
            "asyncio.create_task" in openai_runtime
            and "asyncio.FIRST_EXCEPTION" in openai_runtime
            and "Runner.run(" in openai_runtime
            and "Runner.run_streamed" not in openai_runtime
        ),
        "root_model_call_absent_by_contract": (
            "sdk_agent = Agent(" in openai_runtime
            and "root_definition.name" not in openai_runtime
            and info.bounded_multi_agent_orchestration_root_model_calls == 0
        ),
        "fail_fast_cancellation_path_present": (
            "task.cancel()" in openai_runtime
            and '"orchestration.child.cancelled"' in openai_runtime
            and '"orchestration.failed"' in openai_runtime
        ),
        "declaration_order_aggregation_present": (
            "ordered = sorted(successes, key=lambda item: item.ordinal)" in openai_runtime
            and "aggregate_child_results" in openai_runtime
        ),
        "product_invocation_ledger_integrated": (
            "plan_orchestration_children" in runtime_service
            and "ORCHESTRATION_CHILD" in invocation_service
            and "orchestration_terminal_ordinals" in runtime_service
        ),
        "root_usage_zero_path_exact": (
            "input_tokens=0" in runtime_service
            and "output_tokens=0" in runtime_service
            and "total_tokens=0" in runtime_service
        ),
        "control_api_orchestration_visible": (
            "orchestration_children: list[str]" in control_contract
            and public.orchestration_children == CHILDREN
        ),
        "node_cli_orchestration_visible": (
            "agent.orchestration_children.length === 2" in cli_render
            and "orchestration.child.started" in cli_render
            and "Specialist 결과" in cli_render
        ),
        "focused_orchestration_tests_pass": focused_ok and "7 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "node_typescript_build_pass": node_build_ok,
        "node_tests_pass": node_test_ok,
        "step062_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launcher_present": (
            (ROOT / "sh_run_step062_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step062_acceptance.py").is_file()
        ),
        "references_unchanged": references_ok,
        "step064_not_selected": "STEP064_" not in "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
        ),
    }

    payload = {
        "schema_version": "okcanvas-step062-acceptance-v1",
        "step": "STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "policy": {
            "child_count": policy.child_count,
            "max_parallelism": policy.max_parallelism,
            "max_depth": policy.max_depth,
            "failure_mode": policy.failure_mode,
            "cancellation_mode": policy.cancellation_mode,
            "aggregation_mode": policy.aggregation_mode,
        },
        "root_agent_id": root.agent_id,
        "child_agent_ids": CHILDREN,
        "execution_path": binding.execution_path,
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_build_output_tail": node_build_output.splitlines()[-1] if node_build_output else "",
        "node_test_output_tail": node_test_output.splitlines()[-1] if node_test_output else "",
        "reference_count": len(reference_results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
