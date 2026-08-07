from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.capabilities.topology.errors import CapabilityContractError, CapabilityIntegrityError
from okcanvas_agent_runtime.agent.capabilities.topology.models import CapabilityActivation, CapabilityFamily, SDKExampleInventory, SDKExampleRecord

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,95}$")
_RECORD_KEYS = {
    "example_id",
    "relative_path",
    "family",
    "pattern",
    "product_status",
    "rationale",
    "sha256",
}
_KEYS = {"schema_version", "sdk_package", "sdk_version", "records"}


class SDKExampleCatalog:
    """Validate the pinned SDK example inventory without importing upstream code."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.manifest_path = (
            self.project_root
            / "specs"
            / "capabilities"
            / "examples"
            / "openai-agents-python-0.19.0.json"
        ).resolve()
        self.examples_root = (
            self.project_root
            / "reference"
            / "upstream"
            / "openai-agents-python-0.19.0"
            / "examples"
        ).resolve()

    def resolve(self, *, require_sources: bool = True) -> SDKExampleInventory:
        expected_parent = (
            self.project_root / "specs" / "capabilities" / "examples"
        ).resolve()
        if (
            self.manifest_path.is_symlink()
            or self.manifest_path.parent != expected_parent
            or not self.manifest_path.is_file()
        ):
            raise CapabilityIntegrityError("SDK example inventory is missing or unsafe")
        raw = self.manifest_path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CapabilityIntegrityError("SDK example inventory is invalid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise CapabilityContractError("SDK example inventory keys mismatch")
        if payload["schema_version"] != "okcanvas-sdk-example-inventory-v1":
            raise CapabilityContractError("Unsupported SDK example inventory schema")
        if payload["sdk_package"] != "openai-agents" or payload["sdk_version"] != "0.19.0":
            raise CapabilityContractError("SDK example inventory must pin openai-agents 0.19.0")
        records_payload = payload["records"]
        if not isinstance(records_payload, list) or not 16 <= len(records_payload) <= 128:
            raise CapabilityContractError("SDK example inventory must contain 16..128 records")
        records: list[SDKExampleRecord] = []
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for item in records_payload:
            if not isinstance(item, dict) or set(item) != _RECORD_KEYS:
                raise CapabilityContractError("SDK example record keys mismatch")
            example_id = self._identifier(item, "example_id")
            if example_id in seen_ids:
                raise CapabilityContractError("SDK example IDs must be unique")
            seen_ids.add(example_id)
            relative_path = self._relative_path(item.get("relative_path"))
            if relative_path in seen_paths:
                raise CapabilityContractError("SDK example paths must be unique")
            seen_paths.add(relative_path)
            declared_sha = item.get("sha256")
            if not isinstance(declared_sha, str) or len(declared_sha) != 64 or any(
                character not in "0123456789abcdef" for character in declared_sha
            ):
                raise CapabilityContractError("SDK example source SHA is invalid")
            actual_sha = declared_sha
            if require_sources:
                source_path = self._safe_source(relative_path)
                actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
                if declared_sha != actual_sha:
                    raise CapabilityIntegrityError(
                        f"SDK example source SHA mismatch: {relative_path}"
                    )
            try:
                family = CapabilityFamily(item["family"])
                product_status = CapabilityActivation(item["product_status"])
            except (ValueError, TypeError) as exc:
                raise CapabilityContractError("SDK example family/status is invalid") from exc
            pattern = self._string(item, "pattern", 120)
            rationale = self._string(item, "rationale", 1000)
            records.append(
                SDKExampleRecord(
                    example_id=example_id,
                    relative_path=relative_path,
                    family=family,
                    pattern=pattern,
                    product_status=product_status,
                    rationale=rationale,
                    sha256=actual_sha,
                )
            )
        family_set = {record.family for record in records}
        required = {
            CapabilityFamily.TOOL,
            CapabilityFamily.SKILL,
            CapabilityFamily.SUB_AGENT,
            CapabilityFamily.MCP,
            CapabilityFamily.GUARDRAIL,
            CapabilityFamily.WORKSPACE,
        }
        if not required.issubset(family_set):
            raise CapabilityContractError("SDK example inventory does not cover all core families")
        return SDKExampleInventory(
            schema_version=str(payload["schema_version"]),
            sdk_package="openai-agents",
            sdk_version="0.19.0",
            records=tuple(records),
            inventory_sha256=hashlib.sha256(raw).hexdigest(),
            manifest_path=self.manifest_path,
        )

    def _safe_source(self, relative_path: str) -> Path:
        path = self.examples_root.joinpath(*Path(relative_path).parts)
        if path.is_symlink() or not path.is_file():
            raise CapabilityIntegrityError(f"SDK example source is missing or unsafe: {relative_path}")
        resolved = path.resolve()
        if self.examples_root not in resolved.parents:
            raise CapabilityIntegrityError("SDK example source escapes pinned examples root")
        return resolved

    @staticmethod
    def _relative_path(value: Any) -> str:
        if not isinstance(value, str) or not value or "\\" in value or len(value) > 240:
            raise CapabilityContractError("SDK example relative_path is invalid")
        path = Path(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise CapabilityContractError("SDK example relative_path is unsafe")
        return path.as_posix()

    @staticmethod
    def _string(payload: dict[str, Any], key: str, maximum: int) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
            raise CapabilityContractError(f"SDK example {key} is invalid")
        return value

    @classmethod
    def _identifier(cls, payload: dict[str, Any], key: str) -> str:
        value = cls._string(payload, key, 96)
        if not _ID_RE.fullmatch(value):
            raise CapabilityContractError("SDK example ID is invalid")
        return value
