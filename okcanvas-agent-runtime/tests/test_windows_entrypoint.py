from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import windows_entrypoint


def test_parses_cmd_environment_without_executing_comments_or_values() -> None:
    values = windows_entrypoint.parse_environment_text(
        """
        @echo off
        rem Korean comments and prose are ignored safely.
        set "OPENAI_API_KEY=secret-with-&-and-^-characters"
        set "OKCANVAS_AGENT_MODEL=gpt-agent"
        set "OKCANVAS_CODEX_MODEL=gpt-codex"
        rem set "CODEX_PATH=C:\\ignored\\codex.exe"
        """,
        source_name=".env.local.cmd",
    )
    assert values == {
        "OPENAI_API_KEY": "secret-with-&-and-^-characters",
        "OKCANVAS_AGENT_MODEL": "gpt-agent",
        "OKCANVAS_CODEX_MODEL": "gpt-codex",
    }


def test_parses_plain_dotenv_format() -> None:
    values = windows_entrypoint.parse_environment_text(
        """
        # local only
        OPENAI_API_KEY=secret
        OKCANVAS_AGENT_MODEL=agent-model
        OKCANVAS_DEFAULT_AGENT_ID=conversational-coding-agent
        OKCANVAS_CODEX_MODEL=codex-model
        CODEX_PATH=C:\\Program Files\\Codex\\codex.exe
        """,
        source_name=".env.local",
    )
    assert values["CODEX_PATH"].endswith("codex.exe")
    assert values["OKCANVAS_DEFAULT_AGENT_ID"] == "conversational-coding-agent"


def test_canonical_local_example_uses_only_supported_environment_variables() -> None:
    example = (windows_entrypoint.ROOT / ".env.local.example").read_text(encoding="utf-8")
    values = windows_entrypoint.parse_environment_text(example, source_name=".env.local")
    assert values["OKCANVAS_DEFAULT_AGENT_ID"] == "conversational-coding-agent"
    assert values["OKCANVAS_SESSION_ROOT"] == ".local\\sessions"
    assert values["OKCANVAS_READONLY_WORKSPACE_ROOT"] == "."


def test_rejects_prose_instead_of_executing_it() -> None:
    with pytest.raises(windows_entrypoint.LocalEnvironmentError) as exc_info:
        windows_entrypoint.parse_environment_text(
            "OPENAI key and model settings\nOPENAI_API_KEY=secret\n",
            source_name=".env.local.cmd",
        )
    message = str(exc_info.value)
    assert ".env.local.cmd:1" in message
    assert "secret" not in message


def test_rejects_duplicate_or_unsupported_variables() -> None:
    with pytest.raises(windows_entrypoint.LocalEnvironmentError):
        windows_entrypoint.parse_environment_text(
            "OPENAI_API_KEY=one\nOPENAI_API_KEY=two\n",
            source_name=".env.local",
        )
    with pytest.raises(windows_entrypoint.LocalEnvironmentError):
        windows_entrypoint.parse_environment_text(
            "UNSAFE_VARIABLE=value\n",
            source_name=".env.local",
        )


def test_load_rejects_ambiguous_dual_files(tmp_path: Path) -> None:
    (tmp_path / ".env.local").write_text("OPENAI_API_KEY=one\n", encoding="utf-8")
    (tmp_path / ".env.local.cmd").write_text(
        'set "OPENAI_API_KEY=two"\n', encoding="utf-8"
    )
    with pytest.raises(windows_entrypoint.LocalEnvironmentError):
        windows_entrypoint.load_local_environment(tmp_path)


