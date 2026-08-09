from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")






class CreateSessionRequest(StrictModel):
    agent_definition_id: str = Field(min_length=1, max_length=128)


class ProductSessionResponse(StrictModel):
    schema_version: Literal["okcanvas-product-session-v2"] = "okcanvas-product-session-v2"
    session_id: str
    state: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    history_encryption_key_id: str | None
    active_run_id: str | None
    turn_count: int
    item_count: int
    created_at: str
    updated_at: str
    cleared_at: str | None


class ProductSessionListResponse(StrictModel):
    schema_version: Literal["okcanvas-product-session-list-v1"] = "okcanvas-product-session-list-v1"
    total: int
    sessions: list[ProductSessionResponse]


class SessionKeyRotationResponse(StrictModel):
    schema_version: Literal["okcanvas-session-key-rotation-result-v1"] = (
        "okcanvas-session-key-rotation-result-v1"
    )
    session_id: str
    operation_id: str | None
    source_key_id: str
    target_key_id: str
    item_count: int
    resumed: bool
    already_current: bool
    state: Literal["COMPLETED"]


class RunSubmissionPolicyResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-submission-policy-v1"] = (
        "okcanvas-control-run-submission-policy-v1"
    )
    policy_id: str
    version: str
    authority_scope: str
    idempotency_required: bool
    idempotency_key_min_length: int
    idempotency_key_max_length: int
    input_max_chars: int
    confirmation_mode: str
    read_only_execution_mode: str
    local_tool_execution_mode: str
    write_mcp_execution_mode: str
    handoff_or_session_execution_mode: str
    protected_payload_mode: str
    direct_run_api_default_enabled: bool
    console_mutation_enabled: bool
    policy_sha256: str




class LocalAttachmentUploadResponse(StrictModel):
    schema_version: Literal["okcanvas-local-attachment-record-v1"] = (
        "okcanvas-local-attachment-record-v1"
    )
    attachment_id: str
    state: Literal["UPLOADED"]
    filename: str
    media_type: str
    input_kind: Literal["input_file", "input_image"]
    content_sha256: str
    byte_length: int
    page_count: int | None
    width: int | None
    height: int | None
    expires_at: str
    raw_bytes_persisted_in_events: bool
    raw_bytes_persisted_in_artifacts: bool


class GovernedRunPreflightRequest(StrictModel):
    agent_definition_id: str = Field(min_length=1, max_length=128)
    input: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^session_[0-9a-f]{32}$")
    attachment_id: str | None = Field(
        default=None,
        pattern=r"^attachment_slot_[0-9a-f]{32}$",
    )
    project_snapshot_id: str | None = Field(
        default=None,
        pattern=r"^project_snapshot_slot_[0-9a-f]{32}$",
    )
    idempotency_key: str = Field(min_length=16, max_length=128)


class AssistantRouteRequest(StrictModel):
    input: str = Field(min_length=1, max_length=100_000)
    session_id: str | None = Field(default=None, pattern=r"^session_[0-9a-f]{32}$")
    attachment_id: str | None = Field(default=None, pattern=r"^attachment_slot_[0-9a-f]{32}$")
    project_snapshot_id: str | None = Field(default=None, pattern=r"^project_snapshot_slot_[0-9a-f]{32}$")


class AssistantRunPreflightRequest(StrictModel):
    input: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, pattern=r"^session_[0-9a-f]{32}$")
    attachment_id: str | None = Field(default=None, pattern=r"^attachment_slot_[0-9a-f]{32}$")
    project_snapshot_id: str | None = Field(default=None, pattern=r"^project_snapshot_slot_[0-9a-f]{32}$")
    idempotency_key: str = Field(min_length=16, max_length=128)


class GovernedCommerceSnapshotPreflightRequest(StrictModel):
    source_adapter_id: str = Field(min_length=1, max_length=64)
    snapshot_key: str = Field(min_length=1, max_length=128)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=16, max_length=128)


class RunSubmissionResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-submission-v1"] = (
        "okcanvas-control-run-submission-v1"
    )
    submission_id: str
    state: str
    execution_mode: str
    policy_id: str
    policy_version: str
    policy_sha256: str
    authority_scope: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    session_id: str | None
    model: str | None
    input_sha256: str
    request_fingerprint_sha256: str
    idempotency_key_sha256: str
    source_adapter_id: str | None
    source_adapter_version: str | None
    source_adapter_definition_sha256: str | None
    source_request_sha256: str | None
    source_snapshot_sha256: str | None
    source_acquired_at: str | None
    project_snapshot_sha256: str | None
    project_snapshot_archive_sha256: str | None
    project_snapshot_file_count: int | None
    project_snapshot_total_bytes: int | None
    confirmation_challenge: str | None
    approval_required: bool
    executable_now: bool
    protected_payload_persisted: bool
    protected_payload_ref: str | None
    protected_payload_sha256: str | None
    protected_payload_key_id: str | None
    protected_payload_byte_length: int | None
    task_id: str | None
    run_id: str | None
    confirmed_at: str | None
    payload_consumed_at: str | None
    scheduled_at: str | None
    claim_owner_id: str | None
    claim_acquired_at: str | None
    claim_expires_at: str | None
    claim_attempts: int
    recovery_count: int
    last_recovered_at: str | None
    execution_started_at: str | None
    execution_completed_at: str | None
    payload_retention_state: str
    payload_delete_after: str | None
    payload_deleted_at: str | None
    payload_retention_reason: str | None
    reasons: list[str]
    created_at: str
    replayed: bool


class OrganizationContextQueryRequest(StrictModel):
    query: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=10, ge=1, le=20)
    tenant_id: str | None = Field(default=None, min_length=2, max_length=128)
    principal_id: str | None = Field(default=None, min_length=2, max_length=128)
    roles: list[str] = Field(default_factory=list, max_length=50)


class OrganizationContextMatchResponse(StrictModel):
    kind: Literal["GLOSSARY", "KNOWLEDGE", "DIRECTORY_UNIT", "DIRECTORY_PERSON"]
    record_id: str
    label: str
    summary: str
    source_title: str
    source_version: str
    source_reference: str
    classification: str
    match_type: str
    score: int = Field(ge=1, le=100)


class OrganizationContextQueryResponse(StrictModel):
    schema_version: Literal["okcanvas-organization-context-query-v1"] = (
        "okcanvas-organization-context-query-v1"
    )
    catalog_id: str
    catalog_version: str
    effective_at: str
    catalog_state: Literal["EMPTY", "READY"]
    query_kind: Literal["GLOSSARY", "KNOWLEDGE", "DIRECTORY", "COMBINED"]
    query_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authoritative_match_found: bool
    ambiguous: bool
    filtered_count: int = Field(ge=0)
    matches: list[OrganizationContextMatchResponse]


class AssistantCapabilityRequirementResponse(StrictModel):
    capability_id: str
    availability: Literal["AVAILABLE", "NOT_CONFIGURED", "DISABLED"]
    selected_agent_id: str | None
    side_effect: str


class OrganizationContextRelationTraversalHintResponse(StrictModel):
    schema_version: Literal["okcanvas-organization-context-relation-traversal-hint-v1"] = (
        "okcanvas-organization-context-relation-traversal-hint-v1"
    )
    source_entity_type: str
    source_entity_id: str
    relation_type: str
    direction: Literal["OUTBOUND", "INBOUND"]
    result_entity_types: list[str]
    max_results: int = Field(ge=1, le=20)


class OrganizationContextRequestHintResponse(StrictModel):
    schema_version: Literal["okcanvas-organization-context-request-hint-v1"] = (
        "okcanvas-organization-context-request-hint-v1"
    )
    pattern_id: str
    intent: str
    target_expression: str
    entity_type_hints: list[str]
    requested_fields: list[str]
    preferred_operation: Literal["RESOLVE", "SEARCH", "GET"]
    relation_traversal: OrganizationContextRelationTraversalHintResponse | None = None


class GroupwareContextFilterHintResponse(StrictModel):
    schema_version: Literal["okcanvas-groupware-context-filter-hint-v1"] = (
        "okcanvas-groupware-context-filter-hint-v1"
    )
    pattern_id: str
    resource_kind: Literal["NOTICE", "MAIL", "CALENDAR"]
    tool_name: Literal["search_notices", "search_mail", "list_calendar_events"]
    entity_type: Literal["EMPLOYEE", "PROJECT", "CLIENT", "PRODUCT", "DEPARTMENT"]
    entity_id: str
    label: str
    qualifiers: list[str]
    catalog_revision: int | None = None
    max_results: int = Field(ge=1, le=20)


