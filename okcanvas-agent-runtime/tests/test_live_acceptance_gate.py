from scripts.run_step001_live_acceptance import LIVE_GATE, run


def test_live_acceptance_is_off_by_default(monkeypatch, capsys) -> None:
    monkeypatch.delenv(LIVE_GATE, raising=False)
    assert run() == 2
    assert "Refusing live execution" in capsys.readouterr().err
