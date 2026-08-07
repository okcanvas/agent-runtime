from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
import base64
import hashlib
import json
import sqlite3
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import (
    CommerceSnapshotAdapterCatalog,
    CommerceSnapshotConfigurationError,
    CommerceSnapshotTooLargeError,
    CommerceSnapshotValidationError,
    ControlledCommerceHTTPAdapter,
    GovernedCommerceSnapshotIngressService,
)
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    RunSubmissionBoundaryService,
    RunSubmissionIdempotencyConflict,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
CASE = json.loads(
    (
        ROOT
        / "specs"
        / "business-cases"
        / "store-replenishment-review"
        / "case001-shortage"
        / "input.json"
    ).read_text(encoding="utf-8")
)
ADMIN_KEY = "step025-admin-key-123456"
SUBMITTER_KEY = "step025-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
TOKEN = "step025-commerce-source-token-sentinel"
ENV = {
    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://127.0.0.1:9325",
    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": TOKEN,
}
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}


class DeterministicGateway:
    calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step025"}))
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract})
        )
        return GenericGatewayRunResult(
            output=build_store_replenishment_result(request),
            usage=UsageSummary(requests=1, input_tokens=10, output_tokens=10, total_tokens=20),
            trace_id="trace_step025",
            response_id="resp_step025",
            sdk_version="0.19.0",
        )


def _json_response(payload=CASE, *, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json", **(headers or {})},
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _service(tmp_path: Path, transport: httpx.AsyncBaseTransport):
    product = SQLiteProductStore(tmp_path / "product.sqlite3")
    product.initialize()
    store = SQLiteRunSubmissionStore(tmp_path / "product.sqlite3")
    store.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(PAYLOAD_KEY)
    )
    payloads.initialize()
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
        project_root=str(ROOT), store=store, protected_payload_store=payloads
    )
    return (
        GovernedCommerceSnapshotIngressService(
            project_root=str(ROOT),
            boundary=boundary,
            store=store,
            environment=ENV,
            transport=transport,
        ),
        store,
    )


def test_catalog_locks_single_read_only_adapter() -> None:
    catalog = CommerceSnapshotAdapterCatalog(ROOT)
    adapters = catalog.list_adapters()
    assert len(adapters) == 1
    definition = adapters[0]
    assert definition.adapter_id == "controlled-commerce-http"
    assert definition.method == "GET"
    assert definition.loopback_only is True
    assert definition.follow_redirects is False
    assert definition.max_retry_attempts == 0


def test_adapter_canonicalizes_valid_snapshot_and_binds_hashes() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "GET"
        assert request.url.path == "/v1/inventory-snapshots/case001-shortage"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        return _json_response()

    adapter = ControlledCommerceHTTPAdapter(
        CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http"),
        environment=ENV,
        transport=httpx.MockTransport(handler),
    )
    acquired = asyncio.run(adapter.acquire("case001-shortage"))
    expected = json.dumps(CASE, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert acquired.canonical_request == expected
    assert acquired.source_binding.source_snapshot_sha256 == hashlib.sha256(
        expected.encode("utf-8")
    ).hexdigest()
    assert calls == 1


def test_adapter_rejects_remote_origin_before_network() -> None:
    called = False

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _json_response()

    adapter = ControlledCommerceHTTPAdapter(
        CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http"),
        environment={**ENV, "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://192.0.2.1:9325"},
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CommerceSnapshotConfigurationError):
        asyncio.run(adapter.acquire("case001-shortage"))
    assert called is False


def test_adapter_rejects_duplicate_json_keys_and_oversized_response() -> None:
    definition = CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http")

    async def duplicate(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"snapshot_id":"a","snapshot_id":"b","safety_stock_units":1,"items":[]}',
        )

    with pytest.raises(CommerceSnapshotValidationError):
        asyncio.run(
            ControlledCommerceHTTPAdapter(
                definition, environment=ENV, transport=httpx.MockTransport(duplicate)
            ).acquire("case001-shortage")
        )

    async def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"x" * (definition.max_response_bytes + 1),
        )

    with pytest.raises(CommerceSnapshotTooLargeError):
        asyncio.run(
            ControlledCommerceHTTPAdapter(
                definition, environment=ENV, transport=httpx.MockTransport(oversized)
            ).acquire("case001-shortage")
        )


