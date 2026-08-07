from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass

from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import RuntimeErrorCode


@dataclass(frozen=True)
class ReadinessIssue:
    code: RuntimeErrorCode
    message: str


@dataclass(frozen=True)
class SdkReadiness:
    ready: bool
    sdk_installed: bool
    sdk_version: str | None
    model_configured: bool
    api_key_configured: bool
    issues: tuple[ReadinessIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "sdk_installed": self.sdk_installed,
            "sdk_version": self.sdk_version,
            "expected_sdk_version": EXPECTED_OPENAI_AGENTS_VERSION,
            "model_configured": self.model_configured,
            "api_key_configured": self.api_key_configured,
            "issues": [
                {"code": issue.code.value, "message": issue.message} for issue in self.issues
            ],
        }


def inspect_sdk(settings: RuntimeSettings) -> SdkReadiness:
    issues: list[ReadinessIssue] = []
    sdk_installed = False
    sdk_version: str | None = None

    try:
        module = importlib.import_module("agents")
        required = ("Agent", "Runner", "RunConfig", "gen_trace_id", "set_default_openai_key")
        if getattr(module, "__file__", None) is None or not all(
            hasattr(module, symbol) for symbol in required
        ):
            raise ImportError("The imported 'agents' module is not the OpenAI Agents SDK package")
        sdk_version = importlib.metadata.version("openai-agents")
        sdk_installed = True
    except (ImportError, ModuleNotFoundError, importlib.metadata.PackageNotFoundError):
        issues.append(
            ReadinessIssue(
                RuntimeErrorCode.SDK_NOT_INSTALLED,
                f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} is not installed",
            )
        )

    if sdk_installed and sdk_version != EXPECTED_OPENAI_AGENTS_VERSION:
        issues.append(
            ReadinessIssue(
                RuntimeErrorCode.SDK_VERSION_MISMATCH,
                "The installed openai-agents version does not match the pinned runtime version",
            )
        )

    if settings.model is None:
        issues.append(
            ReadinessIssue(
                RuntimeErrorCode.MODEL_NOT_CONFIGURED,
                "Model is not configured; set OKCANVAS_AGENT_MODEL or pass --model",
            )
        )

    if settings.api_key is None:
        issues.append(
            ReadinessIssue(
                RuntimeErrorCode.API_KEY_MISSING,
                "OPENAI_API_KEY is not configured",
            )
        )

    return SdkReadiness(
        ready=not issues,
        sdk_installed=sdk_installed,
        sdk_version=sdk_version,
        model_configured=settings.model is not None,
        api_key_configured=settings.api_key is not None,
        issues=tuple(issues),
    )
