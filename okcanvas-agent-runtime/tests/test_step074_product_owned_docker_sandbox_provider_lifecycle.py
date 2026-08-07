from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.sandbox.docker import (
    DockerCommandResult,
    DockerSandboxLifecycleService,
    SandboxDockerError,
    SandboxExecutionDisabledError,
    SandboxRuntimeCatalog,
    SandboxRuntimeService,
    SubprocessDockerCommandRunner,
)

ROOT = Path(__file__).resolve().parents[1]
IMAGE_TAG = "hello-world:latest"
IMAGE_DIGEST = "hello-world@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
CONTAINER_ID = "c" * 64


class ScriptedRunner:
    def __init__(self, results: list[DockerCommandResult]) -> None:
        self.results = deque(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments, *, timeout_seconds: int) -> DockerCommandResult:
        assert timeout_seconds == 30
        args = tuple(arguments)
        self.calls.append(args)
        assert self.results, f"Unexpected Docker command: {args}"
        result = self.results.popleft()
        assert result.arguments == args
        return result


def _result(args: list[str], *, stdout: str = "", stderr: str = "", returncode: int = 0) -> DockerCommandResult:
    return DockerCommandResult(tuple(args), returncode, stdout, stderr)


def _image_inspect() -> str:
    return json.dumps(
        [
            {
                "Id": IMAGE_ID,
                "RepoDigests": [IMAGE_DIGEST],
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {"User": ""},
            }
        ]
    )


