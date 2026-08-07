from __future__ import annotations

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import asyncio
import base64
import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, GenericGatewayRunResult
from okcanvas_agent_runtime.application.execution.contracts import GatewayLifecycleEvent
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.submissions import (
    GovernedLifecyclePolicy,
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step019-acceptance-admin-key"
SUBMITTER_KEY = "step019-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}


class SuccessGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step019"}))
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract})
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="STEP019 success path completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=8, output_tokens=4, total_tokens=12),
            trace_id="trace_step019",
            response_id="resp_step019",
            sdk_version="0.19.0",
        )


class FailingGateway:
    async def run(self, **_kwargs):
        raise RuntimeError("controlled-step019-failure")


class NeverGateway:
    async def run(self, **_kwargs):  # pragma: no cover
        raise AssertionError("recovery fixture must not call gateway")


class CapturingScheduler:
    def __init__(self) -> None:
        self.prepared = []

    async def schedule_prepared(self, *, prepared, settings):
        self.prepared.append((prepared, settings))
        return object()


def _wait_submission(client: TestClient, submission_id: str, terminal_states: set[str]) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        payload = client.get(
            f"/v1/run-submissions/{submission_id}", headers=ADMIN_HEADERS
        ).json()
        if payload.get("state") in terminal_states:
            return payload
        time.sleep(0.02)
    raise RuntimeError("submission did not reach expected terminal state")


