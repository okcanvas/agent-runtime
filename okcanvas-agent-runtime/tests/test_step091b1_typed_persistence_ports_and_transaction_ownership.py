from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.adapters.persistence.run_submission import SQLiteRunSubmissionStore
from okcanvas_agent_runtime.application.ports import (
    EvaluationStorePort,
    GovernedRunAdmissionPort,
    RunSubmissionStorePort,
    ServiceResourceOwnershipStorePort,
    SessionRuntimePort,
    ToolApprovalStorePort,
)
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.bootstrap.storage_topology import StorageTopologyError

ROOT = Path(__file__).resolve().parents[1]


def _public_protocol_methods(protocol: type) -> tuple[object, ...]:
    return tuple(
        member
        for name, member in inspect.getmembers(protocol, inspect.isfunction)
        if not name.startswith("_")
    )


def test_persistence_ports_have_no_broad_variadic_signatures() -> None:
    protocols = (
        RunSubmissionStorePort,
        GovernedRunAdmissionPort,
        ToolApprovalStorePort,
        ServiceResourceOwnershipStorePort,
        EvaluationStorePort,
        SessionRuntimePort,
    )
    assert protocols
    for protocol in protocols:
        methods = _public_protocol_methods(protocol)
        assert methods, protocol.__name__
        for method in methods:
            kinds = {parameter.kind for parameter in inspect.signature(method).parameters.values()}
            assert inspect.Parameter.VAR_POSITIONAL not in kinds, (protocol.__name__, method.__name__)
            assert inspect.Parameter.VAR_KEYWORD not in kinds, (protocol.__name__, method.__name__)


def test_sqlite_submission_store_implements_separate_ledger_and_admission_ports(tmp_path: Path) -> None:
    store = SQLiteRunSubmissionStore(tmp_path / "product.sqlite3")
    store.initialize()
    assert isinstance(store, RunSubmissionStorePort)
    assert isinstance(store, GovernedRunAdmissionPort)
    assert "create_governed_task_run" not in RunSubmissionStorePort.__dict__
    assert "create_governed_task_run" in GovernedRunAdmissionPort.__dict__


def test_bootstrap_exposes_one_validated_sqlite_transaction_owner(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step091b1-admin-key-123456",
        gateway=object(),
    )
    topology = app.state.storage_topology
    assert topology.backend_id == "sqlite-local-v1"
    assert topology.transaction_owner_id == "sqlite-run-submission-governed-admission-v1"
    assert topology.submission_store is topology.governed_admission
    assert app.state.run_submission_store is topology.submission_store
    assert app.state.governed_run_admission is topology.governed_admission
    assert isinstance(topology.submission_store, RunSubmissionStorePort)
    assert isinstance(topology.governed_admission, GovernedRunAdmissionPort)
    assert isinstance(topology.tool_approval_store, ToolApprovalStorePort)
    assert isinstance(topology.ownership_store, ServiceResourceOwnershipStorePort)
    assert isinstance(topology.evaluation_store, EvaluationStorePort)
    assert isinstance(topology.session_runtime, SessionRuntimePort)
    with TestClient(app) as client:
        assert client.get("/v1/runtime-info", headers={"X-OKCanvas-Admin-Key": "step091b1-admin-key-123456"}).status_code in {200, 404}


def test_topology_rejects_split_submission_and_admission_owners(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step091b1-admin-key-123456",
        gateway=object(),
    )
    topology = app.state.storage_topology
    split = SQLiteRunSubmissionStore(tmp_path / "other.sqlite3")
    split.initialize()
    with pytest.raises(StorageTopologyError):
        replace(topology, governed_admission=split).validate()
