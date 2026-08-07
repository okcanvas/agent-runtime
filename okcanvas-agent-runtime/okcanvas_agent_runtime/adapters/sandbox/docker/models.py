from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxRuntimePolicy:
    schema_version: str
    policy_id: str
    version: str
    foundation_enabled: bool
    execution_enabled: bool
    agent_execution_enabled: bool
    provider_lifecycle_enabled: bool
    default_workspace_access: str
    declared_workspace_access_modes: tuple[str, ...]
    active_workspace_access_modes: tuple[str, ...]
    physical_workspace_materialization_enabled: bool
    docker_runtime_calls_enabled: bool
    network_mode: str
    exposed_ports: tuple[int, ...]
    host_bind_mounts_enabled: bool
    remote_mounts_enabled: bool
    secrets_enabled: bool
    automatic_image_pull_enabled: bool
    automatic_resume_enabled: bool
    snapshot_resume_enabled: bool
    shell_enabled: bool
    apply_patch_enabled: bool
    skill_materialization_enabled: bool
    model_selected_provider_enabled: bool
    model_selected_host_path_enabled: bool
    sdk_default_capabilities_allowed: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "foundation_enabled": self.foundation_enabled,
            "execution_enabled": self.execution_enabled,
            "agent_execution_enabled": self.agent_execution_enabled,
            "provider_lifecycle_enabled": self.provider_lifecycle_enabled,
            "default_workspace_access": self.default_workspace_access,
            "declared_workspace_access_modes": list(self.declared_workspace_access_modes),
            "active_workspace_access_modes": list(self.active_workspace_access_modes),
            "physical_workspace_materialization_enabled": self.physical_workspace_materialization_enabled,
            "docker_runtime_calls_enabled": self.docker_runtime_calls_enabled,
            "network_mode": self.network_mode,
            "exposed_ports": list(self.exposed_ports),
            "host_bind_mounts_enabled": self.host_bind_mounts_enabled,
            "remote_mounts_enabled": self.remote_mounts_enabled,
            "secrets_enabled": self.secrets_enabled,
            "automatic_image_pull_enabled": self.automatic_image_pull_enabled,
            "automatic_resume_enabled": self.automatic_resume_enabled,
            "snapshot_resume_enabled": self.snapshot_resume_enabled,
            "shell_enabled": self.shell_enabled,
            "apply_patch_enabled": self.apply_patch_enabled,
            "skill_materialization_enabled": self.skill_materialization_enabled,
            "model_selected_provider_enabled": self.model_selected_provider_enabled,
            "model_selected_host_path_enabled": self.model_selected_host_path_enabled,
            "sdk_default_capabilities_allowed": self.sdk_default_capabilities_allowed,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class SandboxProviderContract:
    schema_version: str
    provider_id: str
    version: str
    provider_kind: str
    implementation_mode: str
    execution_enabled: bool
    container_lifecycle_enabled: bool
    sdk_client_mode: str
    image_reference_mode: str
    runtime_image_pull_enabled: bool
    command_mode: str
    container_environment_enabled: bool
    network_mode: str
    exposed_ports: tuple[int, ...]
    host_bind_mounts_enabled: bool
    remote_mounts_enabled: bool
    docker_socket_mount_enabled: bool
    privileged: bool
    cap_add: tuple[str, ...]
    required_cap_drop: tuple[str, ...]
    no_new_privileges_required: bool
    read_only_root_filesystem_required: bool
    non_root_user_required: bool
    non_root_user: str
    memory_limit_bytes: int
    nano_cpus: int
    pids_limit: int
    command_timeout_seconds: int
    stop_timeout_seconds: int
    max_captured_output_bytes: int
    required_labels: tuple[str, ...]
    resume_enabled: bool
    snapshot_enabled: bool
    automatic_delete_required: bool
    orphan_reconciliation_required: bool
    shell_enabled: bool
    apply_patch_enabled: bool
    skill_materialization_enabled: bool
    workspace_materialization_mode: str
    workspace_archive_format: str
    workspace_materializer_user: str
    workspace_materializer_command: tuple[str, ...]
    workspace_mount_path: str
    workspace_tmpfs_max_bytes: int
    workspace_max_files: int
    workspace_max_total_bytes: int
    workspace_max_file_bytes: int
    workspace_allowed_commands: tuple[str, ...]
    contract_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "version": self.version,
            "provider_kind": self.provider_kind,
            "implementation_mode": self.implementation_mode,
            "execution_enabled": self.execution_enabled,
            "container_lifecycle_enabled": self.container_lifecycle_enabled,
            "sdk_client_mode": self.sdk_client_mode,
            "image_reference_mode": self.image_reference_mode,
            "runtime_image_pull_enabled": self.runtime_image_pull_enabled,
            "command_mode": self.command_mode,
            "container_environment_enabled": self.container_environment_enabled,
            "network_mode": self.network_mode,
            "exposed_ports": list(self.exposed_ports),
            "host_bind_mounts_enabled": self.host_bind_mounts_enabled,
            "remote_mounts_enabled": self.remote_mounts_enabled,
            "docker_socket_mount_enabled": self.docker_socket_mount_enabled,
            "privileged": self.privileged,
            "cap_add": list(self.cap_add),
            "required_cap_drop": list(self.required_cap_drop),
            "no_new_privileges_required": self.no_new_privileges_required,
            "read_only_root_filesystem_required": self.read_only_root_filesystem_required,
            "non_root_user_required": self.non_root_user_required,
            "non_root_user": self.non_root_user,
            "memory_limit_bytes": self.memory_limit_bytes,
            "nano_cpus": self.nano_cpus,
            "pids_limit": self.pids_limit,
            "command_timeout_seconds": self.command_timeout_seconds,
            "stop_timeout_seconds": self.stop_timeout_seconds,
            "max_captured_output_bytes": self.max_captured_output_bytes,
            "required_labels": list(self.required_labels),
            "resume_enabled": self.resume_enabled,
            "snapshot_enabled": self.snapshot_enabled,
            "automatic_delete_required": self.automatic_delete_required,
            "orphan_reconciliation_required": self.orphan_reconciliation_required,
            "shell_enabled": self.shell_enabled,
            "apply_patch_enabled": self.apply_patch_enabled,
            "skill_materialization_enabled": self.skill_materialization_enabled,
            "workspace_materialization_mode": self.workspace_materialization_mode,
            "workspace_archive_format": self.workspace_archive_format,
            "workspace_materializer_user": self.workspace_materializer_user,
            "workspace_materializer_command": list(self.workspace_materializer_command),
            "workspace_mount_path": self.workspace_mount_path,
            "workspace_tmpfs_max_bytes": self.workspace_tmpfs_max_bytes,
            "workspace_max_files": self.workspace_max_files,
            "workspace_max_total_bytes": self.workspace_max_total_bytes,
            "workspace_max_file_bytes": self.workspace_max_file_bytes,
            "workspace_allowed_commands": list(self.workspace_allowed_commands),
            "contract_sha256": self.contract_sha256,
        }


