from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextEntityRef,
    SessionContextFocusRecord,
    SessionContextFocusState,
)

from .models import (
    OrganizationContextPreferredOperation,
    OrganizationContextRelationTraversalHint,
    OrganizationContextRequestHint,
)
from .session_context import SessionContextResolution, SessionContextResolutionStatus

_TERMINAL_PUNCTUATION = "?.!。！？"
_ALLOWED_ENTITY_TYPES = {
    "TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT",
    "SYSTEM", "CAPABILITY",
}
_ALLOWED_DIRECTIONS = {"OUTBOUND", "INBOUND"}
_ALLOWED_RELATIONS = {
    "EMPLOYEE_BELONGS_TO_DEPARTMENT": (("EMPLOYEE",), "OUTBOUND", ("DEPARTMENT",)),
    "EMPLOYEE_REPORTS_TO_EMPLOYEE": (("EMPLOYEE",), "OUTBOUND", ("EMPLOYEE",)),
    "PRODUCT_OWNED_BY_DEPARTMENT": (("PRODUCT",), "OUTBOUND", ("DEPARTMENT",)),
    "EMPLOYEE_MANAGES_PRODUCT": (("EMPLOYEE",), "OUTBOUND", ("PRODUCT",)),
    "EMPLOYEE_MANAGES_CLIENT": (("EMPLOYEE",), "OUTBOUND", ("CLIENT",)),
    "CLIENT_USES_PRODUCT": (("CLIENT",), "OUTBOUND", ("PRODUCT",)),
    "PROJECT_FOR_CLIENT": (("PROJECT",), "OUTBOUND", ("CLIENT",)),
    "EMPLOYEE_MANAGES_PROJECT": (("EMPLOYEE",), "OUTBOUND", ("PROJECT",)),
}
# Reverse traversal is permitted only for relations whose source/target identity is fixed by the
# published Organization Context contract.
_ALLOWED_REVERSE_RELATIONS = {
    "CLIENT_USES_PRODUCT": (("PRODUCT",), "INBOUND", ("CLIENT",)),
    "PROJECT_FOR_CLIENT": (("CLIENT",), "INBOUND", ("PROJECT",)),
}


class SessionContextRelationPolicyError(RuntimeError):
    code = "SESSION_CONTEXT_RELATION_POLICY_INVALID"


@dataclass(frozen=True)
class RelationSourceReferenceRule:
    entity_types: tuple[str, ...]
    expressions: tuple[str, ...]


@dataclass(frozen=True)
class RelationTraversalRule:
    pattern_id: str
    source_entity_types: tuple[str, ...]
    relation_type: str
    direction: str
    result_entity_types: tuple[str, ...]
    forms: tuple[str, ...]


@dataclass(frozen=True)
class SessionContextRelationPolicy:
    policy_id: str
    version: str
    max_results: int
    source_references: tuple[RelationSourceReferenceRule, ...]
    relations: tuple[RelationTraversalRule, ...]
    policy_sha256: str


class SessionContextRelationPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.path = Path(project_root).expanduser().resolve() / "specs" / "assistant" / "session-context-relation-follow-up-policy.json"

    @staticmethod
    def _text(value: object, *, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise SessionContextRelationPolicyError(f"Session relation {label} is invalid")
        return value.strip()

    @staticmethod
    def _strings(value: object, *, label: str) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise SessionContextRelationPolicyError(f"Session relation {label} must be a non-empty list")
        result = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
        if len(result) != len(value) or len({item.casefold() for item in result}) != len(result):
            raise SessionContextRelationPolicyError(f"Session relation {label} must contain unique text")
        return result

    def resolve(self) -> SessionContextRelationPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise SessionContextRelationPolicyError("Session relation policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SessionContextRelationPolicyError("Session relation policy is invalid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version", "policy_id", "version", "max_results", "source_references", "relations"
        }:
            raise SessionContextRelationPolicyError("Session relation policy keys are not exact")
        if payload["schema_version"] != "okcanvas-session-context-relation-follow-up-policy-v1":
            raise SessionContextRelationPolicyError("Session relation policy schema is unsupported")
        max_results = payload["max_results"]
        if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 20:
            raise SessionContextRelationPolicyError("Session relation max_results is invalid")

        source_refs_raw = payload["source_references"]
        if not isinstance(source_refs_raw, list) or not source_refs_raw:
            raise SessionContextRelationPolicyError("Session relation source references are invalid")
        source_refs: list[RelationSourceReferenceRule] = []
        source_seen: set[str] = set()
        for item in source_refs_raw:
            if not isinstance(item, dict) or set(item) != {"entity_types", "expressions"}:
                raise SessionContextRelationPolicyError("Session relation source-reference keys are not exact")
            entity_types = self._strings(item["entity_types"], label="source entity types")
            if any(entity_type not in _ALLOWED_ENTITY_TYPES for entity_type in entity_types):
                raise SessionContextRelationPolicyError("Session relation source entity type is unsupported")
            expressions = self._strings(item["expressions"], label="source expressions")
            for expression in expressions:
                folded = expression.casefold()
                if folded in source_seen:
                    raise SessionContextRelationPolicyError("Session relation source expressions overlap")
                source_seen.add(folded)
            source_refs.append(RelationSourceReferenceRule(entity_types=entity_types, expressions=expressions))

        relations_raw = payload["relations"]
        if not isinstance(relations_raw, list) or not relations_raw:
            raise SessionContextRelationPolicyError("Session relation rules are invalid")
        relation_rules: list[RelationTraversalRule] = []
        pattern_seen: set[str] = set()
        form_scope_seen: set[tuple[tuple[str, ...], str]] = set()
        for item in relations_raw:
            if not isinstance(item, dict) or set(item) != {
                "pattern_id", "source_entity_types", "relation_type", "direction", "result_entity_types", "forms"
            }:
                raise SessionContextRelationPolicyError("Session relation rule keys are not exact")
            pattern_id = self._text(item["pattern_id"], label="pattern_id")
            if pattern_id in pattern_seen:
                raise SessionContextRelationPolicyError("Session relation pattern IDs must be unique")
            pattern_seen.add(pattern_id)
            source_types = self._strings(item["source_entity_types"], label="source entity types")
            result_types = self._strings(item["result_entity_types"], label="result entity types")
            if any(value not in _ALLOWED_ENTITY_TYPES for value in (*source_types, *result_types)):
                raise SessionContextRelationPolicyError("Session relation entity type is unsupported")
            relation_type = self._text(item["relation_type"], label="relation_type")
            direction = self._text(item["direction"], label="direction").upper()
            if direction not in _ALLOWED_DIRECTIONS:
                raise SessionContextRelationPolicyError("Session relation direction is unsupported")
            contract = (_ALLOWED_RELATIONS if direction == "OUTBOUND" else _ALLOWED_REVERSE_RELATIONS).get(relation_type)
            if contract is None or contract != (source_types, direction, result_types):
                raise SessionContextRelationPolicyError("Session relation rule disagrees with the bounded relation contract")
            forms = self._strings(item["forms"], label="relation forms")
            for form in forms:
                key = (source_types, form.casefold())
                if key in form_scope_seen:
                    raise SessionContextRelationPolicyError("Session relation forms overlap within a source type")
                form_scope_seen.add(key)
            relation_rules.append(RelationTraversalRule(
                pattern_id=pattern_id,
                source_entity_types=source_types,
                relation_type=relation_type,
                direction=direction,
                result_entity_types=result_types,
                forms=forms,
            ))

        return SessionContextRelationPolicy(
            policy_id=self._text(payload["policy_id"], label="policy_id"),
            version=self._text(payload["version"], label="version"),
            max_results=max_results,
            source_references=tuple(source_refs),
            relations=tuple(relation_rules),
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )


class SessionContextRelationResolver:
    def __init__(self, policy: SessionContextRelationPolicy, follow_up_policy) -> None:
        self.policy = policy
        self.follow_up_policy = follow_up_policy

    @staticmethod
    def _canonical(request: str) -> str:
        return " ".join(request.strip().split()).rstrip(_TERMINAL_PUNCTUATION).strip()

    def _strip_continuation_prefix(self, canonical: str) -> str:
        folded = canonical.casefold()
        for prefix in self.follow_up_policy.continuation_prefixes:
            prefix_folded = prefix.casefold()
            if folded == prefix_folded:
                return ""
            marker = prefix_folded + " "
            if folded.startswith(marker):
                return canonical[len(prefix):].strip()
            comma_marker = prefix_folded + ","
            if folded.startswith(comma_marker):
                return canonical[len(prefix) + 1:].strip()
        return canonical

    def _match_rule(
        self, canonical: str, focus_entity_types: set[str]
    ) -> tuple[RelationTraversalRule, str] | None:
        effective = self._strip_continuation_prefix(canonical)
        folded = effective.casefold()
        matches: list[tuple[RelationTraversalRule, str]] = []
        for rule in self.policy.relations:
            if not focus_entity_types.intersection(rule.source_entity_types):
                continue
            for form in sorted(rule.forms, key=len, reverse=True):
                form_folded = form.casefold()
                if folded == form_folded:
                    matches.append((rule, ""))
                    break
                suffix = " " + form_folded
                if folded.endswith(suffix):
                    source_expression = effective[: len(effective) - len(form) - 1].strip()
                    if source_expression:
                        matches.append((rule, source_expression))
                        break
        if len(matches) != 1:
            return None
        return matches[0]

    def _source_reference_types(self, expression: str) -> tuple[str, ...] | None:
        folded = expression.casefold().strip()
        for rule in self.policy.source_references:
            if folded in {item.casefold() for item in rule.expressions}:
                return rule.entity_types
        return None

    @staticmethod
    def _candidate_search_text(entity: SessionContextEntityRef) -> str:
        return " ".join((entity.label, entity.entity_id, *entity.qualifiers)).casefold()

    def _ordinal_candidate(self, expression: str, candidates: tuple[SessionContextEntityRef, ...]) -> SessionContextEntityRef | None:
        folded = expression.casefold()
        ordinals: list[int] = []
        for rule in self.follow_up_policy.ordinal_selectors:
            if any(token.casefold() in folded for token in rule.expressions):
                ordinals.append(rule.ordinal)
        if len(set(ordinals)) != 1:
            return None
        ordinal = ordinals[0]
        return candidates[ordinal - 1] if ordinal <= len(candidates) else None

    def _refined_candidates(self, expression: str, candidates: tuple[SessionContextEntityRef, ...]) -> tuple[SessionContextEntityRef, ...]:
        canonical = self._canonical(expression)
        tokens = tuple(token.casefold() for token in canonical.split() if token.strip())
        if not tokens:
            return ()
        return tuple(candidate for candidate in candidates if all(token in self._candidate_search_text(candidate) for token in tokens))

    def _hint(self, *, rule: RelationTraversalRule, source: SessionContextEntityRef) -> OrganizationContextRequestHint:
        return OrganizationContextRequestHint(
            pattern_id=f"session-context-relation:{rule.pattern_id}",
            intent="RELATION_LOOKUP",
            target_expression=source.entity_id,
            entity_type_hints=(source.entity_type,),
            requested_fields=("RELATION",),
            preferred_operation=OrganizationContextPreferredOperation.GET,
            relation_traversal=OrganizationContextRelationTraversalHint(
                source_entity_type=source.entity_type,
                source_entity_id=source.entity_id,
                relation_type=rule.relation_type,
                direction=rule.direction,
                result_entity_types=rule.result_entity_types,
                max_results=self.policy.max_results,
            ),
        )

    def resolve(self, *, request: str, focus: SessionContextFocusRecord | None) -> SessionContextResolution | None:
        if focus is None or focus.observation.domain != "ORGANIZATION_CONTEXT" or not focus.candidates:
            return None
        matched = self._match_rule(
            self._canonical(request), {candidate.entity_type for candidate in focus.candidates}
        )
        if matched is None:
            return None
        rule, source_expression = matched
        candidates = focus.candidates[:20]

        def compatible(entity: SessionContextEntityRef) -> bool:
            return entity.entity_type in rule.source_entity_types

        deictic_types = self._source_reference_types(source_expression) if source_expression else ()
        deictic = deictic_types is not None

        if focus.state is SessionContextFocusState.RESOLVED:
            source = focus.active_entity
            if source is None or not compatible(source):
                return None
            if not source_expression:
                selected = source
            elif deictic:
                if deictic_types and source.entity_type not in deictic_types:
                    return None
                selected = source
            else:
                refined = self._refined_candidates(source_expression, (source,))
                if len(refined) != 1:
                    return None
                selected = source
            return SessionContextResolution(
                status=SessionContextResolutionStatus.RESOLVED,
                hint=self._hint(rule=rule, source=selected),
                selected_entity=selected,
                reasons=(
                    "session-context-relation-follow-up-detected",
                    f"bounded-relation:{rule.relation_type}:{rule.direction}",
                    "relation-source-stable-id-bound-in-immutable-routing-hint",
                    "related-entities-must-come-from-get-tool-relationship-evidence",
                ),
            )

        if focus.state not in {SessionContextFocusState.AMBIGUOUS, SessionContextFocusState.MULTIPLE}:
            return None
        if not source_expression or deictic:
            return SessionContextResolution(
                status=SessionContextResolutionStatus.AMBIGUOUS,
                hint=None,
                selected_entity=None,
                reasons=(
                    "session-context-relation-source-remains-multi-candidate",
                    "previous-tool-evidence-does-not-identify-one-relation-source",
                    "model-guessing-blocked",
                ),
            )

        ordinal = self._ordinal_candidate(source_expression, candidates)
        if ordinal is not None:
            if not compatible(ordinal):
                return None
            return SessionContextResolution(
                status=SessionContextResolutionStatus.RESOLVED,
                hint=self._hint(rule=rule, source=ordinal),
                selected_entity=ordinal,
                reasons=(
                    "session-context-relation-source-ordinal-selected",
                    "selection-bounded-to-prior-tool-evidence",
                    "relation-source-stable-id-bound-in-immutable-routing-hint",
                ),
            )

        refined = self._refined_candidates(source_expression, candidates)
        if len(refined) == 1 and compatible(refined[0]):
            source = refined[0]
            return SessionContextResolution(
                status=SessionContextResolutionStatus.RESOLVED,
                hint=self._hint(rule=rule, source=source),
                selected_entity=source,
                reasons=(
                    "session-context-relation-source-refined-from-prior-evidence",
                    "exactly-one-prior-tool-evidence-candidate-matched",
                    "relation-source-stable-id-bound-in-immutable-routing-hint",
                ),
            )
        if len(refined) > 1:
            return SessionContextResolution(
                status=SessionContextResolutionStatus.AMBIGUOUS,
                hint=None,
                selected_entity=None,
                reasons=(
                    "session-context-relation-source-refinement-remains-ambiguous",
                    "multiple-prior-tool-evidence-candidates-still-match",
                    "model-guessing-blocked",
                ),
            )
        return None
