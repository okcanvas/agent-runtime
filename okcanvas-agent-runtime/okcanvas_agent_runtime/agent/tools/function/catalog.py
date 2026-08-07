from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from okcanvas_agent_runtime.agent.tools.function.errors import FunctionToolDefinitionContractError, FunctionToolDefinitionIntegrityError, FunctionToolDefinitionNotFoundError
from okcanvas_agent_runtime.agent.tools.function.models import FunctionToolApprovalMode, FunctionToolRuntime, LocalTextExecutionInput, LocalTextFingerprintOutput, LocalTextMetricsOutput, ProjectReadonlyInspectOutput, SandboxProjectReadonlyInspectOutput

_TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_REQUIRED_KEYS = {
    "schema_version",
    "runtime_version",
    "tool_id",
    "description",
    "sdk_kind",
    "factory_id",
    "input_schema_file",
    "output_schema_file",
    "strict_json_schema",
    "approval_mode",
    "read_only",
    "filesystem_access",
    "network_access",
    "shell_access",
    "arguments_persisted",
    "result_persisted_in_events",
}
_FACTORY_MODELS = {
    "local_text_fingerprint_v1": (LocalTextExecutionInput, LocalTextFingerprintOutput),
    "local_text_metrics_v1": (LocalTextExecutionInput, LocalTextMetricsOutput),
    "project_readonly_inspect_v1": (LocalTextExecutionInput, ProjectReadonlyInspectOutput),
    "sandbox_project_readonly_inspect_v1": (LocalTextExecutionInput, SandboxProjectReadonlyInspectOutput),
}


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _combined_sha(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "none":
        return "none"
    return text


def _parse_flat_policy(path: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise FunctionToolDefinitionContractError(
                f"Tool policy line {line_number} is not a flat key/value entry"
            )
        key, value = line.split(":", 1)
        key = key.strip()
        if not key or key in result:
            raise FunctionToolDefinitionContractError("Tool policy contains duplicate/empty keys")
        result[key] = _parse_scalar(value)
    return result


class FunctionToolRuntimeCatalog:
    """Resolve immutable local Function Tool specifications through a closed factory registry."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "tools").resolve()

    def list_runtimes(self) -> tuple[FunctionToolRuntime, ...]:
        if not self.spec_root.is_dir():
            return ()
        items: list[FunctionToolRuntime] = []
        for entry in sorted(self.spec_root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise FunctionToolDefinitionIntegrityError(
                    f"Symbolic Tool directories are forbidden: {entry.name}"
                )
            if entry.is_dir() and (entry / "definition.json").is_file():
                items.append(self.resolve(entry.name.replace("-", "_")))
        return tuple(items)

    def resolve_many(self, tool_ids: tuple[str, ...] | list[str]) -> tuple[FunctionToolRuntime, ...]:
        resolved = tuple(self.resolve(tool_id) for tool_id in tool_ids)
        if len({item.tool_id for item in resolved}) != len(resolved):
            raise FunctionToolDefinitionContractError("Function Tool IDs must be unique")
        return resolved

    def resolve(self, tool_id: str) -> FunctionToolRuntime:
        if not _TOOL_ID_RE.fullmatch(tool_id):
            raise FunctionToolDefinitionContractError("Invalid Function Tool ID")
        directory_name = tool_id.replace("_", "-")
        raw_directory = self.spec_root / directory_name
        if raw_directory.is_symlink():
            raise FunctionToolDefinitionIntegrityError("Symbolic Tool directories are forbidden")
        directory = raw_directory.resolve()
        if directory.parent != self.spec_root or not directory.is_dir():
            raise FunctionToolDefinitionNotFoundError(f"Function Tool not found: {tool_id}")
        definition_path = self._safe_file(directory, "definition.json")
        policy_path = self._safe_file(directory, "policy.yaml")
        try:
            payload = json.loads(definition_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FunctionToolDefinitionIntegrityError("Function Tool definition is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _REQUIRED_KEYS:
            raise FunctionToolDefinitionContractError("Function Tool definition keys mismatch")
        if payload["schema_version"] != "okcanvas-function-tool-definition-v1":
            raise FunctionToolDefinitionContractError("Unsupported Function Tool schema")
        if payload["tool_id"] != tool_id:
            raise FunctionToolDefinitionContractError("Function Tool ID does not match directory")
        runtime_version = self._string(payload, "runtime_version")
        if not _VERSION_RE.fullmatch(runtime_version):
            raise FunctionToolDefinitionContractError("Function Tool runtime version is invalid")
        sdk_kind = self._string(payload, "sdk_kind")
        if sdk_kind != "function_tool":
            raise FunctionToolDefinitionContractError("Only SDK function_tool is supported")
        factory_id = self._string(payload, "factory_id")
        models = _FACTORY_MODELS.get(factory_id)
        if models is None:
            raise FunctionToolDefinitionContractError("Function Tool factory is not registered")
        approval_mode = FunctionToolApprovalMode(self._string(payload, "approval_mode"))
        input_schema_path = self._safe_file(
            directory, self._relative_filename(payload, "input_schema_file")
        )
        output_schema_path = self._safe_file(
            directory, self._relative_filename(payload, "output_schema_file")
        )
        input_schema = self._load_schema(input_schema_path)
        output_schema = self._load_schema(output_schema_path)
        input_model, output_model = models
        if _canonical(input_schema) != _canonical(input_model.model_json_schema()):
            raise FunctionToolDefinitionContractError("Function Tool input schema drifted from code")
        if _canonical(output_schema) != _canonical(output_model.model_json_schema()):
            raise FunctionToolDefinitionContractError("Function Tool output schema drifted from code")
        booleans = {
            key: self._bool(payload, key)
            for key in (
                "strict_json_schema",
                "read_only",
                "arguments_persisted",
                "result_persisted_in_events",
            )
        }
        capability_values = {
            key: self._string(payload, key)
            for key in ("filesystem_access", "network_access", "shell_access")
        }
        if not booleans["strict_json_schema"]:
            raise FunctionToolDefinitionContractError("Function Tool schemas must remain strict")
        if not booleans["read_only"]:
            raise FunctionToolDefinitionContractError("Function Tools must remain read-only")
        project_inspector = factory_id == "project_readonly_inspect_v1"
        sandbox_project_inspector = factory_id == "sandbox_project_readonly_inspect_v1"
        expected_filesystem = (
            "read-only" if project_inspector else
            "sandbox-read-only" if sandbox_project_inspector else
            "none"
        )
        if capability_values["filesystem_access"] != expected_filesystem:
            raise FunctionToolDefinitionContractError("Function Tool filesystem capability is outside its closed factory contract")
        if capability_values["network_access"] != "none" or capability_values["shell_access"] != "none":
            raise FunctionToolDefinitionContractError("Function Tools may not gain network or Shell access")
        if (project_inspector or sandbox_project_inspector) and approval_mode is not FunctionToolApprovalMode.NEVER:
            raise FunctionToolDefinitionContractError("Read-only project inspection must not require Tool approval")
        if booleans["arguments_persisted"] or booleans["result_persisted_in_events"]:
            raise FunctionToolDefinitionContractError("Raw Tool arguments/results may not be persisted")
        policy = _parse_flat_policy(policy_path)
        expected_policy = {
            "id": tool_id,
            "sdk_kind": sdk_kind,
            "approval_mode": approval_mode.value,
            "read_only": True,
            "filesystem_access": expected_filesystem,
            "network_access": "none",
            "shell_access": "none",
            "arguments_persisted": False,
            "result_persisted_in_events": False,
        }
        if policy != expected_policy:
            raise FunctionToolDefinitionContractError("Function Tool policy disagrees with definition")
        implementation_root = Path(__file__).resolve().parent
        runtime_package_root = implementation_root.parents[2]
        implementation_sha = _combined_sha(
            (
                implementation_root / "implementations.py",
                implementation_root / "factories.py",
                runtime_package_root / "adapters" / "workspace" / "tool_inspection.py",
            )
        )
        definition_sha = _combined_sha(
            (definition_path, policy_path, input_schema_path, output_schema_path)
        )
        return FunctionToolRuntime(
            schema_version=str(payload["schema_version"]),
            runtime_version=runtime_version,
            tool_id=tool_id,
            description=self._bounded_string(payload, "description", 500),
            sdk_kind=sdk_kind,
            factory_id=factory_id,
            approval_mode=approval_mode,
            strict_json_schema=booleans["strict_json_schema"],
            read_only=booleans["read_only"],
            filesystem_access=capability_values["filesystem_access"],
            network_access=capability_values["network_access"],
            shell_access=capability_values["shell_access"],
            arguments_persisted=booleans["arguments_persisted"],
            result_persisted_in_events=booleans["result_persisted_in_events"],
            input_model=input_model,
            output_model=output_model,
            definition_sha256=definition_sha,
            policy_sha256=_file_sha(policy_path),
            input_schema_sha256=_file_sha(input_schema_path),
            output_schema_sha256=_file_sha(output_schema_path),
            implementation_sha256=implementation_sha,
            directory=directory,
        )

    @staticmethod
    def _safe_file(directory: Path, filename: str) -> Path:
        pure = PurePosixPath(filename)
        if pure.is_absolute() or len(pure.parts) != 1 or pure.parts[0] in {"", ".", ".."}:
            raise FunctionToolDefinitionContractError("Tool file paths must be simple filenames")
        raw = directory / pure.as_posix()
        if raw.is_symlink():
            raise FunctionToolDefinitionIntegrityError("Symbolic Tool files are forbidden")
        path = raw.resolve()
        if path.parent != directory or not path.is_file():
            raise FunctionToolDefinitionIntegrityError(f"Tool file is missing or unsafe: {filename}")
        return path

    @staticmethod
    def _load_schema(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FunctionToolDefinitionIntegrityError("Function Tool schema is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise FunctionToolDefinitionContractError("Function Tool schema must be an object")
        return payload

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise FunctionToolDefinitionContractError(f"{key} must be a non-empty string")
        return value.strip()

    @classmethod
    def _bounded_string(cls, payload: dict[str, Any], key: str, maximum: int) -> str:
        value = cls._string(payload, key)
        if len(value) > maximum:
            raise FunctionToolDefinitionContractError(f"{key} exceeds {maximum} characters")
        return value

    @classmethod
    def _relative_filename(cls, payload: dict[str, Any], key: str) -> str:
        return cls._string(payload, key)

    @staticmethod
    def _bool(payload: dict[str, Any], key: str) -> bool:
        value = payload[key]
        if not isinstance(value, bool):
            raise FunctionToolDefinitionContractError(f"{key} must be boolean")
        return value
