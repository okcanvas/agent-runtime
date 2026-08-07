from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from okcanvas_agent_runtime.agent.definitions.errors import AgentDefinitionContractError, AgentDefinitionIntegrityError, AgentDefinitionNotFoundError
from okcanvas_agent_runtime.agent.definitions.models import AgentDefinition
from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog, ProductSkillContractError, ProductSkillIntegrityError, ProductSkillNotFoundError
from okcanvas_agent_runtime.agent.guardrails import GuardrailDefinitionContractError, GuardrailDefinitionIntegrityError, GuardrailDefinitionNotFoundError, GuardrailKind, GuardrailRuntimeCatalog
from okcanvas_agent_runtime.agent.tools.function import FunctionToolDefinitionContractError, FunctionToolDefinitionIntegrityError, FunctionToolDefinitionNotFoundError, FunctionToolRuntimeCatalog, FunctionToolApprovalMode

_AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_ALLOWED_KEYS = {
    "schema_version",
    "agent_id",
    "version",
    "name",
    "instructions_file",
    "output_schema_file",
    "output_contract",
    "tools",
    "mcp_servers",
    "hosted_tools",
    "skills",
    "handoffs",
    "agent_tools",
    "orchestration_children",
    "guardrails",
    "workspace_access",
    "max_turns",
    "workflow_name",
    "session_mode",
    "input_mode",
}


