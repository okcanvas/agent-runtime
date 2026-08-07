from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import ConnectFactory
from okcanvas_agent_runtime.adapters.persistence.postgresql import (
    PostgreSQLConnectionSettings,
    PostgreSQLProductStore,
    PostgreSQLRunSubmissionStore,
    PostgreSQLServiceResourceOwnershipStore,
    PostgreSQLToolApprovalStore,
    PostgreSQLEvaluationStore,
    PostgreSQLSessionMetadataRuntimeService,
)
from okcanvas_agent_runtime.adapters.persistence.run_submission import SQLiteRunSubmissionStore
from okcanvas_agent_runtime.adapters.persistence.service_ownership import SQLiteServiceResourceOwnershipStore
from okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service import SQLiteSessionRuntimeService
from okcanvas_agent_runtime.adapters.persistence.tool_approval import SQLiteToolApprovalStore
from okcanvas_agent_runtime.application.evaluation import SQLiteEvaluationStore
from okcanvas_agent_runtime.application.ports import (
    EvaluationStorePort,
    GovernedRunAdmissionPort,
    RunSubmissionStorePort,
    ServiceResourceOwnershipStorePort,
    SessionRuntimePort,
    ToolApprovalStorePort,
)
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.domain.sessions.models import SQLiteSessionPolicy
from okcanvas_agent_runtime.domain.sessions.rotation_policy import SQLiteSessionKeyRotationPolicy
from okcanvas_agent_runtime.adapters.storage.session_history import SessionHistoryKey
from okcanvas_agent_runtime.adapters.storage.artifacts import LocalFilesystemArtifactBlobStore
from okcanvas_agent_runtime.application.artifacts import ArtifactBlobStorePort


class StorageTopologyError(ValueError):
    """Raised when independently valid adapters cannot preserve one storage topology."""


@dataclass(frozen=True)
class StorageTopology:
    schema_version: str
    backend_id: str
    transaction_owner_id: str
    product_store: ProductStore
    submission_store: RunSubmissionStorePort
    governed_admission: GovernedRunAdmissionPort
    tool_approval_store: ToolApprovalStorePort
    ownership_store: ServiceResourceOwnershipStorePort
    evaluation_store: EvaluationStorePort
    session_runtime: SessionRuntimePort
    artifact_blob_store: ArtifactBlobStorePort

    def validate(self) -> "StorageTopology":
        if self.schema_version != "okcanvas-storage-topology-v1":
            raise StorageTopologyError("Storage topology schema is unsupported")
        expected_owner = {
            "sqlite-local-v1": "sqlite-run-submission-governed-admission-v1",
            "postgresql-hybrid-v1": "postgresql-product-submission-governed-admission-v1",
        }.get(self.backend_id)
        if expected_owner is None:
            raise StorageTopologyError("Storage topology backend is unsupported")
        if self.transaction_owner_id != expected_owner:
            raise StorageTopologyError("Governed admission transaction owner is invalid")
        if self.submission_store is not self.governed_admission:
            raise StorageTopologyError(
                "Submission ledger and governed admission must share one transaction owner"
            )
        if self.backend_id == "postgresql-hybrid-v1":
            stores = (
                self.product_store,
                self.submission_store,
                self.ownership_store,
                self.tool_approval_store,
                self.evaluation_store,
                self.session_runtime,
            )
            digests = {
                getattr(getattr(store, "settings", None), "dsn_sha256", None) for store in stores
            }
            if len(digests) != 1 or None in digests:
                raise StorageTopologyError(
                    "PostgreSQL Product, Submission, ownership, approval, evaluation and Session metadata adapters must share one DSN"
                )
        return self


@dataclass(frozen=True)
class SQLiteStorageTopologySettings:
    product_db: Path
    evaluation_db: Path
    session_root: Path
    artifact_root: Path
    session_policy: SQLiteSessionPolicy
    session_history_key: SessionHistoryKey | None
    session_history_previous_key: SessionHistoryKey | None
    session_key_rotation_policy: SQLiteSessionKeyRotationPolicy
    artifact_blob_store: ArtifactBlobStorePort | None = None


