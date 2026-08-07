from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.errors import CommerceSnapshotDefinitionError
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.models import CommerceSnapshotAdapterDefinition

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_ALLOWED_KEYS = {
    "schema_version",
    "adapter_id",
    "version",
    "name",
    "kind",
    "base_url_env",
    "credential_env",
    "auth_scheme",
    "method",
    "path_template",
    "loopback_only",
    "follow_redirects",
    "connect_timeout_seconds",
    "read_timeout_seconds",
    "max_response_bytes",
    "max_items",
    "max_retry_attempts",
}
_ALLOWED_ENV_NAMES = {
    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL",
    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN",
}


class CommerceSnapshotAdapterCatalog:
    """Resolve immutable allowlisted product-owned snapshot ingress adapters."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "commerce-snapshot-ingress").resolve()
        self.adapter_root = (self.spec_root / "adapters").resolve()
        self.allowlist_path = (self.spec_root / "allowlist.json").resolve()
        self._allowlist = self._load_allowlist()

    def list_adapters(self) -> tuple[CommerceSnapshotAdapterDefinition, ...]:
        return tuple(self.resolve(adapter_id) for adapter_id in sorted(self._allowlist))

    def resolve(self, adapter_id: str) -> CommerceSnapshotAdapterDefinition:
        if not _ID_RE.fullmatch(adapter_id):
            raise CommerceSnapshotDefinitionError("Invalid commerce snapshot adapter ID")
        if adapter_id not in self._allowlist:
            raise CommerceSnapshotDefinitionError(
                f"Commerce snapshot adapter is not allowlisted: {adapter_id}"
            )
        directory = self.adapter_root / adapter_id
        if directory.is_symlink():
            raise CommerceSnapshotDefinitionError("Symbolic adapter directories are forbidden")
        directory = directory.resolve()
        if directory.parent != self.adapter_root or not directory.is_dir():
            raise CommerceSnapshotDefinitionError("Commerce snapshot adapter is missing")
        path = directory / "adapter.json"
        if path.is_symlink() or path.resolve().parent != directory or not path.is_file():
            raise CommerceSnapshotDefinitionError("Commerce snapshot adapter file is unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommerceSnapshotDefinitionError(
                "Commerce snapshot adapter is not valid UTF-8 JSON"
            ) from exc
        if not isinstance(payload, dict) or set(payload) != _ALLOWED_KEYS:
            raise CommerceSnapshotDefinitionError("Commerce snapshot adapter keys are invalid")
        if payload["schema_version"] != "okcanvas-commerce-snapshot-adapter-v1":
            raise CommerceSnapshotDefinitionError("Unsupported commerce snapshot adapter schema")
        if payload["adapter_id"] != adapter_id:
            raise CommerceSnapshotDefinitionError("Adapter ID does not match its directory")
        version = self._string(payload, "version")
        if not _VERSION_RE.fullmatch(version):
            raise CommerceSnapshotDefinitionError("Adapter version must be semantic x.y.z")
        name = self._bounded_string(payload, "name", 200)
        if payload["kind"] != "http-json-get-v1":
            raise CommerceSnapshotDefinitionError("Only http-json-get-v1 is supported")
        base_url_env = self._environment_name(payload, "base_url_env")
        credential_env = self._environment_name(payload, "credential_env")
        if {base_url_env, credential_env} != _ALLOWED_ENV_NAMES:
            raise CommerceSnapshotDefinitionError(
                "Adapter environment injection fields are not allowlisted"
            )
        if payload["auth_scheme"] != "bearer":
            raise CommerceSnapshotDefinitionError("Only bearer credential injection is supported")
        if payload["method"] != "GET":
            raise CommerceSnapshotDefinitionError("Commerce snapshot acquisition must use GET")
        path_template = self._string(payload, "path_template")
        if (
            not path_template.startswith("/")
            or path_template.count("{snapshot_key}") != 1
            or "?" in path_template
            or "#" in path_template
        ):
            raise CommerceSnapshotDefinitionError("Adapter path_template is invalid")
        if payload["loopback_only"] is not True:
            raise CommerceSnapshotDefinitionError("STEP025 requires a loopback-only source")
        if payload["follow_redirects"] is not False:
            raise CommerceSnapshotDefinitionError("Redirects must be disabled")
        connect_timeout = self._bounded_number(
            payload, "connect_timeout_seconds", 0.1, 10.0
        )
        read_timeout = self._bounded_number(payload, "read_timeout_seconds", 0.1, 30.0)
        max_response_bytes = self._bounded_int(
            payload, "max_response_bytes", 1024, 262_144
        )
        max_items = self._bounded_int(payload, "max_items", 1, 100)
        retries = self._bounded_int(payload, "max_retry_attempts", 0, 0)
        return CommerceSnapshotAdapterDefinition(
            schema_version=str(payload["schema_version"]),
            adapter_id=adapter_id,
            version=version,
            name=name,
            kind="http-json-get-v1",
            base_url_env=base_url_env,
            credential_env=credential_env,
            auth_scheme="bearer",
            method="GET",
            path_template=path_template,
            loopback_only=True,
            follow_redirects=False,
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
            max_response_bytes=max_response_bytes,
            max_items=max_items,
            max_retry_attempts=retries,
            definition_sha256=hashlib.sha256(raw).hexdigest(),
            definition_path=path,
        )

    def _load_allowlist(self) -> frozenset[str]:
        if self.allowlist_path.is_symlink() or not self.allowlist_path.is_file():
            raise CommerceSnapshotDefinitionError("Commerce snapshot allowlist is missing")
        try:
            payload = json.loads(self.allowlist_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommerceSnapshotDefinitionError(
                "Commerce snapshot allowlist is invalid"
            ) from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "allowed_adapter_ids",
        }:
            raise CommerceSnapshotDefinitionError("Commerce snapshot allowlist contract is invalid")
        if payload["schema_version"] != "okcanvas-commerce-snapshot-allowlist-v1":
            raise CommerceSnapshotDefinitionError("Unsupported commerce snapshot allowlist schema")
        values = payload["allowed_adapter_ids"]
        if (
            not isinstance(values, list)
            or any(not isinstance(item, str) for item in values)
            or len(values) != len(set(values))
            or any(not _ID_RE.fullmatch(item) for item in values)
        ):
            raise CommerceSnapshotDefinitionError("Commerce snapshot allowlist values are invalid")
        return frozenset(values)

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise CommerceSnapshotDefinitionError(f"{key} must be a non-empty string")
        return value.strip()

    @classmethod
    def _bounded_string(cls, payload: dict[str, Any], key: str, maximum: int) -> str:
        value = cls._string(payload, key)
        if len(value) > maximum:
            raise CommerceSnapshotDefinitionError(f"{key} exceeds {maximum} characters")
        return value

    @classmethod
    def _environment_name(cls, payload: dict[str, Any], key: str) -> str:
        value = cls._string(payload, key)
        if not _ENV_RE.fullmatch(value):
            raise CommerceSnapshotDefinitionError(f"{key} is not a valid environment name")
        return value

    @staticmethod
    def _bounded_number(
        payload: dict[str, Any], key: str, minimum: float, maximum: float
    ) -> float:
        value = payload[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CommerceSnapshotDefinitionError(f"{key} must be numeric")
        result = float(value)
        if not minimum <= result <= maximum:
            raise CommerceSnapshotDefinitionError(
                f"{key} must be between {minimum} and {maximum}"
            )
        return result

    @staticmethod
    def _bounded_int(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise CommerceSnapshotDefinitionError(
                f"{key} must be an integer between {minimum} and {maximum}"
            )
        return value
