from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT_STEP = "WORKSPACE_STEP008R4R1_FINAL_PROMOTION_DOCUMENT_PRODUCTIZATION_PLAN_AND_STORAGE_AUDIT_ALIGNMENT"
PARENT_VERSION = "0.8.4-r1"
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
CURRENT_STEP = CURRENT_BASELINE["workspace_step"]
CURRENT_VERSION = CURRENT_BASELINE["workspace_version"]


class WorkspaceStep008R4R1Test(unittest.TestCase):
    def test_current_identity_exact(self) -> None:
        catalog = json.loads((ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["workspace_step"], CURRENT_STEP)
        self.assertEqual(catalog["workspace_version"], CURRENT_VERSION)
        runtime = next(item for item in catalog["projects"] if item["project_id"] == "agent-runtime")
        self.assertEqual(runtime["baseline"], "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE")
        self.assertEqual(runtime["version"], "2.75.0")

    def test_current_documents_are_aligned(self) -> None:
        from scripts.validate_current_document_sot import validate_current_documents

        self.assertEqual(validate_current_documents(ROOT), [])
        baseline = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
        self.assertIn("okcanvas-agent-runtime/PLANS.md", baseline["current_documents"])

    def test_master_plan_and_storage_audit_present(self) -> None:
        required = [
            ROOT / "docs/plans/OKCANVAS_AGENT_RUNTIME_PRODUCTIZATION_MASTER_PLAN.md",
            ROOT / "docs/plans/STEP091A_PRODUCT_STORAGE_BOUNDARY_EXHAUSTIVE_AUDIT.md",
            ROOT / "docs/audits/STEP091A_PRODUCT_STORAGE_BOUNDARY_EXHAUSTIVE_AUDIT.md",
            ROOT / "docs/evidence/STEP091A_PRODUCT_STORAGE_BOUNDARY_AUDIT_SUMMARY.json",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)
        audit = required[2].read_text(encoding="utf-8")
        self.assertIn("SQLiteRunSubmissionStore.create_governed_task_run", audit)
        self.assertIn("ArtifactBlobStorePort", audit)
        self.assertIn("STEP091B1", audit)

    def test_storage_audit_is_read_only_and_rejects_direct_postgresql_port(self) -> None:
        audit = json.loads((ROOT / "docs/evidence/STEP091A_PRODUCT_STORAGE_BOUNDARY_AUDIT_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["mode"], "READ_ONLY")
        self.assertEqual(audit["product_source_modifications"], 0)
        self.assertFalse(audit["direct_postgresql_port_admitted"])
        self.assertEqual(audit["decision"], "STEP091B1_TYPED_PERSISTENCE_PORTS_AND_TRANSACTION_OWNERSHIP")

    def test_live_contract_records_actual_acceptance(self) -> None:
        contracts = json.loads((ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8"))
        contract = next(item for item in contracts["contracts"] if item["id"] == "runtime-organization-context-connector")
        self.assertEqual(contract["live_openai_acceptance"], "STEP008R4_WINDOWS_LIVE_OPENAI_ACCEPTED_29_OF_29")

    def test_product_runtime_python_digest_evidence(self) -> None:
        evidence = json.loads((ROOT / "docs/evidence/WORKSPACE_STEP008R4R1_PRODUCT_RUNTIME_SOURCE_UNCHANGED.json").read_text(encoding="utf-8"))
        self.assertTrue(evidence["unchanged"])
        self.assertEqual(evidence["workspace_step"], PARENT_STEP)
        self.assertEqual(evidence["before_sha256"], evidence["after_sha256"])


if __name__ == "__main__":
    unittest.main()
