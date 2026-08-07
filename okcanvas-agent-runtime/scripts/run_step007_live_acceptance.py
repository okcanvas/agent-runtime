from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.baseline import PROJECT_VERSION
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, OpenAIGenericAgentGateway
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


async def _run(acceptance_root: Path) -> int:
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    request = (
        "Analyze only this supplied statement: The deployment date is Tuesday, but the release "
        "owner has not been identified. Separate confirmed facts from unverified points."
    )
    before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    database_path = acceptance_root / "product.sqlite3"
    artifact_root = acceptance_root / "artifacts"
    store = SQLiteProductStore(database_path)
    store.initialize()
    envelope = await GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=OpenAIGenericAgentGateway(),
        artifact_root=artifact_root,
    ).run(
        agent_definition_id="coding-agent",
        request=request,
        settings=RuntimeSettings.from_env(),
        live_opt_in=True,
    )
    checks: dict[str, bool] = {"execution_succeeded": envelope.state == "SUCCEEDED"}
    event_types: list[str] = []
    artifact = None
    run = None
    task = None
    if envelope.task_id:
        task = store.get_task(envelope.task_id)
        checks["task_succeeded"] = task.status.value == "SUCCEEDED"
    if envelope.run_id:
        run = store.get_run(envelope.run_id)
        events = store.list_events(envelope.run_id)
        event_types = [event.event_type for event in events]
        checks.update(
            {
                "run_succeeded": run.status.value == "SUCCEEDED",
                "trace_linked": bool(run.trace_id),
                "usage_linked": run.total_tokens > 0,
                "definition_resolved": "agent.definition.resolved" in event_types,
                "agent_started": "agent.started" in event_types,
                "model_started": "model.started" in event_types,
                "model_completed": "model.completed" in event_types,
                "agent_completed": "agent.completed" in event_types,
                "run_completed": event_types[-1:] == ["run.completed"],
                "sequences_monotonic": [event.sequence for event in events]
                == list(range(1, len(events) + 1)),
            }
        )
    if envelope.artifact_id:
        artifact = store.verify_artifact(envelope.artifact_id)
        checks["artifact_verified"] = artifact.sha256 == envelope.artifact_sha256
    database_bytes = database_path.read_bytes()
    checks["raw_request_not_in_database"] = request.encode("utf-8") not in database_bytes
    api_key = os.getenv("OPENAI_API_KEY", "")
    checks["api_key_not_in_database"] = not api_key or api_key.encode() not in database_bytes
    checks["instructions_not_in_database"] = (
        b"Inspect only the information actually provided" not in database_bytes
    )
    after = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    checks["references_unchanged"] = before == after
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step007-live-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "acceptance_id": acceptance_root.name,
        "project_version": PROJECT_VERSION,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "checks": checks,
        "envelope": envelope.model_dump(mode="json"),
        "task": task.__dict__ if task else None,
        "run": run.__dict__ if run else None,
        "event_types": event_types,
        "artifact": artifact.__dict__ if artifact else None,
        "reference_verification_before": before,
        "reference_verification_after": after,
    }
    _write_atomic(acceptance_root / "acceptance-summary.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    print(f"Acceptance evidence: {acceptance_root}")
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-id")
    args = parser.parse_args()
    if os.getenv("OKCANVAS_STEP007_LIVE_ACCEPTANCE") != "1":
        print("STEP007 live acceptance requires OKCANVAS_STEP007_LIVE_ACCEPTANCE=1")
        return 2
    acceptance_id = args.acceptance_id or f"{_stamp()}-{uuid.uuid4().hex[:8]}"
    acceptance_root = ROOT / "docs/evidence/step007-live" / acceptance_id
    if acceptance_root.exists():
        print(f"Acceptance directory already exists: {acceptance_root}")
        return 2
    acceptance_root.mkdir(parents=True)
    return asyncio.run(_run(acceptance_root))


if __name__ == "__main__":
    raise SystemExit(main())
