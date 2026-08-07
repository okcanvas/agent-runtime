from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from test_evaluation_suite_service import _seed_run

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step013-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


class UnusedGateway:
    async def run(self, **_kwargs):
        raise AssertionError("Evaluation Suite API must not invoke a model")


def test_suite_and_baseline_api_are_authenticated_and_persisted(tmp_path: Path) -> None:
    product_db = tmp_path / "product.sqlite3"
    evaluation_db = tmp_path / "evaluation.sqlite3"
    artifact_root = tmp_path / "artifacts"
    store = SQLiteProductStore(product_db)
    store.initialize()
    first = _seed_run(tmp_path, store, suffix="api-a")
    second = _seed_run(tmp_path, store, suffix="api-b")
    app = create_app(
        project_root=ROOT,
        product_db=product_db,
        artifact_root=artifact_root,
        evaluation_db=evaluation_db,
        admin_key=ADMIN_KEY,
        gateway=UnusedGateway(),
    )
    with TestClient(app) as client:
        assert client.get("/v1/evaluation-suites").status_code == 401
        catalog = client.get("/v1/evaluation-suites", headers=HEADERS)
        assert catalog.status_code == 200
        assert catalog.json()["suites"][0]["suite_id"] == "reference-runstate-regression"
        created = client.post(
            "/v1/evaluation-suite-runs",
            headers=HEADERS,
            json={
                "suite_id": "reference-runstate-regression",
                "subjects": [
                    {"subject_id": "primary", "slot_id": "runstate", "run_id": first},
                    {"subject_id": "secondary", "slot_id": "runstate", "run_id": second},
                ],
            },
        )
        assert created.status_code == 201
        suite_run = created.json()
        assert suite_run["state"] == "PASSED"
        baseline = client.post(
            "/v1/evaluation-baselines",
            headers=HEADERS,
            json={"source_suite_run_id": suite_run["suite_run_id"], "label": "API baseline"},
        )
        assert baseline.status_code == 201
        baseline_body = baseline.json()
        fetched = client.get(
            f"/v1/evaluation-baselines/{baseline_body['baseline_id']}", headers=HEADERS
        )
        assert fetched.status_code == 200
        assert fetched.json()["source_suite_run_id"] == suite_run["suite_run_id"]


def test_suite_api_rejects_unknown_baseline_without_partial_writes(tmp_path: Path) -> None:
    product_db = tmp_path / "product.sqlite3"
    evaluation_db = tmp_path / "evaluation.sqlite3"
    store = SQLiteProductStore(product_db)
    store.initialize()
    run_id = _seed_run(tmp_path, store, suffix="api-c")
    app = create_app(
        project_root=ROOT,
        product_db=product_db,
        artifact_root=tmp_path / "artifacts",
        evaluation_db=evaluation_db,
        admin_key=ADMIN_KEY,
        gateway=UnusedGateway(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/evaluation-suite-runs",
            headers=HEADERS,
            json={
                "suite_id": "reference-runstate-regression",
                "baseline_id": "baseline_missing",
                "subjects": [{"subject_id": "primary", "slot_id": "runstate", "run_id": run_id}],
            },
        )
        assert response.status_code == 404
        assert response.json()["code"] == "BASELINE_NOT_FOUND"
