from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from okcanvas_agent_runtime.core.replenishment_limits import JSON_SAFE_INTEGER_MAX, MAX_DERIVED_ITEM_UNIT_VALUE, MAX_INVENTORY_UNIT_VALUE


SCHEMA_VERSION = "okcanvas-agent-run-v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class FindingConfidence(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERENCE = "INFERENCE"


class FindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class CodingFinding(StrictModel):
    severity: FindingSeverity
    confidence: FindingConfidence
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=20)


class CodingAgentResult(StrictModel):
    status: AgentStatus
    summary: str = Field(min_length=1, max_length=4000)
    findings: list[CodingFinding] = Field(default_factory=list, max_length=100)
    unverified: list[str] = Field(default_factory=list, max_length=100)




class AssistantRequestClass(str, Enum):
    ANSWER = "ANSWER"
    WRITE_CONTENT = "WRITE_CONTENT"
    ANALYZE_ATTACHMENT = "ANALYZE_ATTACHMENT"
    CODE_ASSIST = "CODE_ASSIST"
    SEARCH_WEB = "SEARCH_WEB"
    SEARCH_KNOWLEDGE = "SEARCH_KNOWLEDGE"
    READ_SYSTEM = "READ_SYSTEM"
    DRAFT_ACTION = "DRAFT_ACTION"
    WRITE_ACTION = "WRITE_ACTION"
    AUTOMATE = "AUTOMATE"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"


class AssistantSideEffect(str, Enum):
    NONE = "NONE"
    READ = "READ"
    DRAFT = "DRAFT"
    WRITE_REVERSIBLE = "WRITE_REVERSIBLE"
    WRITE_IRREVERSIBLE = "WRITE_IRREVERSIBLE"
    AUTOMATION_DEFINITION = "AUTOMATION_DEFINITION"


class AssistantResultStatus(str, Enum):
    ANSWERED = "ANSWERED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    NEEDS_CAPABILITY = "NEEDS_CAPABILITY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REFUSED = "REFUSED"


class AssistantCitation(StrictModel):
    source_type: Literal[
        "USER_INPUT",
        "SESSION",
        "ATTACHMENT",
        "PROJECT_SNAPSHOT",
        "WEB",
        "ORGANIZATION_KNOWLEDGE",
        "ENTERPRISE_SYSTEM",
    ]
    label: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(default=None, max_length=500)


class AssistantActionSummary(StrictModel):
    capability_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1000)
    side_effect: AssistantSideEffect


class GroupwareReadStatus(str, Enum):
    ANSWERED = "ANSWERED"
    NEEDS_CAPABILITY = "NEEDS_CAPABILITY"
    REFUSED = "REFUSED"


class GroupwareReadCitation(StrictModel):
    source_type: Literal["ENTERPRISE_SYSTEM"] = "ENTERPRISE_SYSTEM"
    label: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(default=None, max_length=500)


class GroupwareReadResult(StrictModel):
    """Strict final output for the permanently read-only Groupware sub-agent.

    The contract intentionally has no action, approval, mutation, or automation fields.  It is
    narrower than ``OrganizationAssistantResult`` so a model cannot validate a write-shaped
    response merely because the instructions asked it not to.
    """

    schema_version: Literal["okcanvas-groupware-read-result-v1"] = (
        "okcanvas-groupware-read-result-v1"
    )
    status: GroupwareReadStatus
    answer: str = Field(min_length=1, max_length=8000)
    request_class: Literal["READ_SYSTEM"] = "READ_SYSTEM"
    side_effect: Literal["READ"] = "READ"
    queried_operations: list[Literal[
        "search_notices",
        "search_mail",
        "list_calendar_events",
    ]] = Field(default_factory=list, max_length=3)
    result_count: int = Field(default=0, ge=0, le=50)
    citations: list[GroupwareReadCitation] = Field(default_factory=list, max_length=30)
    unverified: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_read_only_contract(self) -> "GroupwareReadResult":
        if len(self.queried_operations) != len(set(self.queried_operations)):
            raise ValueError("queried_operations must be unique")
        if self.status is GroupwareReadStatus.ANSWERED:
            if not self.queried_operations:
                raise ValueError("Answered Groupware output must identify at least one read operation")
            if self.result_count > 0 and not self.citations:
                raise ValueError("Non-empty Groupware results require enterprise citations")
        else:
            if self.result_count != 0 or self.citations:
                raise ValueError("Capability-limited or refused output cannot claim Groupware records")
        if self.status is GroupwareReadStatus.NEEDS_CAPABILITY and not self.unverified:
            raise ValueError("Capability-limited Groupware output must identify the missing capability")
        return self


class OrganizationContextReadStatus(str, Enum):
    ANSWERED = "ANSWERED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NEEDS_CAPABILITY = "NEEDS_CAPABILITY"
    REFUSED = "REFUSED"


