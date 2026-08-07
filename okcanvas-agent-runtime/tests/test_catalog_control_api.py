from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.evaluation import (
    DeterministicEvaluator,
    EvaluationCatalog,
    SQLiteEvaluationStore,
)

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step011-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


class UnusedGateway:
    async def run(self, **_kwargs):  # pragma: no cover - catalog API never invokes it
        raise AssertionError("catalog reads must not invoke the model gateway")


def _envelope(run_id: str, *, state: str = "PARTIAL", tokens: int = 2700) -> dict:
    return {
        "state": "SUCCEEDED",
        "run_id": run_id,
        "agent_definition_id": "reference-research-agent",
        "model": "test-model",
        "result": {
            "status": state,
            "summary": "sensitive model output must not enter the evaluation store",
            "findings": [],
            "unverified": [],
        },
        "usage": {"requests": 3, "total_tokens": tokens},
    }


def _events() -> list[dict]:
    return [
        {"event_type": "tool.completed", "payload": {"tool_name": "search_reference"}},
        {"event_type": "tool.completed", "payload": {"tool_name": "read_reference_file"}},
    ]


def _seed_evaluations(path: Path) -> tuple[str, str]:
    case = EvaluationCatalog(ROOT).resolve("reference-runstate")
    store = SQLiteEvaluationStore(path)
    store.initialize()
    evaluator = DeterministicEvaluator()
    first_envelope = _envelope("run_first", tokens=2700)
    first = evaluator.evaluate(
        case=case, envelope=first_envelope, events=_events(), duration_ms=30_000
    )
    store.save(case=case, envelope=first_envelope, result=first)
    second_envelope = _envelope("run_second", tokens=3000)
    second = evaluator.evaluate(
        case=case, envelope=second_envelope, events=_events(), duration_ms=28_000
    )
    store.save(case=case, envelope=second_envelope, result=second)
    return first.evaluation_id, second.evaluation_id


def _app(tmp_path: Path):
    evaluation_db = tmp_path / "evaluation.sqlite3"
    ids = _seed_evaluations(evaluation_db)
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=evaluation_db,
        admin_key=ADMIN_KEY,
        gateway=UnusedGateway(),
    )
    return app, evaluation_db, ids


def test_catalog_endpoints_require_local_admin_authentication(tmp_path: Path) -> None:
    app, _db, _ids = _app(tmp_path)
    with TestClient(app) as client:
        for path in (
            "/v1/agent-definitions",
            "/v1/evaluation-cases",
            "/v1/evaluations",
            "/v1/evaluation-comparisons?left_evaluation_id=a&right_evaluation_id=b",
        ):
            assert client.get(path).status_code == 401


def test_agent_definition_list_and_detail_are_safe_and_deterministic(tmp_path: Path) -> None:
    app, _db, _ids = _app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/v1/agent-definitions", headers=HEADERS)
        assert response.status_code == 200
        payload = response.json()
        ids = [item["agent_id"] for item in payload["definitions"]]
        assert ids == sorted(ids)
        assert {"coding-agent", "reference-research-agent"}.issubset(ids)

        detail = client.get("/v1/agent-definitions/reference-research-agent", headers=HEADERS)
        assert detail.status_code == 200
        body = detail.json()
        assert body["schema_version"] == "okcanvas-control-agent-definition-detail-v1"
        assert body["mcp_servers"] == ["reference-catalog"]
        assert body["instructions_byte_length"] > 0
        assert len(body["instructions_sha256"]) == 64
        assert body["output_schema"]["type"] == "object"
        encoded = str(body).lower()
        assert "instructions" not in body
        assert "instructions_path" not in encoded
        assert "reference/upstream" not in encoded


def test_agent_definition_and_evaluation_case_not_found_are_canonical(tmp_path: Path) -> None:
    app, _db, _ids = _app(tmp_path)
    with TestClient(app) as client:
        missing_agent = client.get("/v1/agent-definitions/missing-agent", headers=HEADERS)
        assert missing_agent.status_code == 404
        assert missing_agent.json()["code"] == "AGENT_DEFINITION_NOT_FOUND"
        invalid_agent = client.get("/v1/agent-definitions/INVALID", headers=HEADERS)
        assert invalid_agent.status_code == 400
        assert invalid_agent.json()["code"] == "AGENT_DEFINITION_ID_INVALID"
        missing_case = client.get("/v1/evaluation-cases/missing-case", headers=HEADERS)
        assert missing_case.status_code == 404
        assert missing_case.json()["code"] == "EVALUATION_CASE_NOT_FOUND"


