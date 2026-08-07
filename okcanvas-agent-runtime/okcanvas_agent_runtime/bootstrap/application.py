from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from okcanvas_agent_protocols.rest.admin import ErrorBody
from okcanvas_agent_runtime.adapters.openai.local_tool_approval import OpenAILocalToolApprovalGateway
from okcanvas_agent_runtime.adapters.sandbox.docker import SandboxRuntimeCatalog
from okcanvas_agent_runtime.adapters.storage.attachments import EncryptedLocalAttachmentStore
from okcanvas_agent_runtime.adapters.storage.artifacts import (
    Boto3S3CompatibleObjectStorageClient,
    LocalFilesystemArtifactBlobStore,
    ObjectStorageArtifactBlobStore,
    ObjectStorageArtifactSettings,
    S3CompatibleClientSettings,
)
from okcanvas_agent_runtime.adapters.storage.project_snapshots import EncryptedProjectSnapshotStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import EncryptedFileProtectedPayloadStore, ProtectedPayloadKey
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.admin import AdminUseCases
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.application.approvals import EncryptedRunStateStore, GovernedLocalToolApprovalService
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution.coordinator import LocalExecutionCoordinator
from okcanvas_agent_runtime.application.operations import OperationsSnapshotService
from okcanvas_agent_runtime.application.service import ServiceUseCases
from okcanvas_agent_runtime.application.submissions import (
    GovernedExecutionLifecycleService,
    GovernedLifecyclePolicyCatalog,
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    RunSubmissionPolicyCatalog,
)
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.bootstrap.storage_topology import (
    PostgreSQLHybridStorageTopologySettings,
    SQLiteStorageTopologySettings,
    build_postgresql_hybrid_storage_topology,
    build_sqlite_storage_topology,
)
from okcanvas_agent_runtime.adapters.persistence.postgresql import PostgreSQLConnectionSettings
from okcanvas_agent_runtime.core.baseline import PROJECT_VERSION
from okcanvas_agent_runtime.core.paths import CLIENTS_PACKAGE_ROOT
from okcanvas_agent_runtime.domain.attachments import LocalAttachmentPolicyCatalog
from okcanvas_agent_runtime.domain.project_snapshots import ProjectSnapshotPolicyCatalog
from okcanvas_agent_runtime.domain.sessions import (
    SQLiteSessionKeyRotationPolicyCatalog,
    SQLiteSessionPolicyCatalog,
    SessionConfigurationError,
    SessionHistoryKey,
)
from okcanvas_agent_runtime.application.evaluation import (
    EvaluationCatalog,
    EvaluationSuiteCatalog,
    EvaluationSuiteService,
    RecordedRunEvaluationService,
)
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.scenarios import WalkingSkeletonScenarioCatalog
from okcanvas_agent_runtime.transport.admin.rest.auth import LocalAdminAuthenticator, LocalRunSubmitterAuthenticator
from okcanvas_agent_runtime.transport.admin.rest.routes import AdminRouteContext, build_admin_router
from okcanvas_agent_runtime.bootstrap.router_registration import include_router_exact
from okcanvas_agent_runtime.transport.service.rest.auth import ServiceClientAuthenticator, ServiceClientTokenRegistry
from okcanvas_agent_runtime.transport.service.rest.routes import build_service_client_router
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import GovernedCommerceSnapshotIngressService



