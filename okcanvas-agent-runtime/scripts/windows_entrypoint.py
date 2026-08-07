from __future__ import annotations

import argparse
import base64
import binascii
import codecs
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
_ALLOWED_KEYS = {
    "OPENAI_API_KEY",
    "OKCANVAS_AGENT_MODEL",
    "OKCANVAS_DEFAULT_AGENT_ID",
    "OKCANVAS_CODEX_MODEL",
    "CODEX_PATH",
    "OKCANVAS_CONTROL_ADMIN_KEY",
    "OKCANVAS_PROJECT_ROOT",
    "OKCANVAS_PRODUCT_DB",
    "OKCANVAS_ARTIFACT_ROOT",
    "OKCANVAS_EVALUATION_DB",
    "OKCANVAS_API_HOST",
    "OKCANVAS_API_PORT",
    "OKCANVAS_ACCEPTANCE_WORK_ROOT",
    "OKCANVAS_DIRECT_RUN_API_ENABLED",
    "OKCANVAS_RUN_SUBMITTER_KEY",
    "OKCANVAS_PROTECTED_PAYLOAD_ROOT",
    "OKCANVAS_RUN_STATE_ROOT",
    "OKCANVAS_SESSION_ROOT",
    "OKCANVAS_SESSION_HISTORY_KEY",
    "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY",
    "OKCANVAS_READONLY_WORKSPACE_ROOT",
    "OKCANVAS_SANDBOX_READONLY_IMAGE",
    "OKCANVAS_SANDBOX_TEMP_ROOT",
    "OKCANVAS_PROTECTED_PAYLOAD_KEY",
    "OKCANVAS_CONTROL_BASE_URL",
    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL",
    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN",
    "OKCANVAS_SANDBOX_LIVE_IMAGE",
    "OKCANVAS_GROUPWARE_READ_BEARER",
}
_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LocalEnvironmentError(ValueError):
    """Raised when a local environment file is ambiguous or malformed."""


def _decode_environment_file(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF16_LE):
        return raw.decode("utf-16")
    if raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp949")
        except UnicodeDecodeError as exc:
            raise LocalEnvironmentError(
                f"{path.name} must be UTF-8, UTF-16, or CP949 text"
            ) from exc


def parse_environment_text(text: str, *, source_name: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.casefold()
        if lowered == "@echo off" or lowered == "echo off":
            continue
        if lowered == "rem" or lowered.startswith("rem "):
            continue
        if line.startswith("::") or line.startswith("#"):
            continue

        assignment = line
        if lowered.startswith("set "):
            assignment = line[4:].strip()
            if assignment.startswith('"'):
                if not assignment.endswith('"') or len(assignment) < 2:
                    raise LocalEnvironmentError(
                        f"{source_name}:{line_number}: unterminated quoted set assignment"
                    )
                assignment = assignment[1:-1]

        if "=" not in assignment:
            raise LocalEnvironmentError(
                f"{source_name}:{line_number}: expected NAME=value or set \"NAME=value\""
            )
        key, value = assignment.split("=", 1)
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key):
            raise LocalEnvironmentError(
                f"{source_name}:{line_number}: invalid environment variable name"
            )
        if key not in _ALLOWED_KEYS:
            raise LocalEnvironmentError(
                f"{source_name}:{line_number}: unsupported environment variable {key}"
            )
        if key in values:
            raise LocalEnvironmentError(
                f"{source_name}:{line_number}: duplicate environment variable {key}"
            )
        values[key] = value
    return values


def load_local_environment(root: Path = ROOT) -> tuple[dict[str, str], Path | None]:
    candidates = [root / ".env.local", root / ".env.local.cmd"]
    existing = [path for path in candidates if path.is_file()]
    if len(existing) > 1:
        raise LocalEnvironmentError(
            "Both .env.local and .env.local.cmd exist; keep only one local environment file"
        )
    if not existing:
        return {}, None
    path = existing[0]
    text = _decode_environment_file(path)
    return parse_environment_text(text, source_name=path.name), path


def build_child_environment(local_values: dict[str, str]) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(local_values)
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(PACKAGE_ROOT) if not current_pythonpath else os.pathsep.join((str(PACKAGE_ROOT), current_pythonpath))
    )
    return environment


def _decode_32_byte_key(value: str, *, variable_name: str) -> bytes:
    normalized = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", normalized):
        return bytes.fromhex(normalized)
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise LocalEnvironmentError(
            f"{variable_name} must be 64 hex characters or 32-byte URL-safe base64"
        ) from exc


