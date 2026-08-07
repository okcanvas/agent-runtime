from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_acceptance_module():
    path = ROOT / "scripts" / "run_step049_acceptance.py"
    spec = importlib.util.spec_from_file_location("step049_acceptance_history_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step049_history_probe_always_closes_sqlite_connection(monkeypatch) -> None:
    module = _load_acceptance_module()

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False
            self.query = None
            self.parameters = None

        def execute(self, query, parameters):
            self.query = query
            self.parameters = parameters
            return self

        def fetchone(self):
            return (8,)

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(module.sqlite3, "connect", lambda _: connection)

    assert module._history_count(Path("history.sqlite3"), "session-test") == 8
    assert connection.closed is True
    assert connection.parameters == ("session-test",)
