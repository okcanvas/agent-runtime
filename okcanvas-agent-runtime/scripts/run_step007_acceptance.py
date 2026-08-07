from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class AcceptanceGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_acceptance"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="The deterministic acceptance gateway inspected only supplied text.",
                findings=[],
                unverified=["Live model behavior"],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                cached_input_tokens=5,
                reasoning_tokens=1,
            ),
            trace_id="trace_step007_acceptance",
            response_id="resp_acceptance",
            sdk_version="0.19.0-test-double",
        )


async def _run(output: Path) -> int:
    started_at = _utc_now()
    request = "STEP007 deterministic acceptance sentinel"
    before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP007", output=output) as workspace:
        temp_root = workspace.root
        store = SQLiteProductStore(temp_root / "product.sqlite3")
        store.initialize()
        service = GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            definitions=AgentDefinitionCatalog(ROOT),
            store=store,
            gateway=AcceptanceGateway(),
            artifact_root=temp_root / "artifacts",
        )
        envelope = await service.run(
            agent_definition_id="coding-agent",
            request=request,
            settings=RuntimeSettings(model="acceptance-model", api_key="acceptance-secret"),
            live_opt_in=True,
        )
        assert envelope.task_id and envelope.run_id and envelope.artifact_id
        task = store.get_task(envelope.task_id)
        run = store.get_run(envelope.run_id)
        events = store.list_events(envelope.run_id)
        artifact = store.verify_artifact(envelope.artifact_id)
        database = (temp_root / "product.sqlite3").read_bytes()
        event_types = [event.event_type for event in events]
        checks = {
            "execution_succeeded": envelope.state == "SUCCEEDED",
            "task_succeeded": task.status.value == "SUCCEEDED",
            "run_succeeded": run.status.value == "SUCCEEDED",
            "trace_linked": run.trace_id == "trace_step007_acceptance",
            "usage_linked": (run.input_tokens, run.output_tokens, run.total_tokens) == (20, 10, 30),
            "definition_resolved": "agent.definition.resolved" in event_types,
            "sdk_lifecycle_normalized": event_types[3:7] == [
                "agent.started", "model.started", "model.completed", "agent.completed"
            ],
            "artifact_registered": artifact.sha256 == envelope.artifact_sha256,
            "raw_request_not_in_database": request.encode() not in database,
            "api_key_not_in_database": b"acceptance-secret" not in database,
            "sequences_monotonic": [event.sequence for event in events] == list(range(1, len(events) + 1)),
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step007-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started_at,
            "completed_at": _utc_now(),
            "checks": checks,
            "agent_definition": AgentDefinitionCatalog(ROOT).resolve("coding-agent").to_public_dict(),
            "task": task.__dict__,
            "run": run.__dict__,
            "event_types": event_types,
            "artifact": artifact.__dict__,
            "envelope": envelope.model_dump(mode="json"),
        }
    after = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    payload["checks"]["references_unchanged"] = before == after  # type: ignore[index]
    payload["reference_verification_before"] = before
    payload["reference_verification_after"] = after
    payload["state"] = "PASSED" if all(payload["checks"].values()) else "FAILED"  # type: ignore[union-attr]
    payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP007_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
