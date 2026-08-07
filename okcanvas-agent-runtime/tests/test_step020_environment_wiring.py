from __future__ import annotations

import importlib


def test_app_from_environment_passes_runstate_root(monkeypatch) -> None:
    module = importlib.import_module("okcanvas_agent_runtime.bootstrap.application")
    captured = {}
    sentinel = object()

    def fake_create_app(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(module, "create_app", fake_create_app)
    monkeypatch.setenv("OKCANVAS_CONTROL_ADMIN_KEY", "A" * 24)
    monkeypatch.setenv("OKCANVAS_RUN_SUBMITTER_KEY", "B" * 24)
    monkeypatch.setenv("OKCANVAS_PROTECTED_PAYLOAD_KEY", "C" * 64)
    monkeypatch.setenv("OKCANVAS_PROTECTED_PAYLOAD_ROOT", ".local/protected-payloads")
    monkeypatch.setenv("OKCANVAS_RUN_STATE_ROOT", ".local/custom-run-states")
    monkeypatch.setenv("OKCANVAS_READONLY_WORKSPACE_ROOT", ".")

    assert module.app_from_environment() is sentinel
    assert captured["run_state_root"] == ".local/custom-run-states"
    assert captured["readonly_workspace_root"] == "."
