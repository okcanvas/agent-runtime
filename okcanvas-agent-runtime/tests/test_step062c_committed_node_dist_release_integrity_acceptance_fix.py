from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.node_acceptance import (
    NODE_RELEASE_MANIFEST_SCHEMA,
    build_node_release_manifest,
    node_release_input_files,
    node_release_output_files,
    node_release_test_files,
    validate_committed_typescript_release,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clients" / "cli"


def test_step062c_runtime_baseline_and_flags_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.windows_typescript_build_uses_node_direct_compiler is False
    assert info.node_cli_committed_dist_release_integrity_fix_implemented is True
    assert info.node_cli_release_manifest_schema == NODE_RELEASE_MANIFEST_SCHEMA
    assert info.node_cli_acceptance_external_typescript_compiler_required is False
    assert info.node_cli_acceptance_npm_install_required is False
    assert info.node_cli_committed_dist_release_integrity_deterministic_accepted is True
    assert info.node_cli_committed_dist_release_integrity_windows_live_accepted is True
    assert info.bounded_multi_agent_orchestration_implemented is True


def test_release_manifest_matches_exact_packaged_inputs_outputs_and_tests() -> None:
    manifest = json.loads((CLI / "typescript-release-manifest.json").read_text(encoding="utf-8"))
    expected = build_node_release_manifest(CLI, typescript_version="5.8.3")
    assert manifest == expected
    assert manifest["schema_version"] == NODE_RELEASE_MANIFEST_SCHEMA
    assert manifest["acceptance"] == {
        "external_typescript_compiler_required": False,
        "npm_install_required": False,
        "network_required": False,
        "validation": "manifest-sha256+source-map-contract+dist-syntax+node-tests",
    }
    assert len(node_release_input_files(CLI)) == 11
    assert len(node_release_output_files(CLI)) == 21
    assert len(node_release_test_files(CLI)) == 2


def test_committed_release_validation_passes_without_node_modules_or_path_tsc_dependency() -> None:
    ok, output = validate_committed_typescript_release(CLI)
    assert ok is True, output
    assert output == (
        "COMMITTED_TYPESCRIPT_RELEASE_VERIFIED "
        "inputs=11 outputs=21 tests=2 external_tsc_required=false"
    )
    package = json.loads((CLI / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((CLI / "package-lock.json").read_text(encoding="utf-8"))
    assert not package.get("dependencies")
    assert not package.get("devDependencies")
    assert set(lock["packages"]) == {""}
    assert not (CLI / "node_modules").exists()
    assert not list((CLI / "src").rglob("*.tmp"))


def test_third_windows_failure_evidence_is_exact() -> None:
    failure = json.loads(
        (ROOT / "docs/evidence/STEP062B_WINDOWS_COMPILER_ABSENCE_FAILURE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["passed_checks"] == 17
    assert failure["total_checks"] == 22
    assert failure["failed_checks"] == [
        "direct_typescript_command_has_no_batch_file",
        "typescript_compiler_resolution_is_filesystem_verified",
        "corrected_step062a_acceptance_pass",
        "corrected_step062_acceptance_pass",
        "node_typescript_build_pass",
    ]
    assert failure["typescript_compiler"] is None
    assert failure["typescript_build_command"] == []
    assert failure["node_build_output_tail"] == "TypeScript compiler command not found on PATH"
    assert failure["node_tests_passed"] is True


def test_predecessor_acceptances_use_committed_release_validation() -> None:
    for name in (
        "scripts/run_step062_acceptance.py",
        "scripts/run_step062a_acceptance.py",
        "scripts/run_step062b_acceptance.py",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "validate_committed_typescript_release(cli_root)" in source
        assert "run_typescript_build(cli_root)" not in source


def test_release_validation_does_not_query_or_require_tsc(monkeypatch) -> None:
    import shutil
    from scripts import node_acceptance

    node = shutil.which("node") or shutil.which("node.exe")
    assert node
    calls: list[str] = []

    def which(name: str) -> str | None:
        calls.append(name)
        if name in {"node", "node.exe"}:
            return node
        return None

    monkeypatch.setattr(node_acceptance.shutil, "which", which)
    ok, output = validate_committed_typescript_release(CLI)
    assert ok is True, output
    assert "tsc" not in calls
    assert "npm" not in calls


def test_release_validation_rejects_tampered_dist(tmp_path: Path) -> None:
    import shutil

    copied = tmp_path / "cli"
    shutil.copytree(CLI, copied)
    target = copied / "dist/render.js"
    target.write_text(target.read_text(encoding="utf-8") + "\n// tampered\n", encoding="utf-8")
    ok, output = validate_committed_typescript_release(copied)
    assert ok is False
    assert "release manifest outputs hash set mismatch" in output