@dataclass(frozen=True)
class SandboxRuntimeFoundation:
    policy: SandboxRuntimePolicy
    provider: SandboxProviderContract
    foundation_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-sandbox-runtime-foundation-v1",
            "policy": self.policy.to_binding_dict(),
            "provider": self.provider.to_binding_dict(),
            "foundation_sha256": self.foundation_sha256,
        }

    def to_public_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.version,
            "policy_sha256": self.policy.policy_sha256,
            "foundation_sha256": self.foundation_sha256,
            "foundation_enabled": self.policy.foundation_enabled,
            "execution_enabled": self.policy.execution_enabled,
            "agent_execution_enabled": self.policy.agent_execution_enabled,
            "provider_lifecycle_enabled": self.policy.provider_lifecycle_enabled,
            "default_workspace_access": self.policy.default_workspace_access,
            "declared_workspace_access_modes": list(self.policy.declared_workspace_access_modes),
            "active_workspace_access_modes": list(self.policy.active_workspace_access_modes),
            "physical_workspace_materialization_enabled": self.policy.physical_workspace_materialization_enabled,
            "docker_runtime_calls_enabled": self.policy.docker_runtime_calls_enabled,
            "network_mode": self.policy.network_mode,
            "exposed_ports": list(self.policy.exposed_ports),
            "host_bind_mounts_enabled": self.policy.host_bind_mounts_enabled,
            "remote_mounts_enabled": self.policy.remote_mounts_enabled,
            "secrets_enabled": self.policy.secrets_enabled,
            "automatic_image_pull_enabled": self.policy.automatic_image_pull_enabled,
            "automatic_resume_enabled": self.policy.automatic_resume_enabled,
            "snapshot_resume_enabled": self.policy.snapshot_resume_enabled,
            "shell_enabled": self.policy.shell_enabled,
            "apply_patch_enabled": self.policy.apply_patch_enabled,
            "skill_materialization_enabled": self.policy.skill_materialization_enabled,
            "model_selected_provider_enabled": self.policy.model_selected_provider_enabled,
            "model_selected_host_path_enabled": self.policy.model_selected_host_path_enabled,
            "sdk_default_capabilities_allowed": self.policy.sdk_default_capabilities_allowed,
            "provider_id": self.provider.provider_id,
            "provider_version": self.provider.version,
            "provider_contract_sha256": self.provider.contract_sha256,
            "provider_kind": self.provider.provider_kind,
            "provider_implementation_mode": self.provider.implementation_mode,
            "provider_execution_enabled": self.provider.execution_enabled,
            "provider_container_lifecycle_enabled": self.provider.container_lifecycle_enabled,
            "provider_image_reference_mode": self.provider.image_reference_mode,
            "provider_runtime_image_pull_enabled": self.provider.runtime_image_pull_enabled,
            "provider_command_mode": self.provider.command_mode,
            "provider_container_environment_enabled": self.provider.container_environment_enabled,
            "provider_workspace_materialization_mode": self.provider.workspace_materialization_mode,
            "provider_workspace_archive_format": self.provider.workspace_archive_format,
            "provider_workspace_materializer_user": self.provider.workspace_materializer_user,
            "provider_workspace_materializer_command": list(self.provider.workspace_materializer_command),
            "provider_workspace_mount_path": self.provider.workspace_mount_path,
            "provider_workspace_tmpfs_max_bytes": self.provider.workspace_tmpfs_max_bytes,
            "provider_workspace_max_files": self.provider.workspace_max_files,
            "provider_workspace_max_total_bytes": self.provider.workspace_max_total_bytes,
            "provider_workspace_max_file_bytes": self.provider.workspace_max_file_bytes,
            "provider_workspace_allowed_commands": list(self.provider.workspace_allowed_commands),
            "provider_docker_socket_mount_enabled": self.provider.docker_socket_mount_enabled,
            "provider_privileged": self.provider.privileged,
            "provider_required_cap_drop": list(self.provider.required_cap_drop),
            "provider_no_new_privileges_required": self.provider.no_new_privileges_required,
            "provider_read_only_root_filesystem_required": self.provider.read_only_root_filesystem_required,
            "provider_non_root_user_required": self.provider.non_root_user_required,
            "provider_non_root_user": self.provider.non_root_user,
            "provider_memory_limit_bytes": self.provider.memory_limit_bytes,
            "provider_nano_cpus": self.provider.nano_cpus,
            "provider_pids_limit": self.provider.pids_limit,
            "provider_command_timeout_seconds": self.provider.command_timeout_seconds,
            "provider_stop_timeout_seconds": self.provider.stop_timeout_seconds,
            "provider_max_captured_output_bytes": self.provider.max_captured_output_bytes,
            "provider_required_labels": list(self.provider.required_labels),
            "provider_automatic_delete_required": self.provider.automatic_delete_required,
            "provider_orphan_reconciliation_required": self.provider.orphan_reconciliation_required,
        }
