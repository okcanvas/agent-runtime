from __future__ import annotations

import importlib.metadata
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from okcanvas_agent_runtime.core.paths import PROJECT_ROOT
from okcanvas_agent_runtime.agent.sdk.codex_readonly_agent import CODEX_READONLY_AGENT_ID, CODEX_THREAD_CONTEXT_KEY, build_codex_readonly_agent
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyErrorCode, CodexReadOnlyResult, CodexUsageSummary
from okcanvas_agent_runtime.agent.tools.codex.readonly_errors import CodexReadOnlyFailure
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings, EXPECTED_OPENAI_AGENTS_VERSION
from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.adapters.evidence import JsonlEventJournal
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import CodexReadiness, inspect_codex_readiness
from okcanvas_agent_runtime.agent.model.trace_export import TraceExportPolicyCatalog, build_sdk_trace_run_config_kwargs


@dataclass(frozen=True)
class CodexGatewayRunResult:
    output: CodexReadOnlyResult
    agent_usage: UsageSummary
    codex_usage: CodexUsageSummary
    trace_id: str
    response_id: str | None
    thread_id: str | None
    sdk_version: str
    codex_cli_version: str


class CodexReadOnlyGateway(Protocol):
    def readiness(self, settings: CodexReadOnlySettings) -> CodexReadiness: ...

    async def run(
        self,
        *,
        request: str,
        run_id: str,
        settings: CodexReadOnlySettings,
        workspace: Path,
        existing_thread_id: str | None,
        journal: JsonlEventJournal,
    ) -> CodexGatewayRunResult: ...


def _nested_int(value: Any, attribute: str) -> int:
    nested = getattr(value, attribute, None)
    return int(nested or 0)


def _agent_usage(usage: Any) -> UsageSummary:
    return UsageSummary(
        requests=int(getattr(usage, "requests", 0) or 0),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        cached_input_tokens=_nested_int(
            getattr(usage, "input_tokens_details", None), "cached_tokens"
        ),
        reasoning_tokens=_nested_int(
            getattr(usage, "output_tokens_details", None), "reasoning_tokens"
        ),
    )




_CODEX_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "TMP",
    "TEMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TERM",
    "NO_COLOR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


