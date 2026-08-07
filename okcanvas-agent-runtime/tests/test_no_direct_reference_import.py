from pathlib import Path

from scripts.verify_no_reference_imports import find_violations

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_never_imports_executable_code_from_reference() -> None:
    assert find_violations(ROOT) == []


def test_reference_verifier_skips_call_source_extraction_when_file_has_no_reference_token(
    tmp_path: Path, monkeypatch,
) -> None:
    import scripts.verify_no_reference_imports as verifier

    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src" / "ordinary.py").write_text(
        "def run():\n"
        "    print('ordinary')\n"
        "    return dict(value=1)\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")

    def reject_unnecessary_source_extraction(*_args, **_kwargs):
        raise AssertionError("call source extraction must be skipped without reference/upstream")

    monkeypatch.setattr(verifier, "_text", reject_unnecessary_source_extraction)
    assert verifier.find_violations(tmp_path) == []
