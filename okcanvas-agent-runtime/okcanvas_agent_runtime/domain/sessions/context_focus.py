from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class SessionContextFocusState(StrEnum):
    EMPTY = "EMPTY"
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    MULTIPLE = "MULTIPLE"


_ALLOWED_ENTITY_TYPES = {
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


@dataclass(frozen=True)
class SessionContextEntityRef:
    entity_type: str
    entity_id: str
    label: str
    qualifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.entity_type not in _ALLOWED_ENTITY_TYPES:
            raise ValueError("Session context entity type is unsupported")
        if not self.entity_id or len(self.entity_id) > 200 or any(c in self.entity_id for c in "\x00\r\n"):
            raise ValueError("Session context entity ID is invalid")
        if not self.label or len(self.label) > 300 or any(c in self.label for c in "\x00\r\n"):
            raise ValueError("Session context entity label is invalid")
        if len(self.qualifiers) > 8:
            raise ValueError("Session context entity qualifiers exceed the bounded limit")
        for value in self.qualifiers:
            if not value or len(value) > 200 or any(c in value for c in "\x00\r\n"):
                raise ValueError("Session context entity qualifier is invalid")

    def to_public_dict(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "label": self.label,
            "qualifiers": list(self.qualifiers),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SessionContextEntityRef":
        if set(value) != {"entity_type", "entity_id", "label", "qualifiers"}:
            raise ValueError("Session context entity keys are not exact")
        entity_type = value.get("entity_type")
        entity_id = value.get("entity_id")
        label = value.get("label")
        qualifiers = value.get("qualifiers")
        if not isinstance(entity_type, str) or not isinstance(entity_id, str) or not isinstance(label, str):
            raise ValueError("Session context entity identity fields must be text")
        if not isinstance(qualifiers, list) or any(not isinstance(item, str) for item in qualifiers):
            raise ValueError("Session context entity qualifiers must be a text list")
        return cls(
            entity_type=entity_type,
            entity_id=entity_id,
            label=label,
            qualifiers=tuple(qualifiers),
        )


@dataclass(frozen=True)
class SessionContextFocusObservation:
    domain: str
    state: SessionContextFocusState
    candidates: tuple[SessionContextEntityRef, ...]
    catalog_revision: int | None = None

    def __post_init__(self) -> None:
        if self.domain != "ORGANIZATION_CONTEXT":
            raise ValueError("Session context focus domain is unsupported")
        if len(self.candidates) > 20:
            raise ValueError("Session context focus candidates exceed the bounded limit")
        identities = {(item.entity_type, item.entity_id) for item in self.candidates}
        if len(identities) != len(self.candidates):
            raise ValueError("Session context focus candidates must be unique")
        if self.state is SessionContextFocusState.EMPTY and self.candidates:
            raise ValueError("EMPTY Session context focus cannot contain candidates")
        if self.state is SessionContextFocusState.RESOLVED and len(self.candidates) != 1:
            raise ValueError("RESOLVED Session context focus requires exactly one candidate")
        if self.state in {SessionContextFocusState.AMBIGUOUS, SessionContextFocusState.MULTIPLE} and len(self.candidates) < 2:
            raise ValueError("Multi-candidate Session context focus requires at least two candidates")
        if self.catalog_revision is not None and self.catalog_revision < 0:
            raise ValueError("Session context catalog revision cannot be negative")

    @property
    def active_entity(self) -> SessionContextEntityRef | None:
        return self.candidates[0] if self.state is SessionContextFocusState.RESOLVED else None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-session-context-focus-observation-v1",
            "domain": self.domain,
            "state": self.state.value,
            "candidates": [item.to_public_dict() for item in self.candidates],
            "catalog_revision": self.catalog_revision,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_public_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SessionContextFocusObservation":
        if set(value) != {"schema_version", "domain", "state", "candidates", "catalog_revision"}:
            raise ValueError("Session context focus observation keys are not exact")
        if value.get("schema_version") != "okcanvas-session-context-focus-observation-v1":
            raise ValueError("Session context focus observation schema is unsupported")
        domain = value.get("domain")
        state = value.get("state")
        raw_candidates = value.get("candidates")
        revision = value.get("catalog_revision")
        if not isinstance(domain, str) or not isinstance(state, str):
            raise ValueError("Session context focus domain/state must be text")
        if not isinstance(raw_candidates, list):
            raise ValueError("Session context focus candidates must be a list")
        if revision is not None and (not isinstance(revision, int) or isinstance(revision, bool)):
            raise ValueError("Session context catalog revision must be an integer")
        if any(not isinstance(item, Mapping) for item in raw_candidates):
            raise ValueError("Session context focus candidates must contain objects only")
        return cls(
            domain=domain,
            state=SessionContextFocusState(state),
            candidates=tuple(SessionContextEntityRef.from_mapping(item) for item in raw_candidates),
            catalog_revision=revision,
        )


@dataclass(frozen=True)
class SessionContextFocusRecord:
    session_id: str
    observation: SessionContextFocusObservation
    source_run_id: str
    source_turn_count: int
    updated_at: str

    def __post_init__(self) -> None:
        if not self.session_id or len(self.session_id) > 200 or any(c in self.session_id for c in "\x00\r\n"):
            raise ValueError("Session context focus session ID is invalid")
        if not self.source_run_id or len(self.source_run_id) > 200 or any(c in self.source_run_id for c in "\x00\r\n"):
            raise ValueError("Session context focus source Run ID is invalid")
        if self.source_turn_count < 1:
            raise ValueError("Session context focus source Turn count must be positive")
        if not self.updated_at or len(self.updated_at) > 100 or any(c in self.updated_at for c in "\x00\r\n"):
            raise ValueError("Session context focus update timestamp is invalid")

    @property
    def state(self) -> SessionContextFocusState:
        return self.observation.state

    @property
    def candidates(self) -> tuple[SessionContextEntityRef, ...]:
        return self.observation.candidates

    @property
    def active_entity(self) -> SessionContextEntityRef | None:
        return self.observation.active_entity

    @property
    def catalog_revision(self) -> int | None:
        return self.observation.catalog_revision

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-session-context-focus-v1",
            "session_id": self.session_id,
            "domain": self.observation.domain,
            "state": self.state.value,
            "active_entity": self.active_entity.to_public_dict() if self.active_entity else None,
            "candidates": [item.to_public_dict() for item in self.candidates],
            "catalog_revision": self.catalog_revision,
            "source_run_id": self.source_run_id,
            "source_turn_count": self.source_turn_count,
            "updated_at": self.updated_at,
        }
