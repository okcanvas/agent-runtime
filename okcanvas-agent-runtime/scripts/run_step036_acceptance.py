from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.evaluation import SQLiteEvaluationStore
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.application.execution.output_registry import OutputContractRuntime
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
import okcanvas_agent_runtime.application.execution.output_registry as output_registry

ADMIN_KEY = "step036-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


class DeterministicReferenceGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.started", {"model": settings.model})
        )
        for tool_name in ("search_reference", "read_reference_file"):
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.started",
                    {
                        "server_id": "reference-catalog",
                        "tool_name": tool_name,
                        "arguments_persisted": False,
                    },
                    source=EventSource.MCP,
                )
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.completed",
                    {
                        "server_id": "reference-catalog",
                        "tool_name": tool_name,
                        "result_persisted": False,
                    },
                    source=EventSource.MCP,
                )
            )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": f"resp-{self.calls}"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id})
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Recorded Runtime binding evidence was verified without re-execution.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(
                requests=3,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
            ),
            trace_id=f"trace-step036-{self.calls}",
            response_id=f"resp-step036-{self.calls}",
            sdk_version="0.19.0",
        )


class NeverGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP036 recorded evaluation must not invoke the model gateway")


def _tamper_runtime_binding(database: Path, run_id: str) -> None:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT payload_json FROM run_event WHERE run_id=? AND event_type=?",
            (run_id, "agent.definition.resolved"),
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row[0]))
        payload["runtime_binding_sha256"] = "0" * 64
        connection.execute(
            "UPDATE run_event SET payload_json=? WHERE run_id=? AND event_type=?",
            (
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                run_id,
                "agent.definition.resolved",
            ),
        )
        connection.commit()
    finally:
        connection.close()


