from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
CURRENT_STEP = CURRENT_BASELINE["workspace_step"]
CURRENT_VERSION = CURRENT_BASELINE["workspace_version"]
HISTORICAL_STEP = "WORKSPACE_STEP008R4R3_RUNTIME_STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE"
HISTORICAL_VERSION = "0.8.4-r3"

class WorkspaceStep008R4R3PostgreSQLTest(unittest.TestCase):
    def test_runtime_step091b2_evidence_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091B2_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["step"], "STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE")
        self.assertEqual(payload["version"], "2.72.0")
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["passed_checks"], payload["total_checks"])
        self.assertEqual(payload["total_checks"], 25)
        self.assertFalse(payload["limitations"]["postgresql_live_server_executed"])

    def test_postgresql_adapter_boundary_is_present(self) -> None:
        root = RUNTIME / "okcanvas_agent_runtime/adapters/persistence/postgresql"
        for name in ("driver.py", "product_store.py", "run_submission.py", "service_ownership.py"):
            self.assertTrue((root / name).is_file(), name)
        driver = (root / "driver.py").read_text(encoding="utf-8")
        submission = (root / "run_submission.py").read_text(encoding="utf-8")
        self.assertIn("pg_advisory_xact_lock", driver)
        self.assertIn("FOR UPDATE", submission)
        self.assertIn("[REDACTED]", driver)

    def test_workspace_current_identity_and_pending_windows_state(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], CURRENT_STEP)
        self.assertEqual(catalog["workspace_version"], CURRENT_VERSION)
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Parent Windows deterministic          33/33 PASSED", handoff)
        self.assertIn("Parent Windows Live OpenAI            29/29 PASSED", handoff)
        self.assertIn("PostgreSQL live server: EXECUTED / 19/19 PASSED", handoff)

    def test_full_runtime_partition_evidence_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091B2_FULL_RUNTIME_TEST_PARTITIONS.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["collected_test_file_count"], 247)
        self.assertEqual(payload["covered_test_file_count"], 247)
        self.assertEqual(payload["total_passed_tests"], 1030)
        self.assertEqual(payload["total_failed_tests"], 0)
        self.assertTrue(payload["exact_file_coverage"])


if __name__ == "__main__":
    unittest.main()
