from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
for candidate in (PACKAGE_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from okcanvas_agent_runtime.adapters.sandbox.docker import (
    DockerSandboxLifecycleService,
    SandboxDockerError,
    SandboxRuntimeCatalog,
    SubprocessDockerCommandRunner,
)

OUTPUT_DEFAULT = ROOT / "docs/evidence/step074-live/STEP074_LIVE_ACCEPTANCE.json"
STEP = "STEP074_PRODUCT_OWNED_DOCKER_SANDBOX_PROVIDER_LIFECYCLE_V1"
VERSION = "2.54.0"


def run(output: Path) -> int:
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    image_reference = os.environ.get("OKCANVAS_SANDBOX_LIVE_IMAGE", "hello-world:latest").strip()
    acceptance_id = f"step074-{uuid.uuid4().hex}"
    result_payload: dict[str, object] | None = None
    readiness_error: dict[str, str] | None = None
    try:
        runner = SubprocessDockerCommandRunner(
            max_output_bytes=foundation.provider.max_captured_output_bytes
        )
        result = DockerSandboxLifecycleService(foundation, runner).run_probe(
            image_reference,
            acceptance_id=acceptance_id,
        )
        result_payload = result.to_public_dict()
    except SandboxDockerError as exc:
        readiness_error = {"code": exc.code, "message": str(exc)}

    result_payload = result_payload or {}
    security = result_payload.get("security")
    if not isinstance(security, dict):
        security = {}
    image = result_payload.get("image")
    if not isinstance(image, dict):
        image = {}
    operations = result_payload.get("command_operations")
    if not isinstance(operations, list):
        operations = []
    checks = {
        "live_environment_ready": readiness_error is None,
        "docker_lifecycle_passed": result_payload.get("state") == "PASSED",
        "local_image_resolved_to_immutable_digest": (
            isinstance(image.get("immutable_reference"), str)
            and "@sha256:" in str(image.get("immutable_reference"))
        ),
        "runtime_image_pull_absent": (
            foundation.provider.runtime_image_pull_enabled is False
            and all("pull" not in str(item).split() for item in operations)
        ),
        "container_created": result_payload.get("created") is True,
        "container_started": result_payload.get("started") is True,
        "container_exited_zero": (
            result_payload.get("exited") is True and result_payload.get("exit_code") == 0
        ),
        "network_none": security.get("network_none") is True,
        "ports_absent": security.get("no_ports") is True,
        "mounts_absent": security.get("no_mounts") is True,
        "network_attachments_absent": security.get("no_network_attachments") is True,
        "privileged_false": security.get("privileged_false") is True,
        "capabilities_drop_all": (
            security.get("cap_add_empty") is True and security.get("cap_drop_all") is True
        ),
        "no_new_privileges": security.get("no_new_privileges") is True,
        "read_only_rootfs": security.get("read_only_rootfs") is True,
        "non_root_user": security.get("non_root_user") is True,
        "memory_cpu_pid_limits": (
            security.get("memory_limit") is True
            and security.get("nano_cpus") is True
            and security.get("pids_limit") is True
        ),
        "restart_disabled": security.get("restart_none") is True,
        "product_labels_exact": security.get("labels_exact") is True,
        "container_deleted": result_payload.get("deleted") is True,
        "orphan_count_zero": result_payload.get("orphan_count") == 0,
        "cleanup_completed": result_payload.get("cleanup_state") == "COMPLETED",
        "bounded_output_recorded": (
            isinstance(result_payload.get("output_sha256"), str)
            and isinstance(result_payload.get("output_bytes"), int)
            and 0 < int(result_payload.get("output_bytes", 0))
            <= foundation.provider.max_captured_output_bytes
        ),
        "agent_workspace_and_model_remain_disabled": (
            foundation.policy.agent_execution_enabled is False
            and foundation.policy.active_workspace_access_modes == ("none",)
        ),
        "external_network_calls_zero": foundation.policy.network_mode == "none",
        "model_calls_zero": True,
    }
    payload = {
        "schema_version": "okcanvas-step074-live-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "requested_image": image_reference,
        "readiness_error": readiness_error,
        "lifecycle": result_payload,
        "sandbox_policy_sha256": foundation.policy.policy_sha256,
        "sandbox_provider_contract_sha256": foundation.provider.contract_sha256,
        "sandbox_foundation_sha256": foundation.foundation_sha256,
        "docker_calls": result_payload.get("docker_call_count", 0),
        "external_network_calls": 0,
        "model_calls": 0,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    api_key = os.environ.get("OPENAI_API_KEY", "")
    payload["checks"]["api_key_not_persisted"] = not (api_key and api_key in serialized)
    payload["passed_checks"] = sum(value is True for value in payload["checks"].values())
    payload["total_checks"] = len(payload["checks"])
    payload["state"] = "PASSED" if all(payload["checks"].values()) else "FAILED"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return run(args.output or OUTPUT_DEFAULT)


if __name__ == "__main__":
    raise SystemExit(main())
