from __future__ import annotations

from tests.artifact_test_support import artifact_service

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
import base64
import sqlite3
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class NeverGateway:
    async def run(self, **kwargs):
        raise AssertionError("Concurrency contract does not execute the gateway")


class CountingScheduler:
    def __init__(self) -> None:
        self.calls = 0
        self.prepared = None

    async def schedule_prepared(self, *, prepared, settings):
        self.calls += 1
        self.prepared = prepared
        await asyncio.sleep(0.02)


def test_concurrent_confirmation_binds_one_task_run_and_claims_one_schedule(tmp_path: Path) -> None:
    database = tmp_path / "product.sqlite3"
    product = SQLiteProductStore(database)
    product.initialize()
    submissions = SQLiteRunSubmissionStore(database)
    submissions.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT), store=submissions, protected_payload_store=payloads
    )
    decision = boundary.preflight(
        authority_scope="LOCAL_RUN_SUBMITTER",
        agent_definition_id="coding-agent",
        request="concurrent governed submission",
        model="test-model",
        idempotency_key="step018-concurrent-idempotency",
    )
    scheduler = CountingScheduler()
    execution = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=product,
        gateway=NeverGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(product, tmp_path / "artifacts"),
    )
    governed = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=scheduler,
    )
    settings = RuntimeSettings(model="test-model", api_key="unused")

    async def run_both():
        return await asyncio.gather(
            governed.confirm_and_schedule(
                submission_id=decision.submission_id,
                confirmation=decision.confirmation_challenge or "",
                settings=settings,
            ),
            governed.confirm_and_schedule(
                submission_id=decision.submission_id,
                confirmation=decision.confirmation_challenge or "",
                settings=settings,
            ),
        )

    first, second = asyncio.run(run_both())
    assert first.task_id == second.task_id
    assert first.run_id == second.run_id
    assert sum(int(item.scheduled) for item in (first, second)) == 1
    assert scheduler.calls == 1

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM run_event").fetchone()[0] == 1
    finally:
        connection.close()
