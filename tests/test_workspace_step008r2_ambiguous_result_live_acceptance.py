from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.workspace_inventory import excluded_package_path
from scripts.run_workspace_step008_live_acceptance import (
    committed_session_turns_observed,
    empty_search_result_observed,
)

ROOT = Path(__file__).resolve().parents[1]
CURRENT_BASELINE = json.loads((ROOT / "specs/workspace/current-baseline.json").read_text(encoding="utf-8"))
STEP = CURRENT_BASELINE["workspace_step"]


class WorkspaceStep008R2AmbiguousResultLiveAcceptanceTests(unittest.TestCase):
    def test_workspace_identity_is_current(self) -> None:
        catalog = json.loads(
            (ROOT / "specs/workspace/project-catalog.json").read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["workspace_step"], STEP)
        self.assertEqual(catalog["workspace_version"], CURRENT_BASELINE["workspace_version"])

    def test_live_harness_owns_exact_short_expression_inventory(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_live_acceptance.py").read_text(
            encoding="utf-8"
        )
        for prompt in ("김민수 정보", "김선임 연락처", "김민수 직책", "과장들 목록"):
            self.assertEqual(source.count(f'"prompt": "{prompt}"'), 1)
        for token in (
            '"preferred_operation": "RESOLVE"',
            '"preferred_operation": "SEARCH"',
            '"tool_name": "resolve_organization_context"',
            '"tool_name": "search_organization_context"',
            'short_expression_route_preflight_exact',
            'actual_openai_model_events_observed_each_turn',
            'expected_mcp_tool_sequence_observed',
            'short_expression_output_contracts_observed',
            'safe_agent_failures',
            'decode_process_output',
            'raw_error_persisted": False',
            'agent.tool.output.normalized',
            'deterministic-ambiguous-tool-evidence-v1',
            'ambiguous_result_normalized_each_ambiguous_turn',
            'structured_output_diagnostics_bounded',
            'normalization_error_category',
            'invocation_id',
        ):
            self.assertIn(token, source)

    def test_live_launcher_loads_runtime_local_environment_without_runtime_source_change(self) -> None:
        launcher = (ROOT / "sh_run_workspace_step008_live_acceptance.cmd").read_text(
            encoding="utf-8"
        )
        entrypoint = (ROOT / "scripts/run_workspace_step008_live_entrypoint.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("workspace_python_bytecode_isolation.py", launcher)
        self.assertIn("run_workspace_step008_live_entrypoint.py", launcher)
        self.assertIn("load_local_environment(RUNTIME_ROOT)", entrypoint)
        self.assertIn("OKCANVAS_WORKSPACE_STEP008_LIVE_ACCEPTANCE", entrypoint)
        self.assertIn("run_workspace_step008_live_acceptance.py", entrypoint)

    def test_live_evidence_is_mutable_and_excluded_from_identity(self) -> None:
        self.assertTrue(
            excluded_package_path(Path("docs/evidence/WORKSPACE_STEP008_LIVE_ACCEPTANCE.json"))
        )
        self.assertTrue(
            excluded_package_path(Path("docs/evidence/WORKSPACE_STEP008R4R3_ACCEPTANCE.json"))
        )

    def test_live_claim_records_actual_windows_acceptance(self) -> None:
        contracts = json.loads(
            (ROOT / "specs/workspace/integration-contracts.json").read_text(encoding="utf-8")
        )
        contract = next(
            item
            for item in contracts["contracts"]
            if item["id"] == "runtime-organization-context-connector"
        )
        self.assertEqual(
            contract["live_openai_acceptance"],
            "STEP008R4_WINDOWS_LIVE_OPENAI_ACCEPTED_29_OF_29",
        )

    def test_live_harness_uses_structured_empty_result_and_committed_turn_events(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_live_acceptance.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('empty_search_result_observed(', source)
        self.assertIn('expected_tool_name=str(case["tool_name"])', source)
        self.assertIn('event_payloads(item, "session.turn.completed")', source)
        self.assertIn('session_turn_completed_events_exact', source)
        self.assertIn('committed_session_turns_observed(', source)
        self.assertNotIn('any(token in answer for token in ("없", "찾지 못", "확인되지"))', source)
        self.assertNotIn('session_item_count >= 8', source)
        self.assertNotIn('session_item_count % 2 == 0', source)

    def test_empty_search_result_contract_is_language_independent(self) -> None:
        self.assertTrue(
            empty_search_result_observed(
                content={"status": "ANSWERED", "answer": "검색되지 않았습니다."},
                citation_refs=[],
                unverified=[],
                normalizations=[{
                    "strategy": "tool-evidence-provenance-alignment-v1",
                    "tool_name": "search_organization_context",
                    "candidate_count": 0,
                    "clarification_applied": False,
                    "model_calls_added": 0,
                    "tool_reexecuted": False,
                }],
                expected_tool_name="search_organization_context",
            )
        )

    def test_committed_turn_contract_accepts_post_compaction_item_count(self) -> None:
        completed = [
            {
                "session_id": "session-1",
                "turn_count": turn,
                "item_count": turn * 4,
                "history_persisted_in_product_events": False,
                "history_persisted_in_product_db": False,
            }
            for turn in range(1, 5)
        ]
        self.assertTrue(
            committed_session_turns_observed(
                session={"turn_count": 4, "item_count": 5},
                session_id="session-1",
                completed_payloads=completed,
                expected_turn_count=4,
            )
        )

    def test_committed_turn_contract_rejects_missing_turn(self) -> None:
        completed = [
            {
                "session_id": "session-1",
                "turn_count": turn,
                "item_count": turn * 4,
                "history_persisted_in_product_events": False,
                "history_persisted_in_product_db": False,
            }
            for turn in (1, 2, 4)
        ]
        self.assertFalse(
            committed_session_turns_observed(
                session={"turn_count": 4, "item_count": 5},
                session_id="session-1",
                completed_payloads=completed,
                expected_turn_count=4,
            )
        )

    def test_deterministic_runner_uses_quiet_runtime_output_file_contract(self) -> None:
        source = (ROOT / "scripts/run_workspace_step008_acceptance.py").read_text(encoding="utf-8")
        runtime_source = (ROOT / "okcanvas-agent-runtime/scripts/run_step091b1_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('"--quiet"', source)
        self.assertIn('parser.add_argument("--quiet"', runtime_source)
        self.assertIn('emit_stdout=not args.quiet', runtime_source)
        self.assertIn('print(f\"[WORKSPACE {STEP}]', source)
        self.assertIn('run_process_to_files(', source)
        self.assertIn('capture_mode', (ROOT / 'scripts/workspace_process.py').read_text(encoding='utf-8'))
        gate_source = (ROOT / 'scripts/run_workspace_step008_runtime_gate.py').read_text(encoding='utf-8')
        self.assertIn('executed_fresh', gate_source)
        self.assertIn('source_snapshot_digest_before', gate_source)
        self.assertIn('--runtime-process-evidence', source)


if __name__ == "__main__":
    unittest.main()