def create_app(
    *,
    project_root: str | Path,
    product_db: str | Path,
    artifact_root: str | Path,
    admin_key: str,
    evaluation_db: str | Path | None = None,
    gateway=None,
    direct_run_submission_enabled: bool = False,
    run_submitter_key: str | None = None,
    protected_payload_root: str | Path | None = None,
    protected_payload_key: str | None = None,
    run_state_root: str | Path | None = None,
    session_root: str | Path | None = None,
    session_history_key: str | None = None,
    session_history_previous_key: str | None = None,
    readonly_workspace_root: str | Path | None = None,
    sandbox_readonly_image: str | None = None,
    sandbox_temporary_parent: str | Path | None = None,
    tool_approval_gateway=None,
    commerce_snapshot_environment: Mapping[str, str] | None = None,
    commerce_snapshot_http_transport=None,
    native_stream_broker: InMemoryNativeSDKStreamBroker | None = None,
    service_client_token_registry_json: str | None = None,
    organization_catalog_root: str | Path | None = None,
    product_store_backend: str = "sqlite-local-v1",
    postgresql_dsn: str | None = None,
    postgresql_connect_factory=None,
    artifact_blob_store_backend: str = "local-filesystem-artifact-v1",
    object_storage_bucket: str | None = None,
    object_storage_prefix: str = "okcanvas-artifacts",
    object_storage_client=None,
) -> FastAPI:
    project = Path(project_root).expanduser().resolve()
    definitions = AgentDefinitionCatalog(project)
    session_policy = SQLiteSessionPolicyCatalog(project).resolve()
    session_key_rotation_policy = SQLiteSessionKeyRotationPolicyCatalog(project).resolve()
    resolved_session_history_key = (
        SessionHistoryKey.from_text(session_history_key)
        if session_history_key is not None and session_history_key.strip()
        else None
    )
    resolved_session_history_previous_key = (
        SessionHistoryKey.from_text(session_history_previous_key)
        if session_history_previous_key is not None and session_history_previous_key.strip()
        else None
    )
    if (
        resolved_session_history_key is not None
        and resolved_session_history_previous_key is not None
        and hmac.compare_digest(
            resolved_session_history_key._raw, resolved_session_history_previous_key._raw
        )
    ):
        raise SessionConfigurationError(
            "Current and previous Session history keys must be distinct"
        )
    normalized_backend = product_store_backend.strip().lower()
    normalized_artifact_backend = artifact_blob_store_backend.strip().lower()
    resolved_artifact_root = Path(artifact_root).expanduser().resolve()
    if normalized_artifact_backend == "local-filesystem-artifact-v1":
        if object_storage_bucket is not None or object_storage_client is not None:
            raise ValueError("Object Storage settings must not be configured for local Artifact storage")
        artifact_blob_store = LocalFilesystemArtifactBlobStore(resolved_artifact_root)
    elif normalized_artifact_backend == "object-storage-artifact-v1":
        if object_storage_client is None or object_storage_bucket is None:
            raise ValueError("Object Storage Artifact backend requires bucket and client")
        artifact_blob_store = ObjectStorageArtifactBlobStore(
            ObjectStorageArtifactSettings(
                bucket=object_storage_bucket, prefix=object_storage_prefix
            ),
            object_storage_client,
        )
    else:
        raise ValueError("Artifact blob storage backend is unsupported")
    local_product_db = Path(product_db).expanduser().resolve()
    local_evaluation_db = Path(
        evaluation_db or (local_product_db.parent / "evaluation.sqlite3")
    )
    local_session_root = Path(session_root or (local_product_db.parent / "sessions"))
    if normalized_backend == "sqlite-local-v1":
        if postgresql_dsn is not None and postgresql_dsn.strip():
            raise ValueError("PostgreSQL DSN must not be configured for the SQLite topology")
        topology = build_sqlite_storage_topology(
            SQLiteStorageTopologySettings(
                product_db=local_product_db,
                evaluation_db=local_evaluation_db,
                session_root=local_session_root,
                artifact_root=resolved_artifact_root,
                artifact_blob_store=artifact_blob_store,
                session_policy=session_policy,
                session_history_key=resolved_session_history_key,
                session_history_previous_key=resolved_session_history_previous_key,
                session_key_rotation_policy=session_key_rotation_policy,
            )
        )
    elif normalized_backend == "postgresql-hybrid-v1":
        if postgresql_dsn is None or not postgresql_dsn.strip():
            raise ValueError("PostgreSQL topology requires OKCANVAS_POSTGRESQL_DSN")
        topology = build_postgresql_hybrid_storage_topology(
            PostgreSQLHybridStorageTopologySettings(
                postgresql=PostgreSQLConnectionSettings(postgresql_dsn),
                local_control_db=local_product_db,
                connect_factory=postgresql_connect_factory,
                evaluation_db=local_evaluation_db,
                session_root=local_session_root,
                artifact_root=resolved_artifact_root,
                artifact_blob_store=artifact_blob_store,
                session_policy=session_policy,
                session_history_key=resolved_session_history_key,
                session_history_previous_key=resolved_session_history_previous_key,
                session_key_rotation_policy=session_key_rotation_policy,
            )
        )
    else:
        raise ValueError("Product storage backend is unsupported")
    store = topology.product_store
    session_runtime = topology.session_runtime
    evaluation_store = topology.evaluation_store
    tool_approval_store = topology.tool_approval_store
    service_resource_ownership = topology.ownership_store
    submission_store = topology.submission_store
    governed_admission = topology.governed_admission
    artifact_service = ArtifactService(
        product_store=store, blob_store=topology.artifact_blob_store
    )
    evaluation_catalog = EvaluationCatalog(project)
    evaluation_suite_catalog = EvaluationSuiteCatalog(project)
    mcp_catalog = MCPServerCatalog(project)
    reference_catalog = ReferenceCatalogService(project)
    walking_skeleton_catalog = WalkingSkeletonScenarioCatalog(project)
    run_submission_policy = RunSubmissionPolicyCatalog(project).resolve()
    recorded_evaluation_service = RecordedRunEvaluationService(
        project_root=project,
        product_store=store,
        evaluation_store=evaluation_store,
        artifact_root=artifact_root,
        runtime_bindings=AgentRuntimeBindingCatalog(project),
        artifact_service=artifact_service,
    )
    evaluation_suite_service = EvaluationSuiteService(
        project_root=project,
        recorded_run_service=recorded_evaluation_service,
        evaluation_store=evaluation_store,
    )
    operations_service = OperationsSnapshotService(
        product_store=store,
        evaluation_store=evaluation_store,
        tool_approval_store=tool_approval_store,
        agent_catalog=definitions,
        evaluation_catalog=evaluation_catalog,
        evaluation_suite_catalog=evaluation_suite_catalog,
        mcp_catalog=mcp_catalog,
        reference_catalog=reference_catalog,
    )
    native_stream_broker = native_stream_broker or InMemoryNativeSDKStreamBroker()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog((definitions).project_root),
        definitions=definitions,
        store=store,
        gateway=gateway
        or OpenAIGenericAgentGateway(
            native_stream_broker=native_stream_broker,
            readonly_workspace_root=(
                str(Path(readonly_workspace_root).expanduser().resolve())
                if readonly_workspace_root is not None
                else None
            ),
            sandbox_readonly_image=(sandbox_readonly_image.strip() if sandbox_readonly_image else None),
            sandbox_temporary_parent=(
                str(Path(sandbox_temporary_parent).expanduser().resolve())
                if sandbox_temporary_parent is not None
                else None
            ),
        ),
        artifact_root=artifact_root,
        session_runtime=session_runtime,
        artifact_service=artifact_service,
    )
    coordinator = LocalExecutionCoordinator(service=service, store=store)
    auth = LocalAdminAuthenticator(admin_key)
    submitter_auth = LocalRunSubmitterAuthenticator(run_submitter_key, admin_key=admin_key)
    service_client_registry = (
        ServiceClientTokenRegistry.from_json_text(service_client_token_registry_json)
        if service_client_token_registry_json is not None and service_client_token_registry_json.strip()
        else None
    )
    service_client_auth = ServiceClientAuthenticator(service_client_registry)
    governed_boundary = None
    governed_execution = None
    governed_lifecycle = None
    payload_store = None
    attachment_store = None
    project_snapshot_store = None
    tool_approval_service = None
    commerce_snapshot_ingress = None
    configured_values = (run_submitter_key, protected_payload_root, protected_payload_key)
    if any(value is not None for value in configured_values):
        if not all(value is not None for value in configured_values):
            raise ValueError(
                "Run submitter key, protected payload root, and protected payload key must be configured together"
            )
        assert protected_payload_root is not None and protected_payload_key is not None
        resolved_protected_payload_key = ProtectedPayloadKey.from_text(protected_payload_key)
        if (
            resolved_session_history_key is not None
            and hmac.compare_digest(
                resolved_session_history_key._raw, resolved_protected_payload_key._raw
            )
        ):
            raise SessionConfigurationError(
                "Session history encryption key must be distinct from the protected payload key"
            )
        if (
            resolved_session_history_previous_key is not None
            and hmac.compare_digest(
                resolved_session_history_previous_key._raw, resolved_protected_payload_key._raw
            )
        ):
            raise SessionConfigurationError(
                "Previous Session history key must be distinct from the protected payload key"
            )
        payload_store = EncryptedFileProtectedPayloadStore(
            protected_payload_root, resolved_protected_payload_key
        )
        payload_store.initialize()
        attachment_policy = LocalAttachmentPolicyCatalog(project).resolve()
        attachment_store = EncryptedLocalAttachmentStore(
            Path(protected_payload_root).expanduser().resolve().parent / "protected-attachments",
            resolved_protected_payload_key,
            attachment_policy,
        )
        attachment_store.initialize()
        project_snapshot_policy = ProjectSnapshotPolicyCatalog(project).resolve()
        project_snapshot_store = EncryptedProjectSnapshotStore(
            Path(protected_payload_root).expanduser().resolve().parent / "protected-project-snapshots",
            resolved_protected_payload_key,
            project_snapshot_policy,
        )
        project_snapshot_store.initialize()
        lifecycle_policy = GovernedLifecyclePolicyCatalog(project).resolve()
        governed_boundary = RunSubmissionBoundaryService(
            runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
            project_root=str(project),
            store=submission_store,
            protected_payload_store=payload_store,
            lifecycle_policy=lifecycle_policy,
            session_runtime=session_runtime,
            attachment_store=attachment_store,
            project_snapshot_store=project_snapshot_store,
        )
        governed_lifecycle = GovernedExecutionLifecycleService(
            submission_store=submission_store,
            product_store=store,
            payload_store=payload_store,
            policy=lifecycle_policy,
            attachment_store=attachment_store,
            project_snapshot_store=project_snapshot_store,
        )
        coordinator.set_completion_observer(governed_lifecycle.observe_run_completion)
        governed_execution = GovernedReadOnlyRunSubmissionService(
            runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
            project_root=str(project),
            store=submission_store,
            protected_payload_store=payload_store,
            admission_store=governed_admission,
            execution_service=service,
            scheduler=coordinator,
            lifecycle_policy=lifecycle_policy,
            attachment_store=attachment_store,
            project_snapshot_store=project_snapshot_store,
        )
        commerce_snapshot_ingress = GovernedCommerceSnapshotIngressService(
            project_root=str(project),
            boundary=governed_boundary,
            store=submission_store,
            environment=commerce_snapshot_environment,
            transport=commerce_snapshot_http_transport,
        )
        run_states = EncryptedRunStateStore(
            run_state_root or (Path(protected_payload_root).expanduser().resolve().parent / "run-states"),
            payload_store.key,
        )
        run_states.initialize()
        tool_approval_service = GovernedLocalToolApprovalService(
            runtime_bindings=AgentRuntimeBindingCatalog(project),
            project_root=project,
            submission_store=submission_store,
            admission_store=governed_admission,
            product_store=store,
            payload_store=payload_store,
            run_state_store=run_states,
            approval_store=tool_approval_store,
            artifact_root=artifact_root,
            lifecycle_service=governed_lifecycle,
            session_runtime=session_runtime,
            gateway=tool_approval_gateway or OpenAILocalToolApprovalGateway(),
            artifact_service=artifact_service,
        )

    app = FastAPI(
        title="OKCanvas Agent Runtime Control API",
        version=PROJECT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.product_store = store
    app.state.execution_coordinator = coordinator
    app.state.evaluation_store = evaluation_store
    app.state.recorded_run_evaluation_service = recorded_evaluation_service
    app.state.evaluation_suite_service = evaluation_suite_service
    app.state.operations_snapshot_service = operations_service
    app.state.run_submission_policy = run_submission_policy
    app.state.storage_topology = topology
    app.state.artifact_blob_store = topology.artifact_blob_store
    app.state.artifact_service = artifact_service
    app.state.run_submission_store = submission_store
    app.state.governed_run_admission = governed_admission
    app.state.governed_submission_boundary = governed_boundary
    app.state.governed_submission_execution = governed_execution
    app.state.governed_execution_lifecycle = governed_lifecycle
    app.state.protected_payload_store = payload_store
    app.state.local_attachment_store = attachment_store
    app.state.project_snapshot_store = project_snapshot_store
    app.state.tool_approval_store = tool_approval_store
    app.state.tool_approval_service = tool_approval_service
    app.state.commerce_snapshot_ingress_service = commerce_snapshot_ingress
    app.state.run_submitter_configured = submitter_auth.configured
    app.state.direct_run_submission_enabled = direct_run_submission_enabled
    app.state.native_sdk_stream_broker = native_stream_broker
    app.state.session_runtime = session_runtime
    app.state.session_policy = session_policy
    app.state.session_key_rotation_policy = session_key_rotation_policy
    app.state.service_client_authenticator = service_client_auth
    app.state.service_resource_ownership = service_resource_ownership
    app.state.service_client_auth_configured = service_client_auth.configured

    service_use_cases = ServiceUseCases(
        ownership=service_resource_ownership,
        definitions=definitions,
        runtime_bindings=AgentRuntimeBindingCatalog(project),
        session_runtime=session_runtime,
        attachment_store=attachment_store,
        project_snapshot_store=project_snapshot_store,
        governed_boundary=governed_boundary,
        governed_execution=governed_execution,
        submission_store=submission_store,
        run_submission_policy=run_submission_policy,
        tool_approval_service=tool_approval_service,
        tool_approval_store=tool_approval_store,
        product_store=store,
        coordinator=coordinator,
        artifact_root=artifact_root,
        sandbox_catalog=SandboxRuntimeCatalog(project),
        organization_catalog_root=organization_catalog_root,
        artifact_service=artifact_service,
    )
    app.state.service_use_cases = service_use_cases
    include_router_exact(
        app,
        build_service_client_router(
            authenticator=service_client_auth, use_cases=service_use_cases
        ),
        owner="service",
    )

    console_assets = CLIENTS_PACKAGE_ROOT / "dev_console" / "assets"
    app.mount("/console/assets", StaticFiles(directory=console_assets), name="operations-console-assets")

    @app.get("/console", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/console/", response_class=HTMLResponse, include_in_schema=False)
    async def operations_console() -> HTMLResponse:
        html = (console_assets / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self'; object-src 'none'; "
                    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                ),
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    runner_assets = CLIENTS_PACKAGE_ROOT / "dev_runner" / "assets"
    app.mount("/runner/assets", StaticFiles(directory=runner_assets), name="interactive-runner-assets")

    @app.get("/runner", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/runner/", response_class=HTMLResponse, include_in_schema=False)
    async def interactive_runner() -> HTMLResponse:
        html = (runner_assets / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self'; object-src 'none'; "
                    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                ),
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.exception_handler(ControlAPIError)
    async def control_error_handler(_request: Request, exc: ControlAPIError) -> JSONResponse:
        body = ErrorBody(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"location": [str(part) for part in item.get("loc", ())], "type": item.get("type")}
            for item in exc.errors()
        ]
        body = ErrorBody(
            code="REQUEST_VALIDATION_FAILED",
            message="Request validation failed",
            details={"errors": errors},
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.get("/healthz")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": "multi-user-server-runtime",
            "version": PROJECT_VERSION,
            "service_client_api": "/v1/service",
            "service_client_auth_configured": service_client_auth.configured,
            "development_harnesses_enabled": True,
        }

    admin_use_cases = AdminUseCases(
        operations_service=operations_service,
        store=store,
        walking_skeleton_catalog=walking_skeleton_catalog,
        definitions=definitions,
        evaluation_catalog=evaluation_catalog,
        evaluation_store=evaluation_store,
        recorded_evaluation_service=recorded_evaluation_service,
        evaluation_suite_catalog=evaluation_suite_catalog,
        evaluation_suite_service=evaluation_suite_service,
        session_runtime=session_runtime,
        runtime_bindings=AgentRuntimeBindingCatalog(project),
        run_submission_policy=run_submission_policy,
        attachment_store=attachment_store,
        governed_boundary=governed_boundary,
        commerce_snapshot_ingress=commerce_snapshot_ingress,
        submission_store=submission_store,
        governed_execution=governed_execution,
        tool_approval_service=tool_approval_service,
        tool_approval_store=tool_approval_store,
        governed_lifecycle=governed_lifecycle,
        direct_run_submission_enabled=direct_run_submission_enabled,
        coordinator=coordinator,
        artifact_root=artifact_root,
        native_stream_broker=native_stream_broker,
        organization_catalog_root=organization_catalog_root,
        artifact_service=artifact_service,
    )
    app.state.admin_use_cases = admin_use_cases
    include_router_exact(
        app,
        build_admin_router(
            context=AdminRouteContext(
                auth=auth,
                submitter_auth=submitter_auth,
                use_cases=admin_use_cases,
            )
        ),
        owner="admin",
    )


    return app


def _object_storage_client_from_environment(environment: Mapping[str, str]):
    backend = environment.get(
        "OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND", "local-filesystem-artifact-v1"
    ).strip().lower()
    if backend != "object-storage-artifact-v1":
        return None
    return Boto3S3CompatibleObjectStorageClient(
        S3CompatibleClientSettings(
            endpoint_url=environment.get("OKCANVAS_ARTIFACT_OBJECT_ENDPOINT_URL"),
            region_name=environment.get("OKCANVAS_ARTIFACT_OBJECT_REGION"),
            addressing_style=environment.get(
                "OKCANVAS_ARTIFACT_OBJECT_ADDRESSING_STYLE", "auto"
            ),
        )
    )


def app_from_environment() -> FastAPI:
    admin_key = os.environ.get("OKCANVAS_CONTROL_ADMIN_KEY", "")
    if not admin_key:
        raise RuntimeError("OKCANVAS_CONTROL_ADMIN_KEY is required")
    submitter_key = os.environ.get("OKCANVAS_RUN_SUBMITTER_KEY")
    payload_key = os.environ.get("OKCANVAS_PROTECTED_PAYLOAD_KEY")
    payload_root = (
        os.environ.get("OKCANVAS_PROTECTED_PAYLOAD_ROOT", ".local/protected-payloads")
        if submitter_key is not None or payload_key is not None
        else None
    )
    return create_app(
        project_root=os.environ.get("OKCANVAS_PROJECT_ROOT", "."),
        product_db=os.environ.get("OKCANVAS_PRODUCT_DB", ".local/product.sqlite3"),
        artifact_root=os.environ.get("OKCANVAS_ARTIFACT_ROOT", ".local/artifacts"),
        evaluation_db=os.environ.get("OKCANVAS_EVALUATION_DB", ".local/evaluation.sqlite3"),
        admin_key=admin_key,
        direct_run_submission_enabled=os.environ.get(
            "OKCANVAS_DIRECT_RUN_API_ENABLED", ""
        ).strip().lower() in {"1", "true", "yes", "on"},
        run_submitter_key=submitter_key,
        protected_payload_root=payload_root,
        protected_payload_key=payload_key,
        run_state_root=os.environ.get("OKCANVAS_RUN_STATE_ROOT"),
        session_root=os.environ.get("OKCANVAS_SESSION_ROOT", ".local/sessions"),
        session_history_key=os.environ.get("OKCANVAS_SESSION_HISTORY_KEY"),
        session_history_previous_key=os.environ.get("OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY"),
        readonly_workspace_root=os.environ.get("OKCANVAS_READONLY_WORKSPACE_ROOT"),
        sandbox_readonly_image=os.environ.get("OKCANVAS_SANDBOX_READONLY_IMAGE"),
        sandbox_temporary_parent=os.environ.get("OKCANVAS_SANDBOX_TEMP_ROOT"),
        service_client_token_registry_json=os.environ.get(
            "OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON"
        ),
        product_store_backend=os.environ.get(
            "OKCANVAS_PRODUCT_STORE_BACKEND", "sqlite-local-v1"
        ),
        postgresql_dsn=os.environ.get("OKCANVAS_POSTGRESQL_DSN"),
        artifact_blob_store_backend=os.environ.get(
            "OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND", "local-filesystem-artifact-v1"
        ),
        object_storage_bucket=os.environ.get("OKCANVAS_ARTIFACT_OBJECT_BUCKET"),
        object_storage_prefix=os.environ.get(
            "OKCANVAS_ARTIFACT_OBJECT_PREFIX", "okcanvas-artifacts"
        ),
        object_storage_client=_object_storage_client_from_environment(os.environ),
    )