class OrganizationContextReadCitation(StrictModel):
    source_type: Literal["ORGANIZATION_KNOWLEDGE"] = "ORGANIZATION_KNOWLEDGE"
    label: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(default=None, max_length=500)


class OrganizationContextReadResult(StrictModel):
    """Strict final output for the external database-SOT Organization Context read Agent."""

    schema_version: Literal["okcanvas-organization-context-read-result-v1"] = (
        "okcanvas-organization-context-read-result-v1"
    )
    status: OrganizationContextReadStatus
    answer: str = Field(min_length=1, max_length=8000)
    request_class: Literal["SEARCH_KNOWLEDGE"] = "SEARCH_KNOWLEDGE"
    side_effect: Literal["READ"] = "READ"
    queried_operations: list[Literal[
        "resolve_organization_context",
        "search_organization_context",
        "get_organization_entity",
    ]] = Field(default_factory=list, max_length=3)
    result_count: int = Field(default=0, ge=0, le=50)
    catalog_revision: int | None = Field(default=None, ge=0)
    citations: list[OrganizationContextReadCitation] = Field(default_factory=list, max_length=30)
    unverified: list[str] = Field(default_factory=list, max_length=50)

    # Cross-field Organization Context semantics are intentionally enforced after the SDK Child
    # run from the actual observed MCP Tool result. Provider strict JSON Schema cannot encode these
    # rules, and running them during SDK output parsing can convert schema-valid ambiguity output
    # into an unrecoverable ModelBehaviorError before Product normalization.


class OrganizationAssistantResult(StrictModel):
    schema_version: Literal["okcanvas-organization-assistant-result-v1"] = (
        "okcanvas-organization-assistant-result-v1"
    )
    status: AssistantResultStatus
    answer: str = Field(min_length=1, max_length=8000)
    request_class: AssistantRequestClass
    side_effect: AssistantSideEffect
    citations: list[AssistantCitation] = Field(default_factory=list, max_length=30)
    completed_actions: list[AssistantActionSummary] = Field(default_factory=list, max_length=20)
    proposed_actions: list[AssistantActionSummary] = Field(default_factory=list, max_length=20)
    pending_approvals: list[AssistantActionSummary] = Field(default_factory=list, max_length=20)
    unverified: list[str] = Field(default_factory=list, max_length=50)
    follow_up_state: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_safety_contract(self) -> "OrganizationAssistantResult":
        if self.status is AssistantResultStatus.NEEDS_CAPABILITY and not self.unverified:
            raise ValueError("Capability-limited output must identify the unavailable or unverified requirement")
        if self.side_effect in {
            AssistantSideEffect.WRITE_REVERSIBLE,
            AssistantSideEffect.WRITE_IRREVERSIBLE,
            AssistantSideEffect.AUTOMATION_DEFINITION,
        } and self.completed_actions:
            raise ValueError("Main Assistant cannot report side-effect completion without a bound execution capability")
        if self.pending_approvals and self.side_effect not in {
            AssistantSideEffect.WRITE_REVERSIBLE,
            AssistantSideEffect.WRITE_IRREVERSIBLE,
            AssistantSideEffect.AUTOMATION_DEFINITION,
        }:
            raise ValueError("Pending approvals require a write or automation side-effect class")
        return self




class HostedWebSearchStatus(str, Enum):
    ANSWERED = "ANSWERED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class HostedWebSearchResult(StrictModel):
    schema_version: Literal["okcanvas-hosted-web-search-result-v1"] = (
        "okcanvas-hosted-web-search-result-v1"
    )
    status: HostedWebSearchStatus
    answer: str = Field(min_length=1, max_length=4000)
    unverified: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_no_model_owned_urls(self) -> "HostedWebSearchResult":
        values = [self.answer, *self.unverified]
        if any("http://" in value.lower() or "https://" in value.lower() for value in values):
            raise ValueError("Hosted Web Search URLs belong only to Product source evidence")
        if self.status is HostedWebSearchStatus.INSUFFICIENT_EVIDENCE and not self.unverified:
            raise ValueError("Insufficient-evidence output must identify unresolved points")
        return self


class LocalDocumentReviewStatus(str, Enum):
    REVIEWED = "REVIEWED"
    INSUFFICIENT_CONTENT = "INSUFFICIENT_CONTENT"


class LocalDocumentObservation(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=4000)


class LocalDocumentReviewResult(StrictModel):
    schema_version: Literal["okcanvas-local-document-review-result-v1"] = (
        "okcanvas-local-document-review-result-v1"
    )
    status: LocalDocumentReviewStatus
    summary: str = Field(min_length=1, max_length=4000)
    observations: list[LocalDocumentObservation] = Field(default_factory=list, max_length=50)
    unverified: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_result(self) -> "LocalDocumentReviewResult":
        if self.status is LocalDocumentReviewStatus.INSUFFICIENT_CONTENT and not self.unverified:
            raise ValueError("Insufficient-content output must identify unresolved points")
        return self


