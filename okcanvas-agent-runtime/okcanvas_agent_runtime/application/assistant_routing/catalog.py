from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    AssistantCapability,
    CapabilityAvailability,
    OrganizationContextPreferredOperation,
    OrganizationContextRequestHint,
)


class AssistantRoutingPolicyError(RuntimeError):
    code = "ASSISTANT_ROUTING_POLICY_INVALID"


_PATTERN_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,79}$")
_INTENT_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
_FIELD_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_ENTITY_TYPES = {
    "TERM",
    "DEPARTMENT",
    "POSITION",
    "EMPLOYEE",
    "PRODUCT",
    "CLIENT",
    "PROJECT",
    "SYSTEM",
    "CAPABILITY",
}
_TERMINAL_PUNCTUATION = "?.!。！？"


@dataclass(frozen=True)
class OrganizationContextShortReadRule:
    pattern_id: str
    intent: str
    suffixes: tuple[str, ...]
    entity_type_hints: tuple[str, ...]
    requested_fields: tuple[str, ...]
    preferred_operation: OrganizationContextPreferredOperation
    min_target_chars: int
    max_target_chars: int

    def match(self, request: str) -> OrganizationContextRequestHint | None:
        canonical = " ".join(request.strip().split()).rstrip(_TERMINAL_PUNCTUATION).strip()
        normalized = canonical.casefold()
        for suffix in self.suffixes:
            if not normalized.endswith(suffix.casefold()):
                continue
            target = canonical[: len(canonical) - len(suffix)].strip()
            if not self.min_target_chars <= len(target) <= self.max_target_chars:
                continue
            if any(character in target for character in "\x00\r\n"):
                continue
            return OrganizationContextRequestHint(
                pattern_id=self.pattern_id,
                intent=self.intent,
                target_expression=target,
                entity_type_hints=self.entity_type_hints,
                requested_fields=self.requested_fields,
                preferred_operation=self.preferred_operation,
            )
        return None


@dataclass(frozen=True)
class AssistantRoutingPolicy:
    policy_id: str
    version: str
    default_agent_id: str
    session_agent_id: str
    capabilities: dict[str, AssistantCapability]
    lexicons: dict[str, tuple[str, ...]]
    organization_context_short_read_rules: tuple[OrganizationContextShortReadRule, ...]
    policy_sha256: str

    def match_organization_context_short_read(
        self, request: str
    ) -> OrganizationContextRequestHint | None:
        for rule in self.organization_context_short_read_rules:
            matched = rule.match(request)
            if matched is not None:
                return matched
        return None