def _container_inspect(*, state: str, running: bool, exit_code: int, network: str = "none") -> str:
    return json.dumps(
        [
            {
                "Id": CONTAINER_ID,
                "Config": {
                    "Image": IMAGE_DIGEST,
                    "User": "65532:65532",
                    "Labels": {
                        "com.okcanvas.agent-runtime.sandbox": "true",
                        "com.okcanvas.agent-runtime.provider": "docker-local-v1",
                        "com.okcanvas.agent-runtime.step": "STEP074",
                        "com.okcanvas.agent-runtime.acceptance-id": "acceptance-074",
                    },
                    "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
                },
                "HostConfig": {
                    "NetworkMode": network,
                    "PortBindings": None,
                    "PublishAllPorts": False,
                    "Binds": None,
                    "Privileged": False,
                    "CapAdd": None,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges"],
                    "ReadonlyRootfs": True,
                    "Memory": 134217728,
                    "NanoCpus": 500000000,
                    "PidsLimit": 64,
                    "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                },
                "Mounts": [],
                "NetworkSettings": {"Networks": {"none": {}}},
                "State": {"Status": state, "Running": running, "ExitCode": exit_code},
            }
        ]
    )


def _success_runner() -> ScriptedRunner:
    create = [
        "container", "create", "--pull=never", "--name", "okcanvas-step074-acceptance-074",
        "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt",
        "no-new-privileges", "--pids-limit", "64", "--memory", "134217728", "--cpus",
        "0.5", "--user", "65532:65532", "--restart", "no", "--stop-timeout", "5",
        "--no-healthcheck",
        "--label", "com.okcanvas.agent-runtime.sandbox=true",
        "--label", "com.okcanvas.agent-runtime.provider=docker-local-v1",
        "--label", "com.okcanvas.agent-runtime.step=STEP074",
        "--label", "com.okcanvas.agent-runtime.acceptance-id=acceptance-074",
        IMAGE_DIGEST,
    ]
    return ScriptedRunner(
        [
            _result(["version", "--format", "{{json .Server.Version}}"], stdout='"27.5.1"\n'),
            _result(["image", "inspect", IMAGE_TAG], stdout=_image_inspect()),
            _result(create, stdout=CONTAINER_ID + "\n"),
            _result(["container", "inspect", CONTAINER_ID], stdout=_container_inspect(state="created", running=False, exit_code=0)),
            _result(["container", "start", "--attach", CONTAINER_ID], stdout="Hello from Docker!\n"),
            _result(["container", "inspect", CONTAINER_ID], stdout=_container_inspect(state="exited", running=False, exit_code=0)),
            _result(["container", "rm", "--force", "--volumes", CONTAINER_ID], stdout=CONTAINER_ID + "\n"),
            _result(["container", "ls", "--all", "--quiet", "--filter", "label=com.okcanvas.agent-runtime.acceptance-id=acceptance-074"], stdout=""),
        ]
    )


def test_step074_windows_live_evidence_is_exact() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP074_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    assert evidence["state"] == "PASSED"
    assert evidence["deterministic_acceptance"] == {"passed_checks": 28, "total_checks": 28}
    assert evidence["live_acceptance"] == {"passed_checks": 27, "total_checks": 27}
    assert evidence["docker_calls"] == 8
    assert evidence["cleanup_state"] == "COMPLETED"
    assert evidence["orphan_count"] == 0
    assert evidence["external_network_calls"] == evidence["model_calls"] == 0
    assert evidence["security"]["runtime_image_pull_absent"] is True


def test_step074_windows_live_closure_is_preserved_under_step075() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_sandbox_foundation_windows_accepted is True
    assert info.product_owned_sandbox_execution_enabled is True
    assert info.product_owned_sandbox_provider_lifecycle_enabled is True
    assert info.product_owned_sandbox_docker_calls_enabled is True
    assert info.product_owned_docker_lifecycle_implemented is True
    assert info.product_owned_docker_lifecycle_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_catalog_preserves_provider_lifecycle_and_enables_readonly_agent_only() -> None:
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    assert foundation.policy.version == "1.2.0"
    assert foundation.policy.execution_enabled is True
    assert foundation.policy.agent_execution_enabled is True
    assert foundation.policy.provider_lifecycle_enabled is True
    assert foundation.policy.docker_runtime_calls_enabled is True
    assert foundation.policy.active_workspace_access_modes == ("none", "sandbox-readonly-v1")
    assert foundation.policy.physical_workspace_materialization_enabled is True
    assert foundation.provider.version == "1.3.0"
    assert foundation.provider.implementation_mode == "product-owned-readonly-workspace-agent-v1"
    assert foundation.provider.container_lifecycle_enabled is True
    assert foundation.provider.runtime_image_pull_enabled is False
    assert foundation.provider.command_mode == "product-owned-readonly-tool-command-only"
    assert foundation.provider.container_environment_enabled is False
    assert foundation.provider.workspace_materialization_mode == "docker-exec-stdin-tar-to-root-owned-tmpfs"
    assert foundation.provider.workspace_archive_format == "gnu-tar-v1"
    assert foundation.provider.workspace_materializer_user == "0:0"
    assert foundation.provider.workspace_materializer_command == ("tar", "-x", "-f", "-", "-C", "/workspace")


def test_catalog_binds_hardened_resource_and_identity_controls() -> None:
    provider = SandboxRuntimeCatalog(ROOT).resolve().provider
    assert provider.network_mode == "none"
    assert provider.exposed_ports == ()
    assert provider.host_bind_mounts_enabled is False
    assert provider.remote_mounts_enabled is False
    assert provider.docker_socket_mount_enabled is False
    assert provider.privileged is False
    assert provider.cap_add == ()
    assert provider.required_cap_drop == ("ALL",)
    assert provider.no_new_privileges_required is True
    assert provider.read_only_root_filesystem_required is True
    assert provider.non_root_user == "65532:65532"
    assert provider.memory_limit_bytes == 134217728
    assert provider.nano_cpus == 500000000
    assert provider.pids_limit == 64
    assert provider.command_timeout_seconds == 30
    assert provider.automatic_delete_required is True
    assert provider.orphan_reconciliation_required is True


def test_service_allows_provider_lifecycle_and_readonly_but_rejects_shell() -> None:
    service = SandboxRuntimeService(SandboxRuntimeCatalog(ROOT).resolve())
    service.require_provider_lifecycle()
    service.require_agent_execution("sandbox-readonly-v1")
    with pytest.raises(SandboxExecutionDisabledError):
        service.require_agent_execution("sandbox-shell-v1")


def test_original_agent_bindings_remain_none_and_all_bind_current_foundation() -> None:
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    assert len(definitions) == 32
    original = [item for item in definitions if item.agent_id != "sandbox-readonly-coding-agent"]
    assert {item.workspace_access for item in original} == {"none"}
    catalog = AgentRuntimeBindingCatalog(ROOT)
    bindings = [catalog.resolve(item) for item in definitions]
    assert len(bindings) == 32
    assert len({item.sandbox_runtime_foundation["foundation_sha256"] for item in bindings}) == 1
    assert all(item.sandbox_runtime_foundation["policy"]["agent_execution_enabled"] is True for item in bindings)
    assert all(item.sandbox_runtime_foundation["provider"]["container_lifecycle_enabled"] is True for item in bindings)


def test_public_metadata_exposes_policy_not_image_or_host_path() -> None:
    public = SandboxRuntimeCatalog(ROOT).resolve().to_public_dict()
    serialized = json.dumps(public, sort_keys=True)
    assert public["provider_lifecycle_enabled"] is True
    assert public["agent_execution_enabled"] is True
    assert public["provider_runtime_image_pull_enabled"] is False
    assert public["provider_non_root_user"] == "65532:65532"
    assert "immutable_reference" not in serialized
    assert "requested_reference" not in serialized
    assert "host_path" not in public
    assert "runtime_image" not in public
    assert "docker.sock" not in serialized


def test_lifecycle_uses_digest_hardening_and_deletes_container() -> None:
    runner = _success_runner()
    result = DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        IMAGE_TAG, acceptance_id="acceptance-074"
    )
    assert result.state == "PASSED"
    assert result.image is not None
    assert result.image.immutable_reference == IMAGE_DIGEST
    assert result.created is result.started is result.exited is result.deleted is True
    assert result.exit_code == 0
    assert result.orphan_count == 0
    assert result.cleanup_state == "COMPLETED"
    assert result.output_sha256 is not None
    assert result.output_bytes > 0
    assert len(runner.results) == 0


