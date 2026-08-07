from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.scenarios import WalkingSkeletonScenarioCatalog

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "walking-skeleton-admin-key"


def test_walking_skeleton_catalog_is_closed_and_exact() -> None:
    catalog = WalkingSkeletonScenarioCatalog(ROOT)
    scenarios = catalog.list_scenarios()
    assert tuple(item.scenario_id for item in scenarios) == catalog.REQUIRED_SCENARIOS
    assert len(scenarios) == 10
    assert all(item.workspace_access == "none" for item in scenarios)
    assert any(item.requires_approval_operator for item in scenarios)
    assert any(item.requires_session for item in scenarios)
    assert {kind for item in scenarios for kind in item.invocation_kinds} == {
        "ROOT",
        "HANDOFF",
        "AGENT_AS_TOOL",
    }


def test_runtime_scenario_api_is_authenticated_and_resolves_catalog(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
    )
    with TestClient(app) as client:
        assert client.get("/v1/runtime-scenarios").status_code == 401
        response = client.get(
            "/v1/runtime-scenarios",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["skeleton_state"] == "IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING"
    assert len(body["scenarios"]) == 10
    assert body["scenarios"][0]["scenario_id"] == "tool-free-structured"