class AgentDefinitionCatalog:
    """Resolve immutable Agent definitions below ``specs/agents``."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "agents").resolve()

    def list_definitions(self) -> tuple[AgentDefinition, ...]:
        if not self.spec_root.is_dir():
            return ()
        definitions: list[AgentDefinition] = []
        for entry in sorted(self.spec_root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise AgentDefinitionIntegrityError(
                    f"Symbolic Agent definition directories are forbidden: {entry.name}"
                )
            if not entry.is_dir():
                continue
            if not (entry / "definition.json").is_file():
                continue
            if not _AGENT_ID_RE.fullmatch(entry.name):
                raise AgentDefinitionContractError(
                    f"Invalid Agent definition directory: {entry.name}"
                )
            definitions.append(self.resolve(entry.name))
        return tuple(definitions)

    def resolve(self, agent_id: str) -> AgentDefinition:
        if not _AGENT_ID_RE.fullmatch(agent_id):
            raise AgentDefinitionContractError("Invalid Agent definition ID")
        directory = self._safe_existing_directory(agent_id)
        definition_path = self._safe_file(directory, "definition.json")
        raw_bytes = definition_path.read_bytes()
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AgentDefinitionIntegrityError(
                f"Agent definition is not valid UTF-8 JSON: {agent_id}"
            ) from exc
        if not isinstance(payload, dict):
            raise AgentDefinitionContractError("Agent definition must be a JSON object")
        unknown = set(payload) - _ALLOWED_KEYS
        required_keys = _ALLOWED_KEYS - {"mcp_servers", "hosted_tools", "skills", "agent_tools", "orchestration_children", "guardrails", "workspace_access", "input_mode"}
        missing = required_keys - set(payload)
        if unknown or missing:
            raise AgentDefinitionContractError(
                f"Agent definition keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if payload["schema_version"] != "okcanvas-agent-definition-v1":
            raise AgentDefinitionContractError("Unsupported Agent definition schema")
        if payload["agent_id"] != agent_id:
            raise AgentDefinitionContractError("Agent definition ID does not match its directory")
        if not _VERSION_RE.fullmatch(self._required_string(payload, "version")):
            raise AgentDefinitionContractError("Agent definition version must be semantic x.y.z")
        name = self._bounded_string(payload, "name", maximum=200)
        workflow_name = self._bounded_string(payload, "workflow_name", maximum=200)
        output_contract = self._bounded_string(payload, "output_contract", maximum=100)
        instructions_path = self._safe_file(
            directory, self._relative_filename(payload, "instructions_file")
        )
        schema_path = self._safe_file(
            directory, self._relative_filename(payload, "output_schema_file")
        )
        instructions = instructions_path.read_text(encoding="utf-8")
        if not instructions.strip() or len(instructions) > 64_000:
            raise AgentDefinitionContractError("Agent instructions must be 1..64000 characters")
        try:
            output_schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AgentDefinitionIntegrityError("Output schema is not valid UTF-8 JSON") from exc
        if not isinstance(output_schema, dict):
            raise AgentDefinitionContractError("Output schema must be a JSON object")
        tools = self._string_tuple(payload, "tools")
        try:
            tool_runtimes = FunctionToolRuntimeCatalog(self.project_root).resolve_many(tools)
        except (
            FunctionToolDefinitionContractError,
            FunctionToolDefinitionIntegrityError,
            FunctionToolDefinitionNotFoundError,
        ) as exc:
            raise AgentDefinitionContractError(
                "Agent definition references an invalid or unregistered Function Tool"
            ) from exc
        mcp_servers = self._string_tuple(payload, "mcp_servers") if "mcp_servers" in payload else ()
        hosted_tools = self._string_tuple(payload, "hosted_tools") if "hosted_tools" in payload else ()
        skills = self._string_tuple(payload, "skills") if "skills" in payload else ()
        try:
            skill_packages = ProductSkillCatalog(self.project_root).resolve_many(skills)
        except (ProductSkillContractError, ProductSkillIntegrityError, ProductSkillNotFoundError) as exc:
            raise AgentDefinitionContractError("Agent definition references an invalid or unregistered Product Skill") from exc
        handoffs = self._string_tuple(payload, "handoffs")
        agent_tools = self._string_tuple(payload, "agent_tools") if "agent_tools" in payload else ()
        orchestration_children = (
            self._string_tuple(payload, "orchestration_children")
            if "orchestration_children" in payload
            else ()
        )
        guardrails = self._string_tuple(payload, "guardrails") if "guardrails" in payload else ()
        try:
            guardrail_runtimes = GuardrailRuntimeCatalog(self.project_root).resolve_many(guardrails)
        except (GuardrailDefinitionContractError, GuardrailDefinitionIntegrityError, GuardrailDefinitionNotFoundError) as exc:
            raise AgentDefinitionContractError("Agent definition references an invalid or unregistered Guardrail") from exc
        tool_guardrail_ids = {item.tool_id for item in guardrail_runtimes if item.kind in {GuardrailKind.TOOL_INPUT, GuardrailKind.TOOL_OUTPUT}}
        if any(tool_id not in tools for tool_id in tool_guardrail_ids):
            raise AgentDefinitionContractError("Tool Guardrail target must be declared by the Agent")
        workspace_access = self._required_string(payload, "workspace_access") if "workspace_access" in payload else "none"
        if workspace_access not in {"none", "sandbox-readonly-v1"}:
            raise AgentDefinitionContractError("Unknown or inactive Agent workspace access mode")
        max_turns = payload["max_turns"]
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or not 1 <= max_turns <= 20:
            raise AgentDefinitionContractError("max_turns must be an integer from 1 to 20")
        session_mode = self._required_string(payload, "session_mode")
        input_mode = self._required_string(payload, "input_mode") if "input_mode" in payload else "text-only"
        if input_mode not in {"text-only", "local-attachment-v1"}:
            raise AgentDefinitionContractError("input_mode must be text-only or local-attachment-v1")
        if session_mode not in {"disabled", "sqlite-v1"}:
            raise AgentDefinitionContractError("session_mode must be disabled or sqlite-v1")
        if agent_id == "groupware-read-agent":
            if (
                tools
                or hosted_tools
                or skills
                or handoffs
                or agent_tools
                or orchestration_children
                or guardrail_runtimes
                or mcp_servers != ("groupware-read",)
                or session_mode != "disabled"
                or input_mode != "text-only"
                or workspace_access != "none"
                or output_contract != "GroupwareReadResult"
                or max_turns != 2
            ):
                raise AgentDefinitionContractError(
                    "Groupware read Sub-agent must retain the exact internal read-only contract"
                )

        sandbox_readonly_mode = workspace_access == "sandbox-readonly-v1"
        if sandbox_readonly_mode:
            if agent_id != "sandbox-readonly-coding-agent":
                raise AgentDefinitionContractError("STEP075 permits one exact read-only Sandbox Agent")
            if (
                tools != ("sandbox_project_readonly_inspect",)
                or mcp_servers or hosted_tools or skills or handoffs or agent_tools
                or orchestration_children or guardrail_runtimes
                or session_mode != "disabled" or input_mode != "text-only"
                or output_contract != "CodingAgentResult" or max_turns != 2
            ):
                raise AgentDefinitionContractError("Read-only Sandbox Agent contract is not exact")
            if len(tool_runtimes) != 1 or tool_runtimes[0].factory_id != "sandbox_project_readonly_inspect_v1":
                raise AgentDefinitionContractError("Read-only Sandbox Agent Tool binding is invalid")
        if hosted_tools:
            if hosted_tools != ("web-search-v1",):
                raise AgentDefinitionContractError(
                    "STEP067 permits exactly one hosted Web Search Tool"
                )
            if (
                tools
                or mcp_servers
                or handoffs
                or agent_tools
                or orchestration_children
                or guardrail_runtimes
                or session_mode != "disabled"
                or workspace_access != "none"
            ):
                raise AgentDefinitionContractError(
                    "Hosted Web Search Agent must be isolated, Session-disabled, and workspace-free"
                )
            if output_contract != "HostedWebSearchResult" or max_turns != 2:
                raise AgentDefinitionContractError(
                    "STEP067 Hosted Web Search requires HostedWebSearchResult and max_turns=2"
                )

        if input_mode == "local-attachment-v1":
            if (
                tools or mcp_servers or hosted_tools or handoffs or agent_tools
                or orchestration_children or guardrail_runtimes
                or session_mode != "disabled" or workspace_access != "none"
            ):
                raise AgentDefinitionContractError(
                    "STEP068 local attachment Agent must be isolated, Session-disabled, and workspace-free"
                )
            if output_contract != "LocalDocumentReviewResult" or max_turns != 1:
                raise AgentDefinitionContractError(
                    "STEP068 local attachment Agent requires LocalDocumentReviewResult and max_turns=1"
                )

        for skill in skill_packages:
            try:
                ProductSkillCatalog(self.project_root).validate_agent_binding(
                    skill=skill,
                    agent_id=agent_id,
                    input_mode=input_mode,
                    output_contract=output_contract,
                    tools=tools,
                    mcp_servers=mcp_servers,
                    hosted_tools=hosted_tools,
                    workspace_access=workspace_access,
                )
            except ProductSkillContractError as exc:
                raise AgentDefinitionContractError("Agent and Product Skill binding is invalid") from exc

        if session_mode == "sqlite-v1":
            session_tool_mode = (
                len(tool_runtimes) == 1
                and tool_runtimes[0].approval_mode is FunctionToolApprovalMode.ALWAYS
                and not handoffs
            )
            session_handoff_mode = (
                len(handoffs) == 1
                and not tools
                and not agent_tools
                and not mcp_servers
                and not hosted_tools
                and not guardrail_runtimes
            )
            session_guardrail_mode = (
                bool(guardrail_runtimes)
                and not tools
                and not handoffs
                and not agent_tools
                and not mcp_servers
                and not hosted_tools
                and all(item.kind in {GuardrailKind.INPUT, GuardrailKind.OUTPUT} for item in guardrail_runtimes)
            )
            session_mcp_mode = (
                len(mcp_servers) == 1
                and not tools
                and not handoffs
                and not agent_tools
                and not guardrail_runtimes
                and not hosted_tools
            )
            session_agent_tool_mode = (
                len(agent_tools) == 1
                and not tools
                and not handoffs
                and not mcp_servers
                and not hosted_tools
                and not guardrail_runtimes
            )
            if orchestration_children:
                raise AgentDefinitionContractError("SQLite Session cannot use bounded orchestration")
            if workspace_access != "none":
                raise AgentDefinitionContractError("SQLite Session Agent must be workspace-free")
            if mcp_servers and not session_mcp_mode:
                raise AgentDefinitionContractError(
                    "STEP050 SQLite Session composition permits exactly one read-only MCP server"
                )
            if agent_tools and not session_agent_tool_mode:
                raise AgentDefinitionContractError(
                    "STEP049 SQLite Session composition permits exactly one terminal Agent-as-Tool child"
                )
            if handoffs and not session_handoff_mode:
                raise AgentDefinitionContractError(
                    "STEP047 SQLite Session composition permits exactly one terminal native Handoff"
                )
            if tools and not session_tool_mode:
                raise AgentDefinitionContractError(
                    "STEP046 SQLite Session composition permits exactly one ALWAYS Function Tool"
                )
            if tools and handoffs:
                raise AgentDefinitionContractError(
                    "SQLite Session does not mix Function Tools and Handoffs"
                )
            if guardrail_runtimes and not session_guardrail_mode:
                raise AgentDefinitionContractError(
                    "STEP048 SQLite Session composition permits Agent input/output Guardrails only"
                )
        if guardrail_runtimes and (
            handoffs or agent_tools or orchestration_children or mcp_servers or hosted_tools or workspace_access != "none"
            or (session_mode != "disabled" and not (session_mode == "sqlite-v1" and session_guardrail_mode))
        ):
            raise AgentDefinitionContractError(
                "Guardrail Agent must be child-free, MCP-free, workspace-free, and use an accepted Session mode"
            )
        if orchestration_children:
            if len(orchestration_children) != 2:
                raise AgentDefinitionContractError(
                    "STEP062 bounded orchestration requires exactly two declared children"
                )
            if tools or mcp_servers or hosted_tools or handoffs or agent_tools or guardrail_runtimes:
                raise AgentDefinitionContractError(
                    "Bounded orchestration root cannot declare Tools, MCP, Handoffs, Agent Tools, or Guardrails"
                )
            if session_mode != "disabled" or workspace_access != "none":
                raise AgentDefinitionContractError(
                    "Bounded orchestration root must be Session-disabled and workspace-free"
                )

        if len([item for item in guardrail_runtimes if item.kind is GuardrailKind.INPUT]) > 1 or len([item for item in guardrail_runtimes if item.kind is GuardrailKind.OUTPUT]) > 1:
            raise AgentDefinitionContractError("STEP044 permits at most one input and one output Guardrail")
        if len([item for item in guardrail_runtimes if item.kind is GuardrailKind.TOOL_INPUT]) > 1 or len([item for item in guardrail_runtimes if item.kind is GuardrailKind.TOOL_OUTPUT]) > 1:
            raise AgentDefinitionContractError("STEP044 permits at most one Tool-input and one Tool-output Guardrail")

        digest = hashlib.sha256()
        digest.update(b"definition.json\0")
        digest.update(raw_bytes)
        digest.update(b"\0instructions.md\0")
        digest.update(instructions_path.read_bytes())
        digest.update(b"\0output.schema.json\0")
        digest.update(schema_path.read_bytes())
        return AgentDefinition(
            schema_version=str(payload["schema_version"]),
            agent_id=agent_id,
            version=str(payload["version"]),
            name=name,
            instructions=instructions,
            output_contract=output_contract,
            output_schema=output_schema,
            tools=tools,
            mcp_servers=mcp_servers,
            hosted_tools=hosted_tools,
            skills=skills,
            handoffs=handoffs,
            agent_tools=agent_tools,
            orchestration_children=orchestration_children,
            guardrails=guardrails,
            workspace_access=workspace_access,
            max_turns=max_turns,
            workflow_name=workflow_name,
            session_mode=session_mode,
            input_mode=input_mode,
            definition_sha256=digest.hexdigest(),
            definition_path=definition_path,
            instructions_path=instructions_path,
            output_schema_path=schema_path,
            tool_capabilities=tuple(item.to_public_dict() for item in tool_runtimes),
            guardrail_capabilities=tuple(item.to_public_dict() for item in guardrail_runtimes),
            skill_capabilities=tuple(item.to_public_dict() for item in skill_packages),
        )

    def _safe_existing_directory(self, agent_id: str) -> Path:
        raw_candidate = self.spec_root / agent_id
        if raw_candidate.is_symlink():
            raise AgentDefinitionIntegrityError("Symbolic Agent definition directories are forbidden")
        candidate = raw_candidate.resolve()
        if candidate.parent != self.spec_root:
            raise AgentDefinitionIntegrityError("Agent definition path escaped the specification root")
        if not candidate.is_dir():
            raise AgentDefinitionNotFoundError(f"Agent definition not found: {agent_id}")
        return candidate

    @staticmethod
    def _safe_file(directory: Path, filename: str) -> Path:
        pure = PurePosixPath(filename)
        if pure.is_absolute() or len(pure.parts) != 1 or pure.parts[0] in {"", ".", ".."}:
            raise AgentDefinitionContractError("Definition file paths must be simple relative filenames")
        raw_candidate = directory / pure.as_posix()
        if raw_candidate.is_symlink():
            raise AgentDefinitionIntegrityError(f"Symbolic definition files are forbidden: {filename}")
        candidate = raw_candidate.resolve()
        if candidate.parent != directory or not candidate.is_file():
            raise AgentDefinitionIntegrityError(f"Definition file is missing or unsafe: {filename}")
        return candidate

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise AgentDefinitionContractError(f"{key} must be a non-empty string")
        return value

    @classmethod
    def _bounded_string(cls, payload: dict[str, Any], key: str, *, maximum: int) -> str:
        value = cls._required_string(payload, key).strip()
        if len(value) > maximum:
            raise AgentDefinitionContractError(f"{key} exceeds {maximum} characters")
        return value

    @classmethod
    def _relative_filename(cls, payload: dict[str, Any], key: str) -> str:
        return cls._required_string(payload, key).strip()

    @staticmethod
    def _string_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
        value = payload[key]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise AgentDefinitionContractError(f"{key} must be an array of non-empty strings")
        if len(set(value)) != len(value):
            raise AgentDefinitionContractError(f"{key} must not contain duplicates")
        return tuple(value)