def test_child_process_receives_secret_only_through_environment(monkeypatch, tmp_path: Path) -> None:
    env_file = windows_entrypoint.ROOT / ".env.local"
    original_exists = env_file.exists()
    original = env_file.read_bytes() if original_exists else b""
    env_file.write_text(
        "OPENAI_API_KEY=do-not-place-on-command-line\n"
        "OKCANVAS_AGENT_MODEL=agent-model\n"
        "OKCANVAS_CODEX_MODEL=codex-model\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    try:
        assert windows_entrypoint.run(["doctor"]) == 0
    finally:
        if original_exists:
            env_file.write_bytes(original)
        else:
            env_file.unlink(missing_ok=True)

    command_text = " ".join(str(part) for part in captured["command"])
    assert "do-not-place-on-command-line" not in command_text
    assert captured["env"]["OPENAI_API_KEY"] == "do-not-place-on-command-line"


def test_utf16_bom_local_file_is_supported(tmp_path: Path) -> None:
    path = tmp_path / ".env.local"
    path.write_text(
        "OPENAI_API_KEY=secret\nOKCANVAS_AGENT_MODEL=agent\nOKCANVAS_CODEX_MODEL=codex\n",
        encoding="utf-16",
    )
    values, loaded = windows_entrypoint.load_local_environment(tmp_path)
    assert loaded == path
    assert values["OPENAI_API_KEY"] == "secret"


def test_write_acceptance_uses_step003_gate(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OPENAI_API_KEY": "secret",
            "OKCANVAS_AGENT_MODEL": "agent",
            "OKCANVAS_CODEX_MODEL": "codex",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["write-acceptance"]) == 0
    assert captured["env"]["OKCANVAS_STEP003_LIVE_ACCEPTANCE"] == "1"
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step003_live_acceptance.py") in captured["command"]


def test_approval_acceptance_uses_step004_gate(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OPENAI_API_KEY": "secret",
            "OKCANVAS_AGENT_MODEL": "agent",
            "OKCANVAS_CODEX_MODEL": "codex",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["approval-acceptance"]) == 0
    assert captured["env"]["OKCANVAS_STEP004_LIVE_ACCEPTANCE"] == "1"
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step004_live_acceptance.py") in captured["command"]


def test_generic_acceptance_uses_step007_gate(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OPENAI_API_KEY": "secret",
            "OKCANVAS_AGENT_MODEL": "agent",
            "OKCANVAS_CODEX_MODEL": "codex",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["generic-acceptance"]) == 0
    assert captured["env"]["OKCANVAS_STEP007_LIVE_ACCEPTANCE"] == "1"
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step007_live_acceptance.py") in captured["command"]


def test_default_doctor_checks_core_agent_readiness(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {"OPENAI_API_KEY": "secret", "OKCANVAS_AGENT_MODEL": "agent"}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["doctor"]) == 0
    assert "doctor" in captured["command"]
    assert "codex-doctor" not in captured["command"]


def test_codex_doctor_is_explicit_optional_adapter_check(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OPENAI_API_KEY": "secret",
            "OKCANVAS_AGENT_MODEL": "agent",
            "OKCANVAS_CODEX_MODEL": "codex",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["codex-doctor"]) == 0
    assert "codex-doctor" in captured["command"]


def test_control_api_environment_keys_are_loaded_as_data(tmp_path: Path) -> None:
    values = windows_entrypoint.parse_environment_text(
        "\n".join(
            [
                "OKCANVAS_CONTROL_ADMIN_KEY=admin-key-with-special-&-characters",
                "OKCANVAS_PRODUCT_DB=.local\\product.sqlite3",
                "OKCANVAS_ARTIFACT_ROOT=.local\\artifacts",
                "OKCANVAS_API_HOST=127.0.0.1",
                "OKCANVAS_API_PORT=8765",
            ]
        ),
        source_name=".env.local",
    )
    assert values["OKCANVAS_CONTROL_ADMIN_KEY"].endswith("&-characters")
    assert values["OKCANVAS_API_PORT"] == "8765"


def test_control_api_acceptance_uses_step008_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["control-api-acceptance"]) == 0
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step008_acceptance.py") in captured["command"]


def test_control_api_launcher_uses_uvicorn_factory(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
            "OKCANVAS_RUN_SUBMITTER_KEY": "submitter-key-123456789",
            "OKCANVAS_PROTECTED_PAYLOAD_KEY": "C" * 64,
            "OKCANVAS_API_HOST": "127.0.0.1",
            "OKCANVAS_API_PORT": "9876",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["control-api"]) == 0
    command = captured["command"]
    assert "uvicorn" in command
    assert "okcanvas_agent_runtime.bootstrap.application:app_from_environment" in command
    assert "--factory" in command
    assert "9876" in command
    assert "admin-key-123456789" not in " ".join(str(item) for item in command)


def test_mcp_acceptance_uses_step009_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {"OPENAI_API_KEY": "secret", "OKCANVAS_AGENT_MODEL": "model"}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["mcp-acceptance"]) == 0
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step009_live_acceptance.py") in captured["command"]
    assert captured["env"]["OKCANVAS_STEP009_LIVE_ACCEPTANCE"] == "1"


def test_catalog_acceptance_uses_step011_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["catalog-acceptance"]) == 0
    assert str(windows_entrypoint.ROOT / "scripts" / "run_step011_acceptance.py") in captured["command"]


def test_evaluation_database_environment_key_is_loaded_as_data() -> None:
    values = windows_entrypoint.parse_environment_text(
        "OKCANVAS_EVALUATION_DB=.local\\evaluation.sqlite3\n",
        source_name=".env.local",
    )
    assert values["OKCANVAS_EVALUATION_DB"].endswith("evaluation.sqlite3")


def test_recorded_evaluation_acceptance_uses_step012_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["recorded-evaluation-acceptance"]) == 0
    assert str(
        windows_entrypoint.ROOT / "scripts" / "run_step012_acceptance.py"
    ) in captured["command"]


