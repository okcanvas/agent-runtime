from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.groupware_read import GroupwareReadCatalog, GroupwareReadState
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.domain.sessions.context_focus import SessionContextFocusRecord
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationAccessContext,
    OrganizationCatalogState,
    OrganizationContextService,
    OrganizationContextReadCatalog,
    OrganizationContextReadState,
)

from .catalog import AssistantRoutingPolicyCatalog
from .grounded_delegation import grounded_structured_delegation_context
from .models import (
    AssistantCapability,
    AssistantRouteDecision,
    AssistantRouteStatus,
    CapabilityAvailability,
    OrganizationContextRequestHint,
    GroupwareContextFilterHint,
    GroundedSessionRouteShadow,
)
from .session_context import (
    SessionContextFollowUpPolicyCatalog,
    SessionContextFollowUpResolver,
    SessionContextResolutionStatus,
)
from .relation_context import (
    SessionContextRelationPolicyCatalog,
    SessionContextRelationResolver,
)
from .cross_domain_context import (
    CrossDomainGroupwarePolicyCatalog, CrossDomainGroupwareResolver,
)


class AssistantRoutingError(RuntimeError):
    code = "ASSISTANT_ROUTING_FAILED"


class OrganizationAssistantRoutingService:
    """Deterministic, safety-first routing before any model or Tool execution.

    STEP084 adds a Product-owned, versioned, read-only organization context catalog. The catalog
    remains empty by default and therefore fails closed until an operator supplies a validated
    Product Configuration Pack snapshot. Matching, tenant/principal/role filtering, ambiguity, and
    no-match outcomes are resolved before any model submission.
    """

    def __init__(
        self,
        project_root: str,
        organization_catalog_root: str | Path | None = None,
    ) -> None:
        self._policy = AssistantRoutingPolicyCatalog(project_root).resolve()
        self._session_context_policy = SessionContextFollowUpPolicyCatalog(project_root).resolve()
        self._session_context_resolver = SessionContextFollowUpResolver(
            self._session_context_policy, self._policy
        )
        self._session_relation_policy = SessionContextRelationPolicyCatalog(project_root).resolve()
        self._session_relation_resolver = SessionContextRelationResolver(
            self._session_relation_policy, self._session_context_policy
        )
        self._cross_domain_groupware_policy = CrossDomainGroupwarePolicyCatalog(project_root).resolve()
        self._cross_domain_groupware_resolver = CrossDomainGroupwareResolver(
            self._cross_domain_groupware_policy
        )
        self._definitions = AgentDefinitionCatalog(project_root)
        self._organization_context = OrganizationContextService(
            project_root,
            organization_catalog_root,
        )
        self._organization_remote = OrganizationContextReadCatalog(project_root)
        self._groupware = GroupwareReadCatalog(project_root)
        for agent_id in {
            self._policy.default_agent_id,
            self._policy.session_agent_id,
            "hosted-web-search-agent",
            "local-document-review-agent",
            "sandbox-readonly-coding-agent",
            self._groupware.policy.agent_id,
            self._organization_remote.policy.root_agent_id,
            self._organization_remote.policy.agent_id,
        }:
            self._definitions.resolve(agent_id)

    @property
    def policy(self):
        return self._policy

    @property
    def session_context_policy(self):
        return self._session_context_policy

    @property
    def session_relation_policy(self):
        return self._session_relation_policy

    @property
    def organization_context(self) -> OrganizationContextService:
        return self._organization_context

    @property
    def groupware(self) -> GroupwareReadCatalog:
        return self._groupware

    @property
    def organization_remote(self) -> OrganizationContextReadCatalog:
        return self._organization_remote

    def grounded_session_route_shadow(self) -> GroundedSessionRouteShadow:
        return GroundedSessionRouteShadow(selected_agent_id=self._policy.session_agent_id)

    def route(
        self,
        *,
        request: str,
        session_id: str | None = None,
        attachment_id: str | None = None,
        project_snapshot_id: str | None = None,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        roles: tuple[str, ...] = (),
        session_context_focus: SessionContextFocusRecord | None = None,
    ) -> AssistantRouteDecision:
        canonical = " ".join(request.strip().split())
        normalized = canonical.casefold()
        if not normalized or "\x00" in normalized:
            raise AssistantRoutingError("Assistant input must be non-empty and NUL-free")
        has = lambda name: any(term in normalized for term in self._policy.lexicons[name])
        enterprise = has("enterprise_system")
        groupware = has("groupware")
        short_read_hint = self._policy.match_organization_context_short_read(canonical)

        if attachment_id is not None:
            return self._decision(
                request_class="ANALYZE_ATTACHMENT",
                capability_id="local-document-review-v1",
                matched_rule_id="attachment-input-v1",
                reasons=("uploaded-local-attachment-present",),
                session_id=session_id,
            )
        if project_snapshot_id is not None:
            return self._decision(
                request_class="CODE_ASSIST",
                capability_id="repository-readonly-analysis-v1",
                matched_rule_id="project-snapshot-input-v1",
                reasons=("immutable-project-snapshot-present", "repository-analysis-read-only"),
                session_id=session_id,
            )
        if (
            session_id is not None and session_context_focus is not None and groupware
            and not has("write_action") and not has("draft_action") and not has("automation")
        ):
            cross_domain = self._cross_domain_groupware_resolver.resolve(
                request=canonical, focus=session_context_focus
            )
            if cross_domain is not None:
                if cross_domain.ambiguous:
                    capability = self._policy.capabilities[self._groupware.policy.capability_id]
                    return self._raw_decision(
                        request_class="READ_SYSTEM", capability=capability,
                        status=AssistantRouteStatus.AMBIGUOUS, selected_agent_id=None,
                        matched_rule_id="groupware-session-cross-domain-focus-ambiguous-v1",
                        reasons=cross_domain.reasons,
                    )
                if cross_domain.hint is not None:
                    return self._groupware_decision(
                        tenant_id=tenant_id, principal_id=principal_id, roles=roles,
                        session_id=session_id, context_filter=cross_domain.hint,
                        contextual_reasons=cross_domain.reasons,
                    )

        if session_id is not None and session_context_focus is not None:
            contextual = self._session_relation_resolver.resolve(
                request=canonical, focus=session_context_focus
            )
            if contextual is None:
                contextual = self._session_context_resolver.resolve(
                    request=canonical, focus=session_context_focus
                )
            if contextual is not None:
                if contextual.status is SessionContextResolutionStatus.AMBIGUOUS:
                    capability = self._policy.capabilities[
                        self._organization_remote.policy.capability_id
                    ]
                    return self._raw_decision(
                        request_class="SEARCH_KNOWLEDGE",
                        capability=capability,
                        status=AssistantRouteStatus.AMBIGUOUS,
                        selected_agent_id=None,
                        matched_rule_id="organization-context-session-follow-up-ambiguous-v1",
                        reasons=(
                            *contextual.reasons,
                            "session-context-focus-derived-only-from-prior-tool-evidence",
                        ),
                    )
                if contextual.hint is not None:
                    return self._organization_short_read_decision(
                        hint=contextual.hint,
                        tenant_id=tenant_id,
                        principal_id=principal_id,
                        roles=roles,
                        session_id=session_id,
                        contextual_reasons=(
                            *contextual.reasons,
                            "session-context-focus-derived-only-from-prior-tool-evidence",
                        ),
                    )

        if (
            session_id is not None
            and has("session_reference")
            and has("session_restatement")
            and not has("external_refresh")
            and not has("automation")
            and not has("write_action")
            and not has("draft_action")
        ):
            return self._decision(
                request_class="ANSWER",
                capability_id="general-assistant-v1",
                matched_rule_id="session-referential-restatement-v1",
                reasons=(
                    "session-reference-detected",
                    "restatement-only-language-detected",
                    "no-external-refresh-requested",
                ),
                session_id=session_id,
            )
        if has("automation"):
            return self._decision(
                request_class="AUTOMATE",
                capability_id="durable-automation-v1",
                matched_rule_id="future-repeated-conditional-work-v1",
                reasons=("future-or-recurring-trigger-language-detected", "durable-scheduler-not-configured"),
                session_id=session_id,
                proposal_only=True,
            )
        if enterprise and has("write_action"):
            return self._decision(
                request_class="WRITE_ACTION",
                capability_id="enterprise-action-write-v1",
                matched_rule_id="enterprise-write-intent-v1",
                reasons=("enterprise-system-context-detected", "write-verb-detected", "approval-required-before-write"),
                session_id=session_id,
                proposal_only=True,
            )
        if enterprise and has("draft_action") and has("enterprise_transaction"):
            return self._decision(
                request_class="DRAFT_ACTION",
                capability_id="enterprise-action-draft-v1",
                matched_rule_id="enterprise-draft-intent-v1",
                reasons=("enterprise-transaction-context-detected", "draft-only-language-detected"),
                session_id=session_id,
                proposal_only=True,
            )
        if groupware and has("read_action"):
            return self._groupware_decision(
                tenant_id=tenant_id,
                principal_id=principal_id,
                roles=roles,
                session_id=session_id,
            )
        if enterprise and has("read_action"):
            return self._decision(
                request_class="READ_SYSTEM",
                capability_id="enterprise-system-read-v1",
                matched_rule_id="enterprise-read-intent-v1",
                reasons=("enterprise-system-context-detected", "read-language-detected", "enterprise-connector-not-configured"),
                session_id=session_id,
            )
        if short_read_hint is not None and not any(
            has(name)
            for name in (
                "automation",
                "write_action",
                "draft_action",
                "content_draft",
                "web",
                "code",
                "groupware",
                "enterprise_system",
            )
        ):
            return self._organization_short_read_decision(
                hint=short_read_hint,
                tenant_id=tenant_id,
                principal_id=principal_id,
                roles=roles,
                session_id=session_id,
            )
        if has("organization") and not has("content_draft"):
            identity = None
            if tenant_id and principal_id:
                identity = DelegatedMCPIdentity.create(
                    tenant_id=tenant_id, principal_id=principal_id, roles=roles
                )
            remote_readiness = self._organization_remote.readiness(identity)
            if remote_readiness.state in {
                OrganizationContextReadState.READY,
                OrganizationContextReadState.ACCESS_DENIED,
            }:
                return self._organization_remote_decision(
                    identity=identity, session_id=session_id
                )
            return self._organization_decision(
                request=request,
                session_id=session_id,
                access=OrganizationAccessContext(
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    roles=tuple(sorted(set(roles))),
                ),
            )
        if has("web"):
            return self._decision(
                request_class="SEARCH_WEB",
                capability_id="public-web-search-v1",
                matched_rule_id="public-web-search-intent-v1",
                reasons=("public-current-information-language-detected",),
                session_id=session_id,
            )
        if has("code"):
            return self._decision(
                request_class="CODE_ASSIST",
                capability_id="general-assistant-v1",
                matched_rule_id="language-only-code-assistance-v1",
                reasons=("code-language-detected", "no-repository-snapshot-present"),
                session_id=session_id,
            )
        if has("content_draft"):
            return self._decision(
                request_class="WRITE_CONTENT",
                capability_id="content-drafting-v1",
                matched_rule_id="content-drafting-intent-v1",
                reasons=("content-generation-language-detected", "no-external-side-effect"),
                session_id=session_id,
            )
        return self._decision(
            request_class="ANSWER",
            capability_id="general-assistant-v1",
            matched_rule_id="default-general-answer-v1",
            reasons=("no-external-capability-required",),
            session_id=session_id,
        )

    def build_model_request(self, decision: AssistantRouteDecision, user_request: str) -> str:
        context: dict[str, object] = {
            "schema_version": "okcanvas-assistant-routing-context-v2",
            "request_class": decision.request_class,
            "side_effect": decision.side_effect,
            "status": decision.status.value,
            "required_capabilities": [item.capability_id for item in decision.required_capabilities],
            "matched_rule_id": decision.matched_rule_id,
            "selected_agent_definition_id": decision.selected_agent_id,
        }
        if decision.grounding is not None:
            context["organization_grounding"] = decision.grounding.to_grounding_dict()
            context["organization_grounding_rules"] = {
                "authoritative_only": True,
                "cite_source_reference": True,
                "do_not_infer_unlisted_organization_facts": True,
            }
        if decision.organization_context_request_hint is not None:
            context["organization_context_request_hint"] = (
                decision.organization_context_request_hint.to_public_dict()
            )
            context["organization_context_request_hint_rules"] = {
                "routing_only": True,
                "not_entity_evidence": True,
                "do_not_select_one_ambiguous_entity": True,
                "tool_result_remains_authoritative": True,
            }
            relation_traversal = decision.organization_context_request_hint.relation_traversal
            if relation_traversal is not None:
                context["organization_context_relation_traversal_rules"] = {
                    "source_stable_id_must_be_used_for_get": True,
                    "source_entity_type_must_match": True,
                    "relation_type_and_direction_are_immutable": True,
                    "related_entities_must_come_from_get_tool_relations": True,
                    "relationship_evidence_must_be_complete": True,
                    "truncated_relationship_evidence_must_fail_closed": True,
                    "do_not_infer_inverse_or_unlisted_relations": True,
                    "max_related_entities": relation_traversal.max_results,
                }
        if decision.grounded_interpretation_shadow is not None:
            context["grounded_structured_delegation"] = grounded_structured_delegation_context()
        if decision.groupware_context_filter is not None:
            context["groupware_context_filter"] = decision.groupware_context_filter.to_public_dict()
            context["groupware_context_filter_rules"] = {
                "routing_only": True,
                "stable_entity_from_prior_tool_evidence": True,
                "exact_tool_name_required": True,
                "exact_entity_type_and_id_must_be_forwarded": True,
                "tool_result_must_confirm_applied_filter": True,
                "returned_records_must_carry_exact_context_ref": True,
                "canonical_context_filter_arguments_only": True,
                "search_query_must_be_empty": True,
                "calendar_time_range_must_be_omitted": True,
                "limit_must_equal": decision.groupware_context_filter.max_results,
                "preserve_anchor_only_after_exact_tool_filter_evidence": True,
                "do_not_fallback_to_label_search": True,
            }
        if any(
            item.capability_id == self._groupware.policy.capability_id
            for item in decision.required_capabilities
        ):
            context["groupware_read_policy"] = {
                "policy_id": self._groupware.policy.policy_id,
                "version": self._groupware.policy.version,
                "allowed_tools": list(self._groupware.policy.allowed_tools),
                "max_results": self._groupware.policy.max_results,
                "write_enabled": False,
                "delegated_identity_required": True,
            }
        if any(
            item.capability_id == self._organization_remote.policy.capability_id
            for item in decision.required_capabilities
        ):
            context["organization_context_read_policy"] = {
                "policy_id": self._organization_remote.policy.policy_id,
                "version": self._organization_remote.policy.version,
                "allowed_tools": list(self._organization_remote.policy.allowed_tools),
                "max_results": self._organization_remote.policy.max_results,
                "production_sot": "DATABASE",
                "write_enabled": False,
                "delegated_identity_required": True,
            }
        return (
            "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
            + "\n\nUSER REQUEST:\n"
            + user_request.strip()
        )

    def _groupware_decision(
        self,
        *,
        tenant_id: str | None,
        principal_id: str | None,
        roles: tuple[str, ...],
        session_id: str | None,
        context_filter: GroupwareContextFilterHint | None = None,
        contextual_reasons: tuple[str, ...] = (),
    ) -> AssistantRouteDecision:
        identity = None
        if tenant_id and principal_id:
            identity = DelegatedMCPIdentity.create(
                tenant_id=tenant_id, principal_id=principal_id, roles=roles
            )
        readiness = self._groupware.readiness(identity)
        configured = self._policy.capabilities[self._groupware.policy.capability_id]
        if readiness.state is GroupwareReadState.READY:
            available = replace(
                configured,
                availability=CapabilityAvailability.AVAILABLE,
                selected_agent_id=self._groupware.policy.agent_id,
            )
            self._definitions.resolve(self._groupware.policy.agent_id)
            selected_agent_id = (
                self._policy.session_agent_id if session_id is not None
                else self._groupware.policy.agent_id
            )
            self._definitions.resolve(selected_agent_id)
            reasons = [
                "groupware-read-intent-detected",
                "delegated-tenant-principal-role-bound",
                "read-only-mcp-tool-allowlist-bound",
                *contextual_reasons,
            ]
            rule = "groupware-read-configured-v1"
            if session_id is not None:
                reasons.extend((
                    "session-owned-main-assistant-retained",
                    "stateless-groupware-subagent-selected",
                    "child-session-persistence-disabled",
                ))
                rule = "groupware-read-session-stateless-subagent-v1"
            return self._raw_decision(
                request_class="READ_SYSTEM",
                capability=available,
                status=AssistantRouteStatus.EXECUTABLE,
                selected_agent_id=selected_agent_id,
                matched_rule_id=rule,
                reasons=tuple(reasons),
                groupware_context_filter=context_filter,
            )
        reasons = ("groupware-read-intent-detected", *contextual_reasons, *readiness.reasons)
        if readiness.state is GroupwareReadState.ACCESS_DENIED:
            capability = replace(configured, availability=CapabilityAvailability.DISABLED)
            rule = "groupware-read-access-denied-v1"
        else:
            capability = configured
            rule = "groupware-read-not-configured-v1"
        return self._raw_decision(
            request_class="READ_SYSTEM",
            capability=capability,
            status=AssistantRouteStatus.NOT_CONFIGURED,
            selected_agent_id=None,
            matched_rule_id=rule,
            reasons=reasons,
            groupware_context_filter=context_filter,
        )

    def _organization_short_read_decision(
        self,
        *,
        hint: OrganizationContextRequestHint,
        tenant_id: str | None,
        principal_id: str | None,
        roles: tuple[str, ...],
        session_id: str | None,
        contextual_reasons: tuple[str, ...] = (),
    ) -> AssistantRouteDecision:
        identity = None
        if tenant_id and principal_id:
            identity = DelegatedMCPIdentity.create(
                tenant_id=tenant_id, principal_id=principal_id, roles=roles
            )
        readiness = self._organization_remote.readiness(identity)
        configured = self._policy.capabilities[
            self._organization_remote.policy.capability_id
        ]
        common_reasons = (
            "organization-context-short-read-pattern-matched",
            "structured-request-hint-created-without-entity-guessing",
            f"organization-context-pattern:{hint.pattern_id}",
            *contextual_reasons,
            *readiness.reasons,
        )
        if readiness.state is OrganizationContextReadState.READY:
            available = replace(
                configured,
                availability=CapabilityAvailability.AVAILABLE,
                selected_agent_id=self._organization_remote.policy.agent_id,
            )
            selected_agent_id = (
                self._organization_remote.policy.root_agent_id
                if session_id is not None
                else self._organization_remote.policy.agent_id
            )
            self._definitions.resolve(selected_agent_id)
            reasons = (
                "organization-context-short-read-pattern-matched",
                "structured-request-hint-created-without-entity-guessing",
                f"organization-context-pattern:{hint.pattern_id}",
                *contextual_reasons,
                "production-database-sot-boundary-selected",
                "delegated-tenant-principal-role-bound",
                "read-only-mcp-tool-allowlist-bound",
            )
            rule = "organization-context-short-read-configured-v1"
            if session_id is not None:
                reasons = (*reasons,
                    "session-owned-organization-context-root-retained",
                    "stateless-organization-context-subagent-selected",
                    "child-session-persistence-disabled",
                )
                rule = "organization-context-short-read-session-stateless-subagent-v1"
            return self._raw_decision(
                request_class="SEARCH_KNOWLEDGE",
                capability=available,
                status=AssistantRouteStatus.EXECUTABLE,
                selected_agent_id=selected_agent_id,
                matched_rule_id=rule,
                reasons=reasons,
                organization_context_request_hint=hint,
            )
        if readiness.state is OrganizationContextReadState.ACCESS_DENIED:
            capability = replace(configured, availability=CapabilityAvailability.DISABLED)
            rule = "organization-context-short-read-access-denied-v1"
        else:
            capability = configured
            rule = "organization-context-short-read-not-configured-v1"
        return self._raw_decision(
            request_class="SEARCH_KNOWLEDGE",
            capability=capability,
            status=AssistantRouteStatus.NOT_CONFIGURED,
            selected_agent_id=None,
            matched_rule_id=rule,
            reasons=common_reasons,
            organization_context_request_hint=hint,
        )

    def _organization_remote_decision(
        self,
        *,
        identity: DelegatedMCPIdentity | None,
        session_id: str | None,
    ) -> AssistantRouteDecision:
        readiness = self._organization_remote.readiness(identity)
        configured = self._policy.capabilities[self._organization_remote.policy.capability_id]
        if readiness.state is OrganizationContextReadState.READY:
            available = replace(
                configured,
                availability=CapabilityAvailability.AVAILABLE,
                selected_agent_id=self._organization_remote.policy.agent_id,
            )
            selected_agent_id = (
                self._organization_remote.policy.root_agent_id
                if session_id is not None
                else self._organization_remote.policy.agent_id
            )
            self._definitions.resolve(selected_agent_id)
            reasons = [
                "organization-context-read-intent-detected",
                "production-database-sot-boundary-selected",
                "delegated-tenant-principal-role-bound",
                "read-only-mcp-tool-allowlist-bound",
            ]
            rule = "organization-context-read-configured-v1"
            if session_id is not None:
                reasons.extend((
                    "session-owned-organization-context-root-retained",
                    "stateless-organization-context-subagent-selected",
                    "child-session-persistence-disabled",
                ))
                rule = "organization-context-read-session-stateless-subagent-v1"
            return self._raw_decision(
                request_class="SEARCH_KNOWLEDGE",
                capability=available,
                status=AssistantRouteStatus.EXECUTABLE,
                selected_agent_id=selected_agent_id,
                matched_rule_id=rule,
                reasons=tuple(reasons),
            )
        capability = replace(configured, availability=CapabilityAvailability.DISABLED)
        return self._raw_decision(
            request_class="SEARCH_KNOWLEDGE",
            capability=capability,
            status=AssistantRouteStatus.NOT_CONFIGURED,
            selected_agent_id=None,
            matched_rule_id="organization-context-read-access-denied-v1",
            reasons=("organization-context-read-intent-detected", *readiness.reasons),
        )

    def _organization_decision(
        self,
        *,
        request: str,
        session_id: str | None,
        access: OrganizationAccessContext,
    ) -> AssistantRouteDecision:
        result = self._organization_context.combined(request, access, limit=8)
        capability = self._policy.capabilities["organization-knowledge-read-v1"]
        if result.catalog_state is OrganizationCatalogState.EMPTY:
            unavailable = replace(
                capability,
                availability=CapabilityAvailability.NOT_CONFIGURED,
                selected_agent_id=None,
            )
            return self._raw_decision(
                request_class="SEARCH_KNOWLEDGE",
                capability=unavailable,
                status=AssistantRouteStatus.NOT_CONFIGURED,
                selected_agent_id=None,
                matched_rule_id="organization-context-catalog-empty-v1",
                reasons=(
                    "organization-specific-language-detected",
                    "organization-context-catalog-empty",
                    "operator-configuration-required",
                ),
                grounding=result,
            )
        if result.ambiguous:
            return self._raw_decision(
                request_class="SEARCH_KNOWLEDGE",
                capability=capability,
                status=AssistantRouteStatus.AMBIGUOUS,
                selected_agent_id=None,
                matched_rule_id="organization-context-ambiguous-v1",
                reasons=(
                    "organization-specific-language-detected",
                    "multiple-authoritative-matches-require-disambiguation",
                ),
                grounding=result,
            )
        if not result.matches:
            return self._raw_decision(
                request_class="SEARCH_KNOWLEDGE",
                capability=capability,
                status=AssistantRouteStatus.NO_MATCH,
                selected_agent_id=None,
                matched_rule_id="organization-context-no-match-v1",
                reasons=(
                    "organization-specific-language-detected",
                    "no-authoritative-organization-record-matched",
                    "model-inference-blocked",
                ),
                grounding=result,
            )
        return self._decision(
            request_class="SEARCH_KNOWLEDGE",
            capability_id="organization-knowledge-read-v1",
            matched_rule_id="organization-context-authoritative-match-v1",
            reasons=(
                "organization-specific-language-detected",
                "authoritative-organization-context-matched",
                "tenant-principal-role-scope-verified",
            ),
            session_id=session_id,
            grounding=result,
        )

    def _decision(
        self,
        *,
        request_class: str,
        capability_id: str,
        matched_rule_id: str,
        reasons: tuple[str, ...],
        session_id: str | None,
        proposal_only: bool = False,
        grounding=None,
        organization_context_request_hint: OrganizationContextRequestHint | None = None,
        groupware_context_filter: GroupwareContextFilterHint | None = None,
    ) -> AssistantRouteDecision:
        capability = self._policy.capabilities[capability_id]
        selected_agent_id = capability.selected_agent_id
        if selected_agent_id == self._policy.default_agent_id and session_id is not None:
            selected_agent_id = self._policy.session_agent_id
        if session_id is not None and selected_agent_id not in {self._policy.session_agent_id}:
            return self._raw_decision(
                request_class=request_class,
                capability=capability,
                status=AssistantRouteStatus.PROPOSAL_ONLY,
                selected_agent_id=None,
                matched_rule_id="session-composition-not-supported-v1",
                reasons=(*reasons, "requested-session-cannot-compose-with-selected-capability"),
                grounding=grounding,
                organization_context_request_hint=organization_context_request_hint,
                groupware_context_filter=groupware_context_filter,
            )
        if capability.availability is CapabilityAvailability.AVAILABLE and selected_agent_id:
            self._definitions.resolve(selected_agent_id)
            status = AssistantRouteStatus.EXECUTABLE
        elif proposal_only:
            selected_agent_id = self._policy.session_agent_id if session_id is not None else self._policy.default_agent_id
            self._definitions.resolve(selected_agent_id)
            status = AssistantRouteStatus.PROPOSAL_ONLY
        else:
            status = AssistantRouteStatus.NOT_CONFIGURED
        return self._raw_decision(
            request_class=request_class,
            capability=capability,
            status=status,
            selected_agent_id=selected_agent_id if status in {AssistantRouteStatus.EXECUTABLE, AssistantRouteStatus.PROPOSAL_ONLY} else None,
            matched_rule_id=matched_rule_id,
            reasons=reasons,
            grounding=grounding,
            organization_context_request_hint=organization_context_request_hint,
            groupware_context_filter=groupware_context_filter,
        )

    def _raw_decision(
        self,
        *,
        request_class: str,
        capability: AssistantCapability,
        status: AssistantRouteStatus,
        selected_agent_id: str | None,
        matched_rule_id: str,
        reasons: tuple[str, ...],
        grounding=None,
        organization_context_request_hint: OrganizationContextRequestHint | None = None,
        groupware_context_filter: GroupwareContextFilterHint | None = None,
    ) -> AssistantRouteDecision:
        return AssistantRouteDecision(
            request_class=request_class,
            side_effect=capability.side_effect,
            status=status,
            selected_agent_id=selected_agent_id,
            required_capabilities=(capability,),
            matched_rule_id=matched_rule_id,
            reasons=reasons,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            policy_sha256=self._policy.policy_sha256,
            grounding=grounding,
            organization_context_request_hint=organization_context_request_hint,
            groupware_context_filter=groupware_context_filter,
        )
