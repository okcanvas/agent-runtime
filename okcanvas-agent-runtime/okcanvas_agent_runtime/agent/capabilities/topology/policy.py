from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.capabilities.topology.errors import CapabilityContractError, CapabilityIntegrityError
from okcanvas_agent_runtime.agent.capabilities.topology.models import CapabilityActivation, CapabilityDiscoveryPolicy, CapabilityLoading, CapabilityNamespace

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_NAMESPACE_KEYS = {"namespace_id", "description", "member_ids", "loading", "activation"}
_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "sdk_package",
    "sdk_version",
    "tool_search",
    "programmatic_tool_calling",
    "namespaces",
}
_TOOL_SEARCH_KEYS = {
    "runtime_enabled",
    "execution",
    "max_namespaces_per_agent",
    "max_deferred_tools_per_agent",
    "allowed_surface_kinds",
}
_PROGRAMMATIC_KEYS = {
    "runtime_enabled",
    "default_allowed_callers",
    "max_callable_tools",
}


class CapabilityDiscoveryPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = (
            self.project_root / "specs" / "capabilities" / "tool-discovery-policy.json"
        ).resolve()

    def resolve(self) -> CapabilityDiscoveryPolicy:
        expected_parent = (self.project_root / "specs" / "capabilities").resolve()
        if self.path.is_symlink() or self.path.parent != expected_parent or not self.path.is_file():
            raise CapabilityIntegrityError("Capability discovery policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CapabilityIntegrityError("Capability discovery policy is invalid UTF-8 JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise CapabilityContractError("Capability discovery policy keys mismatch")
        if payload["schema_version"] != "okcanvas-capability-discovery-policy-v1":
            raise CapabilityContractError("Unsupported capability discovery policy schema")
        policy_id = self._identifier(payload, "policy_id")
        version = self._string(payload, "version", maximum=32)
        if not _VERSION_RE.fullmatch(version):
            raise CapabilityContractError("Capability discovery policy version is invalid")
        if payload["sdk_package"] != "openai-agents" or payload["sdk_version"] != "0.19.0":
            raise CapabilityContractError("Capability discovery policy must pin openai-agents 0.19.0")

        tool_search = payload["tool_search"]
        if not isinstance(tool_search, dict) or set(tool_search) != _TOOL_SEARCH_KEYS:
            raise CapabilityContractError("Tool Search policy keys mismatch")
        if tool_search["runtime_enabled"] is not False:
            raise CapabilityContractError("STEP080 is structure-only and must not enable Tool Search")
        if tool_search["execution"] != "server":
            raise CapabilityContractError("STEP080 pins future Tool Search execution to server")
        max_namespaces = self._integer(tool_search, "max_namespaces_per_agent", 1, 32)
        max_deferred = self._integer(tool_search, "max_deferred_tools_per_agent", 1, 256)
        allowed_surfaces = self._string_tuple(tool_search, "allowed_surface_kinds", 1, 8)
        if allowed_surfaces != ("function-tool", "hosted-mcp"):
            raise CapabilityContractError(
                "SDK 0.19.0 Tool Search surfaces must be function-tool and hosted-mcp"
            )

        programmatic = payload["programmatic_tool_calling"]
        if not isinstance(programmatic, dict) or set(programmatic) != _PROGRAMMATIC_KEYS:
            raise CapabilityContractError("Programmatic Tool Calling policy keys mismatch")
        if programmatic["runtime_enabled"] is not False:
            raise CapabilityContractError(
                "STEP080 is structure-only and must not enable Programmatic Tool Calling"
            )
        allowed_callers = self._string_tuple(
            programmatic, "default_allowed_callers", 1, 2
        )
        if allowed_callers != ("direct",):
            raise CapabilityContractError("STEP080 keeps direct callers only")
        max_programmatic = self._integer(programmatic, "max_callable_tools", 1, 128)

        raw_namespaces = payload["namespaces"]
        if not isinstance(raw_namespaces, list) or not 1 <= len(raw_namespaces) <= 32:
            raise CapabilityContractError("Capability namespaces must contain 1..32 entries")
        namespaces: list[CapabilityNamespace] = []
        namespace_ids: set[str] = set()
        member_ids: set[str] = set()
        for item in raw_namespaces:
            if not isinstance(item, dict) or set(item) != _NAMESPACE_KEYS:
                raise CapabilityContractError("Capability namespace keys mismatch")
            namespace_id = self._identifier(item, "namespace_id")
            if namespace_id in namespace_ids:
                raise CapabilityContractError("Capability namespace IDs must be unique")
            namespace_ids.add(namespace_id)
            description = self._string(item, "description", maximum=500)
            members = self._string_tuple(item, "member_ids", 1, 64)
            if any(member in member_ids for member in members):
                raise CapabilityContractError("A Tool may belong to only one namespace hint")
            member_ids.update(members)
            try:
                loading = CapabilityLoading(item["loading"])
                activation = CapabilityActivation(item["activation"])
            except (ValueError, TypeError) as exc:
                raise CapabilityContractError("Capability namespace enum value is invalid") from exc
            if loading is not CapabilityLoading.EAGER or activation is not CapabilityActivation.STRUCTURE_ONLY:
                raise CapabilityContractError(
                    "STEP080 namespace hints must remain eager and structure-only"
                )
            namespaces.append(
                CapabilityNamespace(
                    namespace_id=namespace_id,
                    description=description,
                    member_ids=members,
                    loading=loading,
                    activation=activation,
                )
            )
        if len(namespaces) > max_namespaces:
            raise CapabilityContractError("Capability namespace count exceeds policy bound")

        return CapabilityDiscoveryPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=policy_id,
            version=version,
            sdk_package="openai-agents",
            sdk_version="0.19.0",
            tool_search_runtime_enabled=False,
            tool_search_execution="server",
            max_namespaces_per_agent=max_namespaces,
            max_deferred_tools_per_agent=max_deferred,
            allowed_tool_search_surface_kinds=allowed_surfaces,
            programmatic_tool_calling_runtime_enabled=False,
            default_allowed_callers=allowed_callers,
            max_programmatic_callable_tools=max_programmatic,
            namespaces=tuple(namespaces),
            policy_sha256=hashlib.sha256(raw).hexdigest(),
            path=self.path,
        )

    @staticmethod
    def _string(payload: dict[str, Any], key: str, *, maximum: int) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
            raise CapabilityContractError(f"{key} must be a bounded non-empty string")
        return value

    @classmethod
    def _identifier(cls, payload: dict[str, Any], key: str) -> str:
        value = cls._string(payload, key, maximum=64)
        if not _ID_RE.fullmatch(value):
            raise CapabilityContractError(f"{key} must be a lowercase capability identifier")
        return value

    @staticmethod
    def _integer(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise CapabilityContractError(f"{key} must be an integer from {minimum} to {maximum}")
        return value

    @staticmethod
    def _string_tuple(
        payload: dict[str, Any], key: str, minimum: int, maximum: int
    ) -> tuple[str, ...]:
        value = payload.get(key)
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            raise CapabilityContractError(f"{key} must be a bounded array")
        if any(not isinstance(item, str) or not item or item != item.strip() for item in value):
            raise CapabilityContractError(f"{key} entries must be non-empty strings")
        if len(set(value)) != len(value):
            raise CapabilityContractError(f"{key} entries must be unique")
        return tuple(value)
