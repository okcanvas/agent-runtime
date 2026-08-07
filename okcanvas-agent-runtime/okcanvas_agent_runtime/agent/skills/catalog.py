from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from okcanvas_agent_runtime.agent.skills.errors import ProductSkillContractError, ProductSkillIntegrityError, ProductSkillNotFoundError
from okcanvas_agent_runtime.agent.skills.models import ProductSkillPackage, ProductSkillResource

_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_CAPABILITY_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,95}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_RESOURCE_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ALLOWED_MEDIA_TYPES = {"text/markdown", "text/plain", "application/json"}
_ALLOWED_INPUT_MODES = {"text-only", "local-attachment-v1"}
_ALLOWED_KEYS = {
    "schema_version",
    "skill_id",
    "version",
    "name",
    "description",
    "execution_mode",
    "instructions_file",
    "resources",
    "allowed_agent_ids",
    "allowed_input_modes",
    "allowed_output_contracts",
    "required_tools",
    "required_mcp_servers",
    "required_hosted_tools",
    "workspace_access",
}
_RESOURCE_KEYS = {"path", "media_type"}
_MAX_INSTRUCTIONS_BYTES = 32_000
_MAX_RESOURCE_FILES = 8
_MAX_RESOURCE_BYTES = 32_000
_MAX_TOTAL_RESOURCE_BYTES = 64_000
_RESERVED_MARKERS = ("<OKCANVAS_PRODUCT_SKILL", "</OKCANVAS_PRODUCT_SKILL>")