class AssistantRoutingPolicyCatalog:
    _TOP_KEYS = {
        "schema_version",
        "policy_id",
        "version",
        "default_agent_id",
        "session_agent_id",
        "capabilities",
        "lexicons",
        "organization_context_short_read_rules",
    }
    _LEXICONS = {
        "automation",
        "organization",
        "enterprise_system",
        "enterprise_transaction",
        "groupware",
        "write_action",
        "draft_action",
        "read_action",
        "web",
        "code",
        "content_draft",
        "session_reference",
        "session_restatement",
        "external_refresh",
    }
    _SHORT_READ_RULE_KEYS = {
        "pattern_id",
        "intent",
        "suffixes",
        "entity_type_hints",
        "requested_fields",
        "preferred_operation",
        "min_target_chars",
        "max_target_chars",
    }

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "assistant" / "routing-policy.json"

    def resolve(self) -> AssistantRoutingPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise AssistantRoutingPolicyError("Assistant routing policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssistantRoutingPolicyError(
                "Assistant routing policy is not valid UTF-8 JSON"
            ) from exc
        if not isinstance(payload, dict) or set(payload) != self._TOP_KEYS:
            raise AssistantRoutingPolicyError("Assistant routing policy keys are not exact")
        if payload["schema_version"] != "okcanvas-organization-assistant-routing-policy-v1":
            raise AssistantRoutingPolicyError("Assistant routing policy schema is unsupported")
        capabilities = self._capabilities(payload["capabilities"])
        lexicons = self._lexicons(payload["lexicons"])
        short_read_rules = self._short_read_rules(
            payload["organization_context_short_read_rules"]
        )
        return AssistantRoutingPolicy(
            policy_id=self._text(payload, "policy_id"),
            version=self._text(payload, "version"),
            default_agent_id=self._text(payload, "default_agent_id"),
            session_agent_id=self._text(payload, "session_agent_id"),
            capabilities=capabilities,
            lexicons=lexicons,
            organization_context_short_read_rules=short_read_rules,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    def _capabilities(self, capabilities_raw: object) -> dict[str, AssistantCapability]:
        if not isinstance(capabilities_raw, list) or not capabilities_raw:
            raise AssistantRoutingPolicyError("Assistant capability catalog must be non-empty")
        capabilities: dict[str, AssistantCapability] = {}
        for item in capabilities_raw:
            if not isinstance(item, dict) or set(item) != {
                "capability_id",
                "availability",
                "selected_agent_id",
                "side_effect",
            }:
                raise AssistantRoutingPolicyError("Assistant capability entry keys are not exact")
            capability_id = self._text(item, "capability_id")
            if capability_id in capabilities:
                raise AssistantRoutingPolicyError("Assistant capability IDs must be unique")
            try:
                availability = CapabilityAvailability(self._text(item, "availability"))
            except ValueError as exc:
                raise AssistantRoutingPolicyError(
                    "Assistant capability availability is invalid"
                ) from exc
            selected = item["selected_agent_id"]
            if selected is not None and (
                not isinstance(selected, str) or not selected.strip()
            ):
                raise AssistantRoutingPolicyError(
                    "Selected Agent ID must be null or non-empty"
                )
            if availability is CapabilityAvailability.AVAILABLE and not selected:
                raise AssistantRoutingPolicyError(
                    "Available capability requires a selected Agent"
                )
            if availability is not CapabilityAvailability.AVAILABLE and selected is not None:
                raise AssistantRoutingPolicyError(
                    "Unavailable capability cannot select an Agent"
                )
            capabilities[capability_id] = AssistantCapability(
                capability_id=capability_id,
                availability=availability,
                selected_agent_id=selected,
                side_effect=self._text(item, "side_effect"),
            )
        return capabilities

    def _lexicons(self, lexicons_raw: object) -> dict[str, tuple[str, ...]]:
        if not isinstance(lexicons_raw, dict) or set(lexicons_raw) != self._LEXICONS:
            raise AssistantRoutingPolicyError("Assistant routing lexicons are not exact")
        lexicons: dict[str, tuple[str, ...]] = {}
        for name, values in lexicons_raw.items():
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise AssistantRoutingPolicyError(
                    f"Assistant routing lexicon is invalid: {name}"
                )
            normalized = tuple(value.casefold() for value in values)
            if len(normalized) != len(set(normalized)):
                raise AssistantRoutingPolicyError(
                    f"Assistant routing lexicon contains duplicates: {name}"
                )
            lexicons[name] = normalized
        return lexicons

    def _short_read_rules(
        self, rules_raw: object
    ) -> tuple[OrganizationContextShortReadRule, ...]:
        if not isinstance(rules_raw, list) or not rules_raw:
            raise AssistantRoutingPolicyError(
                "Organization Context short-read rules must be non-empty"
            )
        rules: list[OrganizationContextShortReadRule] = []
        pattern_ids: set[str] = set()
        suffixes_seen: set[str] = set()
        for item in rules_raw:
            if not isinstance(item, dict) or set(item) != self._SHORT_READ_RULE_KEYS:
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read rule keys are not exact"
                )
            pattern_id = self._text(item, "pattern_id")
            intent = self._text(item, "intent")
            if not _PATTERN_ID_RE.fullmatch(pattern_id):
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read pattern ID is invalid"
                )
            if pattern_id in pattern_ids:
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read pattern IDs must be unique"
                )
            if not _INTENT_RE.fullmatch(intent):
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read intent is invalid"
                )
            suffixes = self._string_tuple(item, "suffixes")
            normalized_suffixes = tuple(value.casefold() for value in suffixes)
            if any(value in suffixes_seen for value in normalized_suffixes):
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read suffixes must be globally unique"
                )
            if any(len(value) < 2 for value in suffixes):
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read suffix is too short"
                )
            suffixes_seen.update(normalized_suffixes)
            entity_type_hints = self._string_tuple(
                item, "entity_type_hints", allow_empty=True
            )
            if any(value not in _ENTITY_TYPES for value in entity_type_hints):
                raise AssistantRoutingPolicyError(
                    "Organization Context entity type hint is invalid"
                )
            requested_fields = self._string_tuple(item, "requested_fields")
            if any(not _FIELD_RE.fullmatch(value) for value in requested_fields):
                raise AssistantRoutingPolicyError(
                    "Organization Context requested field is invalid"
                )
            try:
                preferred_operation = OrganizationContextPreferredOperation(
                    self._text(item, "preferred_operation")
                )
            except ValueError as exc:
                raise AssistantRoutingPolicyError(
                    "Organization Context preferred operation is invalid"
                ) from exc
            minimum = item["min_target_chars"]
            maximum = item["max_target_chars"]
            if (
                not isinstance(minimum, int)
                or isinstance(minimum, bool)
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or not 1 <= minimum <= maximum <= 128
            ):
                raise AssistantRoutingPolicyError(
                    "Organization Context short-read target bounds are invalid"
                )
            rules.append(
                OrganizationContextShortReadRule(
                    pattern_id=pattern_id,
                    intent=intent,
                    suffixes=suffixes,
                    entity_type_hints=entity_type_hints,
                    requested_fields=requested_fields,
                    preferred_operation=preferred_operation,
                    min_target_chars=minimum,
                    max_target_chars=maximum,
                )
            )
            pattern_ids.add(pattern_id)
        return tuple(rules)

    @staticmethod
    def _text(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise AssistantRoutingPolicyError(f"{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _string_tuple(
        payload: dict[str, Any], key: str, *, allow_empty: bool = False
    ) -> tuple[str, ...]:
        value = payload[key]
        if not isinstance(value, list) or (not allow_empty and not value) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise AssistantRoutingPolicyError(f"{key} must be a string list")
        normalized = tuple(item.strip() for item in value)
        if len(normalized) != len(set(normalized)):
            raise AssistantRoutingPolicyError(f"{key} contains duplicates")
        return normalized
