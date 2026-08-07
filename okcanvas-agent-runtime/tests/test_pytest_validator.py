from pathlib import Path

from okcanvas_agent_runtime.support.validation import run_pytest_validation


def _fixture(path: Path, expected: int) -> None:
    (path / "src" / "demo").mkdir(parents=True)
    (path / "tests").mkdir()
    (path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath=["src"]\ntestpaths=["tests"]\n',
        encoding="utf-8",
    )
    (path / "src" / "demo" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (path / "tests" / "test_demo.py").write_text(
        f"from demo import VALUE\n\ndef test_value():\n    assert VALUE == {expected}\n",
        encoding="utf-8",
    )


def test_independent_validator_records_failure(tmp_path: Path) -> None:
    _fixture(tmp_path, 2)
    result = run_pytest_validation(tmp_path)
    assert result.state == "FAILED"
    assert result.exit_code == 1
    assert result.failed == 1
    assert result.passed == 0
    assert result.command[-2:] == ["-p", "no:cacheprovider"]
    assert not (tmp_path / ".pytest_cache").exists()


def test_independent_validator_records_success(tmp_path: Path) -> None:
    _fixture(tmp_path, 1)
    result = run_pytest_validation(tmp_path)
    assert result.state == "PASSED"
    assert result.exit_code == 0
    assert result.passed == 1
    assert result.failed == 0
