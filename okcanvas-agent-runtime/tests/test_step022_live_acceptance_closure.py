from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import run_step022_acceptance, windows_entrypoint


def _workspace(cleanup: str = "COMPLETED") -> dict:
    return {"cleanup_state": cleanup}


def _step021_payload() -> dict:
    return {
        "state": "PASSED",
        "checks": {"one": True, "two": True},
        "acceptance_workspace": _workspace(),
    }


def _step020_payload(*, live: bool) -> dict:
    return {
        "state": "PASSED",
        "live_sdk": live,
        "checks": {
            "approve_branch_passed": True,
            "reject_branch_passed": True,
            "references_unchanged": True,
        },
        "approve": {
            "state": "PASSED",
            "checks": {
                "process_restart_proven": True,
                "tool_executed_exactly_once": True,
            },
        },
        "reject": {
            "state": "PASSED",
            "checks": {
                "process_restart_proven": True,
                "tool_not_executed": True,
            },
        },
        "acceptance_workspace": _workspace(),
    }


def _result(payload: dict) -> dict:
    checks = payload.get("checks", {})
    return {
        "label": "fixture",
        "exit_code": 0,
        "state": payload.get("state"),
        "cleanup_state": payload["acceptance_workspace"]["cleanup_state"],
        "failed_checks": [name for name, value in checks.items() if value is not True],
        "summary_file": "summary.json",
        "log_file": "run.log",
        "payload": payload,
    }


def test_closure_requires_complete_inbox_and_exact_live_mode() -> None:
    assert run_step022_acceptance._step021_passed(_result(_step021_payload())) is True
    assert (
        run_step022_acceptance._step020_passed(_result(_step020_payload(live=True)), live=True)
        is True
    )
    assert (
        run_step022_acceptance._step020_passed(_result(_step020_payload(live=False)), live=True)
        is False
    )


def test_closure_rejects_failed_cleanup_and_missing_restart_proof() -> None:
    step021 = _step021_payload()
    step021["acceptance_workspace"] = _workspace("PRESERVED")
    assert run_step022_acceptance._step021_passed(_result(step021)) is False

    step020 = _step020_payload(live=True)
    step020["approve"]["checks"]["process_restart_proven"] = False
    assert run_step022_acceptance._step020_passed(_result(step020), live=True) is False


def test_safe_child_result_excludes_nested_evidence() -> None:
    payload = _step020_payload(live=True)
    payload["secret_like_internal"] = "must-not-surface"
    safe = run_step022_acceptance._safe_result(_result(payload))
    assert "payload" not in safe
    assert "secret_like_internal" not in safe
    assert safe["approve_state"] == "PASSED"
    assert safe["reject_state"] == "PASSED"


def test_windows_entrypoint_routes_step022_commands(monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_load(root=windows_entrypoint.ROOT):
        return {"OPENAI_API_KEY": "secret", "OKCANVAS_AGENT_MODEL": "agent"}, None

    def fake_run(command, *, cwd, env, check):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)

    assert windows_entrypoint.run(["approval-closure-acceptance"]) == 0
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step022_acceptance.py") in captured[-1]
    assert "--live" not in captured[-1]

    assert windows_entrypoint.run(["approval-live-closure"]) == 0
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step022_acceptance.py") in captured[-1]
    assert "--live" in captured[-1]


def test_live_default_output_uses_excluded_evidence_tree() -> None:
    output = run_step022_acceptance._live_output()
    assert output.name == "closure-summary.json"
    assert "docs/evidence/step022-live" in output.as_posix()


def test_live_readiness_reports_codes_without_secret_values(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OKCANVAS_AGENT_MODEL", raising=False)
    issues = run_step022_acceptance._live_readiness_issues()
    assert "API_KEY_MISSING" in issues
    assert "MODEL_NOT_CONFIGURED" in issues
    assert all("secret" not in item.casefold() for item in issues)


def test_safe_child_result_surfaces_redacted_exception_summary() -> None:
    payload = {
        "state": "FAILED",
        "error_type": "MaxTurnsExceeded",
        "error": "Max turns (1) exceeded",
        "acceptance_workspace": {
            "cleanup_state": "PRESERVED",
            "preserved_path": "C:/tmp/preserved",
        },
    }
    result = {
        "label": "fixture",
        "exit_code": 1,
        "state": "FAILED",
        "cleanup_state": "PRESERVED",
        "failed_checks": [],
        "summary_file": "summary.json",
        "log_file": "run.log",
        "payload": payload,
    }
    safe = run_step022_acceptance._safe_result(result)
    assert safe["error_type"] == "MaxTurnsExceeded"
    assert safe["error"] == "Max turns (1) exceeded"
    assert safe["preserved_path"] == "C:/tmp/preserved"


def test_child_log_redacts_all_configured_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "api-secret")
    monkeypatch.setenv("OKCANVAS_CONTROL_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("OKCANVAS_RUN_SUBMITTER_KEY", "submitter-secret")
    monkeypatch.setenv("OKCANVAS_PROTECTED_PAYLOAD_KEY", "payload-secret")

    output = tmp_path / "summary.json"
    output.write_text('{"state":"FAILED"}', encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        text = "api-secret admin-secret submitter-secret payload-secret"
        return subprocess.CompletedProcess(["python"], 1, stdout=text, stderr=text)

    monkeypatch.setattr(run_step022_acceptance.subprocess, "run", fake_run)
    result = run_step022_acceptance._run_child(
        label="fixture",
        command=["python"],
        output_path=output,
        log_path=tmp_path / "child.log",
    )
    assert result["exit_code"] == 1
    log = (tmp_path / "child.log").read_text(encoding="utf-8")
    assert "api-secret" not in log
    assert "admin-secret" not in log
    assert "submitter-secret" not in log
    assert "payload-secret" not in log
    assert "[REDACTED]" in log
