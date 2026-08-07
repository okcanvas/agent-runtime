from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from current_workspace_baseline import load_current_baseline
from workspace_inventory import snapshot_files
from workspace_process import (
    resolve_executable,
    resolve_project_python,
    run_process,
    run_process_to_files,
    workspace_root_errors,
    write_json_stdout,
)

CURRENT = load_current_baseline(ROOT)
STEP = CURRENT.workspace_step
VERSION = CURRENT.workspace_version
OUTPUT_DEFAULT = ROOT / "docs/evidence/WORKSPACE_STEP008R4R7A_ACCEPTANCE.json"
RUNTIME_STEP = CURRENT.runtime_step
EXAMPLE_STEP = "EXAMPLE_ORGANIZATION_CONTEXT_STEP002R2_REFERENCE_RELATION_FACT_CONSISTENCY_CLOSURE"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def stage(message: str) -> None:
    print(f"[WORKSPACE {STEP}] {message}", file=sys.stderr, flush=True)


def snapshot_digest(snapshot: dict[str, tuple[str, int]]) -> str:
    encoded = json.dumps(
        [[path, value[0], value[1]] for path, value in sorted(snapshot.items())],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_last_json(process: dict[str, Any]) -> dict[str, Any] | None:
    text = str(process.get("stdout", "")).strip()
    for index in reversed([i for i, char in enumerate(text) if char == "{"]):
        try:
            return json.loads(text[index:])
        except json.JSONDecodeError:
            continue
    return None


def copy_project(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            "*.egg-info",
        ),
    )


def manifest_drift() -> dict[str, list[str]]:
    manifest = json.loads((ROOT / "WORKSPACE_MANIFEST.json").read_text(encoding="utf-8"))
    expected = {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest["files"]
    }
    actual = snapshot_files(ROOT, workspace=True)
    return {
        "missing": sorted(set(expected) - set(actual)),
        "changed": sorted(
            path
            for path in set(expected) & set(actual)
            if expected[path] != actual[path]
        ),
        "unexpected": sorted(set(actual) - set(expected)),
    }


def failure(started: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "okcanvas-agent-platform-workspace-step008r4r7a-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "FAILED",
        "started_at": started,
        "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": {"workspace_root_contract_exact": False},
        "passed_checks": 0,
        "total_checks": 1,
        "errors": errors,
        "limitations": {
            "windows_step008r4r7a_executed": os.name == "nt",
            "live_openai_model_called": False,
            "production_database_executed": False,
        },
    }


