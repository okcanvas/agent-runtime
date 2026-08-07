from __future__ import annotations

import importlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyErrorCode
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings, RuntimeSettings
from okcanvas_agent_runtime.adapters.openai.runtime.sdk_readiness import inspect_sdk


@dataclass(frozen=True)
class CodexReadinessIssue:
    code: CodexReadOnlyErrorCode
    message: str


@dataclass(frozen=True)
class CodexReadiness:
    ready: bool
    sdk_installed: bool
    sdk_version: str | None
    codex_cli_installed: bool
    codex_cli_path: str | None
    codex_cli_version: str | None
    agent_model_configured: bool
    codex_model_configured: bool
    api_key_configured: bool
    experimental_codex_importable: bool
    issues: tuple[CodexReadinessIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "sdk_installed": self.sdk_installed,
            "sdk_version": self.sdk_version,
            "codex_cli_installed": self.codex_cli_installed,
            "codex_cli_path": self.codex_cli_path,
            "codex_cli_version": self.codex_cli_version,
            "agent_model_configured": self.agent_model_configured,
            "codex_model_configured": self.codex_model_configured,
            "api_key_configured": self.api_key_configured,
            "experimental_codex_importable": self.experimental_codex_importable,
            "issues": [
                {"code": issue.code.value, "message": issue.message} for issue in self.issues
            ],
        }


def _resolve_codex_path(settings: CodexReadOnlySettings) -> Path | None:
    candidate = settings.codex_path or shutil.which("codex")
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        resolved = shutil.which(str(path))
        if resolved:
            path = Path(resolved)
    try:
        path = path.resolve()
    except OSError:
        return None
    return path if path.is_file() else None


def _read_codex_version(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output or None


def inspect_codex_readiness(settings: CodexReadOnlySettings) -> CodexReadiness:
    issues: list[CodexReadinessIssue] = []
    sdk = inspect_sdk(
        RuntimeSettings(model=settings.agent_model, api_key=settings.api_key)
    )
    for issue in sdk.issues:
        try:
            code = CodexReadOnlyErrorCode(issue.code.value)
        except ValueError:
            continue
        if code in {
            CodexReadOnlyErrorCode.SDK_NOT_INSTALLED,
            CodexReadOnlyErrorCode.SDK_VERSION_MISMATCH,
        }:
            issues.append(CodexReadinessIssue(code, issue.message))

    experimental_importable = False
    if sdk.sdk_installed and sdk.sdk_version:
        try:
            module = importlib.import_module("agents.extensions.experimental.codex")
            required = ("codex_tool", "ThreadOptions", "TurnOptions", "CodexOptions")
            experimental_importable = all(hasattr(module, name) for name in required)
        except (ImportError, ModuleNotFoundError):
            experimental_importable = False
        if not experimental_importable:
            issues.append(
                CodexReadinessIssue(
                    CodexReadOnlyErrorCode.SDK_NOT_INSTALLED,
                    "The installed SDK does not expose the experimental Codex integration",
                )
            )

    codex_path = _resolve_codex_path(settings)
    codex_version = _read_codex_version(codex_path) if codex_path else None
    if codex_path is None:
        issues.append(
            CodexReadinessIssue(
                CodexReadOnlyErrorCode.CODEX_CLI_NOT_INSTALLED,
                "Codex CLI was not found; set CODEX_PATH or add codex to PATH",
            )
        )
    elif codex_version is None:
        issues.append(
            CodexReadinessIssue(
                CodexReadOnlyErrorCode.CODEX_CLI_VERSION_UNREADABLE,
                "Codex CLI exists but its version could not be read",
            )
        )

    if settings.agent_model is None:
        issues.append(
            CodexReadinessIssue(
                CodexReadOnlyErrorCode.AGENT_MODEL_NOT_CONFIGURED,
                "Agent model is not configured",
            )
        )
    if settings.codex_model is None:
        issues.append(
            CodexReadinessIssue(
                CodexReadOnlyErrorCode.CODEX_MODEL_NOT_CONFIGURED,
                "Codex model is not configured",
            )
        )
    if settings.api_key is None:
        issues.append(
            CodexReadinessIssue(
                CodexReadOnlyErrorCode.API_KEY_MISSING,
                "OPENAI_API_KEY is not configured",
            )
        )

    return CodexReadiness(
        ready=not issues,
        sdk_installed=sdk.sdk_installed,
        sdk_version=sdk.sdk_version,
        codex_cli_installed=codex_path is not None,
        codex_cli_path=str(codex_path) if codex_path else None,
        codex_cli_version=codex_version,
        agent_model_configured=settings.agent_model is not None,
        codex_model_configured=settings.codex_model is not None,
        api_key_configured=settings.api_key is not None,
        experimental_codex_importable=experimental_importable,
        issues=tuple(issues),
    )
