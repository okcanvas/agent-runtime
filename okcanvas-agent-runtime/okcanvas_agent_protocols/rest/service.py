from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from okcanvas_agent_protocols.rest.admin import StrictModel


class ServiceCapabilitiesResponse(StrictModel):
    schema_version: Literal["okcanvas-service-client-capabilities-v1"] = (
        "okcanvas-service-client-capabilities-v1"
    )
    runtime_version: str
    service_api_version: Literal["v1"] = "v1"
    multi_user_resource_scoping: Literal[True] = True
    authentication: Literal["bearer-sha256-registry-v1"] = "bearer-sha256-registry-v1"
    supported_clients: list[Literal["agent-cli", "agent-web", "agent-desktop"]]
    durable_event_stream: Literal["persisted-sse-last-event-id"] = "persisted-sse-last-event-id"
    native_sdk_stream_exposed_to_service_clients: Literal[False] = False
    runtime_internal_storage_access_allowed: Literal[False] = False
    development_harnesses: list[str]
    service_resources: list[str]
    run_submission_configured: bool
    local_attachment_ingress_configured: bool
    local_attachment_limits: dict[str, Any]
    project_snapshot_ingress_configured: bool
    project_snapshot_limits: dict[str, Any]
    project_snapshot_api: str | None
    skills_available: bool
    skill_catalog_api: str | None
    skill_foundation_step: str
    next_skill_step: str | None
    sandbox_runtime_foundation_available: bool
    sandbox_execution_enabled: bool
    sandbox_provider_lifecycle_enabled: bool
    sandbox_runtime_api: str | None
    sandbox_foundation_step: str
    capability_topology_available: bool
    capability_foundation_schema: str
    capability_topology_schema: str
    capability_agent_topology_count: int
    capability_binding_count: int
    capability_families: list[str]
    capability_discovery_policy_id: str
    capability_discovery_policy_version: str
    capability_discovery_policy_sha256: str
    capability_tool_search_structure_ready: bool
    capability_tool_search_runtime_enabled: bool
    capability_programmatic_tool_calling_structure_ready: bool
    capability_programmatic_tool_calling_runtime_enabled: bool
    capability_sdk_example_inventory_version: str
    capability_sdk_example_inventory_count: int
    capability_sdk_example_inventory_sha256: str
    capability_topology_root_sha256: str
    architecture_constitution_integrated: bool
    architecture_constitution_id: str
    architecture_constitution_version: str
    architecture_constitution_authority_state: str
    architecture_constitution_sha256: str
    architecture_constitution_clause_count: int
    architecture_constitution_required_gate_count: int
    architecture_constitution_source_movement_allowed: bool
    architecture_step_compliance_gate_implemented: bool
    organization_assistant_routing_available: bool
    organization_assistant_route_api: str
    organization_assistant_preflight_api: str
    organization_assistant_session_api: str
    organization_assistant_policy_id: str
    organization_assistant_policy_version: str
    organization_assistant_policy_sha256: str
    organization_assistant_default_agent_id: str
    organization_assistant_session_agent_id: str
    organization_assistant_unconfigured_capabilities: list[str]
    organization_context_remote_read_state: Literal["NOT_CONFIGURED", "READY", "ACCESS_DENIED"]
    organization_context_remote_endpoint_configured: bool
    organization_context_remote_credential_reference_configured: bool
    organization_context_remote_credential_value_configured: bool
    organization_context_remote_identity_bound: bool
    organization_context_remote_role_allowed: bool
    organization_context_remote_executable_now: bool
    organization_context_foundation_available: bool
    organization_context_catalog_id: str
    organization_context_catalog_version: str
    organization_context_catalog_state: Literal["EMPTY", "READY"]
    organization_context_effective_at: str
    organization_context_record_count: int
    organization_glossary_record_count: int
    organization_knowledge_record_count: int
    organization_directory_record_count: int
    organization_glossary_api: str
    organization_knowledge_api: str
    organization_directory_api: str
    multi_mcp_foundation_available: bool
    multi_mcp_max_remote_servers: int
    delegated_mcp_identity_foundation_available: bool
    mcp_access_policy_id: str
    mcp_access_policy_version: str
    mcp_access_policy_sha256: str
    mcp_credential_reference_count: int
    mcp_active_remote_server_count: int
    mcp_active_delegated_server_count: int
    mcp_health_mode: str
    mcp_circuit_breaker_scope: str
    mcp_write_enabled: bool
    groupware_read_foundation_available: bool
    groupware_read_policy_id: str
    groupware_read_policy_version: str
    groupware_read_policy_sha256: str
    groupware_read_agent_id: str
    groupware_read_server_id: str
    groupware_read_allowed_tools: list[str]
    groupware_read_state: Literal["NOT_CONFIGURED", "READY", "ACCESS_DENIED"]
    groupware_read_endpoint_configured: bool
    groupware_read_credential_reference_configured: bool
    groupware_read_credential_value_configured: bool
    groupware_read_identity_bound: bool
    groupware_read_role_allowed: bool
    groupware_read_executable_now: bool
    groupware_write_enabled: bool
    next_selected_step: str


class ProjectSnapshotUploadResponse(StrictModel):
    schema_version: Literal["okcanvas-project-snapshot-record-v1"] = (
        "okcanvas-project-snapshot-record-v1"
    )
    project_snapshot_id: str
    state: Literal["UPLOADED"]
    filename: str
    archive_sha256: str
    archive_byte_length: int
    snapshot_sha256: str
    file_count: int
    total_bytes: int
    expires_at: str
    raw_archive_persisted_in_events: Literal[False]
    raw_archive_persisted_in_artifacts: Literal[False]


