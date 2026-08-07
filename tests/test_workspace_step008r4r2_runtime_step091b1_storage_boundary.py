from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
STEP = CURRENT_BASELINE["workspace_step"]
VERSION = CURRENT_BASELINE["workspace_version"]
RUNTIME_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
PARENT_RUNTIME_STEP = "STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE"
PARENT_RUNTIME_VERSION = "2.72.0"
RUNTIME_VERSION = "2.75.0"


class WorkspaceStep008R4R3Test(unittest.TestCase):
    def test_current_identity_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], STEP)
        self.assertEqual(catalog["workspace_version"], VERSION)
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], RUNTIME_STEP)
        self.assertEqual(runtime["version"], RUNTIME_VERSION)

    def test_runtime_acceptance_and_full_regression_exact(self) -> None:
        acceptance = json.loads((RUNTIME / "docs/evidence/STEP091B2_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(acceptance["step"], PARENT_RUNTIME_STEP)
        self.assertEqual(acceptance["version"], PARENT_RUNTIME_VERSION)
        self.assertEqual(acceptance["state"], "PASSED")
        self.assertEqual(acceptance["passed_checks"], acceptance["total_checks"])
        self.assertEqual(acceptance["total_checks"], 25)
        full = json.loads((RUNTIME / "docs/evidence/STEP091B2_FULL_RUNTIME_TEST_PARTITIONS.json").read_text(encoding="utf-8"))
        self.assertEqual(full["state"], "PASSED")
        self.assertEqual(full["collected_test_file_count"], 247)
        self.assertEqual(full["covered_test_file_count"], 247)
        self.assertEqual(full["total_passed_tests"], 1030)
        self.assertEqual(full["total_failed_tests"], 0)
        self.assertEqual(full["partition_count"], 12)
        self.assertTrue(full["exact_file_coverage"])

    def test_typed_ports_and_admission_owner_are_explicit(self) -> None:
        source = (RUNTIME / "okcanvas_agent_runtime/application/ports/stores.py").read_text(encoding="utf-8")
        self.assertIn("class RunSubmissionStorePort", source)
        self.assertIn("class GovernedRunAdmissionPort", source)
        self.assertNotIn("*args: Any", source)
        self.assertNotIn("**kwargs: Any", source)
        topology = (RUNTIME / "okcanvas_agent_runtime/bootstrap/storage_topology.py").read_text(encoding="utf-8")
        self.assertIn("okcanvas-storage-topology-v1", topology)
        self.assertIn("sqlite-run-submission-governed-admission-v1", topology)
        self.assertIn("self.submission_store is not self.governed_admission", topology)

    def test_bootstrap_uses_storage_topology(self) -> None:
        source = (RUNTIME / "okcanvas_agent_runtime/bootstrap/application.py").read_text(encoding="utf-8")
        self.assertIn("build_sqlite_storage_topology", source)
        self.assertIn("app.state.storage_topology", source)
        self.assertIn("app.state.governed_run_admission", source)

    def test_postgresql_scope_is_explicit_and_bounded(self) -> None:
        acceptance = json.loads((RUNTIME / "docs/evidence/STEP091B2_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        checks = acceptance["checks"]
        self.assertTrue(checks["postgresql_topology_identity_exact"])
        self.assertTrue(checks["postgresql_same_dsn_validation_present"])
        self.assertTrue(checks["bootstrap_postgresql_opt_in_present"])
        self.assertTrue(checks["sqlite_default_retained"])
        self.assertTrue(checks["artifact_blob_storage_deferred"])
        contract = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))
        current = next(item for item in contract["contracts"] if item["id"] == "runtime-organization-context-connector")
        self.assertTrue(current["postgresql_implemented"])
        self.assertTrue(current["postgresql_live_accepted"])
        self.assertTrue(current["artifact_blob_store_implemented"])
        self.assertEqual(current["storage_backend"], "sqlite-local-v1")
        self.assertEqual(current["supported_storage_backends"], ["sqlite-local-v1", "postgresql-hybrid-v1"])

    def test_parent_windows_live_acceptance_is_retained_not_reclaimed(self) -> None:
        contract = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))
        current = next(item for item in contract["contracts"] if item["id"] == "runtime-organization-context-connector")
        self.assertEqual(current["live_openai_acceptance"], "STEP008R4_WINDOWS_LIVE_OPENAI_ACCEPTED_29_OF_29")
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Parent Windows deterministic          33/33 PASSED", handoff)
        self.assertIn("Parent Windows Live OpenAI            29/29 PASSED", handoff)
        self.assertIn("Promotion: NOT_READY", handoff)


if __name__ == "__main__":
    unittest.main()
