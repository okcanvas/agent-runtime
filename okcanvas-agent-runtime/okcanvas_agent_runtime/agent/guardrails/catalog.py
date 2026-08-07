from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.guardrails.errors import GuardrailDefinitionContractError, GuardrailDefinitionIntegrityError, GuardrailDefinitionNotFoundError
from okcanvas_agent_runtime.agent.guardrails.models import GuardrailKind, GuardrailRuntime

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_KEYS = {
    "schema_version", "guardrail_id", "version", "kind", "implementation_id",
    "marker", "tool_id", "run_in_parallel", "behavior",
}
_ALLOWED_IMPLEMENTATIONS = {
    "input_marker_block_v1": GuardrailKind.INPUT,
    "output_marker_block_v1": GuardrailKind.OUTPUT,
    "tool_input_deny_v1": GuardrailKind.TOOL_INPUT,
    "tool_output_deny_v1": GuardrailKind.TOOL_OUTPUT,
}


def _implementation_sha() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ("models.py", "catalog.py", "runtime.py"):
        path = root / name
        digest.update(name.encode("utf-8")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


class GuardrailRuntimeCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "guardrails").resolve()

    def list_runtimes(self) -> tuple[GuardrailRuntime, ...]:
        if not self.spec_root.is_dir():
            return ()
        return tuple(self.resolve(p.name) for p in sorted(self.spec_root.iterdir()) if p.is_dir() and (p / "definition.json").is_file())

    def resolve_many(self, ids: tuple[str, ...] | list[str]) -> tuple[GuardrailRuntime, ...]:
        items = tuple(self.resolve(value) for value in ids)
        if len({item.guardrail_id for item in items}) != len(items):
            raise GuardrailDefinitionContractError("Guardrail IDs must be unique")
        return items

    def resolve(self, guardrail_id: str) -> GuardrailRuntime:
        if not _ID_RE.fullmatch(guardrail_id):
            raise GuardrailDefinitionContractError("Invalid Guardrail ID")
        raw_dir = self.spec_root / guardrail_id
        if raw_dir.is_symlink():
            raise GuardrailDefinitionIntegrityError("Symbolic Guardrail directories are forbidden")
        directory = raw_dir.resolve()
        if directory.parent != self.spec_root or not directory.is_dir():
            raise GuardrailDefinitionNotFoundError(f"Guardrail not found: {guardrail_id}")
        path = directory / "definition.json"
        if path.is_symlink() or path.resolve().parent != directory or not path.is_file():
            raise GuardrailDefinitionIntegrityError("Guardrail definition is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuardrailDefinitionIntegrityError("Guardrail definition is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise GuardrailDefinitionContractError("Guardrail definition keys mismatch")
        if payload["schema_version"] != "okcanvas-guardrail-definition-v1" or payload["guardrail_id"] != guardrail_id:
            raise GuardrailDefinitionContractError("Guardrail schema or identity mismatch")
        version = self._string(payload, "version")
        if not _VERSION_RE.fullmatch(version):
            raise GuardrailDefinitionContractError("Guardrail version must be semantic x.y.z")
        kind = GuardrailKind(self._string(payload, "kind"))
        implementation_id = self._string(payload, "implementation_id")
        if _ALLOWED_IMPLEMENTATIONS.get(implementation_id) is not kind:
            raise GuardrailDefinitionContractError("Guardrail implementation is not registered for its kind")
        marker = payload["marker"]
        if marker is not None and (not isinstance(marker, str) or not marker or len(marker) > 128):
            raise GuardrailDefinitionContractError("Guardrail marker must be null or 1..128 characters")
        tool_id = payload["tool_id"]
        if tool_id is not None and (not isinstance(tool_id, str) or not tool_id):
            raise GuardrailDefinitionContractError("Guardrail tool_id must be null or non-empty")
        run_in_parallel = payload["run_in_parallel"]
        if not isinstance(run_in_parallel, bool):
            raise GuardrailDefinitionContractError("run_in_parallel must be boolean")
        behavior = self._string(payload, "behavior")
        if behavior != "RAISE_EXCEPTION":
            raise GuardrailDefinitionContractError("STEP044 supports RAISE_EXCEPTION only")
        if kind in {GuardrailKind.INPUT, GuardrailKind.OUTPUT}:
            if marker is None or tool_id is not None:
                raise GuardrailDefinitionContractError("Agent Guardrails require marker and no tool_id")
            if kind is GuardrailKind.INPUT and run_in_parallel:
                raise GuardrailDefinitionContractError("STEP044 input Guardrails must run before model execution")
        else:
            if marker is not None or tool_id is None or run_in_parallel:
                raise GuardrailDefinitionContractError("Tool Guardrails require tool_id and no marker/parallel mode")
        return GuardrailRuntime(
            schema_version=str(payload["schema_version"]), guardrail_id=guardrail_id,
            version=version, kind=kind, implementation_id=implementation_id,
            marker=marker, tool_id=tool_id, run_in_parallel=run_in_parallel,
            behavior=behavior, definition_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            implementation_sha256=_implementation_sha(), directory=directory,
        )

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise GuardrailDefinitionContractError(f"{key} must be a non-empty string")
        return value.strip()