def test_create_command_has_no_shell_env_mount_port_or_pull() -> None:
    runner = _success_runner()
    DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        IMAGE_TAG, acceptance_id="acceptance-074"
    )
    create = next(call for call in runner.calls if call[:2] == ("container", "create"))
    assert "--pull=never" in create
    assert "--network" in create and create[create.index("--network") + 1] == "none"
    assert "--read-only" in create
    assert ("--cap-drop", "ALL") == create[create.index("--cap-drop"):create.index("--cap-drop") + 2]
    assert ("--security-opt", "no-new-privileges") == create[create.index("--security-opt"):create.index("--security-opt") + 2]
    assert "--privileged" not in create
    assert "--cap-add" not in create
    assert "--env" not in create and "-e" not in create
    assert "--mount" not in create and "--volume" not in create and "-v" not in create
    assert "--publish" not in create and "-p" not in create and "-P" not in create
    assert create[-1] == IMAGE_DIGEST


def test_start_failure_still_deletes_container() -> None:
    runner = _success_runner()
    values = list(runner.results)
    values[4] = _result(["container", "start", "--attach", CONTAINER_ID], stderr="failed", returncode=1)
    values = values[:5] + values[6:]
    runner = ScriptedRunner(values)
    result = DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        IMAGE_TAG, acceptance_id="acceptance-074"
    )
    assert result.state == "FAILED"
    assert result.error_code == "DOCKER_COMMAND_FAILED"
    assert result.created is True
    assert result.started is False
    assert result.deleted is True
    assert result.cleanup_state == "COMPLETED"
    assert result.orphan_count == 0


def test_security_mismatch_fails_before_start_and_still_deletes() -> None:
    runner = _success_runner()
    values = list(runner.results)
    values[3] = _result(["container", "inspect", CONTAINER_ID], stdout=_container_inspect(state="created", running=False, exit_code=0, network="bridge"))
    values = values[:4] + values[6:]
    runner = ScriptedRunner(values)
    result = DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        IMAGE_TAG, acceptance_id="acceptance-074"
    )
    assert result.state == "FAILED"
    assert result.error_code == "CONTAINER_SECURITY_MISMATCH"
    assert result.started is False
    assert result.deleted is True
    assert result.orphan_count == 0


def test_missing_local_image_never_calls_create_or_pull() -> None:
    runner = ScriptedRunner(
        [
            _result(["version", "--format", "{{json .Server.Version}}"], stdout='"27.5.1"'),
            _result(["image", "inspect", IMAGE_TAG], stderr="No such image", returncode=1),
            _result(["container", "ls", "--all", "--quiet", "--filter", "label=com.okcanvas.agent-runtime.acceptance-id=acceptance-074"], stdout=""),
        ]
    )
    result = DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        IMAGE_TAG, acceptance_id="acceptance-074"
    )
    assert result.state == "FAILED"
    assert result.created is False
    assert all(call[:2] != ("container", "create") for call in runner.calls)
    assert all("pull" not in call for call in runner.calls)


def test_digest_reference_must_match_local_repodigest() -> None:
    other = "hello-world@sha256:" + "d" * 64
    runner = ScriptedRunner(
        [
            _result(["version", "--format", "{{json .Server.Version}}"], stdout='"27.5.1"'),
            _result(["image", "inspect", other], stdout=_image_inspect()),
            _result(["container", "ls", "--all", "--quiet", "--filter", "label=com.okcanvas.agent-runtime.acceptance-id=acceptance-074"], stdout=""),
        ]
    )
    result = DockerSandboxLifecycleService(SandboxRuntimeCatalog(ROOT).resolve(), runner).run_probe(
        other, acceptance_id="acceptance-074"
    )
    assert result.state == "FAILED"
    assert result.error_code == "IMAGE_DIGEST_MISMATCH"