class GroundedInterpretationRouteShadowResponse(StrictModel):
    schema_version: Literal["okcanvas-assistant-route-v3"] = "okcanvas-assistant-route-v3"
    interpretation_mode: Literal["LLM_GROUNDED"] = "LLM_GROUNDED"
    request_class: None = None
    side_effect: None = None
    status: Literal["EXECUTABLE"] = "EXECUTABLE"
    selected_agent_definition_id: str
    executable_now: Literal[True] = True
    matched_rule_id: str
    reasons: list[str]
    authoritative: Literal[False] = False
    legacy_authoritative_route_schema: Literal["okcanvas-assistant-route-v2"] = (
        "okcanvas-assistant-route-v2"
    )


class AssistantRouteResponse(StrictModel):
    schema_version: Literal["okcanvas-assistant-route-v2"] = "okcanvas-assistant-route-v2"
    request_class: Literal[
        "ANSWER", "WRITE_CONTENT", "ANALYZE_ATTACHMENT", "CODE_ASSIST",
        "SEARCH_WEB", "SEARCH_KNOWLEDGE", "READ_SYSTEM", "DRAFT_ACTION",
        "WRITE_ACTION", "AUTOMATE", "CLARIFY", "REFUSE",
    ]
    side_effect: Literal[
        "NONE", "READ", "DRAFT", "WRITE_REVERSIBLE",
        "WRITE_IRREVERSIBLE", "AUTOMATION_DEFINITION",
    ]
    status: Literal["EXECUTABLE", "PROPOSAL_ONLY", "NOT_CONFIGURED", "NO_MATCH", "AMBIGUOUS"]
    selected_agent_definition_id: str | None
    executable_now: bool
    required_capabilities: list[AssistantCapabilityRequirementResponse]
    matched_rule_id: str
    reasons: list[str]
    policy_id: str
    policy_version: str
    policy_sha256: str
    grounding_state: Literal[
        "NOT_APPLICABLE", "NOT_CONFIGURED", "MATCHED", "NO_MATCH", "AMBIGUOUS"
    ]
    grounding_catalog_id: str | None
    grounding_catalog_version: str | None
    grounding_effective_at: str | None
    grounding: list[OrganizationContextMatchResponse]
    organization_context_request_hint: OrganizationContextRequestHintResponse | None = None
    groupware_context_filter: GroupwareContextFilterHintResponse | None = None
    grounded_interpretation_shadow: GroundedInterpretationRouteShadowResponse | None = None


class AssistantRunPreflightResponse(StrictModel):
    schema_version: Literal["okcanvas-assistant-run-preflight-v2"] = (
        "okcanvas-assistant-run-preflight-v2"
    )
    route: AssistantRouteResponse
    submission: RunSubmissionResponse | None


class GovernedRunConfirmRequest(StrictModel):
    confirmation: str = Field(min_length=1, max_length=256)


class GovernedRunSubmissionResponse(StrictModel):
    schema_version: Literal["okcanvas-governed-run-submission-v1"] = (
        "okcanvas-governed-run-submission-v1"
    )
    submission: RunSubmissionResponse
    task_id: str
    run_id: str
    scheduled: bool
    replayed: bool


class GovernedRecoveryResponse(StrictModel):
    schema_version: Literal["okcanvas-governed-recovery-result-v1"] = (
        "okcanvas-governed-recovery-result-v1"
    )
    scanned: int
    recovered: int
    skipped: int
    failed: int
    submission_ids: list[str]


class OrphanedRunReconciliationRequest(StrictModel):
    confirmation: Literal["RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART"]


class OrphanedRunReconciliationResponse(StrictModel):
    schema_version: Literal["okcanvas-orphaned-running-reconciliation-v1"] = (
        "okcanvas-orphaned-running-reconciliation-v1"
    )
    scanned: int
    reconciled: int
    skipped: int
    failed: int
    submission_ids: list[str]
    run_ids: list[str]


class TerminalOutcomeReconciliationRequest(StrictModel):
    confirmation: Literal[
        "RECONCILE_TERMINAL_RUN_OUTCOMES_AFTER_PROCESS_RESTART"
    ]


class TerminalOutcomeReconciliationResponse(StrictModel):
    schema_version: Literal["okcanvas-terminal-outcome-reconciliation-v1"] = (
        "okcanvas-terminal-outcome-reconciliation-v1"
    )
    scanned: int
    reconciled: int
    deleted: int
    retained: int
    skipped: int
    failed: int
    submission_ids: list[str]
    run_ids: list[str]


class ProtectedPayloadRetentionResponse(StrictModel):
    schema_version: Literal["okcanvas-protected-payload-retention-result-v1"] = (
        "okcanvas-protected-payload-retention-result-v1"
    )
    scanned: int
    deleted: int
    retained: int
    failed: int
    submission_ids: list[str]


