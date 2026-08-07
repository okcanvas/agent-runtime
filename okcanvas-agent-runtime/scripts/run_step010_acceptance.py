from __future__ import annotations

import argparse
import json
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.application.evaluation import (
    DeterministicEvaluator,
    EvaluationCatalog,
    SQLiteEvaluationStore,
    compare_results,
)

ROOT = Path(__file__).resolve().parents[1]


def _envelope(*, status: str = "PARTIAL", tokens: int = 2785, run_id: str = "run_a") -> dict[str, object]:
    return {
        "state": "SUCCEEDED",
        "run_id": run_id,
        "agent_definition_id": "reference-research-agent",
        "model": "fixture-model",
        "result": {
            "status": status,
            "summary": "redacted fixture",
            "findings": [],
            "unverified": [],
        },
        "usage": {"requests": 3, "total_tokens": tokens},
    }


def run_acceptance(output: Path) -> int:
    case = EvaluationCatalog(ROOT).resolve("reference-runstate")
    events = [
        {"event_type": "tool.completed", "payload": {"tool_name": "search_reference"}},
        {"event_type": "tool.completed", "payload": {"tool_name": "read_reference_file"}},
    ]
    with AcceptanceWorkspace(step_id="STEP010", output=output) as workspace:
        database = workspace.database_dir / "acceptance-evaluation.sqlite3"
        store = SQLiteEvaluationStore(database)
        store.initialize()
        evaluator = DeterministicEvaluator()
        passed_envelope = _envelope()
        passed = evaluator.evaluate(
            case=case, envelope=passed_envelope, events=events, duration_ms=32_000
        )
        store.save(case=case, envelope=passed_envelope, result=passed)
        failed_envelope = _envelope(tokens=6000, run_id="run_b")
        failed = evaluator.evaluate(
            case=case, envelope=failed_envelope, events=events[:1], duration_ms=70_000
        )
        store.save(case=case, envelope=failed_envelope, result=failed)
        rows = SQLiteEvaluationStore(database).list_case(case.case_id)
        comparison = compare_results(
            {"evaluation_id": passed.evaluation_id, "state": passed.state, "metrics": passed.metrics},
            {"evaluation_id": failed.evaluation_id, "state": failed.state, "metrics": failed.metrics},
        )
        checks = {
            "passing_case_accepted": passed.state == "PASSED",
            "missing_tool_fails": failed.checks["required_tools"] is False,
            "token_budget_fails": failed.checks["token_budget"] is False,
            "latency_budget_fails": failed.checks["latency_budget"] is False,
            "history_survives_restart": len(rows) == 2,
            "comparison_created": comparison["state_changed"] is True,
            "raw_result_not_persisted": b"redacted fixture" not in database.read_bytes(),
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step010-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "case_id": case.case_id,
            "case_manifest_sha256": case.manifest_sha256,
            "history_count": len(rows),
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP010_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
