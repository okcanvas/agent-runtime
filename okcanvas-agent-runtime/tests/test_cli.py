import json

from okcanvas_agent_runtime.bootstrap.development_cli import main


def test_info_cli(capsys) -> None:
    assert main(["info"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "okcanvas-agent-runtime"
    assert payload["step"] == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert payload["codex_readonly_implemented"] is True
    assert payload["codex_live_accepted"] is True
    assert payload["workspace_write_implemented"] is True
    assert payload["workspace_write_live_accepted"] is True


def test_doctor_fails_closed_without_sdk_model_and_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OKCANVAS_AGENT_MODEL", raising=False)
    assert main(["doctor"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is False
    codes = {item["code"] for item in payload["issues"]}
    assert "SDK_NOT_INSTALLED" in codes
    assert "MODEL_NOT_CONFIGURED" in codes
    assert "API_KEY_MISSING" in codes


def test_run_requires_explicit_confirmation(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    assert main(["run", "--input", "analyze this"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "LIVE_OPT_IN_REQUIRED"
    assert "must-not-leak" not in json.dumps(payload)
