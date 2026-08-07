from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step017-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


class ExplodingGateway:
    async def run(self, **kwargs):
        raise AssertionError("Direct Run gateway must not be called when disabled")


def test_direct_run_api_is_disabled_by_default_and_policy_is_readable(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=ExplodingGateway(),
    )
    with TestClient(app) as client:
        denied = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={"input": "must not execute", "confirm_live_call": True},
        )
        policy = client.get("/v1/run-submission-policy", headers=HEADERS)
        unauthorized = client.get("/v1/run-submission-policy")
        shell = client.get("/console")
        script = client.get("/console/assets/console.js")
    assert denied.status_code == 403
    assert denied.json()["code"] == "DIRECT_RUN_SUBMISSION_DISABLED"
    assert policy.status_code == 200
    assert policy.json()["console_mutation_enabled"] is False
    assert policy.json()["direct_run_api_default_enabled"] is False
    assert unauthorized.status_code == 401
    assert "Run Submission Boundary" in shell.text
    assert "/v1/run-submission-policy" in script.text
    assert 'method:"POST"' not in script.text
