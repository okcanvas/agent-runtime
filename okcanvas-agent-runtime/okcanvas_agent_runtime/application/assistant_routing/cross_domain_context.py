from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextFocusRecord, SessionContextFocusState,
)
from .models import GroupwareContextFilterHint


class CrossDomainContextContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class GroupwareResourceRule:
    resource_kind: str
    terms: tuple[str, ...]
    tool_name: str


@dataclass(frozen=True)
class CrossDomainGroupwarePolicy:
    policy_id: str
    version: str
    allowed_source_entity_types: tuple[str, ...]
    entity_reference_terms: dict[str, tuple[str, ...]]
    resource_rules: tuple[GroupwareResourceRule, ...]
    max_results: int
    policy_sha256: str


@dataclass(frozen=True)
class CrossDomainGroupwareResolution:
    hint: GroupwareContextFilterHint | None
    ambiguous: bool
    reasons: tuple[str, ...]


class CrossDomainGroupwarePolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.path = Path(project_root) / "specs" / "assistant" / "session-cross-domain-groupware-policy.json"

    def resolve(self) -> CrossDomainGroupwarePolicy:
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CrossDomainContextContractError("Cross-domain Groupware policy is invalid JSON") from exc
        expected = {
            "schema_version","policy_id","version","allowed_source_entity_types",
            "entity_reference_terms","resource_rules","max_results",
            "preserve_anchor_only_after_exact_tool_filter_evidence","multiple_focus_must_not_guess",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise CrossDomainContextContractError("Cross-domain Groupware policy keys are not exact")
        if payload["schema_version"] != "okcanvas-session-cross-domain-groupware-policy-v1":
            raise CrossDomainContextContractError("Cross-domain Groupware policy schema is unsupported")
        if payload["preserve_anchor_only_after_exact_tool_filter_evidence"] is not True or payload["multiple_focus_must_not_guess"] is not True:
            raise CrossDomainContextContractError("Cross-domain Groupware safety controls must remain enabled")
        allowed = payload["allowed_source_entity_types"]
        refs = payload["entity_reference_terms"]
        rules = payload["resource_rules"]
        if not isinstance(allowed,list) or not allowed or any(not isinstance(x,str) or not x for x in allowed):
            raise CrossDomainContextContractError("Cross-domain source entity types are invalid")
        if not isinstance(refs,dict) or set(refs) != set(allowed):
            raise CrossDomainContextContractError("Cross-domain entity reference terms are incomplete")
        normalized_refs: dict[str, tuple[str,...]] = {}
        for entity_type, terms in refs.items():
            if not isinstance(terms,list) or not terms or any(not isinstance(t,str) or not t.strip() for t in terms):
                raise CrossDomainContextContractError("Cross-domain entity reference terms are invalid")
            normalized_refs[entity_type]=tuple(t.casefold() for t in terms)
        if not isinstance(rules,list) or len(rules)!=3:
            raise CrossDomainContextContractError("Cross-domain Groupware resource rules must remain exact")
        parsed=[]
        seen=set()
        for item in rules:
            if not isinstance(item,dict) or set(item)!={"resource_kind","terms","tool_name"}:
                raise CrossDomainContextContractError("Cross-domain Groupware resource rule keys are invalid")
            if item["tool_name"] not in {"search_notices","search_mail","list_calendar_events"}:
                raise CrossDomainContextContractError("Cross-domain Groupware tool is not allowlisted")
            terms=item["terms"]
            if not isinstance(terms,list) or not terms or any(not isinstance(t,str) or not t.strip() for t in terms):
                raise CrossDomainContextContractError("Cross-domain Groupware resource terms are invalid")
            if item["resource_kind"] in seen:
                raise CrossDomainContextContractError("Cross-domain Groupware resource kinds must be unique")
            seen.add(item["resource_kind"])
            parsed.append(GroupwareResourceRule(item["resource_kind"],tuple(t.casefold() for t in terms),item["tool_name"]))
        max_results=payload["max_results"]
        if not isinstance(max_results,int) or isinstance(max_results,bool) or not 1 <= max_results <= 20:
            raise CrossDomainContextContractError("Cross-domain Groupware max_results is invalid")
        return CrossDomainGroupwarePolicy(
            policy_id=str(payload["policy_id"]),version=str(payload["version"]),
            allowed_source_entity_types=tuple(allowed),entity_reference_terms=normalized_refs,
            resource_rules=tuple(parsed),max_results=max_results,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )


class CrossDomainGroupwareResolver:
    def __init__(self, policy: CrossDomainGroupwarePolicy) -> None:
        self.policy=policy

    def resolve(self, *, request: str, focus: SessionContextFocusRecord) -> CrossDomainGroupwareResolution | None:
        canonical=" ".join(request.strip().split())
        normalized=canonical.casefold()
        matched_resources=[r for r in self.policy.resource_rules if any(term in normalized for term in r.terms)]
        if len(matched_resources) != 1:
            return None
        resource=matched_resources[0]
        candidate_types={item.entity_type for item in focus.candidates}
        referenced_types={
            entity_type for entity_type,terms in self.policy.entity_reference_terms.items()
            if any(term in normalized for term in terms)
        }
        if not referenced_types or not (candidate_types & referenced_types):
            return None
        if focus.state is not SessionContextFocusState.RESOLVED or focus.active_entity is None:
            return CrossDomainGroupwareResolution(
                hint=None, ambiguous=True,
                reasons=("cross-domain-groupware-reference-detected","session-context-focus-not-singular","cross-domain-focus-must-not-guess"),
            )
        entity=focus.active_entity
        if entity.entity_type not in self.policy.allowed_source_entity_types or entity.entity_type not in referenced_types:
            return None
        return CrossDomainGroupwareResolution(
            hint=GroupwareContextFilterHint(
                pattern_id="session-cross-domain-groupware-context-ref-v1",
                resource_kind=resource.resource_kind,tool_name=resource.tool_name,
                entity_type=entity.entity_type,entity_id=entity.entity_id,label=entity.label,
                qualifiers=entity.qualifiers,catalog_revision=focus.catalog_revision,max_results=self.policy.max_results,
            ),
            ambiguous=False,
            reasons=("cross-domain-groupware-reference-detected","stable-organization-context-focus-bound","exact-groupware-context-ref-required"),
        )