def _direct_recovery_fixture(root: Path) -> dict[str, object]:
    database = root / "product.sqlite3"
    product = SQLiteProductStore(database)
    product.initialize()
    submissions = SQLiteRunSubmissionStore(database)
    submissions.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        root / "payloads", ProtectedPayloadKey.from_text(PAYLOAD_KEY)
    )
    payloads.initialize()
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT), store=submissions, protected_payload_store=payloads
    )
    execution = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=product,
        gateway=NeverGateway(),
        artifact_root=root / "artifacts",
    )
    first_scheduler = CapturingScheduler()
    first = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=first_scheduler,
        owner_id="step019-owner-one",
        lifecycle_policy=GovernedLifecyclePolicy(
            claim_lease_seconds=5,
            max_claim_attempts=3,
            failed_payload_retention_days=7,
        ),
    )
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="STEP019 stale recovery fixture",
        model="acceptance-model",
        idempotency_key="step019-recovery-fixture-key",
    )
    settings = RuntimeSettings(model="acceptance-model", api_key="fixture-key")
    initial = asyncio.run(
        first.confirm_and_schedule(
            submission_id=decision.submission_id,
            confirmation=decision.confirmation_challenge or "",
            settings=settings,
        )
    )
    old_prepared, _ = first_scheduler.prepared[0]
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE run_submission_preflight SET claim_expires_at = ? WHERE submission_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
                decision.submission_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    second_scheduler = CapturingScheduler()
    second = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=second_scheduler,
        owner_id="step019-owner-two",
        lifecycle_policy=GovernedLifecyclePolicy(
            claim_lease_seconds=5,
            max_claim_attempts=3,
            failed_payload_retention_days=7,
        ),
    )
    recovered = asyncio.run(second.recover_stale(settings_factory=lambda _decision: settings))
    new_prepared, _ = second_scheduler.prepared[0]
    old_started = bool(old_prepared.start_execution and old_prepared.start_execution())
    new_started = bool(new_prepared.start_execution and new_prepared.start_execution())
    current = submissions.get(decision.submission_id)
    return {
        "submission_id": decision.submission_id,
        "run_id": initial.run_id,
        "recovered": recovered.recovered,
        "old_started": old_started,
        "new_started": new_started,
        "claim_attempts": current.claim_attempts,
        "recovery_count": current.recovery_count,
        "state": current.state.value,
        "event_types": [event.event_type for event in product.list_events(initial.run_id)],
    }


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP019", output=output) as workspace:
        success_root = workspace.scratch_dir / "success"
        failure_root = workspace.scratch_dir / "failure"
        recovery_root = workspace.scratch_dir / "recovery"

        success_app = create_app(
            project_root=ROOT,
            product_db=success_root / "product.sqlite3",
            artifact_root=success_root / "artifacts",
            evaluation_db=success_root / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            gateway=SuccessGateway(),
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=success_root / "payloads",
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(success_app) as client:
            success_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": "STEP019 successful payload cleanup",
                    "model": "acceptance-model",
                    "idempotency_key": "step019-success-idempotency",
                },
            ).json()
            success_path = success_root / "payloads" / f"{success_preflight['protected_payload_ref']}.json"
            existed_before = success_path.is_file()
            confirmed = client.post(
                f"/v1/run-submissions/{success_preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": success_preflight["confirmation_challenge"]},
            ).json()
            success_detail = _wait_submission(
                client, success_preflight["submission_id"], {"EXECUTION_SUCCEEDED"}
            )
            success_events = client.get(
                f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
            ).json()["events"]

        failure_app = create_app(
            project_root=ROOT,
            product_db=failure_root / "product.sqlite3",
            artifact_root=failure_root / "artifacts",
            evaluation_db=failure_root / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            gateway=FailingGateway(),
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=failure_root / "payloads",
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(failure_app) as client:
            failure_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": "STEP019 failed payload preservation",
                    "model": "acceptance-model",
                    "idempotency_key": "step019-failure-idempotency",
                },
            ).json()
            client.post(
                f"/v1/run-submissions/{failure_preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": failure_preflight["confirmation_challenge"]},
            )
            failure_detail = _wait_submission(
                client, failure_preflight["submission_id"], {"EXECUTION_FAILED"}
            )
            failure_path = failure_root / "payloads" / f"{failure_preflight['protected_payload_ref']}.json"
            retained_before_cleanup = failure_path.is_file()
            connection = sqlite3.connect(failure_root / "product.sqlite3")
            try:
                connection.execute(
                    "UPDATE run_submission_preflight SET payload_delete_after = ? WHERE submission_id = ?",
                    ("2000-01-01T00:00:00Z", failure_preflight["submission_id"]),
                )
                connection.commit()
            finally:
                connection.close()
            cleanup = client.post(
                "/v1/protected-payloads/cleanup-expired", headers=SUBMIT_HEADERS
            ).json()
            failure_after_cleanup = client.get(
                f"/v1/run-submissions/{failure_preflight['submission_id']}",
                headers=ADMIN_HEADERS,
            ).json()

        recovery = _direct_recovery_fixture(recovery_root)
        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }
        checks = {
            "success_payload_existed_before_execution": existed_before,
            "success_run_terminalized": success_detail.get("state") == "EXECUTION_SUCCEEDED",
            "success_payload_deleted": not success_path.exists()
            and success_detail.get("payload_retention_state") == "DELETED",
            "success_retention_event_recorded": "payload.retention.applied"
            in [event.get("event_type") for event in success_events],
            "failure_run_terminalized": failure_detail.get("state") == "EXECUTION_FAILED",
            "failure_payload_retained": retained_before_cleanup
            and failure_detail.get("payload_retention_state") == "RETAINED",
            "failure_retention_deadline_recorded": failure_detail.get("payload_delete_after") is not None,
            "expired_cleanup_deleted_payload": cleanup.get("deleted") == 1
            and not failure_path.exists(),
            "cleanup_ledger_updated": failure_after_cleanup.get("payload_retention_state") == "DELETED"
            and failure_after_cleanup.get("payload_deleted_at") is not None,
            "stale_claim_recovered": recovery.get("recovered") == 1,
            "old_generation_fenced": recovery.get("old_started") is False,
            "new_generation_started": recovery.get("new_started") is True,
            "recovery_attempt_bounded_and_counted": recovery.get("claim_attempts") == 2
            and recovery.get("recovery_count") == 1,
            "recovery_event_recorded": "run.execution.recovered" in recovery.get("event_types", []),
            "recovery_run_started_once": recovery.get("event_types", []).count("run.started") == 1,
            "recovery_state_started": recovery.get("state") == "EXECUTION_STARTED",
            "console_remains_read_only": 'method:"POST"'
            not in (legacy_source_contract(ROOT, "okcanvas_agent_runtime/operations_console/assets/console.js")).read_text(
                encoding="utf-8"
            ),
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step019-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "success_submission_id": success_preflight["submission_id"],
            "failure_submission_id": failure_preflight["submission_id"],
            "recovery": recovery,
            "cleanup": cleanup,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP019_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