def test_concurrent_same_idempotency_reads_source_once(tmp_path: Path) -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return _json_response()

    service, _store = _service(tmp_path, httpx.MockTransport(handler))

    async def invoke():
        return await service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            source_adapter_id="controlled-commerce-http",
            snapshot_key="case001-shortage",
            model="test-model",
            idempotency_key="step025-concurrent-idempotency",
        )

    async def run_both():
        return await asyncio.gather(invoke(), invoke())

    first, second = asyncio.run(run_both())
    assert first.submission_id == second.submission_id
    assert calls == 1


def test_replay_mismatch_conflicts_without_second_read(tmp_path: Path) -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _json_response()

    service, _store = _service(tmp_path, httpx.MockTransport(handler))
    asyncio.run(
        service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            source_adapter_id="controlled-commerce-http",
            snapshot_key="case001-shortage",
            model="test-model",
            idempotency_key="step025-replay-conflict-key",
        )
    )
    with pytest.raises(RunSubmissionIdempotencyConflict):
        asyncio.run(
            service.preflight(
                authority_scope="LOCAL_RUN_SUBMITTER",
                source_adapter_id="controlled-commerce-http",
                snapshot_key="different-snapshot",
                model="test-model",
                idempotency_key="step025-replay-conflict-key",
            )
        )
    assert calls == 1


def test_control_api_ingress_binds_snapshot_before_task_and_runs_once(tmp_path: Path) -> None:
    source_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal source_calls
        source_calls += 1
        assert request.method == "GET"
        return _json_response()

    gateway = DeterministicGateway()
    product_db = tmp_path / "product.sqlite3"
    app = create_app(
        project_root=ROOT,
        product_db=product_db,
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
        gateway=gateway,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected",
        protected_payload_key=PAYLOAD_KEY,
        commerce_snapshot_environment=ENV,
        commerce_snapshot_http_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/commerce-snapshot-ingress/preflight",
            headers=HEADERS,
            json={
                "source_adapter_id": "controlled-commerce-http",
                "snapshot_key": "case001-shortage",
                "model": "test-model",
                "idempotency_key": "step025-api-idempotency-key",
            },
        )
        assert response.status_code == 201, response.text
        preflight = response.json()
        replay = client.post(
            "/v1/commerce-snapshot-ingress/preflight",
            headers=HEADERS,
            json={
                "source_adapter_id": "controlled-commerce-http",
                "snapshot_key": "case001-shortage",
                "model": "test-model",
                "idempotency_key": "step025-api-idempotency-key",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["submission_id"] == preflight["submission_id"]
        connection = sqlite3.connect(product_db)
        try:
            assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 0
        finally:
            connection.close()
        confirmed = client.post(
            f"/v1/run-submissions/{preflight['submission_id']}/confirm",
            headers=HEADERS,
            json={"confirmation": preflight["confirmation_challenge"]},
        )
        assert confirmed.status_code == 202, confirmed.text
        run_id = confirmed.json()["run_id"]
        deadline = time.monotonic() + 3
        terminal = None
        while time.monotonic() < deadline:
            terminal = client.get(f"/v1/runs/{run_id}", headers=HEADERS).json()
            if terminal["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.02)
        assert terminal and terminal["status"] == "SUCCEEDED"
        outcome = client.get(f"/v1/runs/{run_id}/outcome", headers=HEADERS)
        assert outcome.status_code == 200
        detail = client.get(
            f"/v1/run-submissions/{preflight['submission_id']}", headers=HEADERS
        ).json()

    canonical = json.dumps(CASE, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    database_bytes = product_db.read_bytes()
    assert preflight["source_adapter_id"] == "controlled-commerce-http"
    assert preflight["source_snapshot_sha256"] == preflight["input_sha256"]
    assert preflight["source_request_sha256"] is not None
    assert source_calls == 1
    assert gateway.calls == 1
    assert detail["payload_retention_state"] == "DELETED"
    assert canonical.encode("utf-8") not in database_bytes
    assert TOKEN.encode("utf-8") not in database_bytes


def test_adapter_rejects_snapshot_identity_mismatch() -> None:
    from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import (
        CommerceSnapshotIdentityMismatchError,
    )

    async def handler(_request: httpx.Request) -> httpx.Response:
        payload = {**CASE, "snapshot_id": "different-snapshot"}
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=payload,
        )

    adapter = ControlledCommerceHTTPAdapter(
        CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http"),
        environment=ENV,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CommerceSnapshotIdentityMismatchError) as exc_info:
        asyncio.run(adapter.acquire("case001-shortage"))
    assert exc_info.value.code == "COMMERCE_SNAPSHOT_IDENTITY_MISMATCH"
    assert "different-snapshot" not in str(exc_info.value)
