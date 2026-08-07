from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ProductSessionState(StrEnum):
    ACTIVE = "ACTIVE"
    CLEARING = "CLEARING"
    CLEARED = "CLEARED"


@dataclass(frozen=True)
class SQLiteSessionPolicy:
    schema_version: str
    policy_id: str
    version: str
    session_mode: str
    max_active_turns: int
    history_limit: int | None
    compaction_enabled: bool
    compaction_mode: str
    compaction_provider: str
    compaction_api: str
    compaction_model: str
    compaction_trigger_candidate_items: int
    compaction_max_input_items: int
    compaction_store: bool
    compaction_previous_response_id_allowed: bool
    compaction_automatic: bool
    compaction_restore_previous_on_failure: bool
    compaction_raw_history_in_events: bool
    encryption_enabled: bool
    encryption_mode: str
    encryption_envelope_version: int
    key_derivation: str
    legacy_plaintext_mode: str
    ttl_seconds: int | None
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductSessionRecord:
    session_id: str
    state: ProductSessionState
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

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["schema_version"] = "okcanvas-product-session-v2"
        return payload
