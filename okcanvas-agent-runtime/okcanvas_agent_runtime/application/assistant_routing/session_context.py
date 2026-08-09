from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextEntityRef,
    SessionContextFocusRecord,
    SessionContextFocusState,
)

from .models import OrganizationContextPreferredOperation, OrganizationContextRequestHint

_TERMINAL_PUNCTUATION = "?.!。！？"
_ALLOWED_ENTITY_TYPES = {
    "TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT",
    "SYSTEM", "CAPABILITY",
}


class SessionContextFollowUpPolicyError(RuntimeError):
    code = "SESSION_CONTEXT_FOLLOW_UP_POLICY_INVALID"


class SessionContextResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class DeicticReferenceRule:
    expressions: tuple[str, ...]
    entity_types: tuple[str, ...]


@dataclass(frozen=True)
class TargetlessFormRule:
    pattern_id: str
    forms: tuple[str, ...]


@dataclass(frozen=True)
class OrdinalSelectorRule:
    ordinal: int
    expressions: tuple[str, ...]


@dataclass(frozen=True)
class SessionContextFollowUpPolicy:
    policy_id: str
    version: str
    deictic_references: tuple[DeicticReferenceRule, ...]
    targetless_forms: tuple[TargetlessFormRule, ...]
    continuation_prefixes: tuple[str, ...]
    ordinal_selectors: tuple[OrdinalSelectorRule, ...]
    max_candidates: int
    policy_sha256: str


@dataclass(frozen=True)
class SessionContextResolution:
    status: SessionContextResolutionStatus
    hint: OrganizationContextRequestHint | None
    selected_entity: SessionContextEntityRef | None
    reasons: tuple[str, ...]


class SessionContextFollowUpPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.path = Path(project_root).expanduser().resolve() / "specs" / "assistant" / "session-context-follow-up-policy.json"

    def resolve(self) -> SessionContextFollowUpPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise SessionContextFollowUpPolicyError("Session contextual follow-up policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SessionContextFollowUpPolicyError("Session contextual follow-up policy is invalid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version", "policy_id", "version", "deictic_references", "targetless_forms",
            "continuation_prefixes", "ordinal_selectors", "max_candidates",
        }:
            raise SessionContextFollowUpPolicyError("Session contextual follow-up policy keys are not exact")
        if payload["schema_version"] != "okcanvas-session-context-follow-up-policy-v1":
            raise SessionContextFollowUpPolicyError("Session contextual follow-up policy schema is unsupported")
        max_candidates = payload["max_candidates"]
        if not isinstance(max_candidates, int) or not 2 <= max_candidates <= 20:
            raise SessionContextFollowUpPolicyError("Session contextual follow-up candidate bound is invalid")
        return SessionContextFollowUpPolicy(
            policy_id=self._text(payload, "policy_id"),
            version=self._text(payload, "version"),
            deictic_references=self._deictic(payload["deictic_references"]),
            targetless_forms=self._targetless(payload["targetless_forms"]),
            continuation_prefixes=self._expressions(payload["continuation_prefixes"]),
            ordinal_selectors=self._ordinals(payload["ordinal_selectors"]),
            max_candidates=max_candidates,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _text(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SessionContextFollowUpPolicyError(f"Session contextual follow-up {key} is invalid")
        return value.strip()

    @staticmethod
    def _expressions(value: object) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise SessionContextFollowUpPolicyError("Session contextual follow-up expressions are invalid")
        result = tuple(str(item).strip() for item in value if isinstance(item, str) and item.strip())
        if len(result) != len(value) or len(set(item.casefold() for item in result)) != len(result):
            raise SessionContextFollowUpPolicyError("Session contextual follow-up expressions must be unique text")
        return result

    def _deictic(self, value: object) -> tuple[DeicticReferenceRule, ...]:
        if not isinstance(value, list) or not value:
            raise SessionContextFollowUpPolicyError("Session contextual deictic rules are invalid")
        result: list[DeicticReferenceRule] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict) or set(item) != {"entity_types", "expressions"}:
                raise SessionContextFollowUpPolicyError("Session contextual deictic rule keys are not exact")
            types = item["entity_types"]
            if not isinstance(types, list) or any(t not in _ALLOWED_ENTITY_TYPES for t in types):
                raise SessionContextFollowUpPolicyError("Session contextual deictic entity types are invalid")
            expressions = self._expressions(item["expressions"])
            for expression in expressions:
                folded = expression.casefold()
                if folded in seen:
                    raise SessionContextFollowUpPolicyError("Session contextual deictic expressions overlap")
                seen.add(folded)
            result.append(DeicticReferenceRule(expressions=expressions, entity_types=tuple(types)))
        return tuple(result)

    def _targetless(self, value: object) -> tuple[TargetlessFormRule, ...]:
        if not isinstance(value, list) or not value:
            raise SessionContextFollowUpPolicyError("Session contextual targetless rules are invalid")
        result: list[TargetlessFormRule] = []
        patterns: set[str] = set()
        forms_seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict) or set(item) != {"pattern_id", "forms"}:
                raise SessionContextFollowUpPolicyError("Session contextual targetless rule keys are not exact")
            pattern_id = str(item["pattern_id"]).strip()
            if not pattern_id or pattern_id in patterns:
                raise SessionContextFollowUpPolicyError("Session contextual targetless pattern is invalid")
            patterns.add(pattern_id)
            forms = self._expressions(item["forms"])
            for form in forms:
                folded = form.casefold()
                if folded in forms_seen:
                    raise SessionContextFollowUpPolicyError("Session contextual targetless forms overlap")
                forms_seen.add(folded)
            result.append(TargetlessFormRule(pattern_id=pattern_id, forms=forms))
        return tuple(result)

    def _ordinals(self, value: object) -> tuple[OrdinalSelectorRule, ...]:
        if not isinstance(value, list):
            raise SessionContextFollowUpPolicyError("Session contextual ordinal rules are invalid")
        result: list[OrdinalSelectorRule] = []
        ordinals: set[int] = set()
        expressions_seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict) or set(item) != {"ordinal", "expressions"}:
                raise SessionContextFollowUpPolicyError("Session contextual ordinal rule keys are not exact")
            ordinal = item["ordinal"]
            if not isinstance(ordinal, int) or ordinal < 1 or ordinal > 20 or ordinal in ordinals:
                raise SessionContextFollowUpPolicyError("Session contextual ordinal is invalid")
            ordinals.add(ordinal)
            expressions = self._expressions(item["expressions"])
            for expression in expressions:
                folded = expression.casefold()
                if folded in expressions_seen:
                    raise SessionContextFollowUpPolicyError("Session contextual ordinal expressions overlap")
                expressions_seen.add(folded)
            result.append(OrdinalSelectorRule(ordinal=ordinal, expressions=expressions))
        return tuple(result)


