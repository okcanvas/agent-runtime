from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.evaluation import (
    DeterministicEvaluator,
    EvaluationCatalog,
    SQLiteEvaluationStore,
)
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step011-local-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SENSITIVE_OUTPUT = "STEP011 sensitive model output must not be exposed"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _seed(path: Path) -> tuple[str, str]:
    case = EvaluationCatalog(ROOT).resolve("reference-runstate")
    store = SQLiteEvaluationStore(path)
    store.initialize()
    evaluator = DeterministicEvaluator()
    events = [
        {"event_type": "tool.completed", "payload": {"tool_name": "search_reference"}},
        {"event_type": "tool.completed", "payload": {"tool_name": "read_reference_file"}},
    ]
    ids: list[str] = []
    for index, (tokens, duration) in enumerate(((2700, 30_000), (3000, 28_000)), start=1):
        envelope = {
            "state": "SUCCEEDED",
            "run_id": f"run_step011_{index}",
            "agent_definition_id": "reference-research-agent",
            "model": "acceptance-model",
            "result": {
                "status": "PARTIAL",
                "summary": SENSITIVE_OUTPUT,
                "findings": [],
                "unverified": [],
            },
            "usage": {"requests": 3, "total_tokens": tokens},
        }
        result = evaluator.evaluate(
            case=case, envelope=envelope, events=events, duration_ms=duration
        )
        store.save(case=case, envelope=envelope, result=result)
        ids.append(result.evaluation_id)
    return ids[0], ids[1]


class UnusedGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP011 catalog acceptance must not invoke the model gateway")


def run_acceptance(output: Path) -> int:
    before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    started_at = _now()
    with AcceptanceWorkspace(step_id="STEP011", output=output) as workspace:
        root = workspace.root
        evaluation_db = root / "evaluation.sqlite3"
        first_id, second_id = _seed(evaluation_db)
        app = create_app(
            project_root=ROOT,
            product_db=root / "product.sqlite3",
            artifact_root=root / "artifacts",
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=UnusedGateway(),
        )
        database_before = hashlib.sha256(evaluation_db.read_bytes()).hexdigest()
        with TestClient(app) as client:
            unauthorized = client.get("/v1/agent-definitions")
            definitions = client.get("/v1/agent-definitions", headers=HEADERS)
            definition = client.get(
                "/v1/agent-definitions/reference-research-agent", headers=HEADERS
            )
            cases = client.get("/v1/evaluation-cases", headers=HEADERS)
            case = client.get(
                "/v1/evaluation-cases/reference-runstate", headers=HEADERS
            )
            history = client.get(
                "/v1/evaluations",
                headers=HEADERS,
                params={"case_id": "reference-runstate", "limit": 1, "offset": 0},
            )
            detail = client.get(f"/v1/evaluations/{first_id}", headers=HEADERS)
            comparison = client.get(
                "/v1/evaluation-comparisons",
                headers=HEADERS,
                params={
                    "left_evaluation_id": first_id,
                    "right_evaluation_id": second_id,
                },
            )
            missing = client.get("/v1/evaluations/eval_missing", headers=HEADERS)
        database_after = hashlib.sha256(evaluation_db.read_bytes()).hexdigest()

    after = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    definition_body = definition.json()
    history_body = history.json()
    all_payload = json.dumps(
        {
            "definitions": definitions.json(),
            "definition": definition_body,
            "cases": cases.json(),
            "case": case.json(),
            "history": history_body,
            "detail": detail.json(),
            "comparison": comparison.json(),
        },
        ensure_ascii=False,
    )
    checks = {
        "unauthorized_rejected": unauthorized.status_code == 401,
        "agent_definitions_listed": definitions.status_code == 200
        and len(definitions.json()["definitions"]) >= 2,
        "agent_definition_detail": definition.status_code == 200
        and definition_body["mcp_servers"] == ["reference-catalog"],
        "instructions_not_exposed": "instructions" not in definition_body
        and "instructions_path" not in all_payload,
        "evaluation_cases_listed": cases.status_code == 200
        and cases.json()["cases"][0]["case_id"] == "reference-runstate",
        "evaluation_case_detail": case.status_code == 200
        and case.json()["required_tools"] == ["search_reference", "read_reference_file"],
        "evaluation_history_paginated": history.status_code == 200
        and history_body["total"] == 2
        and len(history_body["results"]) == 1,
        "evaluation_detail": detail.status_code == 200
        and detail.json()["evaluation_id"] == first_id,
        "comparison_created": comparison.status_code == 200
        and comparison.json()["token_delta"] == 300
        and comparison.json()["duration_delta_ms"] == -2000,
        "missing_evaluation_canonical": missing.status_code == 404
        and missing.json()["code"] == "EVALUATION_NOT_FOUND",
        "sensitive_output_not_exposed": SENSITIVE_OUTPUT not in all_payload,
        "evaluation_database_unchanged": database_before == database_after,
        "references_unchanged": before == after,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step011-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "agent_definition_count": len(definitions.json().get("definitions", [])),
        "evaluation_case_count": len(cases.json().get("cases", [])),
        "evaluation_history_total": history_body.get("total"),
    }
    payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP011_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
