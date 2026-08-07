from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


class ArchitectureConstitutionError(ValueError):
    """Raised when the packaged architecture constitution is incomplete or corrupted."""


def _canonical_sha(payload: dict[str, Any]) -> str:
    normalized = dict(payload)
    normalized.pop("constitution_sha256", None)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ArchitectureConstitutionSnapshot:
    schema_version: str
    constitution_id: str
    constitution_version: str
    authority_state: str
    source_step: str
    source_version: str
    implementation_state: str
    clause_count: int
    required_gate_count: int
    normative_annex_count: int
    source_inventory_count: int
    constitution_sha256: str
    product_source_movement_allowed: bool

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "constitution_id": self.constitution_id,
            "constitution_version": self.constitution_version,
            "authority_state": self.authority_state,
            "source_step": self.source_step,
            "source_version": self.source_version,
            "implementation_state": self.implementation_state,
            "clause_count": self.clause_count,
            "required_gate_count": self.required_gate_count,
            "normative_annex_count": self.normative_annex_count,
            "source_inventory_count": self.source_inventory_count,
            "constitution_sha256": self.constitution_sha256,
            "product_source_movement_allowed": self.product_source_movement_allowed,
        }


def _load_resource(name: str) -> dict[str, Any]:
    resource = files("okcanvas_agent_runtime.core.governance.resources").joinpath(name)
    try:
        raw = resource.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchitectureConstitutionError(
            f"Architecture constitution resource {name!r} is unavailable or invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise ArchitectureConstitutionError(
            f"Architecture constitution resource {name!r} must contain an object"
        )
    return payload


def resolve_architecture_constitution() -> ArchitectureConstitutionSnapshot:
    payload = _load_resource("architecture_constitution.json")
    gate_payload = _load_resource("constitution_gate_catalog.json")

    clauses = payload.get("clauses")
    required_gate_ids = payload.get("required_gate_ids")
    annexes = payload.get("normative_annexes")
    source_inventory = payload.get("source_inventory")
    if not isinstance(clauses, list) or len(clauses) != 127:
        raise ArchitectureConstitutionError("Architecture constitution must contain 127 clauses")
    if not isinstance(required_gate_ids, list) or len(required_gate_ids) != 32:
        raise ArchitectureConstitutionError("Architecture constitution must contain 32 required gates")
    if not isinstance(annexes, list) or len(annexes) != 12:
        raise ArchitectureConstitutionError("Architecture constitution must contain 12 normative annex records")
    if not isinstance(source_inventory, list) or len(source_inventory) != 9:
        raise ArchitectureConstitutionError("Architecture constitution must contain 9 source inventory records")

    clause_ids = [item.get("id") for item in clauses if isinstance(item, dict)]
    if len(clause_ids) != len(clauses) or len(set(clause_ids)) != len(clause_ids):
        raise ArchitectureConstitutionError("Architecture constitution clause IDs must be unique")
    gate_ids = set(required_gate_ids)
    if len(gate_ids) != len(required_gate_ids):
        raise ArchitectureConstitutionError("Architecture constitution gate IDs must be unique")
    for clause in clauses:
        if not isinstance(clause, dict):
            raise ArchitectureConstitutionError("Architecture constitution clauses must be objects")
        referenced = clause.get("required_gates", [])
        if not isinstance(referenced, list) or not set(referenced).issubset(gate_ids):
            raise ArchitectureConstitutionError(
                f"Clause {clause.get('id')} references an unknown required gate"
            )

    catalog_gates = gate_payload.get("gates")
    if not isinstance(catalog_gates, list):
        raise ArchitectureConstitutionError("Architecture constitution gate catalog is invalid")
    catalog_ids = {
        item.get("gate_id") for item in catalog_gates if isinstance(item, dict)
    }
    if catalog_ids != gate_ids:
        raise ArchitectureConstitutionError(
            "Architecture constitution gate catalog does not match required gate IDs"
        )
    if not all(item.get("mandatory") is True for item in catalog_gates):
        raise ArchitectureConstitutionError("All constitution gates must be mandatory")

    expected_sha = payload.get("constitution_sha256")
    actual_sha = _canonical_sha(payload)
    if expected_sha != actual_sha:
        raise ArchitectureConstitutionError(
            "Architecture constitution canonical SHA-256 does not match"
        )

    source = payload.get("product_source_baseline")
    if not isinstance(source, dict):
        raise ArchitectureConstitutionError("Architecture constitution source baseline is missing")

    return ArchitectureConstitutionSnapshot(
        schema_version=str(payload.get("schema_version")),
        constitution_id=str(payload.get("constitution_id")),
        constitution_version=str(payload.get("constitution_version")),
        authority_state=str(payload.get("authority_state")),
        source_step=str(source.get("step")),
        source_version=str(source.get("version")),
        implementation_state=str(payload.get("implementation_state")),
        clause_count=len(clauses),
        required_gate_count=len(required_gate_ids),
        normative_annex_count=len(annexes),
        source_inventory_count=len(source_inventory),
        constitution_sha256=str(expected_sha),
        product_source_movement_allowed=False,
    )
