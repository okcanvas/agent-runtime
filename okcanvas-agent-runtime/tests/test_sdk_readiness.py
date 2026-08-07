import types

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import RuntimeErrorCode
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness


def test_namespace_directory_is_not_mistaken_for_sdk(monkeypatch) -> None:
    namespace_module = types.ModuleType("agents")
    namespace_module.__file__ = None
    monkeypatch.setattr(sdk_readiness.importlib, "import_module", lambda name: namespace_module)

    readiness = sdk_readiness.inspect_sdk(
        RuntimeSettings(model="test-model", api_key="not-exposed")
    )
    assert readiness.ready is False
    assert readiness.sdk_installed is False
    assert readiness.issues[0].code == RuntimeErrorCode.SDK_NOT_INSTALLED
    assert "not-exposed" not in str(readiness.to_dict())


def test_missing_model_and_key_are_reported_without_secret_values(monkeypatch) -> None:
    monkeypatch.setattr(
        sdk_readiness.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name)),
    )
    readiness = sdk_readiness.inspect_sdk(RuntimeSettings(model=None, api_key=None))
    codes = {issue.code for issue in readiness.issues}
    assert RuntimeErrorCode.SDK_NOT_INSTALLED in codes
    assert RuntimeErrorCode.MODEL_NOT_CONFIGURED in codes
    assert RuntimeErrorCode.API_KEY_MISSING in codes
