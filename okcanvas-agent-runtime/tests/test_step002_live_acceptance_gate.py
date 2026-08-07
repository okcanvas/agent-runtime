from scripts.run_step002_live_acceptance import LIVE_GATE, run


def test_step002_live_acceptance_requires_explicit_gate(monkeypatch) -> None:
    monkeypatch.delenv(LIVE_GATE, raising=False)
    assert run() == 2
