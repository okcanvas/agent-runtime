from __future__ import annotations

import os
from dataclasses import dataclass


EXPECTED_OPENAI_AGENTS_VERSION = "0.19.0"


@dataclass(frozen=True)
class RuntimeSettings:
    model: str | None
    api_key: str | None
    workflow_name: str = "OKCanvas Minimal Coding Agent"
    max_turns: int = 1

    @classmethod
    def from_env(cls, *, model_override: str | None = None) -> RuntimeSettings:
        model = model_override or os.getenv("OKCANVAS_AGENT_MODEL")
        api_key = os.getenv("OPENAI_API_KEY")
        return cls(
            model=model.strip() if model and model.strip() else None,
            api_key=api_key if api_key and api_key.strip() else None,
        )


@dataclass(frozen=True)
class CodexReadOnlySettings:
    agent_model: str | None
    codex_model: str | None
    api_key: str | None
    codex_path: str | None = None
    workflow_name: str = "OKCanvas Codex Read-only Analysis"
    max_turns: int = 3
    idle_timeout_seconds: float = 120.0

    @classmethod
    def from_env(
        cls,
        *,
        agent_model_override: str | None = None,
        codex_model_override: str | None = None,
        codex_path_override: str | None = None,
    ) -> CodexReadOnlySettings:
        agent_model = agent_model_override or os.getenv("OKCANVAS_AGENT_MODEL")
        codex_model = codex_model_override or os.getenv("OKCANVAS_CODEX_MODEL")
        codex_path = codex_path_override or os.getenv("CODEX_PATH")
        api_key = os.getenv("OPENAI_API_KEY")
        return cls(
            agent_model=agent_model.strip() if agent_model and agent_model.strip() else None,
            codex_model=codex_model.strip() if codex_model and codex_model.strip() else None,
            api_key=api_key if api_key and api_key.strip() else None,
            codex_path=codex_path.strip() if codex_path and codex_path.strip() else None,
        )


@dataclass(frozen=True)
class CodexWriteSettings:
    agent_model: str | None
    codex_model: str | None
    api_key: str | None
    codex_path: str | None = None
    workflow_name: str = "OKCanvas Codex Disposable Workspace Write"
    max_turns: int = 2
    idle_timeout_seconds: float = 180.0
    max_agent_total_tokens: int = 120_000
    max_codex_total_tokens: int = 120_000

    @classmethod
    def from_env(
        cls,
        *,
        agent_model_override: str | None = None,
        codex_model_override: str | None = None,
        codex_path_override: str | None = None,
    ) -> "CodexWriteSettings":
        agent_model = agent_model_override or os.getenv("OKCANVAS_AGENT_MODEL")
        codex_model = codex_model_override or os.getenv("OKCANVAS_CODEX_MODEL")
        codex_path = codex_path_override or os.getenv("CODEX_PATH")
        api_key = os.getenv("OPENAI_API_KEY")
        return cls(
            agent_model=agent_model.strip() if agent_model and agent_model.strip() else None,
            codex_model=codex_model.strip() if codex_model and codex_model.strip() else None,
            api_key=api_key if api_key and api_key.strip() else None,
            codex_path=codex_path.strip() if codex_path and codex_path.strip() else None,
        )

    def as_readonly_settings(self) -> CodexReadOnlySettings:
        return CodexReadOnlySettings(
            agent_model=self.agent_model,
            codex_model=self.codex_model,
            api_key=self.api_key,
            codex_path=self.codex_path,
            workflow_name=self.workflow_name,
            max_turns=self.max_turns,
            idle_timeout_seconds=self.idle_timeout_seconds,
        )
