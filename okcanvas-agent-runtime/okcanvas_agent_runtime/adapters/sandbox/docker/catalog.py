from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.adapters.sandbox.docker.errors import SandboxProviderContractError, SandboxRuntimePolicyError
from okcanvas_agent_runtime.adapters.sandbox.docker.models import SandboxProviderContract, SandboxRuntimeFoundation, SandboxRuntimePolicy


class SandboxRuntimeCatalog:
    """Load the closed Product-owned Sandbox contract without starting a container."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "sandbox").resolve()
        self.policy_path = self.spec_root / "policies" / "default-sandbox-runtime-policy.json"
        self.provider_path = self.spec_root / "providers" / "docker-local-v1" / "provider.json"

    def resolve(self) -> SandboxRuntimeFoundation:
        policy = self._resolve_policy()
        provider = self._resolve_provider()
        if not policy.foundation_enabled:
            raise SandboxRuntimePolicyError("Sandbox Runtime foundation must remain enabled")
        if not policy.execution_enabled or not policy.provider_lifecycle_enabled:
            raise SandboxRuntimePolicyError("STEP074 provider lifecycle must be enabled")
        if not policy.agent_execution_enabled:
            raise SandboxRuntimePolicyError("STEP075 requires Product-owned Agent Sandbox execution")
        if not policy.docker_runtime_calls_enabled:
            raise SandboxRuntimePolicyError("STEP074 provider lifecycle requires Docker calls")
        if policy.default_workspace_access != "none":
            raise SandboxRuntimePolicyError("STEP075 default workspace access must remain none")
        if policy.active_workspace_access_modes != ("none", "sandbox-readonly-v1"):
            raise SandboxRuntimePolicyError("STEP075 active workspace modes are not exact")
        if not policy.physical_workspace_materialization_enabled:
            raise SandboxRuntimePolicyError("STEP075 requires bounded physical workspace materialization")
        if policy.network_mode != provider.network_mode or policy.network_mode != "none":
            raise SandboxRuntimePolicyError("Sandbox network mode must remain none")
        if policy.exposed_ports != provider.exposed_ports or policy.exposed_ports:
            raise SandboxRuntimePolicyError("Sandbox ports must remain disabled")
        if policy.automatic_image_pull_enabled or provider.runtime_image_pull_enabled:
            raise SandboxRuntimePolicyError("Runtime image pull must remain disabled")
        if any(
            (
                policy.host_bind_mounts_enabled,
                policy.remote_mounts_enabled,
                policy.secrets_enabled,
                policy.automatic_resume_enabled,
                policy.snapshot_resume_enabled,
                policy.shell_enabled,
                policy.apply_patch_enabled,
                policy.skill_materialization_enabled,
                policy.model_selected_provider_enabled,
                policy.model_selected_host_path_enabled,
                policy.sdk_default_capabilities_allowed,
                provider.host_bind_mounts_enabled,
                provider.remote_mounts_enabled,
                provider.docker_socket_mount_enabled,
                provider.privileged,
                provider.container_environment_enabled,
                provider.resume_enabled,
                provider.snapshot_enabled,
                provider.shell_enabled,
                provider.apply_patch_enabled,
                provider.skill_materialization_enabled,
            )
        ):
            raise SandboxRuntimePolicyError("STEP075 forbidden Sandbox capability is enabled")
        if not provider.execution_enabled or not provider.container_lifecycle_enabled:
            raise SandboxProviderContractError("STEP075 Docker lifecycle is not enabled")
        if provider.cap_add:
            raise SandboxProviderContractError("Sandbox provider cannot add Linux capabilities")
        if provider.required_cap_drop != ("ALL",):
            raise SandboxProviderContractError("Sandbox provider must drop all capabilities")
        if not all(
            (
                provider.no_new_privileges_required,
                provider.read_only_root_filesystem_required,
                provider.non_root_user_required,
                provider.automatic_delete_required,
                provider.orphan_reconciliation_required,
            )
        ):
            raise SandboxProviderContractError("Required Docker lifecycle controls are incomplete")
        canonical = self._canonical(
            {
                "schema_version": "okcanvas-sandbox-runtime-foundation-v1",
                "policy": policy.to_binding_dict(),
                "provider": provider.to_binding_dict(),
            }
        )
        return SandboxRuntimeFoundation(
            policy=policy,
            provider=provider,
            foundation_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def validate_agent_workspace_access(self, workspace_access: str) -> None:
        foundation = self.resolve()
        if workspace_access not in foundation.policy.active_workspace_access_modes:
            raise SandboxRuntimePolicyError(
                "Agent workspace access is not active in the Product Sandbox policy"
            )

    def _resolve_policy(self) -> SandboxRuntimePolicy:
        payload, canonical = self._read_exact_json(
            self.policy_path, error_type=SandboxRuntimePolicyError
        )
        expected = {
            "schema_version", "policy_id", "version", "foundation_enabled",
            "execution_enabled", "agent_execution_enabled", "provider_lifecycle_enabled",
            "default_workspace_access", "declared_workspace_access_modes",
            "active_workspace_access_modes", "physical_workspace_materialization_enabled",
            "docker_runtime_calls_enabled", "network_mode", "exposed_ports",
            "host_bind_mounts_enabled", "remote_mounts_enabled", "secrets_enabled",
            "automatic_image_pull_enabled", "automatic_resume_enabled",
            "snapshot_resume_enabled", "shell_enabled", "apply_patch_enabled",
            "skill_materialization_enabled", "model_selected_provider_enabled",
            "model_selected_host_path_enabled", "sdk_default_capabilities_allowed",
        }
        if set(payload) != expected:
            raise SandboxRuntimePolicyError("Sandbox Runtime policy fields are not exact")
        if payload["schema_version"] != "okcanvas-sandbox-runtime-policy-v1":
            raise SandboxRuntimePolicyError("Unsupported Sandbox Runtime policy schema")
        if payload["policy_id"] != "default-product-sandbox-runtime-v1":
            raise SandboxRuntimePolicyError("Unexpected Sandbox Runtime policy ID")
        if payload["version"] != "1.2.0":
            raise SandboxRuntimePolicyError("Unexpected Sandbox Runtime policy version")
        declared = self._string_tuple(payload, "declared_workspace_access_modes")
        if declared != (
            "none", "sandbox-readonly-v1", "sandbox-patch-v1", "sandbox-shell-v1"
        ):
            raise SandboxRuntimePolicyError("Sandbox workspace mode declarations are not exact")
        return SandboxRuntimePolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            foundation_enabled=self._exact_bool(payload, "foundation_enabled", True),
            execution_enabled=self._exact_bool(payload, "execution_enabled", True),
            agent_execution_enabled=self._exact_bool(payload, "agent_execution_enabled", True),
            provider_lifecycle_enabled=self._exact_bool(payload, "provider_lifecycle_enabled", True),
            default_workspace_access=self._exact_string(payload, "default_workspace_access", "none"),
            declared_workspace_access_modes=declared,
            active_workspace_access_modes=self._string_tuple(payload, "active_workspace_access_modes"),
            physical_workspace_materialization_enabled=self._exact_bool(
                payload, "physical_workspace_materialization_enabled", True
            ),
            docker_runtime_calls_enabled=self._exact_bool(payload, "docker_runtime_calls_enabled", True),
            network_mode=self._exact_string(payload, "network_mode", "none"),
            exposed_ports=self._integer_tuple(payload, "exposed_ports"),
            host_bind_mounts_enabled=self._exact_bool(payload, "host_bind_mounts_enabled", False),
            remote_mounts_enabled=self._exact_bool(payload, "remote_mounts_enabled", False),
            secrets_enabled=self._exact_bool(payload, "secrets_enabled", False),
            automatic_image_pull_enabled=self._exact_bool(payload, "automatic_image_pull_enabled", False),
            automatic_resume_enabled=self._exact_bool(payload, "automatic_resume_enabled", False),
            snapshot_resume_enabled=self._exact_bool(payload, "snapshot_resume_enabled", False),
            shell_enabled=self._exact_bool(payload, "shell_enabled", False),
            apply_patch_enabled=self._exact_bool(payload, "apply_patch_enabled", False),
            skill_materialization_enabled=self._exact_bool(payload, "skill_materialization_enabled", False),
            model_selected_provider_enabled=self._exact_bool(payload, "model_selected_provider_enabled", False),
            model_selected_host_path_enabled=self._exact_bool(payload, "model_selected_host_path_enabled", False),
            sdk_default_capabilities_allowed=self._exact_bool(payload, "sdk_default_capabilities_allowed", False),
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def _resolve_provider(self) -> SandboxProviderContract:
        payload, canonical = self._read_exact_json(
            self.provider_path, error_type=SandboxProviderContractError
        )
        expected = {
            "schema_version", "provider_id", "version", "provider_kind",
            "implementation_mode", "execution_enabled", "container_lifecycle_enabled",
            "sdk_client_mode", "image_reference_mode", "runtime_image_pull_enabled",
            "command_mode", "container_environment_enabled", "network_mode", "exposed_ports",
            "host_bind_mounts_enabled", "remote_mounts_enabled", "docker_socket_mount_enabled",
            "privileged", "cap_add", "required_cap_drop", "no_new_privileges_required",
            "read_only_root_filesystem_required", "non_root_user_required", "non_root_user",
            "memory_limit_bytes", "nano_cpus", "pids_limit", "command_timeout_seconds",
            "stop_timeout_seconds", "max_captured_output_bytes", "required_labels",
            "resume_enabled", "snapshot_enabled", "automatic_delete_required",
            "orphan_reconciliation_required", "shell_enabled", "apply_patch_enabled",
            "skill_materialization_enabled", "workspace_materialization_mode",
            "workspace_archive_format", "workspace_materializer_user",
            "workspace_materializer_command", "workspace_mount_path",
            "workspace_tmpfs_max_bytes", "workspace_max_files",
            "workspace_max_total_bytes", "workspace_max_file_bytes",
            "workspace_allowed_commands",
        }
        if set(payload) != expected:
            raise SandboxProviderContractError("Sandbox provider fields are not exact")
        if payload["schema_version"] != "okcanvas-sandbox-provider-contract-v1":
            raise SandboxProviderContractError("Unsupported Sandbox provider schema")
        if payload["provider_id"] != "docker-local-v1":
            raise SandboxProviderContractError("STEP075 permits docker-local-v1 only")
        if payload["version"] != "1.3.0":
            raise SandboxProviderContractError("Unexpected Sandbox provider version")
        required_labels = self._string_tuple(payload, "required_labels")
        if required_labels != (
            "com.okcanvas.agent-runtime.sandbox",
            "com.okcanvas.agent-runtime.provider",
            "com.okcanvas.agent-runtime.step",
            "com.okcanvas.agent-runtime.acceptance-id",
        ):
            raise SandboxProviderContractError("Sandbox provider labels are not exact")
        if self._string_tuple(payload, "workspace_allowed_commands") != ("find", "cat", "grep", "tail"):
            raise SandboxProviderContractError("Sandbox read-only command allowlist is not exact")
        materializer_command = self._string_tuple(payload, "workspace_materializer_command")
        if materializer_command != ("tar", "-x", "-f", "-", "-C", "/workspace"):
            raise SandboxProviderContractError("Sandbox materializer command is not exact")
        return SandboxProviderContract(
            schema_version=str(payload["schema_version"]),
            provider_id=str(payload["provider_id"]),
            version=str(payload["version"]),
            provider_kind=self._exact_string(payload, "provider_kind", "local-docker"),
            implementation_mode=self._exact_string(
                payload, "implementation_mode", "product-owned-readonly-workspace-agent-v1"
            ),
            execution_enabled=self._exact_bool(payload, "execution_enabled", True),
            container_lifecycle_enabled=self._exact_bool(payload, "container_lifecycle_enabled", True),
            sdk_client_mode=self._exact_string(
                payload, "sdk_client_mode", "not-used-product-owned-docker-cli"
            ),
            image_reference_mode=self._exact_string(
                payload, "image_reference_mode", "local-tag-resolved-to-immutable-repodigest"
            ),
            runtime_image_pull_enabled=self._exact_bool(payload, "runtime_image_pull_enabled", False),
            command_mode=self._exact_string(payload, "command_mode", "product-owned-readonly-tool-command-only"),
            container_environment_enabled=self._exact_bool(payload, "container_environment_enabled", False),
            network_mode=self._exact_string(payload, "network_mode", "none"),
            exposed_ports=self._integer_tuple(payload, "exposed_ports"),
            host_bind_mounts_enabled=self._exact_bool(payload, "host_bind_mounts_enabled", False),
            remote_mounts_enabled=self._exact_bool(payload, "remote_mounts_enabled", False),
            docker_socket_mount_enabled=self._exact_bool(payload, "docker_socket_mount_enabled", False),
            privileged=self._exact_bool(payload, "privileged", False),
            cap_add=self._string_tuple(payload, "cap_add"),
            required_cap_drop=self._string_tuple(payload, "required_cap_drop"),
            no_new_privileges_required=self._exact_bool(payload, "no_new_privileges_required", True),
            read_only_root_filesystem_required=self._exact_bool(payload, "read_only_root_filesystem_required", True),
            non_root_user_required=self._exact_bool(payload, "non_root_user_required", True),
            non_root_user=self._exact_string(payload, "non_root_user", "65532:65532"),
            memory_limit_bytes=self._exact_int(payload, "memory_limit_bytes", 134217728),
            nano_cpus=self._exact_int(payload, "nano_cpus", 500000000),
            pids_limit=self._exact_int(payload, "pids_limit", 64),
            command_timeout_seconds=self._exact_int(payload, "command_timeout_seconds", 30),
            stop_timeout_seconds=self._exact_int(payload, "stop_timeout_seconds", 5),
            max_captured_output_bytes=self._exact_int(payload, "max_captured_output_bytes", 131072),
            required_labels=required_labels,
            resume_enabled=self._exact_bool(payload, "resume_enabled", False),
            snapshot_enabled=self._exact_bool(payload, "snapshot_enabled", False),
            automatic_delete_required=self._exact_bool(payload, "automatic_delete_required", True),
            orphan_reconciliation_required=self._exact_bool(payload, "orphan_reconciliation_required", True),
            shell_enabled=self._exact_bool(payload, "shell_enabled", False),
            apply_patch_enabled=self._exact_bool(payload, "apply_patch_enabled", False),
            skill_materialization_enabled=self._exact_bool(payload, "skill_materialization_enabled", False),
            workspace_materialization_mode=self._exact_string(
                payload, "workspace_materialization_mode", "docker-exec-stdin-tar-to-root-owned-tmpfs"
            ),
            workspace_archive_format=self._exact_string(payload, "workspace_archive_format", "gnu-tar-v1"),
            workspace_materializer_user=self._exact_string(payload, "workspace_materializer_user", "0:0"),
            workspace_materializer_command=materializer_command,
            workspace_mount_path=self._exact_string(payload, "workspace_mount_path", "/workspace"),
            workspace_tmpfs_max_bytes=self._exact_int(payload, "workspace_tmpfs_max_bytes", 33554432),
            workspace_max_files=self._exact_int(payload, "workspace_max_files", 3000),
            workspace_max_total_bytes=self._exact_int(payload, "workspace_max_total_bytes", 33554432),
            workspace_max_file_bytes=self._exact_int(payload, "workspace_max_file_bytes", 524288),
            workspace_allowed_commands=self._string_tuple(payload, "workspace_allowed_commands"),
            contract_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def _read_exact_json(
        self,
        path: Path,
        *,
        error_type: type[SandboxRuntimePolicyError] | type[SandboxProviderContractError],
    ) -> tuple[dict[str, Any], str]:
        if not self.spec_root.is_dir() or self.spec_root.is_symlink():
            raise error_type("Sandbox specification root is missing or unsafe")
        current = path
        while current != self.spec_root:
            if current.is_symlink():
                raise error_type("Symbolic Sandbox specification paths are forbidden")
            current = current.parent
        resolved = path.resolve()
        if self.spec_root not in resolved.parents or not path.is_file():
            raise error_type("Sandbox specification file is missing or escaped its root")
        try:
            payload = json.loads(path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise error_type("Sandbox specification is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise error_type("Sandbox specification must be a JSON object")
        return payload, self._canonical(payload)

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _exact_bool(payload: dict[str, Any], key: str, expected: bool) -> bool:
        if payload.get(key) is not expected:
            raise SandboxRuntimePolicyError(f"Sandbox field {key} is outside the contract")
        return expected

    @staticmethod
    def _exact_string(payload: dict[str, Any], key: str, expected: str) -> str:
        if payload.get(key) != expected:
            raise SandboxRuntimePolicyError(f"Sandbox field {key} is outside the contract")
        return expected

    @staticmethod
    def _exact_int(payload: dict[str, Any], key: str, expected: int) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or value != expected:
            raise SandboxRuntimePolicyError(f"Sandbox field {key} is outside the contract")
        return expected

    @staticmethod
    def _string_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
        value = payload.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise SandboxRuntimePolicyError(f"Sandbox field {key} must be a string list")
        if len(value) != len(set(value)):
            raise SandboxRuntimePolicyError(f"Sandbox field {key} contains duplicates")
        return tuple(value)

    @staticmethod
    def _integer_tuple(payload: dict[str, Any], key: str) -> tuple[int, ...]:
        value = payload.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in value
        ):
            raise SandboxRuntimePolicyError(f"Sandbox field {key} must be an integer list")
        return tuple(value)
