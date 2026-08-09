from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SCHEMA_RE = re.compile(r"^okcanvas-[a-z0-9-]+-v[1-9][0-9]*$")
_PROJECT_PATH_RE = re.compile(r"^[a-z0-9-]+(?:/[a-z0-9-]+){0,2}$")


class GroupwareDeploymentContractError(RuntimeError):
    code = "GROUPWARE_DEPLOYMENT_CONTRACT_INVALID"


@dataclass(frozen=True)
class GroupwareDeploymentBoundary:
    read_agent_definition_location: str
    mcp_client_declaration_location: str
    mcp_provider_deployment: str
    mcp_provider_implementation_in_runtime: bool
    organization_specific_adapter_in_runtime: bool
    test_fixture_location: str
    read_agent_permanently_read_only: bool
    write_extension_strategy: str
    future_write_agent_id: str
    future_write_mcp_server_id: str
    external_connector_repository: str
    external_groupware_connector_path: str
    connector_examples_repository: str
    groupware_api_fake_example_path: str
    connector_examples_required: bool
    groupware_api_fake_is_mcp_server: bool
    boundary_sha256: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-deployment-boundary-v2",
            "read_agent_definition_location": self.read_agent_definition_location,
            "mcp_client_declaration_location": self.mcp_client_declaration_location,
            "mcp_provider_deployment": self.mcp_provider_deployment,
            "mcp_provider_implementation_in_runtime": self.mcp_provider_implementation_in_runtime,
            "organization_specific_adapter_in_runtime": self.organization_specific_adapter_in_runtime,
            "test_fixture_location": self.test_fixture_location,
            "read_agent_permanently_read_only": self.read_agent_permanently_read_only,
            "write_extension_strategy": self.write_extension_strategy,
            "future_write_agent_id": self.future_write_agent_id,
            "future_write_mcp_server_id": self.future_write_mcp_server_id,
            "external_connector_repository": self.external_connector_repository,
            "external_groupware_connector_path": self.external_groupware_connector_path,
            "connector_examples_repository": self.connector_examples_repository,
            "groupware_api_fake_example_path": self.groupware_api_fake_example_path,
            "connector_examples_required": self.connector_examples_required,
            "groupware_api_fake_is_mcp_server": self.groupware_api_fake_is_mcp_server,
            "boundary_sha256": self.boundary_sha256,
        }


@dataclass(frozen=True)
class GroupwareProviderToolContract:
    tool_name: str
    input_schema_version: str
    output_schema_version: str
    mutates: bool

    def to_public_dict(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "mutates": self.mutates,
        }


@dataclass(frozen=True)
class GroupwareReadProviderContract:
    server_id: str
    transport: str
    provider_deployment: str
    provider_implemented_in_runtime: bool
    required_identity_fields: tuple[str, ...]
    required_identity_headers: tuple[str, ...]
    external_connector_project_path: str
    credential_reference_transmitted: bool
    tools: tuple[GroupwareProviderToolContract, ...]
    contract_sha256: str

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return tuple(item.tool_name for item in self.tools)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-read-provider-contract-v3",
            "server_id": self.server_id,
            "transport": self.transport,
            "provider_deployment": self.provider_deployment,
            "provider_implemented_in_runtime": self.provider_implemented_in_runtime,
            "required_identity_fields": list(self.required_identity_fields),
            "required_identity_headers": list(self.required_identity_headers),
            "external_connector_project_path": self.external_connector_project_path,
            "credential_reference_transmitted": self.credential_reference_transmitted,
            "tools": [item.to_public_dict() for item in self.tools],
            "contract_sha256": self.contract_sha256,
        }


