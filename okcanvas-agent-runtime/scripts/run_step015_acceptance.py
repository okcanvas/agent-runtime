from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs.models import RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step015-acceptance-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_acceptance(output: Path) -> int:
    with AcceptanceWorkspace(step_id="STEP015", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        artifact_root = workspace.artifact_dir
        before_references = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=artifact_root,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
        )
        store = app.state.product_store
        task = store.create_task(
            task_type="GENERIC_AGENT",
            input_sha256=hashlib.sha256(b"step015 fixture").hexdigest(),
            agent_definition_id="coding-agent",
            agent_definition_version="1.0.0",
        )
        run = store.create_run(task_id=task.task_id)
        store.transition_task(task.task_id, TaskStatus.RUNNING)
        store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
        store.update_run_execution_metadata(
            run.run_id,
            trace_id="trace_step015_fixture",
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
        )
        store.transition_run(run.run_id, RunStatus.SUCCEEDED, event_type="run.completed")
        store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
        product_before = _sha(product_db)
        evaluation_before = _sha(evaluation_db)

        with TestClient(app) as client:
            shell = client.get("/console")
            css = client.get("/console/assets/console.css")
            js = client.get("/console/assets/console.js")
            unauth = client.get("/v1/operations/summary")
            summary_response = client.get("/v1/operations/summary", headers=HEADERS)
            summary = summary_response.json()
            tasks = client.get("/v1/tasks?status=SUCCEEDED", headers=HEADERS).json()
            runs = client.get("/v1/runs?status=SUCCEEDED", headers=HEADERS).json()
            agents = client.get("/v1/agent-definitions", headers=HEADERS).json()
            cases = client.get("/v1/evaluation-cases", headers=HEADERS).json()
            suites = client.get("/v1/evaluation-suites", headers=HEADERS).json()

        script = js.text
        after_references = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        checks = {
            "console_shell_served": shell.status_code == 200,
            "console_assets_served": css.status_code == 200 and js.status_code == 200,
            "console_csp_enabled": "default-src 'self'" in shell.headers.get("content-security-policy", ""),
            "admin_key_not_embedded": ADMIN_KEY not in shell.text and ADMIN_KEY not in script,
            "session_storage_only": "sessionStorage" in script and "localStorage" not in script,
            "console_get_only": 'method:"GET"' in script and all(
                token not in script for token in ('method:"POST"', 'method:"PATCH"', 'method:"DELETE"')
            ),
            "api_auth_required": unauth.status_code == 401,
            "summary_loaded": summary_response.status_code == 200,
            "summary_read_only": summary.get("runtime", {}).get("console_mode") == "read-only",
            "product_counts_correct": summary.get("product", {}).get("run_total") == 1 and summary.get("product", {}).get("task_total") == 1,
            "run_list_loaded": runs.get("total") == 1 and runs.get("runs", [{}])[0].get("run_id") == run.run_id,
            "task_list_loaded": tasks.get("total") == 1 and tasks.get("tasks", [{}])[0].get("task_id") == task.task_id,
            "catalogs_loaded": len(agents.get("definitions", [])) == 4 and len(cases.get("cases", [])) >= 1 and len(suites.get("suites", [])) >= 1,
            "mcp_read_only_visible": all(item.get("read_only") is True for item in summary.get("catalog", {}).get("mcp_servers", [])),
            "references_verified": summary.get("references", {}).get("verified") == summary.get("references", {}).get("total") == 4,
            "product_db_unchanged_by_gets": _sha(product_db) == product_before,
            "evaluation_db_unchanged_by_gets": _sha(evaluation_db) == evaluation_before,
            "references_unchanged": before_references == after_references,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step015-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "run_id": run.run_id,
            "task_id": task.task_id,
            "summary": {
                "runtime": summary.get("runtime"),
                "product": summary.get("product"),
                "catalog": summary.get("catalog"),
                "evaluation": summary.get("evaluation"),
                "reference_total": summary.get("references", {}).get("total"),
                "reference_verified": summary.get("references", {}).get("verified"),
            },
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP015_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