class ReplenishmentReviewStatus(str, Enum):
    READY = "READY"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReplenishmentAction(str, Enum):
    REORDER = "REORDER"
    NO_ACTION = "NO_ACTION"


class ReplenishmentRisk(str, Enum):
    SHORTAGE = "SHORTAGE"
    COVERED = "COVERED"


class StoreReplenishmentRecommendation(StrictModel):
    sku: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    available_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    forecast_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    inbound_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    safety_stock_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    projected_units: int = Field(ge=-MAX_INVENTORY_UNIT_VALUE, le=MAX_DERIVED_ITEM_UNIT_VALUE)
    reorder_units: int = Field(ge=0, le=MAX_DERIVED_ITEM_UNIT_VALUE)
    action: ReplenishmentAction
    risk: ReplenishmentRisk
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_calculation(self) -> "StoreReplenishmentRecommendation":
        expected_projected = self.available_units + self.inbound_units - self.forecast_units
        expected_reorder = max(
            self.forecast_units
            + self.safety_stock_units
            - self.available_units
            - self.inbound_units,
            0,
        )
        if self.projected_units != expected_projected:
            raise ValueError("projected_units does not match the inventory equation")
        if self.reorder_units != expected_reorder:
            raise ValueError("reorder_units does not match the replenishment equation")
        expected_action = (
            ReplenishmentAction.REORDER
            if expected_reorder > 0
            else ReplenishmentAction.NO_ACTION
        )
        expected_risk = (
            ReplenishmentRisk.SHORTAGE
            if expected_reorder > 0
            else ReplenishmentRisk.COVERED
        )
        if self.action is not expected_action:
            raise ValueError("action does not match reorder_units")
        if self.risk is not expected_risk:
            raise ValueError("risk does not match reorder_units")
        return self


class StoreReplenishmentReviewResult(StrictModel):
    schema_version: Literal["okcanvas-store-replenishment-review-v1"] = (
        "okcanvas-store-replenishment-review-v1"
    )
    status: ReplenishmentReviewStatus
    snapshot_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    reviewed_skus: int = Field(ge=0, le=100)
    total_reorder_units: int = Field(ge=0, le=JSON_SAFE_INTEGER_MAX)
    recommendations: list[StoreReplenishmentRecommendation] = Field(
        default_factory=list, max_length=100
    )
    unverified: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_review(self) -> "StoreReplenishmentReviewResult":
        if self.status is ReplenishmentReviewStatus.INSUFFICIENT_DATA:
            if self.recommendations or self.reviewed_skus != 0 or self.total_reorder_units != 0:
                raise ValueError("insufficient-data output cannot contain calculated recommendations")
            if not self.unverified:
                raise ValueError("insufficient-data output must identify unresolved inputs")
            return self

        if self.reviewed_skus != len(self.recommendations):
            raise ValueError("reviewed_skus must equal recommendation count")
        if len({item.sku for item in self.recommendations}) != len(self.recommendations):
            raise ValueError("recommendation SKUs must be unique")
        expected_total = sum(item.reorder_units for item in self.recommendations)
        if self.total_reorder_units != expected_total:
            raise ValueError("total_reorder_units must equal recommendation sum")
        expected_status = (
            ReplenishmentReviewStatus.ACTION_REQUIRED
            if expected_total > 0
            else ReplenishmentReviewStatus.READY
        )
        if self.status is not expected_status:
            raise ValueError("status does not match calculated reorder total")
        expected_order = sorted(
            self.recommendations, key=lambda item: (-item.reorder_units, item.sku)
        )
        if [item.sku for item in self.recommendations] != [item.sku for item in expected_order]:
            raise ValueError("recommendations must be sorted by reorder_units desc then SKU")
        return self


class UsageSummary(StrictModel):
    requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


class RuntimeErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LIVE_OPT_IN_REQUIRED = "LIVE_OPT_IN_REQUIRED"
    API_KEY_MISSING = "API_KEY_MISSING"
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    SDK_NOT_INSTALLED = "SDK_NOT_INSTALLED"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    SDK_RUN_FAILED = "SDK_RUN_FAILED"
    OUTPUT_CONTRACT_INVALID = "OUTPUT_CONTRACT_INVALID"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RuntimeErrorPayload(StrictModel):
    code: RuntimeErrorCode
    message: str
    retryable: bool = False
    detail_type: str | None = None


class RunEnvelope(StrictModel):
    schema_version: Literal["okcanvas-agent-run-v1"] = SCHEMA_VERSION
    run_id: str
    request_id: str
    agent_id: Literal["coding-agent"] = "coding-agent"
    state: Literal["SUCCEEDED", "FAILED"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    model: str | None
    sdk_version: str | None
    trace_id: str | None
    response_id: str | None
    input_sha256: str
    live_call: bool
    result: CodingAgentResult | None = None
    usage: UsageSummary = Field(default_factory=UsageSummary)
    error: RuntimeErrorPayload | None = None