def test_invalid_image_and_acceptance_identifiers_are_rejected() -> None:
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    runner = ScriptedRunner([])
    service = DockerSandboxLifecycleService(foundation, runner)
    with pytest.raises(SandboxDockerError):
        service.run_probe(IMAGE_TAG, acceptance_id="../escape")


def test_docker_subprocess_environment_excludes_product_secrets() -> None:
    environment = SubprocessDockerCommandRunner.sanitized_environment(
        {
            "PATH": "x",
            "SYSTEMROOT": "y",
            "DOCKER_HOST": "npipe:////./pipe/docker_engine",
            "OPENAI_API_KEY": "secret",
            "OKCANVAS_PROTECTED_PAYLOAD_KEY": "secret2",
            "OKCANVAS_AGENT_MODEL": "gpt-4.1",
        }
    )
    assert environment["PATH"] == "x"
    assert "DOCKER_HOST" in environment
    assert "OPENAI_API_KEY" not in environment
    assert "OKCANVAS_PROTECTED_PAYLOAD_KEY" not in environment
    assert "OKCANVAS_AGENT_MODEL" not in environment


def test_step073_windows_acceptance_is_recorded_exactly() -> None:
    evidence = json.loads((ROOT / "docs/evidence/STEP073_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(encoding="utf-8"))
    assert evidence["state"] == "PASSED"
    assert evidence["passed_checks"] == evidence["total_checks"] == 26
    assert evidence["agent_definition_count"] == 26
    assert evidence["docker_calls"] == evidence["external_network_calls"] == evidence["model_calls"] == 0


def test_service_endpoint_is_authenticated_metadata_only(tmp_path: Path) -> None:
    registry = json.dumps(
        {
            "schema_version": "okcanvas-service-client-token-registry-v1",
            "tokens": [
                {
                    "token_id": "step074-user",
                    "token_sha256": __import__("hashlib").sha256(b"step074-token").hexdigest(),
                    "tenant_id": "tenant-step074",
                    "principal_id": "principal-step074",
                    "roles": ["agent-user"],
                }
            ],
        }
    )
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step074-admin-key-value",
        run_submitter_key="step074-submitter-key-value",
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key="11" * 32,
        session_root=tmp_path / "sessions",
        session_history_key="22" * 32,
        service_client_token_registry_json=registry,
    )
    with TestClient(app) as client:
        assert client.get("/v1/service/sandbox-runtime").status_code == 401
        response = client.get(
            "/v1/service/sandbox-runtime",
            headers={"Authorization": "Bearer step074-token"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_lifecycle_enabled"] is True
        assert payload["agent_execution_enabled"] is True
        assert payload["provider_runtime_image_pull_enabled"] is False
        capabilities = client.get(
            "/v1/service/capabilities",
            headers={"Authorization": "Bearer step074-token"},
        ).json()
        assert capabilities["sandbox_execution_enabled"] is True
        assert capabilities["sandbox_provider_lifecycle_enabled"] is True
        assert capabilities["next_selected_step"] == "UNSELECTED_PENDING_USER_SELECTION"


def test_windows_entrypoint_accepts_local_image_and_routes_live_script(monkeypatch, tmp_path: Path) -> None:
    from scripts import windows_entrypoint

    values = windows_entrypoint.parse_environment_text(
        "OKCANVAS_SANDBOX_LIVE_IMAGE=hello-world:latest\n",
        source_name=".env.local",
    )
    assert values == {"OKCANVAS_SANDBOX_LIVE_IMAGE": "hello-world:latest"}
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: (values, tmp_path / ".env.local"))

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)
    assert windows_entrypoint.run(["docker-sandbox-lifecycle-live-acceptance"]) == 0
    assert str(captured["command"][1]).endswith("run_step074_live_acceptance.py")
    assert captured["env"]["OKCANVAS_SANDBOX_LIVE_IMAGE"] == "hello-world:latest"


def test_windows_launchers_preserve_bytecode_and_data_only_loader_chain() -> None:
    deterministic = (ROOT / "sh_run_step074_acceptance.cmd").read_text(encoding="utf-8")
    live = (ROOT / "sh_run_step074_live_acceptance.cmd").read_text(encoding="utf-8")
    assert "python_bytecode_isolation.py scripts\\run_step074_acceptance.py" in deterministic
    assert (
        "python_bytecode_isolation.py scripts\\windows_entrypoint.py "
        "docker-sandbox-lifecycle-live-acceptance"
    ) in live
