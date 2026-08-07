from scripts.run_step004_live_acceptance import LIVE_GATE, run


def test_step004_live_acceptance_requires_explicit_gate(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(LIVE_GATE, raising=False)
    assert run(["--output-root", str(tmp_path)]) == 2
