from __future__ import annotations

import hashlib
import json
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output = ROOT / "docs" / "evidence" / "STEP005_CORE_STORE_ACCEPTANCE.json"
    with AcceptanceWorkspace(step_id="STEP005", output=output) as workspace:
        database = workspace.database_dir / "acceptance-product-state.sqlite3"
        artifact_path = workspace.artifact_dir / "result.json"
        artifact_path.write_text('{"accepted":true}', encoding="utf-8")
        store = SQLiteProductStore(database)
        store.initialize()
        task = store.create_task(
            task_type="CORE_STORE_ACCEPTANCE",
            input_sha256=hashlib.sha256(b"acceptance-input").hexdigest(),
            agent_definition_id="coding-agent",
            agent_definition_version="v1",
        )
        store.transition_task(task.task_id, TaskStatus.RUNNING)
        run = store.create_run(task_id=task.task_id)
        store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
        store.append_event(
            run.run_id,
            event_type="agent.started",
            source=EventSource.AGENT_SDK,
            payload={"agent_id": "coding-agent"},
        )
        artifact = store.register_artifact(
            run_id=run.run_id,
            artifact_type="structured-output",
            path=artifact_path,
            media_type="application/json",
        )
        store.verify_artifact(artifact.artifact_id)
        store.transition_run(
            run.run_id,
            RunStatus.SUCCEEDED,
            event_type="run.completed",
            payload={"artifact_id": artifact.artifact_id},
        )
        store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
        restarted = SQLiteProductStore(database)
        restarted.initialize()
        events = restarted.list_events(run.run_id)
        result: dict[str, object] = {
            "schema_version": "okcanvas-step005-core-store-acceptance-v1",
            "state": "PASSED",
            "task_status": restarted.get_task(task.task_id).status.value,
            "run_status": restarted.get_run(run.run_id).status.value,
            "event_sequences": [event.sequence for event in events],
            "event_types": [event.event_type for event in events],
            "artifact_sha256": restarted.verify_artifact(artifact.artifact_id).sha256,
            "schema_versions": restarted.schema_versions(),
            "database_bytes": database.stat().st_size,
        }
        result = workspace.finalize(result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