def build_sqlite_storage_topology(settings: SQLiteStorageTopologySettings) -> StorageTopology:
    product_db = settings.product_db.expanduser().resolve()
    evaluation_db = settings.evaluation_db.expanduser().resolve()
    session_root = settings.session_root.expanduser().resolve()
    artifact_blob_store = settings.artifact_blob_store or LocalFilesystemArtifactBlobStore(settings.artifact_root)

    product_store = SQLiteProductStore(product_db)
    submission_store = SQLiteRunSubmissionStore(product_db)
    approval_store = SQLiteToolApprovalStore(product_db)
    ownership_store = SQLiteServiceResourceOwnershipStore(product_db)
    evaluation_store = SQLiteEvaluationStore(evaluation_db)
    session_runtime = SQLiteSessionRuntimeService(
        session_root,
        settings.session_policy,
        history_key=settings.session_history_key,
        previous_history_key=settings.session_history_previous_key,
        key_rotation_policy=settings.session_key_rotation_policy,
    )

    for store in (
        product_store,
        submission_store,
        approval_store,
        ownership_store,
        evaluation_store,
        session_runtime,
        artifact_blob_store,
    ):
        store.initialize()

    return StorageTopology(
        schema_version="okcanvas-storage-topology-v1",
        backend_id="sqlite-local-v1",
        transaction_owner_id="sqlite-run-submission-governed-admission-v1",
        product_store=product_store,
        submission_store=submission_store,
        governed_admission=submission_store,
        tool_approval_store=approval_store,
        ownership_store=ownership_store,
        evaluation_store=evaluation_store,
        session_runtime=session_runtime,
        artifact_blob_store=artifact_blob_store,
    ).validate()


@dataclass(frozen=True)
class PostgreSQLHybridStorageTopologySettings:
    postgresql: PostgreSQLConnectionSettings
    local_control_db: Path
    evaluation_db: Path
    session_root: Path
    artifact_root: Path
    session_policy: SQLiteSessionPolicy
    session_history_key: SessionHistoryKey | None
    session_history_previous_key: SessionHistoryKey | None
    session_key_rotation_policy: SQLiteSessionKeyRotationPolicy
    artifact_blob_store: ArtifactBlobStorePort | None = None
    connect_factory: ConnectFactory | None = None


def build_postgresql_hybrid_storage_topology(
    settings: PostgreSQLHybridStorageTopologySettings,
) -> StorageTopology:
    local_control_db = settings.local_control_db.expanduser().resolve()
    evaluation_db = settings.evaluation_db.expanduser().resolve()
    session_root = settings.session_root.expanduser().resolve()
    artifact_blob_store = settings.artifact_blob_store or LocalFilesystemArtifactBlobStore(settings.artifact_root)

    product_store = PostgreSQLProductStore(
        settings.postgresql, connect_factory=settings.connect_factory
    )
    submission_store = PostgreSQLRunSubmissionStore(
        settings.postgresql, connect_factory=settings.connect_factory
    )
    ownership_store = PostgreSQLServiceResourceOwnershipStore(
        settings.postgresql, connect_factory=settings.connect_factory
    )
    approval_store = PostgreSQLToolApprovalStore(
        settings.postgresql, connect_factory=settings.connect_factory
    )
    evaluation_store = PostgreSQLEvaluationStore(
        settings.postgresql, connect_factory=settings.connect_factory
    )
    session_runtime = PostgreSQLSessionMetadataRuntimeService(
        settings.postgresql,
        session_root,
        settings.session_policy,
        history_key=settings.session_history_key,
        previous_history_key=settings.session_history_previous_key,
        key_rotation_policy=settings.session_key_rotation_policy,
        connect_factory=settings.connect_factory,
    )

    for store in (
        product_store,
        ownership_store,
        submission_store,
        approval_store,
        evaluation_store,
        session_runtime,
        artifact_blob_store,
    ):
        store.initialize()

    return StorageTopology(
        schema_version="okcanvas-storage-topology-v1",
        backend_id="postgresql-hybrid-v1",
        transaction_owner_id="postgresql-product-submission-governed-admission-v1",
        product_store=product_store,
        submission_store=submission_store,
        governed_admission=submission_store,
        tool_approval_store=approval_store,
        ownership_store=ownership_store,
        evaluation_store=evaluation_store,
        session_runtime=session_runtime,
        artifact_blob_store=artifact_blob_store,
    ).validate()