def test_evaluation_case_list_and_detail(tmp_path: Path) -> None:
    app, _db, _ids = _app(tmp_path)
    with TestClient(app) as client:
        listing = client.get("/v1/evaluation-cases", headers=HEADERS)
        assert listing.status_code == 200
        assert [item["case_id"] for item in listing.json()["cases"]] == [
            "agent-as-tool-v1",
            "immutable-openai-model-route-v1",
            "immutable-openai-provider-identifier-minimization-v1",
            "immutable-openai-response-storage-disabled-v1",
            "immutable-openai-zero-retry-v1",
            "immutable-reasoning-evidence-minimization-v1",
            "local-text-fingerprint",
            "local-text-metrics",
            "native-guardrail-v1",
            "native-handoff-v1",
            "node-cli-session-conversation-v1",
            "reference-runstate",
            "sqlite-session-approval-v1",
            "sqlite-session-native-agent-tool-v1",
            "sqlite-session-native-guardrail-v1",
            "sqlite-session-native-handoff-v1",
            "sqlite-session-native-mcp-v1",
            "sqlite-session-v1",
            "store-replenishment-case001",
            "store-replenishment-case002-covered",
            "store-replenishment-case003-tie-ordering",
            "store-replenishment-case004-single-shortage",
            "tui-client-foundation-v1",
        ]
        detail = client.get("/v1/evaluation-cases/reference-runstate", headers=HEADERS)
        body = detail.json()
        assert detail.status_code == 200
        assert body["required_tools"] == ["search_reference", "read_reference_file"]
        assert body["forbidden_tools"] == ["write_reference_file", "web_search"]
        assert body["required_result"] == {"status": "PARTIAL"}
        assert len(body["manifest_sha256"]) == 64


def test_evaluation_history_filters_detail_and_comparison(tmp_path: Path) -> None:
    app, _db, (first_id, second_id) = _app(tmp_path)
    with TestClient(app) as client:
        listing = client.get(
            "/v1/evaluations?case_id=reference-runstate&state=PASSED&limit=1&offset=0",
            headers=HEADERS,
        )
        assert listing.status_code == 200
        body = listing.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert len(body["results"]) == 1
        assert body["results"][0]["checks"]["required_tools"] is True

        detail = client.get(f"/v1/evaluations/{first_id}", headers=HEADERS)
        assert detail.status_code == 200
        assert detail.json()["subject_run_id"] == "run_first"
        assert "sensitive model output" not in str(detail.json())

        comparison = client.get(
            "/v1/evaluation-comparisons",
            headers=HEADERS,
            params={
                "left_evaluation_id": first_id,
                "right_evaluation_id": second_id,
            },
        )
        assert comparison.status_code == 200
        compared = comparison.json()
        assert compared["token_delta"] == 300
        assert compared["duration_delta_ms"] == -2000
        assert compared["state_changed"] is False

        missing = client.get("/v1/evaluations/eval_missing", headers=HEADERS)
        assert missing.status_code == 404
        assert missing.json()["code"] == "EVALUATION_NOT_FOUND"


def test_catalog_get_requests_do_not_mutate_evaluation_database(tmp_path: Path) -> None:
    app, evaluation_db, ids = _app(tmp_path)
    before = hashlib.sha256(evaluation_db.read_bytes()).hexdigest()
    with TestClient(app) as client:
        assert client.get("/v1/agent-definitions", headers=HEADERS).status_code == 200
        assert client.get("/v1/evaluation-cases", headers=HEADERS).status_code == 200
        assert client.get("/v1/evaluations", headers=HEADERS).status_code == 200
        assert client.get(f"/v1/evaluations/{ids[0]}", headers=HEADERS).status_code == 200
    after = hashlib.sha256(evaluation_db.read_bytes()).hexdigest()
    assert before == after