def validate_control_api_environment(environment: dict[str, str]) -> None:
    admin_key = environment.get("OKCANVAS_CONTROL_ADMIN_KEY", "")
    if len(admin_key) < 16:
        raise LocalEnvironmentError(
            "OKCANVAS_CONTROL_ADMIN_KEY must contain at least 16 characters"
        )
    if admin_key.casefold().startswith("replace-with"):
        raise LocalEnvironmentError(
            "OKCANVAS_CONTROL_ADMIN_KEY is still an example placeholder"
        )

    submitter_key = environment.get("OKCANVAS_RUN_SUBMITTER_KEY", "")
    protected_key = environment.get("OKCANVAS_PROTECTED_PAYLOAD_KEY", "")
    session_history_key = environment.get("OKCANVAS_SESSION_HISTORY_KEY", "")
    session_history_previous_key = environment.get(
        "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY", ""
    )
    session_raw: bytes | None = None
    if session_history_key.strip():
        session_raw = _decode_32_byte_key(
            session_history_key, variable_name="OKCANVAS_SESSION_HISTORY_KEY"
        )
        if len(session_raw) != 32:
            raise LocalEnvironmentError(
                "OKCANVAS_SESSION_HISTORY_KEY must decode to exactly 32 bytes"
            )
        if protected_key.strip():
            protected_raw_for_separation = _decode_32_byte_key(
                protected_key, variable_name="OKCANVAS_PROTECTED_PAYLOAD_KEY"
            )
            if session_raw == protected_raw_for_separation:
                raise LocalEnvironmentError(
                    "OKCANVAS_SESSION_HISTORY_KEY must be distinct from OKCANVAS_PROTECTED_PAYLOAD_KEY"
                )
    if session_history_previous_key.strip():
        previous_raw = _decode_32_byte_key(
            session_history_previous_key,
            variable_name="OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY",
        )
        if len(previous_raw) != 32:
            raise LocalEnvironmentError(
                "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY must decode to exactly 32 bytes"
            )
        if session_raw is None:
            raise LocalEnvironmentError(
                "OKCANVAS_SESSION_HISTORY_KEY is required when the previous Session key is configured"
            )
        if previous_raw == session_raw:
            raise LocalEnvironmentError(
                "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY must be distinct from OKCANVAS_SESSION_HISTORY_KEY"
            )
        if protected_key.strip():
            protected_raw_for_separation = _decode_32_byte_key(
                protected_key, variable_name="OKCANVAS_PROTECTED_PAYLOAD_KEY"
            )
            if previous_raw == protected_raw_for_separation:
                raise LocalEnvironmentError(
                    "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY must be distinct from OKCANVAS_PROTECTED_PAYLOAD_KEY"
                )
    governed_requested = bool(submitter_key or protected_key)
    if not governed_requested:
        return
    if len(submitter_key) < 16:
        raise LocalEnvironmentError(
            "OKCANVAS_RUN_SUBMITTER_KEY must contain at least 16 characters when governed Run submission is configured"
        )
    if submitter_key.casefold().startswith("replace-with"):
        raise LocalEnvironmentError(
            "OKCANVAS_RUN_SUBMITTER_KEY is still an example placeholder"
        )
    if submitter_key == admin_key:
        raise LocalEnvironmentError(
            "OKCANVAS_RUN_SUBMITTER_KEY must be distinct from OKCANVAS_CONTROL_ADMIN_KEY"
        )
    if not protected_key.strip():
        raise LocalEnvironmentError(
            "OKCANVAS_PROTECTED_PAYLOAD_KEY is required when governed Run submission is configured"
        )
    raw = _decode_32_byte_key(
        protected_key, variable_name="OKCANVAS_PROTECTED_PAYLOAD_KEY"
    )
    if len(raw) != 32:
        raise LocalEnvironmentError(
            "OKCANVAS_PROTECTED_PAYLOAD_KEY must decode to exactly 32 bytes"
        )

    readonly_root = environment.get("OKCANVAS_READONLY_WORKSPACE_ROOT", "").strip()
    if readonly_root:
        candidate = Path(readonly_root).expanduser()
        if candidate.is_symlink() or not candidate.is_dir():
            raise LocalEnvironmentError(
                "OKCANVAS_READONLY_WORKSPACE_ROOT must be an existing real directory"
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="windows_entrypoint")
    parser.add_argument("command", choices=("doctor", "codex-doctor", "live-acceptance", "write-acceptance", "approval-acceptance", "generic-acceptance", "control-api", "control-api-acceptance", "mcp-acceptance", "catalog-acceptance", "recorded-evaluation-acceptance", "evaluation-suite-acceptance", "acceptance-workspace-acceptance", "operations-console-acceptance", "operations-console-live-acceptance", "run-submission-boundary-acceptance", "governed-run-submission-acceptance", "governed-recovery-retention-acceptance", "governed-local-tool-approval-acceptance", "governed-local-tool-approval-live-acceptance", "approval-inbox-acceptance", "approval-closure-acceptance", "approval-live-closure", "approval-operator", "approval-operator-acceptance", "business-agent-acceptance", "business-agent-live-acceptance", "business-output-recovery-acceptance", "commerce-snapshot-ingress-acceptance", "commerce-multi-case-acceptance", "commerce-ingress-failure-matrix-acceptance", "commerce-snapshot-identity-acceptance", "commerce-snapshot-strict-types-acceptance", "commerce-snapshot-non-empty-acceptance", "commerce-snapshot-bounded-quantities-acceptance", "agent-output-contract-registry-acceptance", "agent-runtime-binding-acceptance", "orphaned-running-reconciliation-acceptance", "terminal-outcome-reconciliation-acceptance", "recorded-runtime-binding-evaluation-acceptance", "interactive-runner-acceptance", "function-tool-runtime-acceptance", "native-sdk-streaming-acceptance", "sub-agent-invocation-scope-acceptance", "native-handoff-acceptance", "agent-as-tool-acceptance", "sqlite-session-acceptance", "tui-client", "windows-venv-launcher-acceptance", "skill-document-review-live-acceptance", "trace-export-disabled-live-acceptance", "windows-pycache-overlay-live-acceptance", "windows-crlf-local-env-live-acceptance", "docker-sandbox-lifecycle-live-acceptance", "readonly-sandbox-workspace-live-acceptance", "readonly-sandbox-workspace-normalized-live-acceptance", "readonly-sandbox-workspace-operation-live-acceptance", "readonly-sandbox-workspace-tar-stream-live-acceptance", "readonly-sandbox-workspace-stdin-contract-live-acceptance", "readonly-sandbox-workspace-hash-domain-live-acceptance", "readonly-sandbox-answer-completeness-live-acceptance", "readonly-sandbox-deterministic-evidence-completion-live-acceptance", "immutable-project-snapshot-binding-live-acceptance", "binary-ingress-slot-lifecycle-live-acceptance", "atomic-service-submission-ownership-transfer-live-acceptance", "atomic-task-run-ownership-transfer-live-acceptance", "capability-topology-live-acceptance", "architecture-constitution-live-acceptance", "root-package-architecture-live-acceptance", "groupware-readonly-acceptance", "groupware-boundary-acceptance", "groupware-connector-contract-acceptance", "workspace-step004-live-acceptance", "workspace-step007-live-acceptance", "workspace-step007r1-live-acceptance"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        local_values, source = load_local_environment()
    except (OSError, LocalEnvironmentError) as exc:
        print(f"[ERROR] Local environment file is invalid: {exc}", file=sys.stderr)
        print(
            '[HINT] Use .env.local.example or lines shaped like set "NAME=value".',
            file=sys.stderr,
        )
        return 2

    if source is not None:
        print(
            f"[INFO] Loaded local environment from {source.name} without executing it.",
            file=sys.stderr,
        )

    environment = build_child_environment(local_values)
    environment["OKCANVAS_LOCAL_ENV_SOURCE_NAME"] = source.name if source is not None else ""
    environment["OKCANVAS_LOCAL_ENV_LOADED_KEYS"] = ",".join(sorted(local_values))
    if args.command == "control-api":
        try:
            validate_control_api_environment(environment)
        except LocalEnvironmentError as exc:
            print(f"[ERROR] Control API environment is invalid: {exc}", file=sys.stderr)
            print(
                '[HINT] Generate a key with: .venv\\Scripts\\python.exe -c "from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key; print(generate_protected_payload_key())"',
                file=sys.stderr,
            )
            return 2
    if args.command == "doctor":
        command = [
            sys.executable,
            "-m",
            "okcanvas_agent_runtime",
            "doctor",
            "--pretty",
            *args.arguments,
        ]
    elif args.command == "codex-doctor":
        command = [
            sys.executable,
            "-m",
            "okcanvas_agent_runtime",
            "codex-doctor",
            "--pretty",
            *args.arguments,
        ]
    elif args.command == "live-acceptance":
        environment["OKCANVAS_STEP002_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step002_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "write-acceptance":
        environment["OKCANVAS_STEP003_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step003_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "approval-acceptance":
        environment["OKCANVAS_STEP004_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step004_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "generic-acceptance":
        environment["OKCANVAS_STEP007_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step007_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "control-api-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step008_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "mcp-acceptance":
        environment["OKCANVAS_STEP009_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step009_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "catalog-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step011_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "recorded-evaluation-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step012_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "evaluation-suite-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step013_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "acceptance-workspace-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step014_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "operations-console-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step015_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "operations-console-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step016_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "run-submission-boundary-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step017_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "governed-run-submission-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step018_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "governed-recovery-retention-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step019_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "governed-local-tool-approval-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step020_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "governed-local-tool-approval-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step020_acceptance.py"),
            "--live",
            *args.arguments,
        ]
    elif args.command == "approval-inbox-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step021_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "approval-closure-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step022_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "approval-live-closure":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step022_acceptance.py"),
            "--live",
            *args.arguments,
        ]
    elif args.command == "approval-operator":
        command = [
            sys.executable,
            "-m",
            "okcanvas_agent_runtime",
            *args.arguments,
        ]
    elif args.command == "tui-client":
        command = [
            sys.executable,
            "-m",
            "okcanvas_agent_runtime",
            "tui",
            *args.arguments,
        ]
    elif args.command == "approval-operator-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step023_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "business-agent-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step024_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "business-agent-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step024_acceptance.py"),
            "--live",
            *args.arguments,
        ]
    elif args.command == "business-output-recovery-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step024b_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-snapshot-ingress-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step025_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-multi-case-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step026_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-ingress-failure-matrix-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step027_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-snapshot-identity-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step028_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-snapshot-strict-types-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step029_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-snapshot-non-empty-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step030_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "commerce-snapshot-bounded-quantities-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step031_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "agent-output-contract-registry-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step032_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "agent-runtime-binding-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step033_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "orphaned-running-reconciliation-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step034_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "terminal-outcome-reconciliation-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step035_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "recorded-runtime-binding-evaluation-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step036_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "interactive-runner-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step037_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "function-tool-runtime-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step038_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "native-sdk-streaming-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step039_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "sub-agent-invocation-scope-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step040_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "native-handoff-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step041_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "agent-as-tool-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step042_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "sqlite-session-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step043_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "windows-venv-launcher-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step030a_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "skill-document-review-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step071_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "trace-export-disabled-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step072_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "windows-pycache-overlay-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step072a_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "windows-crlf-local-env-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step072b_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "docker-sandbox-lifecycle-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step074_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-normalized-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075a_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-operation-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075b_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-tar-stream-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075c_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-stdin-contract-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075d_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-workspace-hash-domain-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075e_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-answer-completeness-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075f_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "readonly-sandbox-deterministic-evidence-completion-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step075g_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "immutable-project-snapshot-binding-live-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step076_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "binary-ingress-slot-lifecycle-live-acceptance":
        environment["OKCANVAS_STEP077_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step077_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "atomic-service-submission-ownership-transfer-live-acceptance":
        environment["OKCANVAS_STEP078_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step078_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "atomic-task-run-ownership-transfer-live-acceptance":
        environment["OKCANVAS_STEP079_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP079A_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step079a_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "capability-topology-live-acceptance":
        environment["OKCANVAS_STEP080_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step080_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "architecture-constitution-live-acceptance":
        environment["OKCANVAS_STEP080_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP080A_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step080a_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "groupware-readonly-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step086_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "groupware-boundary-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step086r1_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "groupware-connector-contract-acceptance":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step086r2_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "workspace-step004-live-acceptance":
        environment["OKCANVAS_WORKSPACE_STEP004_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT.parent / "scripts" / "run_workspace_step004_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "workspace-step007-live-acceptance":
        environment["OKCANVAS_WORKSPACE_STEP007_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT.parent / "scripts" / "run_workspace_step007_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "workspace-step007r1-live-acceptance":
        environment["OKCANVAS_WORKSPACE_STEP007R1_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT.parent / "scripts" / "run_workspace_step007r1_live_acceptance.py"),
            *args.arguments,
        ]
    elif args.command == "root-package-architecture-live-acceptance":
        environment["OKCANVAS_STEP080_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP080A_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP081_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP081A_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP081C_LIVE_ACCEPTANCE"] = "1"
        environment["OKCANVAS_STEP081D_LIVE_ACCEPTANCE"] = "1"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_step081d_live_acceptance.py"),
            *args.arguments,
        ]
    else:
        host = environment.get("OKCANVAS_API_HOST", "127.0.0.1")
        port = environment.get("OKCANVAS_API_PORT", "8765")
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "okcanvas_agent_runtime.bootstrap.application:app_from_environment",
            "--factory",
            "--host",
            host,
            "--port",
            port,
            *args.arguments,
        ]

    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(run())