class CreateRunRequest(StrictModel):
    agent_definition_id: str = Field(default="coding-agent", min_length=1, max_length=128)
    input: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    confirm_live_call: bool = False


class CreateRunResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-created-v1"] = (
        "okcanvas-control-run-created-v1"
    )
    task_id: str
    run_id: str
    task_status: str
    run_status: str


class EvaluateRecordedRunRequest(StrictModel):
    case_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")


class TaskResponse(StrictModel):
    schema_version: Literal["okcanvas-control-task-v1"] = "okcanvas-control-task-v1"
    task_id: str
    task_type: str
    status: str
    input_sha256: str
    agent_definition_id: str
    agent_definition_version: str
    created_at: str
    updated_at: str
    completed_at: str | None


class AgentInvocationResponse(StrictModel):
    schema_version: Literal["okcanvas-control-agent-invocation-v1"] = (
        "okcanvas-control-agent-invocation-v1"
    )
    invocation_id: str
    run_id: str
    root_invocation_id: str
    parent_invocation_id: str | None
    invocation_kind: str
    state: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    depth: int
    ordinal: int
    state_namespace: str
    workspace_access: str
    workspace_ref: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str
    started_at: str | None
    completed_at: str | None


class AgentInvocationListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-agent-invocation-list-v1"] = (
        "okcanvas-control-agent-invocation-list-v1"
    )
    run_id: str
    total: int
    invocations: list[AgentInvocationResponse]


class RunResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-v1"] = "okcanvas-control-run-v1"
    run_id: str
    task_id: str
    attempt: int
    status: str
    agent_definition_id: str
    agent_definition_version: str
    trace_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str
    started_at: str | None
    completed_at: str | None


class EventResponse(StrictModel):
    schema_version: Literal["okcanvas-control-event-v1"] = "okcanvas-control-event-v1"
    run_id: str
    sequence: int
    event_type: str
    source: str
    occurred_at: str
    payload_schema_version: str
    payload_sha256: str
    payload: dict[str, Any]


class EventListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-event-list-v1"] = (
        "okcanvas-control-event-list-v1"
    )
    run_id: str
    after_sequence: int
    events: list[EventResponse]


class RunArtifactResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-artifact-v1"] = (
        "okcanvas-control-run-artifact-v1"
    )
    artifact_id: str
    run_id: str
    artifact_type: str
    media_type: str
    sha256: str
    byte_length: int
    created_at: str
    verified_at: str | None
    content: dict[str, Any]


class CancelRunResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-cancelled-v1"] = (
        "okcanvas-control-run-cancelled-v1"
    )
    task_id: str
    run_id: str
    task_status: str
    run_status: str


class ErrorBody(StrictModel):
    schema_version: Literal["okcanvas-control-error-v1"] = "okcanvas-control-error-v1"
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)



class WalkingSkeletonScenarioResponse(StrictModel):
    schema_version: Literal["okcanvas-control-walking-skeleton-scenario-v1"] = (
        "okcanvas-control-walking-skeleton-scenario-v1"
    )
    scenario_id: str
    title: str
    summary: str
    agent_definition_id: str
    action_mode: str
    request_templates: list[str]
    evaluation_case_id: str | None
    expected_terminal_state: str
    expected_error_code: str | None
    requires_session: bool
    requires_approval_operator: bool
    capabilities: list[str]
    invocation_kinds: list[str]
    workspace_access: str


class WalkingSkeletonScenarioListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-walking-skeleton-scenario-list-v1"] = (
        "okcanvas-control-walking-skeleton-scenario-list-v1"
    )
    catalog_id: str
    version: str
    catalog_sha256: str
    skeleton_state: str
    scenarios: list[WalkingSkeletonScenarioResponse]


class AgentDefinitionSummaryResponse(StrictModel):
    schema_version: Literal["okcanvas-control-agent-definition-summary-v1"] = (
        "okcanvas-control-agent-definition-summary-v1"
    )
    agent_id: str
    version: str
    name: str
    output_contract: str
    tools: list[str]
    tool_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    mcp_servers: list[str]
    hosted_tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    handoffs: list[str]
    agent_tools: list[str]
    orchestration_children: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    guardrail_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    workspace_access: str
    max_turns: int
    workflow_name: str
    session_mode: str
    input_mode: str
    definition_sha256: str
    capability_topology: dict[str, Any]


class AgentDefinitionListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-agent-definition-list-v1"] = (
        "okcanvas-control-agent-definition-list-v1"
    )
    definitions: list[AgentDefinitionSummaryResponse]


class AgentDefinitionDetailResponse(AgentDefinitionSummaryResponse):
    schema_version: Literal["okcanvas-control-agent-definition-detail-v1"] = (
        "okcanvas-control-agent-definition-detail-v1"
    )
    instructions_sha256: str
    instructions_byte_length: int
    effective_instructions_sha256: str
    effective_instructions_byte_length: int
    output_schema: dict[str, Any]


class EvaluationCaseSummaryResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-case-summary-v1"] = (
        "okcanvas-control-evaluation-case-summary-v1"
    )
    case_id: str
    version: str
    agent_definition_id: str
    required_tools: list[str]
    forbidden_tools: list[str]
    max_total_tokens: int | None
    max_duration_ms: int | None
    manifest_sha256: str


class EvaluationCaseListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-case-list-v1"] = (
        "okcanvas-control-evaluation-case-list-v1"
    )
    cases: list[EvaluationCaseSummaryResponse]


class EvaluationCaseDetailResponse(EvaluationCaseSummaryResponse):
    schema_version: Literal["okcanvas-control-evaluation-case-detail-v1"] = (
        "okcanvas-control-evaluation-case-detail-v1"
    )
    required_result: dict[str, Any]
    forbidden_result: dict[str, Any]


class EvaluationResultResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-result-v1"] = (
        "okcanvas-control-evaluation-result-v1"
    )
    evaluation_id: str
    case_id: str
    case_version: str
    case_manifest_sha256: str
    subject_run_id: str
    subject_agent_definition_id: str
    subject_runtime_binding_sha256: str
    subject_model: str | None
    state: str
    checks: dict[str, bool]
    metrics: dict[str, int]
    failures: list[str]
    created_at: str


class EvaluationResultListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-result-list-v1"] = (
        "okcanvas-control-evaluation-result-list-v1"
    )
    total: int
    limit: int
    offset: int
    results: list[EvaluationResultResponse]


class EvaluationComparisonResponse(StrictModel):
    schema_version: Literal["okcanvas-evaluation-comparison-v1"] = (
        "okcanvas-evaluation-comparison-v1"
    )
    left_evaluation_id: str
    right_evaluation_id: str
    state_changed: bool
    token_delta: int
    duration_delta_ms: int
    tool_call_delta: int


class EvaluationSuiteSlotResponse(StrictModel):
    slot_id: str
    case_id: str
    required: bool


class EvaluationSuiteSummaryResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-suite-summary-v1"] = (
        "okcanvas-control-evaluation-suite-summary-v1"
    )
    suite_id: str
    version: str
    max_subjects: int
    slots: list[EvaluationSuiteSlotResponse]
    baseline_comparison: dict[str, int]
    manifest_sha256: str


class EvaluationSuiteListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-suite-list-v1"] = (
        "okcanvas-control-evaluation-suite-list-v1"
    )
    suites: list[EvaluationSuiteSummaryResponse]


class EvaluationSuiteSubjectRequest(StrictModel):
    subject_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")
    slot_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")
    run_id: str = Field(min_length=1, max_length=128)


class CreateEvaluationSuiteRunRequest(StrictModel):
    suite_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")
    subjects: list[EvaluationSuiteSubjectRequest] = Field(min_length=1, max_length=20)
    baseline_id: str | None = Field(default=None, min_length=1, max_length=128)


class EvaluationSuiteMemberResponse(StrictModel):
    suite_run_id: str
    subject_id: str
    slot_id: str
    case_id: str
    subject_run_id: str
    evaluation_id: str
    state: str
    metrics: dict[str, int]


class EvaluationSuiteRunResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-suite-run-v1"] = (
        "okcanvas-control-evaluation-suite-run-v1"
    )
    suite_run_id: str
    suite_id: str
    suite_version: str
    suite_manifest_sha256: str
    state: str
    comparison_state: str
    baseline_id: str | None
    subject_count: int
    evaluation_count: int
    aggregate: dict[str, int]
    regressions: list[dict[str, Any]]
    created_at: str
    members: list[EvaluationSuiteMemberResponse]


class CreateEvaluationBaselineRequest(StrictModel):
    source_suite_run_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=100)


class EvaluationBaselineMemberResponse(StrictModel):
    subject_id: str
    slot_id: str
    case_id: str
    state: str
    metrics: dict[str, int]