async def _run_agent(
    *, service: GenericAgentExecutionService, gateway: DeterministicReferenceGateway, suffix: str
):
    before = gateway.calls
    envelope = await service.run(
        agent_definition_id="reference-research-agent",
        request=f"STEP036 recorded Runtime binding verification {suffix}",
        settings=RuntimeSettings(model="deterministic-model", api_key="sentinel-secret"),
        live_opt_in=True,
    )
    assert gateway.calls == before + 1
    return envelope


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP036", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        store = SQLiteProductStore(product_db)
        store.initialize()
        gateway = DeterministicReferenceGateway()
        service = GenericAgentExecutionService(
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            definitions=AgentDefinitionCatalog(ROOT),
            store=store,
            gateway=gateway,
            artifact_root=workspace.artifact_dir,
        )
        valid, tampered, current_drift = asyncio.run(
            _create_runs(service=service, gateway=gateway)
        )
        expected_binding = AgentRuntimeBindingCatalog(ROOT).resolve(
            AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
        )
        _tamper_runtime_binding(product_db, tampered.run_id)

        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=NeverGateway(),
        )
        with TestClient(app) as client:
            valid_response = client.post(
                f"/v1/runs/{valid.run_id}/evaluations",
                headers=HEADERS,
                json={"case_id": "reference-runstate"},
            )
            tampered_response = client.post(
                f"/v1/runs/{tampered.run_id}/evaluations",
                headers=HEADERS,
                json={"case_id": "reference-runstate"},
            )

            original_contract = output_registry._OUTPUT_CONTRACTS["CodingAgentResult"]
            output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = OutputContractRuntime(
                contract_name="CodingAgentResult",
                output_type=CodingAgentResult,
                runtime_version="1.0.1-drift",
                implementation_id="step036-controlled-current-runtime-drift",
            )
            try:
                current_drift_response = client.post(
                    f"/v1/runs/{current_drift.run_id}/evaluations",
                    headers=HEADERS,
                    json={"case_id": "reference-runstate"},
                )
            finally:
                output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = original_contract

            list_response = client.get("/v1/evaluations", headers=HEADERS)

        evaluation_store = SQLiteEvaluationStore(evaluation_db)
        rows, total = evaluation_store.list_results()
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        valid_body = valid_response.json()
        tampered_body = tampered_response.json()
        current_drift_body = current_drift_response.json()
        list_body = list_response.json()
        persisted_binding = rows[0].get("subject_runtime_binding_sha256") if rows else None
        checks = {
            "three_reference_agent_runs_succeeded": all(
                envelope.state == "SUCCEEDED" for envelope in (valid, tampered, current_drift)
            ),
            "one_model_turn_per_seed_run": gateway.calls == 3,
            "recorded_evaluation_invoked_no_model": gateway.calls == 3,
            "valid_recorded_run_evaluated": valid_response.status_code == 201
            and valid_body.get("state") == "PASSED",
            "runtime_binding_persisted_with_evaluation": persisted_binding
            == expected_binding.runtime_binding_sha256,
            "runtime_binding_exposed_by_control_api": valid_body.get(
                "subject_runtime_binding_sha256"
            )
            == expected_binding.runtime_binding_sha256,
            "recorded_binding_matches_execution_event": any(
                event.event_type == "agent.definition.resolved"
                and event.payload.get("runtime_binding_sha256")
                == expected_binding.runtime_binding_sha256
                for event in store.list_events(valid.run_id)
            ),
            "tampered_recorded_binding_rejected": tampered_response.status_code == 409
            and tampered_body.get("code") == "RUNTIME_BINDING_DRIFT",
            "current_runtime_drift_rejected": current_drift_response.status_code == 409
            and current_drift_body.get("code") == "RUNTIME_BINDING_DRIFT",
            "drift_created_no_evaluation": total == 1,
            "evaluation_list_contains_only_valid_result": list_response.status_code == 200
            and list_body.get("total") == 1
            and len(list_body.get("results", [])) == 1,
            "all_three_artifacts_preserved": len(
                list(workspace.artifact_dir.rglob("final-output.json"))
            )
            == 3,
            "runtime_binding_is_non_secret_sha": isinstance(persisted_binding, str)
            and len(persisted_binding) == 64
            and "sentinel-secret" not in persisted_binding,
            "api_key_not_in_product_or_evaluation_db": b"sentinel-secret"
            not in product_db.read_bytes()
            and b"sentinel-secret" not in evaluation_db.read_bytes(),
            "references_unchanged": references_before == references_after,
            "runtime_binding_verification_is_evaluation_only": gateway.calls == 3,
            "valid_evaluation_case_exact": valid_body.get("case_id") == "reference-runstate",
            "valid_subject_agent_exact": valid_body.get("subject_agent_definition_id")
            == "reference-research-agent",
        }
        payload = {
            "schema_version": "okcanvas-step036-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "runtime_binding_sha256": expected_binding.runtime_binding_sha256,
            "gateway_call_count": gateway.calls,
            "evaluation_count": total,
            "valid": {
                "run_id": valid.run_id,
                "http_status": valid_response.status_code,
                "evaluation_id": valid_body.get("evaluation_id"),
                "state": valid_body.get("state"),
                "subject_runtime_binding_sha256": valid_body.get(
                    "subject_runtime_binding_sha256"
                ),
            },
            "tampered_recorded_binding": {
                "run_id": tampered.run_id,
                "http_status": tampered_response.status_code,
                "code": tampered_body.get("code"),
            },
            "current_runtime_drift": {
                "run_id": current_drift.run_id,
                "http_status": current_drift_response.status_code,
                "code": current_drift_body.get("code"),
            },
            "artifact_count": len(list(workspace.artifact_dir.rglob("final-output.json"))),
        }
        final = workspace.finalize(payload)
        print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if final["state"] == "PASSED" else 1


async def _create_runs(*, service, gateway):
    return (
        await _run_agent(service=service, gateway=gateway, suffix="valid"),
        await _run_agent(service=service, gateway=gateway, suffix="tampered-recorded-binding"),
        await _run_agent(service=service, gateway=gateway, suffix="current-runtime-drift"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP036_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