class ServiceSandboxRuntimeResponse(StrictModel):
    schema_version: Literal["okcanvas-service-sandbox-runtime-v1"] = (
        "okcanvas-service-sandbox-runtime-v1"
    )
    policy_id: str
    policy_version: str
    policy_sha256: str
    foundation_sha256: str
    foundation_enabled: bool
    execution_enabled: bool
    agent_execution_enabled: bool
    provider_lifecycle_enabled: bool
    default_workspace_access: str
    declared_workspace_access_modes: list[str]
    active_workspace_access_modes: list[str]
    physical_workspace_materialization_enabled: bool
    docker_runtime_calls_enabled: bool
    network_mode: str
    exposed_ports: list[int]
    host_bind_mounts_enabled: bool
    remote_mounts_enabled: bool
    secrets_enabled: bool
    automatic_image_pull_enabled: bool
    automatic_resume_enabled: bool
    snapshot_resume_enabled: bool
    shell_enabled: bool
    apply_patch_enabled: bool
    skill_materialization_enabled: bool
    model_selected_provider_enabled: bool
    model_selected_host_path_enabled: bool
    sdk_default_capabilities_allowed: bool
    provider_id: str
    provider_version: str
    provider_contract_sha256: str
    provider_kind: str
    provider_implementation_mode: str
    provider_execution_enabled: bool
    provider_container_lifecycle_enabled: bool
    provider_image_reference_mode: str
    provider_runtime_image_pull_enabled: bool
    provider_command_mode: str
    provider_container_environment_enabled: bool
    provider_workspace_materialization_mode: str
    provider_workspace_archive_format: str
    provider_workspace_materializer_user: str
    provider_workspace_materializer_command: list[str]
    provider_workspace_mount_path: str
    provider_workspace_tmpfs_max_bytes: int
    provider_workspace_max_files: int
    provider_workspace_max_total_bytes: int
    provider_workspace_max_file_bytes: int
    provider_workspace_allowed_commands: list[str]
    provider_docker_socket_mount_enabled: bool
    provider_privileged: bool
    provider_required_cap_drop: list[str]
    provider_no_new_privileges_required: bool
    provider_read_only_root_filesystem_required: bool
    provider_non_root_user_required: bool
    provider_non_root_user: str
    provider_memory_limit_bytes: int
    provider_nano_cpus: int
    provider_pids_limit: int
    provider_command_timeout_seconds: int
    provider_stop_timeout_seconds: int
    provider_max_captured_output_bytes: int
    provider_required_labels: list[str]
    provider_automatic_delete_required: bool
    provider_orphan_reconciliation_required: bool


class ServiceWhoAmIResponse(StrictModel):
    schema_version: Literal["okcanvas-service-principal-v1"] = "okcanvas-service-principal-v1"
    token_id: str
    tenant_id: str
    principal_id: str
    roles: list[str]


class ServiceArtifactSummaryResponse(StrictModel):
    schema_version: Literal["okcanvas-service-artifact-summary-v1"] = (
        "okcanvas-service-artifact-summary-v1"
    )
    artifact_id: str
    run_id: str
    artifact_type: str
    media_type: str
    sha256: str
    byte_length: int
    created_at: str
    verified_at: str | None


class ServiceArtifactListResponse(StrictModel):
    schema_version: Literal["okcanvas-service-artifact-list-v1"] = (
        "okcanvas-service-artifact-list-v1"
    )
    run_id: str
    total: int
    artifacts: list[ServiceArtifactSummaryResponse]


class ServiceErrorContractResponse(StrictModel):
    schema_version: Literal["okcanvas-service-error-contract-v1"] = (
        "okcanvas-service-error-contract-v1"
    )
    error_schema_version: Literal["okcanvas-control-error-v1"] = "okcanvas-control-error-v1"
    retryable_is_explicit: Literal[True] = True
    resource_non_disclosure_status: Literal[404] = 404
    cursor_header: Literal["Last-Event-ID"] = "Last-Event-ID"
    notes: list[str] = Field(default_factory=list)


class ServiceSubmissionListResponse(StrictModel):
    schema_version: Literal["okcanvas-service-submission-list-v1"] = (
        "okcanvas-service-submission-list-v1"
    )
    total: int
    submissions: list[dict[str, Any]]


class ServiceSkillResourceResponse(StrictModel):
    path: str
    media_type: str
    sha256: str
    byte_length: int


class ServiceSkillResponse(StrictModel):
    schema_version: Literal["okcanvas-service-skill-v1"] = "okcanvas-service-skill-v1"
    skill_id: str
    version: str
    name: str
    description: str
    execution_mode: str
    resources: list[ServiceSkillResourceResponse]
    allowed_agent_ids: list[str]
    allowed_input_modes: list[str]
    allowed_output_contracts: list[str]
    required_tools: list[str]
    required_mcp_servers: list[str]
    required_hosted_tools: list[str]
    workspace_access: str
    instructions_sha256: str
    instructions_byte_length: int
    manifest_sha256: str
    package_sha256: str
    executable_code_included: Literal[False] = False
    dynamic_dependency_installation: Literal[False] = False
    client_side_execution: Literal[False] = False


class ServiceSkillListResponse(StrictModel):
    schema_version: Literal["okcanvas-service-skill-list-v1"] = "okcanvas-service-skill-list-v1"
    total: int
    skills: list[ServiceSkillResponse]