class ProductSkillCatalog:
    """Resolve immutable Product-owned Skill packages below ``specs/skills``."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "skills").resolve()

    def list_packages(self) -> tuple[ProductSkillPackage, ...]:
        if not self.spec_root.is_dir():
            return ()
        packages: list[ProductSkillPackage] = []
        for entry in sorted(self.spec_root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise ProductSkillIntegrityError(
                    f"Symbolic Skill package directories are forbidden: {entry.name}"
                )
            if not entry.is_dir() or not (entry / "skill.json").is_file():
                continue
            packages.append(self.resolve(entry.name))
        return tuple(packages)

    def resolve_many(self, skill_ids: tuple[str, ...]) -> tuple[ProductSkillPackage, ...]:
        if len(skill_ids) > 1:
            raise ProductSkillContractError("Product Skill V1 permits at most one Skill per Agent")
        if len(set(skill_ids)) != len(skill_ids):
            raise ProductSkillContractError("Agent Skill IDs must be unique")
        return tuple(self.resolve(skill_id) for skill_id in skill_ids)

    def resolve(self, skill_id: str) -> ProductSkillPackage:
        if not _SKILL_ID_RE.fullmatch(skill_id):
            raise ProductSkillContractError("Invalid Product Skill ID")
        directory = self._safe_existing_directory(skill_id)
        manifest_path = self._safe_file(directory, "skill.json")
        manifest_bytes = manifest_path.read_bytes()
        try:
            payload = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProductSkillIntegrityError("Skill manifest is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ProductSkillContractError("Skill manifest must be a JSON object")
        unknown = set(payload) - _ALLOWED_KEYS
        missing = _ALLOWED_KEYS - set(payload)
        if unknown or missing:
            raise ProductSkillContractError(
                f"Skill manifest keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if payload["schema_version"] != "okcanvas-product-skill-v1":
            raise ProductSkillContractError("Unsupported Product Skill schema")
        if payload["skill_id"] != skill_id:
            raise ProductSkillContractError("Skill ID does not match package directory")
        version = self._required_string(payload, "version", maximum=32)
        if not _VERSION_RE.fullmatch(version):
            raise ProductSkillContractError("Skill version must be semantic x.y.z")
        name = self._required_string(payload, "name", maximum=160)
        description = self._required_string(payload, "description", maximum=800)
        execution_mode = self._required_string(payload, "execution_mode", maximum=80)
        if execution_mode != "instructions-and-static-resources":
            raise ProductSkillContractError("Skill V1 supports instructions-and-static-resources only")
        if payload["workspace_access"] != "none":
            raise ProductSkillContractError("Skill V1 cannot request workspace access")

        instructions_file = self._relative_file(payload, "instructions_file")
        if instructions_file != "instructions.md":
            raise ProductSkillContractError("Skill instructions_file must be instructions.md")
        instructions_path = self._safe_file(directory, instructions_file)
        instructions = self._read_bounded_text(
            instructions_path,
            maximum=_MAX_INSTRUCTIONS_BYTES,
            label="Skill instructions",
        )
        self._reject_reserved_markers(instructions)

        resources_payload = payload["resources"]
        if not isinstance(resources_payload, list) or not 1 <= len(resources_payload) <= _MAX_RESOURCE_FILES:
            raise ProductSkillContractError("Skill resources must contain 1..8 entries")
        resources: list[ProductSkillResource] = []
        seen_paths: set[str] = set()
        total_resource_bytes = 0
        declared_files = {"skill.json", instructions_file}
        for raw in resources_payload:
            if not isinstance(raw, dict) or set(raw) != _RESOURCE_KEYS:
                raise ProductSkillContractError("Skill resource entries require path and media_type")
            relative = self._validated_resource_path(raw["path"])
            if relative in seen_paths:
                raise ProductSkillContractError("Skill resource paths must be unique")
            seen_paths.add(relative)
            media_type = raw["media_type"]
            if media_type not in _ALLOWED_MEDIA_TYPES:
                raise ProductSkillContractError("Unsupported Skill resource media type")
            path = self._safe_file(directory, relative)
            content = self._read_bounded_text(path, maximum=_MAX_RESOURCE_BYTES, label="Skill resource")
            self._reject_reserved_markers(content)
            if media_type == "application/json":
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise ProductSkillIntegrityError("Skill JSON resource is invalid") from exc
                if not isinstance(parsed, (dict, list)):
                    raise ProductSkillContractError("Skill JSON resource must be an object or array")
            raw_bytes = content.encode("utf-8")
            total_resource_bytes += len(raw_bytes)
            if total_resource_bytes > _MAX_TOTAL_RESOURCE_BYTES:
                raise ProductSkillContractError("Skill resources exceed the total byte limit")
            resources.append(
                ProductSkillResource(
                    path=relative,
                    media_type=media_type,
                    sha256=hashlib.sha256(raw_bytes).hexdigest(),
                    byte_length=len(raw_bytes),
                    text=content,
                )
            )
            declared_files.add(relative)

        self._verify_exact_package_files(directory, declared_files)
        allowed_agent_ids = self._identifier_tuple(
            payload, "allowed_agent_ids", pattern=_AGENT_ID_RE, minimum=1
        )
        allowed_input_modes = self._string_tuple(payload, "allowed_input_modes", minimum=1)
        if any(item not in _ALLOWED_INPUT_MODES for item in allowed_input_modes):
            raise ProductSkillContractError("Skill allowed_input_modes contains an unsupported mode")
        allowed_output_contracts = self._output_contract_tuple(payload, "allowed_output_contracts")
        required_tools = self._identifier_tuple(payload, "required_tools", pattern=_CAPABILITY_ID_RE)
        required_mcp_servers = self._identifier_tuple(
            payload, "required_mcp_servers", pattern=_CAPABILITY_ID_RE
        )
        required_hosted_tools = self._identifier_tuple(
            payload, "required_hosted_tools", pattern=_CAPABILITY_ID_RE
        )

        instructions_bytes = instructions.encode("utf-8")
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        package_digest = hashlib.sha256()
        for relative, sha in sorted(
            [("skill.json", manifest_sha), (instructions_file, hashlib.sha256(instructions_bytes).hexdigest())]
            + [(item.path, item.sha256) for item in resources],
            key=lambda item: item[0],
        ):
            package_digest.update(relative.encode("utf-8"))
            package_digest.update(b"\0")
            package_digest.update(sha.encode("ascii"))
            package_digest.update(b"\0")

        return ProductSkillPackage(
            schema_version="okcanvas-product-skill-v1",
            skill_id=skill_id,
            version=version,
            name=name,
            description=description,
            execution_mode=execution_mode,
            instructions=instructions,
            instructions_sha256=hashlib.sha256(instructions_bytes).hexdigest(),
            instructions_byte_length=len(instructions_bytes),
            resources=tuple(resources),
            allowed_agent_ids=allowed_agent_ids,
            allowed_input_modes=allowed_input_modes,
            allowed_output_contracts=allowed_output_contracts,
            required_tools=required_tools,
            required_mcp_servers=required_mcp_servers,
            required_hosted_tools=required_hosted_tools,
            workspace_access="none",
            manifest_sha256=manifest_sha,
            package_sha256=package_digest.hexdigest(),
            directory=directory,
            manifest_path=manifest_path,
        )

    def validate_agent_binding(
        self,
        *,
        skill: ProductSkillPackage,
        agent_id: str,
        input_mode: str,
        output_contract: str,
        tools: tuple[str, ...],
        mcp_servers: tuple[str, ...],
        hosted_tools: tuple[str, ...],
        workspace_access: str,
    ) -> None:
        if agent_id not in skill.allowed_agent_ids:
            raise ProductSkillContractError("Agent is not allowlisted by the Product Skill")
        if input_mode not in skill.allowed_input_modes:
            raise ProductSkillContractError("Agent input mode is not allowed by the Product Skill")
        if output_contract not in skill.allowed_output_contracts:
            raise ProductSkillContractError("Agent output contract is not allowed by the Product Skill")
        if workspace_access != skill.workspace_access:
            raise ProductSkillContractError("Agent workspace access does not match the Product Skill")
        if not set(skill.required_tools).issubset(tools):
            raise ProductSkillContractError("Agent does not declare every Tool required by the Product Skill")
        if not set(skill.required_mcp_servers).issubset(mcp_servers):
            raise ProductSkillContractError("Agent does not declare every MCP server required by the Product Skill")
        if not set(skill.required_hosted_tools).issubset(hosted_tools):
            raise ProductSkillContractError("Agent does not declare every Hosted Tool required by the Product Skill")

    def _safe_existing_directory(self, skill_id: str) -> Path:
        directory = self.spec_root / skill_id
        if directory.is_symlink() or not directory.is_dir():
            raise ProductSkillNotFoundError(f"Product Skill not found: {skill_id}")
        resolved = directory.resolve()
        if resolved.parent != self.spec_root:
            raise ProductSkillIntegrityError("Product Skill directory escapes specs/skills")
        return resolved

    @staticmethod
    def _safe_file(directory: Path, relative: str) -> Path:
        path = directory.joinpath(*PurePosixPath(relative).parts)
        if path.is_symlink() or not path.is_file():
            raise ProductSkillIntegrityError(f"Skill package file is missing or unsafe: {relative}")
        resolved = path.resolve()
        if directory not in resolved.parents:
            raise ProductSkillIntegrityError("Skill package file escapes its package directory")
        return resolved

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str, *, maximum: int) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
            raise ProductSkillContractError(f"Skill {key} must be a bounded non-empty string")
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ProductSkillContractError(f"Skill {key} contains control characters")
        return value

    @staticmethod
    def _relative_file(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ProductSkillContractError(f"Skill {key} must be a relative filename")
        pure = PurePosixPath(value)
        if pure.is_absolute() or len(pure.parts) != 1 or pure.name in {".", ".."}:
            raise ProductSkillContractError(f"Skill {key} must be a direct relative filename")
        return value

    @staticmethod
    def _validated_resource_path(value: Any) -> str:
        if not isinstance(value, str) or not value or len(value) > 200 or "\\" in value:
            raise ProductSkillContractError("Skill resource path is invalid")
        pure = PurePosixPath(value)
        parts = pure.parts
        if pure.is_absolute() or len(parts) < 2 or parts[0] != "resources":
            raise ProductSkillContractError("Skill resources must be below resources/")
        if any(part in {".", ".."} or not _RESOURCE_SEGMENT_RE.fullmatch(part) for part in parts):
            raise ProductSkillContractError("Skill resource path contains an invalid segment")
        if parts[-1].startswith("."):
            raise ProductSkillContractError("Hidden Skill resources are forbidden")
        return pure.as_posix()

    @staticmethod
    def _read_bounded_text(path: Path, *, maximum: int, label: str) -> str:
        raw = path.read_bytes()
        if not raw or len(raw) > maximum or b"\0" in raw:
            raise ProductSkillContractError(f"{label} must be bounded non-empty UTF-8 text")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProductSkillIntegrityError(f"{label} is not UTF-8") from exc
        if text != text.strip() + ("\n" if text.endswith("\n") else ""):
            # Allow a single conventional trailing newline, but no surrounding blank padding.
            normalized = text[:-1] if text.endswith("\n") else text
            if normalized != normalized.strip():
                raise ProductSkillContractError(f"{label} has leading or trailing blank padding")
        return text

    @staticmethod
    def _reject_reserved_markers(text: str) -> None:
        if any(marker in text for marker in _RESERVED_MARKERS):
            raise ProductSkillContractError("Skill content contains a reserved Runtime marker")

    @staticmethod
    def _string_tuple(payload: dict[str, Any], key: str, *, minimum: int = 0) -> tuple[str, ...]:
        value = payload.get(key)
        if not isinstance(value, list) or len(value) < minimum or len(value) > 32:
            raise ProductSkillContractError(f"Skill {key} must be a bounded array")
        if any(not isinstance(item, str) or not item or item != item.strip() for item in value):
            raise ProductSkillContractError(f"Skill {key} entries must be non-empty strings")
        if len(set(value)) != len(value):
            raise ProductSkillContractError(f"Skill {key} entries must be unique")
        return tuple(value)

    @classmethod
    def _identifier_tuple(
        cls,
        payload: dict[str, Any],
        key: str,
        *,
        pattern: re.Pattern[str],
        minimum: int = 0,
    ) -> tuple[str, ...]:
        values = cls._string_tuple(payload, key, minimum=minimum)
        if any(not pattern.fullmatch(value) for value in values):
            raise ProductSkillContractError(f"Skill {key} contains an invalid identifier")
        return values

    @classmethod
    def _output_contract_tuple(cls, payload: dict[str, Any], key: str) -> tuple[str, ...]:
        values = cls._string_tuple(payload, key, minimum=1)
        if any(len(value) > 100 or not re.fullmatch(r"^[A-Za-z][A-Za-z0-9]{1,99}$", value) for value in values):
            raise ProductSkillContractError("Skill allowed_output_contracts contains an invalid contract")
        return values

    @staticmethod
    def _verify_exact_package_files(directory: Path, declared_files: set[str]) -> None:
        actual: set[str] = set()
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ProductSkillIntegrityError("Symbolic paths are forbidden in Product Skill packages")
            if path.is_file():
                actual.add(path.relative_to(directory).as_posix())
        if actual != declared_files:
            raise ProductSkillIntegrityError(
                f"Skill package file inventory mismatch: missing={sorted(declared_files-actual)}, unknown={sorted(actual-declared_files)}"
            )