def run(
    output: Path,
    *,
    supplied_runtime_evidence: Path | None = None,
    supplied_runtime_process_evidence: Path | None = None,
    emit_stdout: bool = True,
) -> int:
    started = now()
    errors = workspace_root_errors(ROOT)
    if errors:
        payload = failure(started, errors)
        stage("workspace root contract failed")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if emit_stdout:
            write_json_stdout(payload)
        return 2

    runtime_root = ROOT / "okcanvas-agent-runtime"
    connector_root = ROOT / "okcanvas-connectors/organization-context-mcp-server"
    example_root = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
    try:
        node = resolve_executable("node")
        npm = resolve_executable("npm")
        runtime_python = resolve_project_python(
            runtime_root,
            required_modules=("pytest", "fastapi", "pydantic"),
            fallback_executable=sys.executable,
            allow_fallback=os.name != "nt",
        )
        connector_python = resolve_project_python(
            connector_root,
            required_modules=("pytest", "fastapi", "httpx", "pydantic"),
            fallback_executable=sys.executable,
            allow_fallback=os.name != "nt",
        )
    except FileNotFoundError as exc:
        payload = failure(started, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if emit_stdout:
            write_json_stdout(payload)
        return 2

    stage("workspace manifest verification start")
    drift = manifest_drift()
    stage("workspace manifest verification complete")
    stage("parent source snapshot start")
    before = {
        "runtime": snapshot_files(runtime_root),
        "connector": snapshot_files(connector_root),
        "example": snapshot_files(example_root),
    }
    stage("parent source snapshot complete")
    stage("workspace unit tests start")
    unit = run_process(
        sys.executable,
        ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
        cwd=ROOT,
    )

    stage(f"workspace unit tests complete rc={unit.get('returncode')}")
    with tempfile.TemporaryDirectory(prefix="s008-") as temp_name:
        temp = Path(temp_name)
        connector = temp / "connector"
        example = temp / "example"
        copy_project(connector_root, connector)
        copy_project(example_root, example)
        runtime_output = temp / "runtime-step091d.json"
        connector_env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        if supplied_runtime_evidence is not None:
            stage("runtime STEP091D supplied fresh evidence verification start")
            runtime_output.write_bytes(supplied_runtime_evidence.read_bytes())
            gate_payload = json.loads(supplied_runtime_process_evidence.read_text(encoding="utf-8"))
            runtime_acceptance = dict(gate_payload.get("process", {}))
            runtime_acceptance["supplied_fresh_gate_state"] = gate_payload.get("state")
            runtime_acceptance["supplied_fresh_gate_executed"] = gate_payload.get("executed_fresh")
            runtime_acceptance["supplied_source_unchanged"] = gate_payload.get("source_unchanged")
            runtime_acceptance["supplied_source_snapshot_digest"] = gate_payload.get(
                "source_snapshot_digest_after"
            )
            stage(
                "runtime STEP091D supplied fresh evidence verification complete "
                f"rc={runtime_acceptance.get('returncode')}"
            )
        else:
            stage("runtime STEP091D acceptance start")
            runtime_acceptance = run_process_to_files(
                runtime_python,
                ["scripts/run_step091d_acceptance.py", "--output", str(runtime_output), "--quiet"],
                cwd=runtime_root,
                stdout_path=temp / "runtime-step091d.stdout.log",
                stderr_path=temp / "runtime-step091d.stderr.log",
            )
            runtime_acceptance["supplied_fresh_gate_state"] = "DIRECT_EXECUTION"
            runtime_acceptance["supplied_fresh_gate_executed"] = True
            runtime_acceptance["supplied_source_unchanged"] = True
            runtime_acceptance["supplied_source_snapshot_digest"] = snapshot_digest(before["runtime"])
            stage(f"runtime STEP091D acceptance complete rc={runtime_acceptance.get('returncode')}")
        stage("organization connector acceptance start")
        connector_acceptance = run_process(
            connector_python,
            ["scripts/run_acceptance.py"],
            cwd=connector,
            env=connector_env,
        )
        stage(f"organization connector acceptance complete rc={connector_acceptance.get('returncode')}")
        stage("organization example acceptance start")
        example_acceptance = run_process(npm, ["run", "acceptance"], cwd=example)
        stage(f"organization example acceptance complete rc={example_acceptance.get('returncode')}")
        stage("connector-example integration start")
        integration = run_process_to_files(
            connector_python,
            [
                str(ROOT / "tests/run_organization_context_connector_example_e2e.py"),
                "--connector-root",
                str(connector),
                "--example-root",
                str(example),
            ],
            cwd=ROOT,
            env=connector_env,
            stdout_path=temp / "organization-context-integration.stdout.log",
            stderr_path=temp / "organization-context-integration.stderr.log",
        )
        stage(f"connector-example integration complete rc={integration.get('returncode')}")
        runtime_payload = (
            json.loads(runtime_output.read_text(encoding="utf-8"))
            if runtime_output.is_file()
            else parse_last_json(runtime_acceptance)
        )

    stage("post-acceptance parent source snapshot start")
    after = {
        "runtime": snapshot_files(runtime_root),
        "connector": snapshot_files(connector_root),
        "example": snapshot_files(example_root),
    }
    stage("post-acceptance parent source snapshot complete")
    connector_payload = parse_last_json(connector_acceptance) or {}
    example_payload = parse_last_json(example_acceptance) or {}
    integration_payload = parse_last_json(integration) or {}
    integration_checks = integration_payload.get("checks", {})

    catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
    contracts = {
        item["id"]: item
        for item in json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
    }
    projects = {item["project_id"]: item for item in catalog["projects"]}
    routing_policy = json.loads((runtime_root / "specs/assistant/routing-policy.json").read_text(encoding="utf-8"))
    root_agent = json.loads((runtime_root / "specs/agents/organization-context-session-agent/definition.json").read_text(encoding="utf-8"))
    child_agent = json.loads((runtime_root / "specs/agents/organization-context-read-agent/definition.json").read_text(encoding="utf-8"))
    manifest_a = json.loads((example_root / "fixtures/tenant-a/manifest.json").read_text(encoding="utf-8"))
    relations_a = json.loads((example_root / "fixtures/tenant-a/relations.json").read_text(encoding="utf-8"))
    runtime_contract = contracts["runtime-organization-context-connector"]
    example_contract = contracts["connector-example-organization-context-api"]
    live_harness_source = (ROOT / "scripts/run_workspace_step008_live_acceptance.py").read_text(encoding="utf-8")
    live_entrypoint_source = (ROOT / "scripts/run_workspace_step008_live_entrypoint.py").read_text(encoding="utf-8")
    live_launcher_source = (ROOT / "sh_run_workspace_step008_live_acceptance.cmd").read_text(encoding="utf-8")
    runtime_checks = runtime_payload.get("checks", {})
    retained_step091b3r1 = runtime_payload.get("step091b3r1_parent", {})
    retained_step091b3 = retained_step091b3r1.get("step091b3_parent", {})
    retained_postgresql_live = runtime_payload.get("postgresql_live_parent", {})
    retained_step091b3_checks = retained_step091b3.get("checks", {})
    retained_step091c = retained_step091b3.get("step091c_parent", {})
    retained_step091c_checks = retained_step091c.get("checks", {})
    retained_step091b2 = retained_step091c.get("step091b2_parent", {})
    retained_step091b2_checks = retained_step091b2.get("checks", {})
    retained_step091b1 = retained_step091b2.get("step091b1_parent", {})
    retained_step091b1_checks = retained_step091b1.get("checks", {})
    retained_step090r1_checks = retained_step091b1.get("step090r1_parent", {}).get("checks", {})
    runtime_full_summary = json.loads((runtime_root / "docs/evidence/STEP091D_FULL_RUNTIME_TEST_PARTITIONS.json").read_text(encoding="utf-8"))

    checks = {
        "workspace_root_contract_exact": not errors,
        "workspace_identity_exact": catalog.get("workspace_step") == STEP
        and catalog.get("workspace_version") == VERSION,
        "runtime_identity_exact": projects["agent-runtime"].get("baseline") == RUNTIME_STEP
        and projects["agent-runtime"].get("version") == "2.75.0",
        "example_identity_exact": projects["organization-context-api-fake-example"].get("baseline") == EXAMPLE_STEP
        and projects["organization-context-api-fake-example"].get("version") == "0.2.2",
        "runtime_acceptance_executed_fresh": runtime_acceptance.get("returncode") == 0
        and runtime_acceptance.get("supplied_fresh_gate_executed") is True
        and runtime_acceptance.get("supplied_source_unchanged") is True
        and runtime_acceptance.get("supplied_source_snapshot_digest") == snapshot_digest(before["runtime"])
        and runtime_acceptance.get("supplied_fresh_gate_state") in {"PASSED", "DIRECT_EXECUTION"}
        and runtime_payload.get("state") == "PASSED"
        and runtime_payload.get("passed_checks") == runtime_payload.get("total_checks") == 19,
        "runtime_package_gate_included": runtime_checks.get("package_identity_exact") is True,
        "real_postgresql_live_acceptance_retained": retained_postgresql_live.get("state") == "PASSED"
        and retained_postgresql_live.get("passed_checks") == retained_postgresql_live.get("total_checks") == 19
        and runtime_contract.get("postgresql_live_accepted") is True,
        "object_storage_live_gate_readiness_exact": runtime_checks.get("s3_compatible_deployment_client_present") is True
        and runtime_checks.get("credentials_remain_sdk_chain_owned") is True
        and runtime_checks.get("environment_composition_injects_object_client") is True
        and runtime_checks.get("real_object_storage_live_harness_present") is True
        and runtime_checks.get("live_bucket_not_created_or_deleted") is True
        and runtime_checks.get("live_evidence_secret_safe") is True
        and runtime_contract.get("artifact_object_storage_environment_composition") is True
        and runtime_contract.get("artifact_object_storage_client") == "s3-compatible-boto3-v1"
        and runtime_contract.get("artifact_object_storage_live_gate_implemented") is True
        and runtime_contract.get("artifact_object_storage_live_gate") == "real-s3-compatible-isolated-prefix-v1"
        and runtime_contract.get("artifact_object_storage_live_confirmation_value") == "CREATE_AND_DELETE_ISOLATED_TEST_PREFIX"
        and runtime_contract.get("artifact_object_storage_live_accepted") is False,
        "runtime_typed_persistence_ports_exact": retained_step091b1_checks.get("typed_ports_have_no_broad_variadic_signatures") is True
        and retained_step091b1_checks.get("submission_port_runtime_conformance") is True
        and retained_step091b1_checks.get("admission_port_runtime_conformance") is True
        and retained_step091b1_checks.get("session_port_runtime_conformance") is True
        and retained_step091b1_checks.get("evaluation_port_runtime_conformance") is True,
        "governed_admission_transaction_owner_exact": retained_step091b1_checks.get("governed_admission_port_separated") is True
        and retained_step091b1_checks.get("submission_and_admission_same_transaction_owner") is True
        and retained_step091b2_checks.get("governed_admission_atomic_sql_retained") is True
        and retained_step091b2_checks.get("postgresql_submission_and_admission_same_owner") is True,
        "storage_topology_exact": retained_step091b2_checks.get("postgresql_topology_identity_exact") is True
        and retained_step091b2_checks.get("postgresql_same_dsn_validation_present") is True
        and retained_step091b2_checks.get("bootstrap_postgresql_opt_in_present") is True
        and retained_step091b2_checks.get("sqlite_default_retained") is True,
        "postgresql_control_metadata_exact": retained_step091b3_checks.get("postgresql_metadata_stores_share_one_dsn") is True
        and retained_step091b3_checks.get("postgresql_tool_approval_implemented") is True
        and retained_step091b3_checks.get("approval_product_transaction_domain_retained") is True
        and retained_step091b3_checks.get("postgresql_evaluation_implemented") is True
        and retained_step091b3_checks.get("postgresql_session_metadata_implemented") is True
        and retained_step091b3_checks.get("postgresql_topology_uses_metadata_stores") is True
        and runtime_contract.get("postgresql_tool_approval_implemented") is True
        and runtime_contract.get("postgresql_evaluation_implemented") is True
        and runtime_contract.get("postgresql_session_metadata_implemented") is True,
        "hybrid_session_metadata_history_boundary_exact": retained_step091b3_checks.get("session_history_remains_encrypted_local_sqlite") is True
        and retained_step091b3_checks.get("session_metadata_row_locking_present") is True
        and runtime_contract.get("postgresql_session_metadata_backend") == "postgresql-session-metadata-v1"
        and runtime_contract.get("session_history_backend") == "encrypted-local-sqlite-history-v1"
        and runtime_contract.get("distributed_session_history_implemented") is False,
        "artifact_blob_store_boundary_exact": retained_step091c_checks.get("artifact_blob_port_typed") is True
        and retained_step091c_checks.get("artifact_service_coordinates_blob_and_metadata") is True
        and retained_step091c_checks.get("local_blob_reference_opaque") is True
        and retained_step091c_checks.get("object_storage_reference_opaque") is True
        and retained_step091c_checks.get("object_storage_sdk_neutral") is True
        and retained_step091c_checks.get("product_store_metadata_only") is True
        and retained_step091c_checks.get("execution_uses_artifact_service") is True
        and retained_step091c_checks.get("service_read_uses_artifact_service") is True
        and retained_step091c_checks.get("admin_read_uses_artifact_service") is True
        and retained_step091c_checks.get("evaluation_uses_artifact_service") is True
        and retained_step091c_checks.get("topology_owns_blob_store") is True
        and retained_step091c_checks.get("bootstrap_blob_backend_explicit") is True
        and retained_step091c_checks.get("local_artifact_default_retained") is True
        and runtime_contract.get("artifact_blob_store_implemented") is True
        and runtime_contract.get("artifact_storage_reference") == "OPAQUE"
        and runtime_contract.get("artifact_object_storage_live_accepted") is False,
        "runtime_full_regression_exact": runtime_full_summary.get("state") == "PASSED"
        and runtime_full_summary.get("step") == RUNTIME_STEP
        and runtime_full_summary.get("collected_test_file_count") == 251
        and runtime_full_summary.get("covered_test_file_count") == 251
        and runtime_full_summary.get("total_passed_tests") == 1047
        and runtime_full_summary.get("total_failed_tests") == 0
        and runtime_full_summary.get("partition_count") == 18
        and runtime_full_summary.get("exact_file_coverage") is True,
        "short_expression_policy_exact": routing_policy.get("version") == "1.5.0"
        and len(routing_policy.get("organization_context_short_read_rules", [])) == 4,
        "existing_agent_boundary_retained": root_agent.get("agent_tools") == ["organization-context-read-agent"]
        and child_agent.get("mcp_servers") == ["organization-context-read"]
        and root_agent.get("skills") == []
        and child_agent.get("skills") == [],
        "request_hint_is_not_entity_evidence": runtime_contract.get("request_hint_schema") == "okcanvas-organization-context-request-hint-v1"
        and runtime_contract.get("request_hint_is_entity_evidence") is False,
        "ambiguous_result_normalization_contract_exact": (
            runtime_contract.get("ambiguous_result_normalization") is True
            and runtime_contract.get("ambiguous_result_normalization_strategy")
            == "product-owned-mcp-evidence-normalization-v1"
            and runtime_contract.get("safe_structured_output_diagnostics") is True
            and runtime_contract.get("raw_model_output_persisted") is False
            and retained_step090r1_checks.get(
                "ambiguous_result_normalization_and_diagnostics_exact"
            ) is True
        ),
        "connector_acceptance_passed": connector_payload.get("state") == "PASSED"
        and connector_payload.get("passed_checks") == connector_payload.get("total_checks") == 11,
        "example_acceptance_passed": example_payload.get("state") == "PASSED"
        and example_payload.get("passed_checks") == example_payload.get("total_checks") == 19,
        "example_employee_relation_consistency_proven": example_payload.get("checks", {}).get("employee_scalar_relation_fact_consistency_proven") is True,
        "reference_relation_count_exact": manifest_a.get("expected_counts", {}).get("relations") == 893
        and len(relations_a) == 893
        and example_contract.get("reference_dataset_counts", {}).get("relations") == 893,
        "connector_example_integration_passed": integration_payload.get("state") == "PASSED"
        and integration_payload.get("passed_checks") == integration_payload.get("total_checks") == 17,
        "dynamic_entity_resolution_retained": integration_checks.get("employee_context_resolved") is True
        and integration_checks.get("same_name_ambiguity_preserved") is True
        and integration_checks.get("similar_client_ambiguity_preserved") is True,
        "delegated_identity_and_secret_redaction_retained": integration_checks.get("delegated_identity_forwarded") is True
        and integration_checks.get("authorization_value_not_captured") is True,
        "workspace_unit_tests_passed": unit.get("returncode") == 0,
        "node_and_project_python_resolved": bool(node)
        and bool(npm)
        and bool(runtime_python)
        and bool(connector_python),
        "subproject_acceptance_did_not_mutate_source": before == after,
        "workspace_manifest_exact": drift == {"missing": [], "changed": [], "unexpected": []},
        "step008_short_expression_live_harness_present": all(
            token in live_harness_source
            for token in (
                '"prompt": "김민수 정보"',
                '"prompt": "김선임 연락처"',
                '"prompt": "김민수 직책"',
                '"prompt": "과장들 목록"',
                'short_expression_route_preflight_exact',
                'actual_openai_model_events_observed_each_turn',
                'expected_mcp_tool_sequence_observed',
                'short_expression_output_contracts_observed',
                'agent.tool.output.normalized',
                'deterministic-ambiguous-tool-evidence-v1',
                'ambiguous_result_normalized_each_ambiguous_turn',
                'structured_output_diagnostics_bounded',
                'normalization_error_category',
                'invocation_id',
                'session.turn.completed',
                'session_turn_completed_events_exact',
                'tool-evidence-provenance-alignment-v1',
                'candidate_count',
            )
        ),
        "step008_live_entrypoint_loads_local_environment": all(
            token in live_entrypoint_source
            for token in (
                'load_local_environment(RUNTIME_ROOT)',
                'OKCANVAS_WORKSPACE_STEP008_LIVE_ACCEPTANCE',
                'run_workspace_step008_live_acceptance.py',
            )
        ),
        "step008_live_launcher_uses_workspace_bytecode_isolation": all(
            token in live_launcher_source
            for token in (
                'workspace_python_bytecode_isolation.py',
                'run_workspace_step008_live_entrypoint.py',
            )
        ),
        "parent_live_acceptance_retained": contracts["runtime-organization-context-connector"].get("live_openai_acceptance")
        == "STEP008R4_WINDOWS_LIVE_OPENAI_ACCEPTED_29_OF_29",
    }
    state = "PASSED" if all(checks.values()) else "FAILED"
    payload = {
        "schema_version": "okcanvas-agent-platform-workspace-step008r4r7a-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "LOCAL_DETERMINISTIC_SHORT_EXPRESSION_ROUTING_REFERENCE_FACT_AND_FRESH_SUBPROJECT_ACCEPTANCE",
        "state": state,
        "started_at": started,
        "completed_at": now(),
        "execution_platform": "windows" if os.name == "nt" else os.name,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "processes": {
            "workspace_unit_tests": unit,
            "runtime_acceptance": runtime_acceptance,
            "connector_acceptance": connector_acceptance,
            "example_acceptance": example_acceptance,
            "connector_example_integration": integration,
        },
        "parsed": {
            "runtime": runtime_payload,
            "connector": connector_payload,
            "example": example_payload,
            "connector_example": integration_payload,
        },
        "workspace_manifest_drift": drift,
        "resolved_interpreters": {
            "node": node,
            "npm": npm,
            "runtime": runtime_python,
            "organization_context_connector": connector_python,
            "workspace_bootstrap": sys.executable,
        },
        "limitations": {
            "windows_step008r4r7a_executed": os.name == "nt",
            "live_openai_model_called": False,
            "live_organization_context_connector_called": False,
            "production_database_executed": False,
            "real_postgresql_server_executed": False,
            "postgresql_live_gate_implemented": True,
            "real_enterprise_organization_context_called": False,
        },
    }
    stage(f"final state={state} passed={sum(value is True for value in checks.values())}/{len(checks)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if emit_stdout:
        write_json_stdout(payload)
    return 0 if state == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--runtime-evidence", type=Path)
    parser.add_argument("--runtime-process-evidence", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if (args.runtime_evidence is None) != (args.runtime_process_evidence is None):
        parser.error("--runtime-evidence and --runtime-process-evidence must be provided together")
    return run(
        args.output.resolve(),
        supplied_runtime_evidence=args.runtime_evidence.resolve() if args.runtime_evidence else None,
        supplied_runtime_process_evidence=(
            args.runtime_process_evidence.resolve() if args.runtime_process_evidence else None
        ),
        emit_stdout=not args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
