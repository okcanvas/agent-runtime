from okcanvas_agent_runtime.core.config import CodexReadOnlySettings
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import inspect_codex_readiness


def test_codex_readiness_fails_closed_without_sdk_cli_models_or_key() -> None:
    readiness = inspect_codex_readiness(
        CodexReadOnlySettings(agent_model=None, codex_model=None, api_key=None)
    )
    assert readiness.ready is False
    codes = {issue.code.value for issue in readiness.issues}
    assert "SDK_NOT_INSTALLED" in codes
    assert "CODEX_CLI_NOT_INSTALLED" in codes
    assert "AGENT_MODEL_NOT_CONFIGURED" in codes
    assert "CODEX_MODEL_NOT_CONFIGURED" in codes
    assert "API_KEY_MISSING" in codes
