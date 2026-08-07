from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "okcanvas-agent-runtime"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
CURRENT_STEP = CURRENT_BASELINE["workspace_step"]
CURRENT_VERSION = CURRENT_BASELINE["workspace_version"]
CURRENT_RUNTIME_STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
CURRENT_RUNTIME_VERSION = "2.75.0"
PARENT_RUNTIME_STEP = "STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY"
PARENT_RUNTIME_VERSION = "2.73.0"


class WorkspaceStep008R4R4ArtifactBlobStoreTest(unittest.TestCase):
    def test_current_identity_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], CURRENT_STEP)
        self.assertEqual(catalog["workspace_version"], CURRENT_VERSION)
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], CURRENT_RUNTIME_STEP)
        self.assertEqual(runtime["version"], CURRENT_RUNTIME_VERSION)

    def test_runtime_step091c_acceptance_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091C_DETERMINISTIC_ACCEPTANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["step"], PARENT_RUNTIME_STEP)
        self.assertEqual(payload["version"], PARENT_RUNTIME_VERSION)
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["passed_checks"], payload["total_checks"])
        self.assertEqual(payload["total_checks"], 26)
        for name in (
            "artifact_blob_port_typed",
            "artifact_service_coordinates_blob_and_metadata",
            "local_blob_reference_opaque",
            "object_storage_reference_opaque",
            "object_storage_sdk_neutral",
            "product_store_metadata_only",
            "execution_uses_artifact_service",
            "service_read_uses_artifact_service",
            "admin_read_uses_artifact_service",
            "evaluation_uses_artifact_service",
            "topology_owns_blob_store",
            "bootstrap_blob_backend_explicit",
        ):
            self.assertTrue(payload["checks"][name], name)

    def test_step091c_full_runtime_partition_evidence_exact(self) -> None:
        payload = json.loads((RUNTIME / "docs/evidence/STEP091C_FULL_RUNTIME_TEST_PARTITIONS.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "PASSED")
        self.assertEqual(payload["collected_test_file_count"], 248)
        self.assertEqual(payload["covered_test_file_count"], 248)
        self.assertEqual(payload["total_passed_tests"], 1034)
        self.assertEqual(payload["total_failed_tests"], 0)
        self.assertEqual(payload["partition_count"], 12)
        self.assertTrue(payload["all_log_hashes_valid"])
        self.assertTrue(payload["partition_assignments_exact"])
        self.assertTrue(payload["exact_file_coverage"])

    def test_workspace_contract_retains_blob_scope(self) -> None:
        contracts = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))["contracts"]
        current = next(item for item in contracts if item["id"] == "runtime-organization-context-connector")
        self.assertTrue(current["artifact_blob_store_implemented"])
        self.assertEqual(current["artifact_blob_store_port"], "ArtifactBlobStorePort")
        self.assertEqual(current["artifact_service"], "ArtifactService")
        self.assertEqual(current["artifact_storage_reference"], "OPAQUE")
        self.assertEqual(current["artifact_local_backend"], "local-filesystem-artifact-v1")
        self.assertEqual(current["artifact_object_storage_backend"], "object-storage-artifact-v1")
        self.assertFalse(current["artifact_object_storage_live_accepted"])

    def test_current_windows_and_object_storage_live_are_not_claimed(self) -> None:
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Parent Windows deterministic          33/33 PASSED", handoff)
        self.assertIn("Parent Windows Live OpenAI            29/29 PASSED", handoff)
        self.assertIn("Object Storage live server", handoff)
        self.assertIn("NOT_EXECUTED", handoff)
        self.assertIn("Promotion: NOT_READY", handoff)


if __name__ == "__main__":
    unittest.main()