class GroupwareDeploymentCatalog:
    """Validate Product-owned Agent/client contracts and external connector ownership."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.boundary_path = self.project_root / "specs/groupware/deployment-boundary.json"
        self.provider_path = self.project_root / "specs/groupware/read-provider-contract.json"
        self.boundary = self._load_boundary()
        self.provider = self._load_provider()
        if self.provider.server_id != "groupware-read":
            raise GroupwareDeploymentContractError("Groupware read provider server identity is invalid")
        if self.boundary.future_write_mcp_server_id == self.provider.server_id:
            raise GroupwareDeploymentContractError(
                "Future Groupware write MCP identity must remain separate from the read provider"
            )
        if self.boundary.external_groupware_connector_path != self.provider.external_connector_project_path:
            raise GroupwareDeploymentContractError("Groupware external connector project paths drifted")

    def validate_fixture_directory(self) -> tuple[dict[str, object], ...]:
        root = self.project_root / "fixtures/groupware/read-provider-contract"
        if root.is_symlink() or not root.is_dir():
            raise GroupwareDeploymentContractError("Groupware provider fixture directory is missing or unsafe")
        fixtures: list[dict[str, object]] = []
        expected_by_tool = {item.tool_name: item for item in self.provider.tools}
        for tool_name in self.provider.allowed_tools:
            path = root / f"{tool_name}.json"
            payload = self._load_json(path)
            expected_keys = {
                "schema_version", "tool_name", "tenant_id", "principal_id", "roles",
                "delegation_id", "result_schema_version", "records", "mutated", "context_ref",
            }
            if set(payload) != expected_keys:
                raise GroupwareDeploymentContractError("Groupware provider fixture keys are not exact")
            if payload["schema_version"] != "okcanvas-groupware-read-provider-fixture-v1":
                raise GroupwareDeploymentContractError("Groupware provider fixture schema is unsupported")
            if payload["tool_name"] != tool_name or payload["mutated"] is not False:
                raise GroupwareDeploymentContractError("Groupware provider fixture is not exact read-only evidence")
            contract = expected_by_tool[tool_name]
            if payload["result_schema_version"] != contract.output_schema_version:
                raise GroupwareDeploymentContractError("Groupware provider fixture output schema drifted")
            for field in ("tenant_id", "principal_id", "delegation_id"):
                if not isinstance(payload[field], str) or not payload[field].strip():
                    raise GroupwareDeploymentContractError("Groupware provider fixture identity is incomplete")
            roles = payload["roles"]
            records = payload["records"]
            if not isinstance(roles, list) or not roles or not all(isinstance(item, str) and item for item in roles):
                raise GroupwareDeploymentContractError("Groupware provider fixture roles are invalid")
            if not isinstance(records, list) or len(records) > 50 or not all(isinstance(item, dict) for item in records):
                raise GroupwareDeploymentContractError("Groupware provider fixture records are invalid")
            fixtures.append(payload)
        extra = sorted(path.name for path in root.glob("*.json") if path.stem not in expected_by_tool)
        if extra:
            raise GroupwareDeploymentContractError("Undeclared Groupware provider fixtures are forbidden")
        return tuple(fixtures)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-deployment-foundation-v2",
            "boundary": self.boundary.to_public_dict(),
            "provider_contract": self.provider.to_public_dict(),
            "fixture_contract_expected_count": len(self.provider.tools),
            "actual_external_provider_implemented_in_runtime": False,
            "external_connector_project_selected": True,
            "external_connector_live_groupware_verified": False,
            "connector_example_required": False,
        }

    def _load_boundary(self) -> GroupwareDeploymentBoundary:
        raw = self._safe_bytes(self.boundary_path)
        payload = self._decode(raw)
        expected = {
            "schema_version", "read_agent_definition_location", "mcp_client_declaration_location",
            "mcp_provider_deployment", "mcp_provider_implementation_in_runtime",
            "organization_specific_adapter_in_runtime", "test_fixture_location",
            "read_agent_permanently_read_only", "write_extension_strategy",
            "future_write_agent_id", "future_write_mcp_server_id",
            "external_connector_repository", "external_groupware_connector_path",
            "connector_examples_repository", "groupware_api_fake_example_path",
            "connector_examples_required", "groupware_api_fake_is_mcp_server",
        }
        if set(payload) != expected or payload["schema_version"] != "okcanvas-groupware-deployment-boundary-v2":
            raise GroupwareDeploymentContractError("Groupware deployment boundary keys or schema are invalid")
        exact = {
            "read_agent_definition_location": "runtime-internal",
            "mcp_client_declaration_location": "runtime-internal",
            "mcp_provider_deployment": "external-connector-service",
            "mcp_provider_implementation_in_runtime": False,
            "organization_specific_adapter_in_runtime": False,
            "test_fixture_location": "runtime-internal",
            "read_agent_permanently_read_only": True,
            "write_extension_strategy": "separate-agent-separate-mcp-separate-credential",
            "external_connector_repository": "okcanvas-connectors",
            "external_groupware_connector_path": "okcanvas-connectors/groupware-mcp-server",
            "connector_examples_repository": "okcanvas-connector-examples",
            "groupware_api_fake_example_path": "okcanvas-connector-examples/groupware/groupware-api-fake",
            "connector_examples_required": False,
            "groupware_api_fake_is_mcp_server": False,
        }
        if any(payload[key] != value for key, value in exact.items()):
            raise GroupwareDeploymentContractError("Groupware deployment ownership boundary drifted")
        for key in ("future_write_agent_id", "future_write_mcp_server_id"):
            if not isinstance(payload[key], str) or not _ID_RE.fullmatch(payload[key]):
                raise GroupwareDeploymentContractError("Future Groupware write identity is invalid")
        for key in (
            "external_connector_repository", "external_groupware_connector_path",
            "connector_examples_repository", "groupware_api_fake_example_path",
        ):
            if not isinstance(payload[key], str) or not _PROJECT_PATH_RE.fullmatch(payload[key]):
                raise GroupwareDeploymentContractError("Groupware project path is invalid")
        return GroupwareDeploymentBoundary(
            **{key: payload[key] for key in expected if key != "schema_version"},
            boundary_sha256=hashlib.sha256(raw).hexdigest(),
        )

    def _load_provider(self) -> GroupwareReadProviderContract:
        raw = self._safe_bytes(self.provider_path)
        payload = self._decode(raw)
        expected = {
            "schema_version", "server_id", "transport", "provider_deployment",
            "provider_implemented_in_runtime", "required_identity_fields",
            "required_identity_headers", "external_connector_project_path",
            "credential_reference_transmitted", "tools",
        }
        if set(payload) != expected or payload["schema_version"] != "okcanvas-groupware-read-provider-contract-v3":
            raise GroupwareDeploymentContractError("Groupware read provider contract keys or schema are invalid")
        if payload["server_id"] != "groupware-read" or payload["transport"] != "remote-streamable-http":
            raise GroupwareDeploymentContractError("Groupware read provider transport identity drifted")
        if payload["provider_deployment"] != "external-connector-service" or payload["provider_implemented_in_runtime"] is not False:
            raise GroupwareDeploymentContractError("Groupware read provider ownership drifted")
        identity_fields = payload["required_identity_fields"]
        if identity_fields != ["tenant_id", "principal_id", "roles", "delegation_id"]:
            raise GroupwareDeploymentContractError("Groupware read provider delegated identity fields are not exact")
        identity_headers = payload["required_identity_headers"]
        expected_headers = [
            "X-OKCanvas-Tenant-ID", "X-OKCanvas-Principal-ID",
            "X-OKCanvas-Roles", "X-OKCanvas-Delegation-ID",
        ]
        if identity_headers != expected_headers:
            raise GroupwareDeploymentContractError("Groupware read provider delegated headers are not exact")
        project_path = payload["external_connector_project_path"]
        if project_path != "okcanvas-connectors/groupware-mcp-server":
            raise GroupwareDeploymentContractError("Groupware external connector path drifted")
        if payload["credential_reference_transmitted"] is not False:
            raise GroupwareDeploymentContractError("Credential references must not cross the MCP boundary")
        tools_raw = payload["tools"]
        if not isinstance(tools_raw, list) or len(tools_raw) != 3:
            raise GroupwareDeploymentContractError("Groupware read provider must declare exactly three tools")
        tools: list[GroupwareProviderToolContract] = []
        for item in tools_raw:
            if not isinstance(item, dict) or set(item) != {
                "tool_name", "input_schema_version", "output_schema_version", "mutates"
            }:
                raise GroupwareDeploymentContractError("Groupware provider Tool contract keys are not exact")
            if not isinstance(item["tool_name"], str) or not _TOOL_RE.fullmatch(item["tool_name"]):
                raise GroupwareDeploymentContractError("Groupware provider Tool name is invalid")
            if item["mutates"] is not False:
                raise GroupwareDeploymentContractError("Groupware provider Tool mutation is forbidden")
            if not all(
                isinstance(item[key], str) and _SCHEMA_RE.fullmatch(item[key])
                for key in ("input_schema_version", "output_schema_version")
            ):
                raise GroupwareDeploymentContractError("Groupware provider Tool schema identity is invalid")
            tools.append(GroupwareProviderToolContract(**item))
        names = tuple(item.tool_name for item in tools)
        if names != ("search_notices", "search_mail", "list_calendar_events"):
            raise GroupwareDeploymentContractError("Groupware provider Tool inventory is not exact")
        return GroupwareReadProviderContract(
            server_id=str(payload["server_id"]),
            transport=str(payload["transport"]),
            provider_deployment=str(payload["provider_deployment"]),
            provider_implemented_in_runtime=bool(payload["provider_implemented_in_runtime"]),
            required_identity_fields=tuple(str(item) for item in identity_fields),
            required_identity_headers=tuple(str(item) for item in identity_headers),
            external_connector_project_path=str(project_path),
            credential_reference_transmitted=False,
            tools=tuple(tools),
            contract_sha256=hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _decode(raw: bytes) -> dict[str, object]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GroupwareDeploymentContractError("Groupware deployment JSON is invalid") from exc
        if not isinstance(payload, dict):
            raise GroupwareDeploymentContractError("Groupware deployment JSON must be an object")
        return payload

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        return GroupwareDeploymentCatalog._decode(GroupwareDeploymentCatalog._safe_bytes(path))

    @staticmethod
    def _safe_bytes(path: Path) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise GroupwareDeploymentContractError(f"Groupware deployment file is missing or unsafe: {path}")
        return path.read_bytes()
