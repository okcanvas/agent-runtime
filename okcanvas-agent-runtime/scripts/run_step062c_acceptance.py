from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scripts.node_acceptance import (
    NODE_RELEASE_MANIFEST_SCHEMA,
    build_node_release_manifest,
    node_test_command,
    run_command,
    run_node_tests,
    validate_committed_typescript_release,
)

OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP062C_ACCEPTANCE.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return value


def run(output: Path) -> int:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
    from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

    info = RuntimeInfo()
    cli_root = ROOT / "clients" / "cli"
    package = _load_json(cli_root / "package.json")
    lock = _load_json(cli_root / "package-lock.json")
    manifest = _load_json(cli_root / "typescript-release-manifest.json")
    failure = _load_json(
        ROOT / "docs/evidence/STEP062B_WINDOWS_COMPILER_ABSENCE_FAILURE_SUMMARY.json"
    )
    helper_source = (ROOT / "scripts/node_acceptance.py").read_text(encoding="utf-8")
    predecessor_sources = [
        (ROOT / name).read_text(encoding="utf-8")
        for name in (
            "scripts/run_step062_acceptance.py",
            "scripts/run_step062a_acceptance.py",
            "scripts/run_step062b_acceptance.py",
        )
    ]

    with tempfile.TemporaryDirectory(prefix="okcanvas-step062c-") as temp_dir:
        predecessor_output = Path(temp_dir) / "step062b.json"
        predecessor_ok, predecessor_console = run_command(
            [
                sys.executable,
                "scripts/run_step062b_acceptance.py",
                "--output",
                str(predecessor_output),
            ],
            ROOT,
        )
        predecessor = _load_json(predecessor_output) if predecessor_output.is_file() else {}

    focused_ok, focused_output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step062c_committed_node_dist_release_integrity_acceptance_fix.py",
        ],
        ROOT,
    )
    compile_ok, compile_output = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts/node_acceptance.py",
            "scripts/generate_node_cli_release_manifest.py",
            "scripts/run_step062_acceptance.py",
            "scripts/run_step062a_acceptance.py",
            "scripts/run_step062b_acceptance.py",
            "scripts/run_step062c_acceptance.py",
        ],
        ROOT,
    )
    release_ok, release_output = validate_committed_typescript_release(cli_root)
    node_test_ok, node_test_output = run_node_tests(cli_root)
    explicit_test_command = node_test_command("node", cli_root)
    expected_manifest = build_node_release_manifest(cli_root, typescript_version="5.8.3")

    reference_results = ReferenceCatalogService(ROOT).verify_all()
    references_ok = len(reference_results) == 4 and all(item.verified for item in reference_results)

    required_docs = [
        ROOT / "docs/plans/STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX.md",
        ROOT
        / "docs/reference/STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP062B_WINDOWS_COMPILER_ABSENCE_FAILURE_SUMMARY.json",
        ROOT / "HANDOFF.md",
        ROOT / "PLANS.md",
        ROOT / "docs/plans/ROADMAP.md",
        ROOT / "README.md",
    ]
    baseline = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/baseline.py")).read_text(encoding="utf-8")

    checks = {
        "baseline_version_and_step_exact": (
            info.version == "2.43.1"
            and info.step == "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"
            and 'PROJECT_VERSION = "2.43.1"' in baseline
            and 'CURRENT_STEP = "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX"'
            in baseline
        ),
        "step062b_third_windows_failure_evidence_exact": (
            failure.get("state") == "FAILED"
            and failure.get("passed_checks") == 17
            and failure.get("total_checks") == 22
            and failure.get("failed_checks")
            == [
                "direct_typescript_command_has_no_batch_file",
                "typescript_compiler_resolution_is_filesystem_verified",
                "corrected_step062a_acceptance_pass",
                "corrected_step062_acceptance_pass",
                "node_typescript_build_pass",
            ]
            and failure.get("typescript_compiler") is None
            and failure.get("typescript_build_command") == []
            and failure.get("node_build_output_tail")
            == "TypeScript compiler command not found on PATH"
            and failure.get("node_tests_passed") is True
        ),
        "step062_orchestration_boundary_preserved": (
            info.bounded_multi_agent_orchestration_implemented is True
            and info.bounded_multi_agent_orchestration_child_count == 2
            and info.bounded_multi_agent_orchestration_max_parallelism == 2
            and info.bounded_multi_agent_orchestration_max_depth == 1
            and info.bounded_multi_agent_orchestration_root_model_calls == 0
            and info.bounded_multi_agent_orchestration_windows_live_accepted is True
        ),
        "step062c_runtime_flags_exact": (
            info.windows_typescript_build_uses_node_direct_compiler is False
            and info.windows_typescript_build_avoids_npm_batch is True
            and info.node_cli_committed_dist_release_integrity_fix_implemented is True
            and info.node_cli_release_manifest_schema == NODE_RELEASE_MANIFEST_SCHEMA
            and info.node_cli_acceptance_external_typescript_compiler_required is False
            and info.node_cli_acceptance_npm_install_required is False
            and info.node_cli_committed_dist_release_integrity_deterministic_accepted is True
            and info.node_cli_committed_dist_release_integrity_windows_live_accepted is True
        ),
        "node_package_zero_dependencies_exact": (
            package.get("name") == "@okcanvas/agent-cli"
            and package.get("version") == "0.5.0"
            and package.get("bin", {}).get("okcanvas-agent") == "./dist/cli.js"
            and not package.get("dependencies")
            and not package.get("devDependencies")
        ),
        "node_lock_zero_dependencies_exact": (
            lock.get("lockfileVersion") == 3
            and isinstance(lock.get("packages"), dict)
            and set(lock["packages"]) == {""}
        ),
        "release_manifest_identity_exact": (
            manifest.get("schema_version") == NODE_RELEASE_MANIFEST_SCHEMA
            and manifest.get("package_name") == "@okcanvas/agent-cli"
            and manifest.get("package_version") == "0.5.0"
            and manifest.get("artifact_mode") == "committed-typescript-dist"
        ),
        "release_manifest_build_evidence_exact": (
            manifest.get("release_build")
            == {
                "tool": "typescript",
                "version": "5.8.3",
                "command": "tsc -p tsconfig.json",
                "dist_reproduced_byte_identical": True,
            }
        ),
        "release_manifest_acceptance_contract_exact": (
            manifest.get("acceptance")
            == {
                "external_typescript_compiler_required": False,
                "npm_install_required": False,
                "network_required": False,
                "validation": "manifest-sha256+source-map-contract+dist-syntax+node-tests",
            }
        ),
        "release_manifest_all_hashes_exact": manifest == expected_manifest,
        "release_manifest_file_counts_exact": (
            len(manifest.get("inputs", {})) == 11
            and len(manifest.get("outputs", {})) == 21
            and len(manifest.get("tests", {})) == 2
        ),
        "committed_typescript_release_validation_pass": (
            release_ok
            and release_output
            == "COMMITTED_TYPESCRIPT_RELEASE_VERIFIED inputs=11 outputs=21 tests=2 external_tsc_required=false"
        ),
        "acceptance_has_no_external_tsc_or_npm_requirement": (
            "def validate_committed_typescript_release" in helper_source
            and "external TypeScript compiler acceptance contract mismatch" in helper_source
            and all("validate_committed_typescript_release(cli_root)" in source for source in predecessor_sources)
            and all("run_typescript_build(cli_root)" not in source for source in predecessor_sources)
        ),
        "no_node_modules_or_temporary_cli_source": (
            not (cli_root / "node_modules").exists()
            and not list((cli_root / "src").rglob("*.tmp"))
        ),
        "node_tests_use_explicit_sorted_files": (
            explicit_test_command
            == [
                "node",
                "--test",
                str(Path("test/config.test.mjs")),
                str(Path("test/render.test.mjs")),
            ]
            and all("*" not in item for item in explicit_test_command)
        ),
        "corrected_step062b_acceptance_pass": (
            predecessor_ok
            and predecessor.get("state") == "PASSED"
            and predecessor.get("passed_checks") == 22
            and predecessor.get("total_checks") == 22
        ),
        "corrected_step062a_acceptance_pass": (
            predecessor.get("corrected_step062a_state") == "PASSED"
            and predecessor.get("corrected_step062a_passed_checks") == 18
            and predecessor.get("corrected_step062a_total_checks") == 18
        ),
        "corrected_step062_acceptance_pass": (
            predecessor.get("corrected_step062_state") == "PASSED"
            and predecessor.get("corrected_step062_passed_checks") == 29
            and predecessor.get("corrected_step062_total_checks") == 29
        ),
        "focused_release_integrity_tests_pass": focused_ok and "7 passed" in focused_output,
        "python_compileall_pass": compile_ok,
        "node_tests_pass": node_test_ok and "# pass 14" in node_test_output,
        "release_manifest_generator_present": (
            (ROOT / "scripts/generate_node_cli_release_manifest.py").is_file()
            and (cli_root / "typescript-release-manifest.json").is_file()
        ),
        "step062c_documents_present": all(path.is_file() for path in required_docs),
        "acceptance_launchers_present": (
            (ROOT / "sh_run_step062_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062a_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062b_acceptance.cmd").is_file()
            and (ROOT / "sh_run_step062c_acceptance.cmd").is_file()
            and (ROOT / "scripts/run_step062c_acceptance.py").is_file()
        ),
        "references_unchanged": references_ok,
        "step064_not_selected": "STEP064_"
        not in "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in [ROOT / "HANDOFF.md", ROOT / "PLANS.md", ROOT / "docs/plans/ROADMAP.md"]
        ),
    }

    payload = {
        "schema_version": "okcanvas-step062c-acceptance-v1",
        "step": "STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX",
        "version": "2.43.1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(1 for value in checks.values() if value),
        "total_checks": len(checks),
        "checks": checks,
        "corrected_step062b_state": predecessor.get("state"),
        "corrected_step062b_passed_checks": predecessor.get("passed_checks"),
        "corrected_step062b_total_checks": predecessor.get("total_checks"),
        "corrected_step062a_state": predecessor.get("corrected_step062a_state"),
        "corrected_step062a_passed_checks": predecessor.get("corrected_step062a_passed_checks"),
        "corrected_step062a_total_checks": predecessor.get("corrected_step062a_total_checks"),
        "corrected_step062_state": predecessor.get("corrected_step062_state"),
        "corrected_step062_passed_checks": predecessor.get("corrected_step062_passed_checks"),
        "corrected_step062_total_checks": predecessor.get("corrected_step062_total_checks"),
        "release_validation_output": release_output,
        "manifest_input_count": len(manifest.get("inputs", {})),
        "manifest_output_count": len(manifest.get("outputs", {})),
        "manifest_test_count": len(manifest.get("tests", {})),
        "focused_test_output": focused_output.splitlines()[-1] if focused_output else "",
        "python_compile_output": compile_output.splitlines()[-1] if compile_output else "",
        "node_test_output_tail": node_test_output.splitlines()[-1] if node_test_output else "",
        "predecessor_console_tail": predecessor_console.splitlines()[-1]
        if predecessor_console
        else "",
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
