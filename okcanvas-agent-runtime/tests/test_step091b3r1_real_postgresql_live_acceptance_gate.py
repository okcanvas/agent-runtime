from __future__ import annotations

import json
import re
from pathlib import Path

from scripts import run_step091b3r1_postgresql_live_acceptance as live

ROOT = Path(__file__).resolve().parents[1]


def test_live_schema_name_is_isolated_and_identifier_safe() -> None:
    names = {live._schema_name() for _ in range(10)}
    assert len(names) == 10
    assert all(name.startswith(live.SCHEMA_PREFIX) for name in names)
    assert all(re.fullmatch(r"[a-z0-9_]+", name) for name in names)
    assert all(len(name) < 64 for name in names)


def test_live_gate_refuses_missing_dsn_without_importing_driver(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv(live.LIVE_DSN_ENV, raising=False)
    monkeypatch.delenv(live.LIVE_CONFIRM_ENV, raising=False)
    output = tmp_path / "missing-dsn.json"
    result = live.main(["--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 2
    assert payload["state"] == "FAILED"
    assert payload["failure_code"] == "POSTGRESQL_LIVE_DSN_MISSING"
    assert "dsn" not in json.dumps(payload).lower() or "dsn_missing" in json.dumps(payload).lower()


def test_live_gate_requires_explicit_destructive_confirmation(
    tmp_path: Path, monkeypatch
) -> None:
    dsn = "postgresql://runtime:top-secret@db.example/okcanvas"
    monkeypatch.setenv(live.LIVE_DSN_ENV, dsn)
    monkeypatch.delenv(live.LIVE_CONFIRM_ENV, raising=False)
    output = tmp_path / "missing-confirmation.json"
    result = live.main(["--output", str(output)])
    payload_text = output.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    assert result == 2
    assert payload["failure_code"] == "POSTGRESQL_LIVE_CONFIRMATION_MISSING"
    assert dsn not in payload_text
    assert "top-secret" not in payload_text
    assert "db.example" not in payload_text


def test_live_decision_has_unique_exact_hashes() -> None:
    first = live._decision("first")
    second = live._decision("second")
    assert first.submission_id != second.submission_id
    assert first.idempotency_key_sha256 != second.idempotency_key_sha256
    assert len(first.idempotency_key_sha256) == 64
    assert first.approval_required is False
    assert first.executable_now is True


def test_live_gate_source_proves_real_server_concurrency_and_cleanup_contract() -> None:
    source = (ROOT / "scripts/run_step091b3r1_postgresql_live_acceptance.py").read_text(
        encoding="utf-8"
    )
    required = (
        "psycopg.connect",
        "CREATE SCHEMA",
        "DROP SCHEMA IF EXISTS",
        "SET search_path",
        "ThreadPoolExecutor",
        "concurrent_admission_is_idempotent",
        "governed_admission_rolls_back_atomically",
        "concurrent_event_sequences_are_contiguous",
        "approval_state_machine_and_resume_fence_live",
        "evaluation_round_trip_live",
        "session_active_run_row_lock_live",
        "session_metadata_survives_service_restart",
        "sqlite_default_topology_retained",
        "dsn_sha256",
    )
    assert all(token in source for token in required)
    assert "failure_code = f\"POSTGRESQL_LIVE_ACCEPTANCE_{type(exc).__name__.upper()}\"" in source
    assert "str(exc)" not in source[source.index("except Exception as exc:  # live diagnostics"):]


def test_live_windows_launcher_uses_bytecode_isolation() -> None:
    launcher = (ROOT / "sh_run_step091b3r1_postgresql_live_acceptance.cmd").read_text(
        encoding="utf-8"
    )
    assert "scripts\\python_bytecode_isolation.py" in launcher
    assert "scripts\\run_step091b3r1_postgresql_live_acceptance.py" in launcher
    assert "%*" in launcher
