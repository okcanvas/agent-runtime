from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceStep005R1GroupwarePatternTests(unittest.TestCase):
    def test_workspace_runner_reuses_groupware_owned_e2e_shape(self) -> None:
        source = (ROOT / "scripts/run_workspace_step005r1_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('connector = temp / "c"', source)
        self.assertIn('example = temp / "e"', source)
        self.assertIn("tests/run_organization_context_connector_example_e2e.py", source)
        self.assertNotIn('OKCANVAS_ORGANIZATION_CONTEXT_EXAMPLE_ROOT', source)

    def test_organization_context_e2e_uses_proven_workspace_process_boundary(self) -> None:
        source = (ROOT / "tests/run_organization_context_connector_example_e2e.py").read_text(encoding="utf-8")
        self.assertIn("from workspace_process import prepare_invocation, resolve_executable", source)
        self.assertIn('npm_invocation, npm_shell = prepare_invocation(npm, ["run", "build"])', source)
        self.assertIn('[node, "dist/src/main.js"]', source)

    def test_connector_keeps_groupware_compileall_pattern_without_bespoke_compiler(self) -> None:
        connector = ROOT / "okcanvas-connectors/organization-context-mcp-server"
        source = (connector / "scripts/run_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('"compileall": [sys.executable, "-m", "compileall", "-q"', source)
        self.assertFalse((connector / "scripts/compile_source_tree.py").exists())

    def test_example_matches_groupware_construction_guide_project_closure(self) -> None:
        example = ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
        package = json.loads((example / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "0.2.2")
        self.assertEqual(package["scripts"]["package:source"], "node scripts/package-source.mjs")
        self.assertTrue((example / "scripts/package-source.mjs").is_file())
        acceptance = (example / "scripts/run-acceptance.ts").read_text(encoding="utf-8")
        self.assertIn("typescript_build_dependency_closed", acceptance)
        self.assertIn("EXAMPLE_ORGANIZATION_CONTEXT_STEP002R2_ACCEPTANCE.json", acceptance)

    def test_step005r1_windows_identity_is_retained_as_parent_evidence(self) -> None:
        summary = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP005R1_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["step"], "WORKSPACE_STEP005R1_GROUPWARE_ACCEPTANCE_PATTERN_ALIGNMENT")
        self.assertEqual(summary["version"], "0.5.1")
        self.assertEqual(summary["state"], "PASSED")
        self.assertEqual(summary["passed_checks"], 27)

    def test_step005_compatibility_launcher_delegates_to_r1(self) -> None:
        source = (ROOT / "sh_run_workspace_step005_acceptance.cmd").read_text(encoding="utf-8")
        self.assertIn("call sh_run_workspace_step005r1_acceptance.cmd %*", source)


if __name__ == "__main__":
    unittest.main()