def test_acceptance_workspace_environment_key_is_loaded_as_data() -> None:
    values = windows_entrypoint.parse_environment_text(
        "OKCANVAS_ACCEPTANCE_WORK_ROOT=D:\\NODE_AGENTS\\acceptance-work\n",
        source_name=".env.local",
    )
    assert values["OKCANVAS_ACCEPTANCE_WORK_ROOT"].endswith("acceptance-work")


def test_acceptance_workspace_launcher_uses_step014_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["acceptance-workspace-acceptance"]) == 0
    assert str(
        windows_entrypoint.ROOT / "scripts" / "run_step014_acceptance.py"
    ) in captured["command"]


def test_step020_acceptance_launcher_uses_named_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["governed-local-tool-approval-acceptance"]) == 0
    assert str(
        windows_entrypoint.ROOT / "scripts" / "run_step020_acceptance.py"
    ) in captured["command"]
    assert "--live" not in captured["command"]


def test_step020_live_acceptance_launcher_adds_live_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {"OPENAI_API_KEY": "secret", "OKCANVAS_AGENT_MODEL": "model"}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["governed-local-tool-approval-live-acceptance"]) == 0
    assert str(
        windows_entrypoint.ROOT / "scripts" / "run_step020_acceptance.py"
    ) in captured["command"]
    assert "--live" in captured["command"]


def test_step021_acceptance_launcher_uses_inbox_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(root=windows_entrypoint.ROOT):
        return {}, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["approval-inbox-acceptance"]) == 0
    assert str(
        windows_entrypoint.ROOT / "scripts" / "run_step021_acceptance.py"
    ) in captured["command"]


def test_control_api_launcher_rejects_invalid_protected_payload_key_without_starting_uvicorn(monkeypatch, capsys) -> None:
    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
            "OKCANVAS_RUN_SUBMITTER_KEY": "submitter-key-123456789",
            "OKCANVAS_PROTECTED_PAYLOAD_KEY": "replace-with-32-byte-urlsafe-base64-key",
        }, None

    called = False

    def fake_run(command, *, cwd, env, check):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["control-api"]) == 2
    assert called is False
    stderr = capsys.readouterr().err
    assert "must decode to exactly 32 bytes" in stderr
    assert "replace-with-32-byte" not in stderr
    assert "generate_protected_payload_key" in stderr


def test_control_api_environment_accepts_32_byte_urlsafe_base64_key() -> None:
    windows_entrypoint.validate_control_api_environment(
        {
            "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
            "OKCANVAS_RUN_SUBMITTER_KEY": "submitter-key-123456789",
            "OKCANVAS_PROTECTED_PAYLOAD_KEY": "Q0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0M=",
        }
    )


def test_control_api_environment_rejects_same_admin_and_submitter_key() -> None:
    with pytest.raises(windows_entrypoint.LocalEnvironmentError):
        windows_entrypoint.validate_control_api_environment(
            {
                "OKCANVAS_CONTROL_ADMIN_KEY": "same-key-123456789",
                "OKCANVAS_RUN_SUBMITTER_KEY": "same-key-123456789",
                "OKCANVAS_PROTECTED_PAYLOAD_KEY": "C" * 64,
            }
        )


def test_control_api_environment_rejects_example_admin_placeholder() -> None:
    with pytest.raises(windows_entrypoint.LocalEnvironmentError) as exc_info:
        windows_entrypoint.validate_control_api_environment(
            {"OKCANVAS_CONTROL_ADMIN_KEY": "replace-with-at-least-16-random-characters"}
        )
    assert "placeholder" in str(exc_info.value)


def test_control_api_environment_validates_distinct_session_history_key() -> None:
    windows_entrypoint.validate_control_api_environment(
        {
            "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
            "OKCANVAS_RUN_SUBMITTER_KEY": "submitter-key-123456789",
            "OKCANVAS_PROTECTED_PAYLOAD_KEY": "C" * 64,
            "OKCANVAS_SESSION_HISTORY_KEY": "D" * 64,
        }
    )


def test_control_api_environment_rejects_invalid_or_reused_session_history_key() -> None:
    with pytest.raises(windows_entrypoint.LocalEnvironmentError, match="SESSION_HISTORY_KEY"):
        windows_entrypoint.validate_control_api_environment(
            {
                "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
                "OKCANVAS_SESSION_HISTORY_KEY": "not-a-32-byte-key",
            }
        )
    with pytest.raises(windows_entrypoint.LocalEnvironmentError, match="must be distinct"):
        windows_entrypoint.validate_control_api_environment(
            {
                "OKCANVAS_CONTROL_ADMIN_KEY": "admin-key-123456789",
                "OKCANVAS_RUN_SUBMITTER_KEY": "submitter-key-123456789",
                "OKCANVAS_PROTECTED_PAYLOAD_KEY": "C" * 64,
                "OKCANVAS_SESSION_HISTORY_KEY": "C" * 64,
            }
        )