def _codex_subprocess_env() -> dict[str, str]:
    env = {name: os.environ[name] for name in _CODEX_ENV_ALLOWLIST if os.environ.get(name)}
    # Codex may invoke Python while inspecting or validating a workspace. Prevent those
    # child commands from creating __pycache__ inside disposable/read-only repositories.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class OpenAICodexReadOnlyGateway:
    def readiness(self, settings: CodexReadOnlySettings) -> CodexReadiness:
        return inspect_codex_readiness(settings)

    async def run(
        self,
        *,
        request: str,
        run_id: str,
        settings: CodexReadOnlySettings,
        workspace: Path,
        existing_thread_id: str | None,
        journal: JsonlEventJournal,
    ) -> CodexGatewayRunResult:
        readiness = self.readiness(settings)
        if not readiness.ready:
            issue = readiness.issues[0]
            raise CodexReadOnlyFailure(issue.code, issue.message)

        assert settings.agent_model is not None
        assert settings.codex_model is not None
        assert settings.api_key is not None
        assert readiness.codex_cli_path is not None
        assert readiness.codex_cli_version is not None

        try:
            from agents import Agent, ModelSettings, RunConfig, Runner, gen_trace_id, set_default_openai_key
            from agents.extensions.experimental.codex import CodexOptions, ThreadOptions, TurnCompletedEvent, TurnOptions, codex_tool
        except (ImportError, ModuleNotFoundError) as exc:
            raise CodexReadOnlyFailure(
                CodexReadOnlyErrorCode.SDK_NOT_INSTALLED,
                f"openai-agents=={EXPECTED_OPENAI_AGENTS_VERSION} with Codex integration is required",
                detail_type=type(exc).__name__,
            ) from exc

        codex_usage = CodexUsageSummary()

        async def on_stream(payload: Any) -> None:
            nonlocal codex_usage
            await journal.record_codex_payload(payload)
            event = getattr(payload, "event", None)
            if isinstance(event, TurnCompletedEvent) and event.usage is not None:
                codex_usage = CodexUsageSummary(
                    input_tokens=codex_usage.input_tokens + int(event.usage.input_tokens or 0),
                    cached_input_tokens=(
                        codex_usage.cached_input_tokens
                        + int(event.usage.cached_input_tokens or 0)
                    ),
                    output_tokens=codex_usage.output_tokens + int(event.usage.output_tokens or 0),
                )

        set_default_openai_key(settings.api_key)
        tool = codex_tool(
            name="codex_engineer",
            sandbox_mode="read-only",
            working_directory=str(workspace),
            skip_git_repo_check=False,
            codex_options=CodexOptions(
                codex_path_override=readiness.codex_cli_path,
                api_key=settings.api_key,
                env=_codex_subprocess_env(),
            ),
            default_thread_options=ThreadOptions(
                model=settings.codex_model,
                model_reasoning_effort="low",
                network_access_enabled=False,
                web_search_enabled=False,
                approval_policy="never",
            ),
            default_turn_options=TurnOptions(
                idle_timeout_seconds=settings.idle_timeout_seconds,
            ),
            on_stream=on_stream,
            use_run_context_thread_id=True,
        )
        agent = build_codex_readonly_agent(
            Agent,
            model=settings.agent_model,
            tool=tool,
            model_settings=ModelSettings(tool_choice="required"),
        )
        context: dict[str, str] = {}
        if existing_thread_id:
            context[CODEX_THREAD_CONTEXT_KEY] = existing_thread_id

        trace_id = gen_trace_id()
        trace_export_policy = TraceExportPolicyCatalog(PROJECT_ROOT).resolve()
        trace_run_config_settings = build_sdk_trace_run_config_kwargs(trace_export_policy)
        run_config = RunConfig(
            workflow_name=settings.workflow_name,
            trace_id=trace_id,
            group_id=run_id,
            **trace_run_config_settings,
            trace_metadata={
                "run_id": run_id,
                "agent_id": CODEX_READONLY_AGENT_ID,
                "mode": "read-only",
                "trace_export_policy_id": trace_export_policy.policy_id,
                "trace_export_policy_sha256": trace_export_policy.policy_sha256,
                "provider_trace_export_enabled": False,
            },
        )

        try:
            result = await Runner.run(
                agent,
                request,
                context=context,
                max_turns=settings.max_turns,
                run_config=run_config,
            )
        except Exception as exc:
            raise CodexReadOnlyFailure(
                CodexReadOnlyErrorCode.CODEX_RUN_FAILED,
                "OpenAI Agents SDK Codex read-only run failed",
                retryable=True,
                detail_type=type(exc).__name__,
            ) from exc

        try:
            output = result.final_output_as(CodexReadOnlyResult, raise_if_incorrect_type=True)
            if not isinstance(output, CodexReadOnlyResult):
                output = CodexReadOnlyResult.model_validate(output)
        except (TypeError, ValidationError, ValueError) as exc:
            raise CodexReadOnlyFailure(
                CodexReadOnlyErrorCode.OUTPUT_CONTRACT_INVALID,
                "The Codex Agent output did not match CodexReadOnlyResult",
                detail_type=type(exc).__name__,
            ) from exc

        thread_id = context.get(CODEX_THREAD_CONTEXT_KEY) or journal.thread_id
        return CodexGatewayRunResult(
            output=output,
            agent_usage=_agent_usage(result.context_wrapper.usage),
            codex_usage=codex_usage,
            trace_id=trace_id,
            response_id=result.last_response_id,
            thread_id=thread_id,
            sdk_version=importlib.metadata.version("openai-agents"),
            codex_cli_version=readiness.codex_cli_version,
        )