class SessionContextFollowUpResolver:
    def __init__(self, policy: SessionContextFollowUpPolicy, routing_policy) -> None:
        self.policy = policy
        self.routing_policy = routing_policy
        self._short_rules = {rule.pattern_id: rule for rule in routing_policy.organization_context_short_read_rules}
        for targetless in policy.targetless_forms:
            if targetless.pattern_id not in self._short_rules:
                raise SessionContextFollowUpPolicyError(
                    f"Session contextual targetless pattern is not a routing short-read rule: {targetless.pattern_id}"
                )

    @staticmethod
    def _canonical(request: str) -> str:
        return " ".join(request.strip().split()).rstrip(_TERMINAL_PUNCTUATION).strip()

    def _deictic_rule(self, value: str) -> DeicticReferenceRule | None:
        normalized = value.casefold().strip()
        for rule in self.policy.deictic_references:
            if normalized in {item.casefold() for item in rule.expressions}:
                return rule
        return None

    def _targetless_pattern(self, canonical: str) -> str | None:
        normalized = canonical.casefold()
        for rule in self.policy.targetless_forms:
            if normalized in {item.casefold() for item in rule.forms}:
                return rule.pattern_id
        return None

    def _strip_continuation_prefix(self, canonical: str) -> tuple[str, bool]:
        folded = canonical.casefold()
        for prefix in self.policy.continuation_prefixes:
            prefix_folded = prefix.casefold()
            if folded == prefix_folded:
                return "", True
            marker = prefix_folded + " "
            if folded.startswith(marker):
                return canonical[len(prefix):].strip(), True
            comma_marker = prefix_folded + ","
            if folded.startswith(comma_marker):
                remainder = canonical[len(prefix) + 1 :].strip()
                return remainder, True
        return canonical, False

    def _field_match(self, canonical: str):
        effective, _continued = self._strip_continuation_prefix(canonical)
        direct = self.routing_policy.match_organization_context_short_read(effective)
        if direct is not None:
            return direct, direct.target_expression
        normalized = effective.casefold()
        for targetless in self.policy.targetless_forms:
            rule = self._short_rules[targetless.pattern_id]
            for form in targetless.forms:
                form_folded = form.casefold()
                if normalized == form_folded:
                    return OrganizationContextRequestHint(
                        pattern_id=rule.pattern_id,
                        intent=rule.intent,
                        target_expression="",
                        entity_type_hints=rule.entity_type_hints,
                        requested_fields=rule.requested_fields,
                        preferred_operation=rule.preferred_operation,
                    ), ""
                suffix = " " + form_folded
                if normalized.endswith(suffix):
                    target = effective[: len(effective) - len(form) - 1].strip()
                    if target:
                        return OrganizationContextRequestHint(
                            pattern_id=rule.pattern_id,
                            intent=rule.intent,
                            target_expression=target,
                            entity_type_hints=rule.entity_type_hints,
                            requested_fields=rule.requested_fields,
                            preferred_operation=rule.preferred_operation,
                        ), target
        return None, None

    @staticmethod
    def _candidate_hint(base_hint: OrganizationContextRequestHint | None, entity: SessionContextEntityRef, *, pattern_id: str) -> OrganizationContextRequestHint:
        if base_hint is None:
            return OrganizationContextRequestHint(
                pattern_id=pattern_id,
                intent="ENTITY_DETAIL_LOOKUP",
                target_expression=entity.entity_id,
                entity_type_hints=(entity.entity_type,),
                requested_fields=("DETAIL",),
                preferred_operation=OrganizationContextPreferredOperation.GET,
            )
        return OrganizationContextRequestHint(
            pattern_id=pattern_id,
            intent=base_hint.intent,
            target_expression=entity.entity_id,
            entity_type_hints=(entity.entity_type,),
            requested_fields=base_hint.requested_fields,
            preferred_operation=OrganizationContextPreferredOperation.GET,
        )

    @staticmethod
    def _candidate_search_text(entity: SessionContextEntityRef) -> str:
        return " ".join((entity.label, entity.entity_id, *entity.qualifiers)).casefold()

    def _ordinal_candidate(self, expression: str, candidates: tuple[SessionContextEntityRef, ...]) -> SessionContextEntityRef | None:
        folded = expression.casefold()
        matched: list[int] = []
        for rule in self.policy.ordinal_selectors:
            if any(token.casefold() in folded for token in rule.expressions):
                matched.append(rule.ordinal)
        if len(set(matched)) != 1:
            return None
        ordinal = matched[0]
        return candidates[ordinal - 1] if ordinal <= len(candidates) else None

    def _refined_candidates(self, expression: str, candidates: tuple[SessionContextEntityRef, ...]) -> tuple[SessionContextEntityRef, ...]:
        canonical = self._canonical(expression)
        if not canonical:
            return ()
        tokens = tuple(token.casefold() for token in canonical.split() if token.strip())
        if not tokens:
            return ()
        return tuple(
            candidate
            for candidate in candidates
            if all(token in self._candidate_search_text(candidate) for token in tokens)
        )

    def resolve(self, *, request: str, focus: SessionContextFocusRecord | None) -> SessionContextResolution | None:
        if focus is None or focus.observation.domain != "ORGANIZATION_CONTEXT" or not focus.candidates:
            return None
        candidates = focus.candidates[: self.policy.max_candidates]
        canonical = self._canonical(request)
        base_hint, target = self._field_match(canonical)
        deictic = self._deictic_rule(target) if target is not None and target else self._deictic_rule(canonical)
        targetless = target == "" and base_hint is not None

        if focus.state is SessionContextFocusState.RESOLVED:
            entity = focus.active_entity
            if entity is None:
                return None
            if deictic is not None:
                if deictic.entity_types and entity.entity_type not in deictic.entity_types:
                    return None
                return SessionContextResolution(
                    status=SessionContextResolutionStatus.RESOLVED,
                    hint=self._candidate_hint(
                        base_hint, entity, pattern_id="session-context-stable-entity-follow-up-v1"
                    ),
                    selected_entity=entity,
                    reasons=(
                        "session-context-follow-up-detected",
                        "previous-tool-evidence-single-stable-entity",
                        "stable-entity-id-bound-in-immutable-read-routing-hint",
                    ),
                )
            if targetless:
                return SessionContextResolution(
                    status=SessionContextResolutionStatus.RESOLVED,
                    hint=self._candidate_hint(
                        base_hint, entity, pattern_id="session-context-ellipsis-follow-up-v1"
                    ),
                    selected_entity=entity,
                    reasons=(
                        "session-context-ellipsis-detected",
                        "previous-tool-evidence-single-stable-entity",
                        "stable-entity-id-bound-in-immutable-read-routing-hint",
                    ),
                )
            return None

        if focus.state not in {SessionContextFocusState.AMBIGUOUS, SessionContextFocusState.MULTIPLE}:
            return None

        reference_expression = target if base_hint is not None and target else canonical
        ordinal = self._ordinal_candidate(reference_expression, candidates)
        if ordinal is not None:
            return SessionContextResolution(
                status=SessionContextResolutionStatus.RESOLVED,
                hint=self._candidate_hint(
                    base_hint, ordinal, pattern_id="session-context-ordinal-candidate-follow-up-v1"
                ),
                selected_entity=ordinal,
                reasons=(
                    "session-context-candidate-ordinal-selected",
                    "selection-bounded-to-prior-tool-evidence",
                    "stable-entity-id-bound-in-immutable-read-routing-hint",
                ),
            )

        if deictic is not None or targetless:
            return SessionContextResolution(
                status=SessionContextResolutionStatus.AMBIGUOUS,
                hint=None,
                selected_entity=None,
                reasons=(
                    "session-context-reference-remains-multi-candidate",
                    "previous-tool-evidence-does-not-identify-one-entity",
                    "model-guessing-blocked",
                ),
            )

        refined = self._refined_candidates(reference_expression, candidates)
        if len(refined) == 1:
            entity = refined[0]
            return SessionContextResolution(
                status=SessionContextResolutionStatus.RESOLVED,
                hint=self._candidate_hint(
                    base_hint, entity, pattern_id="session-context-evidence-candidate-refinement-v1"
                ),
                selected_entity=entity,
                reasons=(
                    "session-context-candidate-refinement-detected",
                    "exactly-one-prior-tool-evidence-candidate-matched",
                    "stable-entity-id-bound-in-immutable-read-routing-hint",
                ),
            )
        if len(refined) > 1:
            return SessionContextResolution(
                status=SessionContextResolutionStatus.AMBIGUOUS,
                hint=None,
                selected_entity=None,
                reasons=(
                    "session-context-candidate-refinement-remains-ambiguous",
                    "multiple-prior-tool-evidence-candidates-still-match",
                    "model-guessing-blocked",
                ),
            )
        return None