class EvaluationBaselineResponse(StrictModel):
    schema_version: Literal["okcanvas-control-evaluation-baseline-v1"] = (
        "okcanvas-control-evaluation-baseline-v1"
    )
    baseline_id: str
    suite_id: str
    suite_version: str
    suite_manifest_sha256: str
    source_suite_run_id: str
    label: str
    aggregate: dict[str, int]
    members: list[EvaluationBaselineMemberResponse]
    created_at: str


class TaskListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-task-list-v1"] = "okcanvas-control-task-list-v1"
    total: int
    limit: int
    offset: int
    tasks: list[TaskResponse]


class RunListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-run-list-v1"] = "okcanvas-control-run-list-v1"
    total: int
    limit: int
    offset: int
    runs: list[RunResponse]


class OperationsRuntimeResponse(StrictModel):
    project: str
    version: str
    step: str
    mode: str
    console_mode: Literal["read-only"]


class OperationsProductResponse(StrictModel):
    task_total: int
    task_status_counts: dict[str, int]
    run_total: int
    run_status_counts: dict[str, int]
    artifact_total: int


class OperationsMCPServerResponse(StrictModel):
    server_id: str
    version: str
    name: str
    read_only: bool
    allowed_tools: list[str]


class OperationsCatalogResponse(StrictModel):
    agent_definition_total: int
    evaluation_case_total: int
    evaluation_suite_total: int
    mcp_server_total: int
    mcp_servers: list[OperationsMCPServerResponse]


class OperationsEvaluationResponse(StrictModel):
    evaluation_total: int
    evaluation_states: dict[str, int]
    suite_run_total: int
    baseline_total: int


class OperationsApprovalResponse(StrictModel):
    approval_total: int
    pending_total: int
    approval_states: dict[str, int]


class OperationsReferenceItemResponse(StrictModel):
    reference_id: str
    expected_tree_sha256: str
    actual_tree_sha256: str
    expected_file_count: int
    actual_file_count: int
    expected_byte_count: int
    actual_byte_count: int
    verified: bool


class OperationsReferencesResponse(StrictModel):
    total: int
    verified: int
    items: list[OperationsReferenceItemResponse]


class OperationsSummaryResponse(StrictModel):
    schema_version: Literal["okcanvas-operations-summary-v1"] = "okcanvas-operations-summary-v1"
    runtime: OperationsRuntimeResponse
    product: OperationsProductResponse
    catalog: OperationsCatalogResponse
    evaluation: OperationsEvaluationResponse
    approvals: OperationsApprovalResponse
    references: OperationsReferencesResponse
    recent_runs: list[RunResponse]


class ToolApprovalInboxItemResponse(StrictModel):
    approval_id: str
    submission_id: str
    task_id: str
    run_id: str
    session_id: str | None = None
    state: str
    decision: str | None
    tool_name: str
    trace_id: str | None
    tool_execution_count: int
    created_at: str
    decided_at: str | None
    completed_at: str | None


class ToolApprovalListResponse(StrictModel):
    schema_version: Literal["okcanvas-control-tool-approval-list-v1"] = (
        "okcanvas-control-tool-approval-list-v1"
    )
    total: int
    limit: int
    offset: int
    approvals: list[ToolApprovalInboxItemResponse]


class ToolApprovalResponse(StrictModel):
    schema_version: Literal["okcanvas-control-tool-approval-v1"] = (
        "okcanvas-control-tool-approval-v1"
    )
    approval_id: str
    submission_id: str
    task_id: str
    run_id: str
    session_id: str | None = None
    session_item_count_before: int | None = None
    state: str
    decision: str | None
    tool_name: str
    tool_call_id_sha256: str
    arguments_sha256: str
    run_state_ref: str
    run_state_sha256: str
    run_state_byte_length: int
    run_state_key_id: str
    trace_id: str | None
    response_id: str | None
    tool_execution_count: int
    created_at: str
    decided_at: str | None
    completed_at: str | None


class ToolApprovalDecisionRequest(StrictModel):
    decision: Literal["APPROVE", "REJECT"]
    confirmation: str = Field(min_length=1, max_length=512)


class ToolApprovalResumeResponse(StrictModel):
    schema_version: Literal["okcanvas-control-tool-approval-resume-v1"] = (
        "okcanvas-control-tool-approval-resume-v1"
    )
    approval: ToolApprovalResponse
    task_id: str
    run_id: str
    state: str
    artifact_id: str | None
    tool_executed: bool
    replayed: bool
