from pathlib import Path

from scripts.package_source import include


def test_local_secret_file_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    assert include(root / ".env.local") is False
    assert include(root / ".env.local.cmd") is False
    assert include(root / ".env.local.example") is True
    assert not (root / ".env.local.cmd.example").exists()
    assert not (root / ".env.example").exists()


def test_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step002-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_source_package_uses_canonical_archive_root() -> None:
    from scripts.package_source import ARCHIVE_ROOT

    assert ARCHIVE_ROOT.as_posix() == "okcanvas-agent-runtime"


def test_step003_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step003-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_step004_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step004-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_step007_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step007-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_local_product_state_directory_is_excluded() -> None:
    root = Path(__file__).resolve().parents[1]
    assert include(root / ".local" / "product.sqlite3") is False


def test_step008_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step008-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_step009_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step009-live" / "run-001" / "summary.json"
    assert include(path) is False


def test_step071_live_acceptance_evidence_is_excluded_from_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "evidence" / "step071-live" / "run-001" / "acceptance-summary.json"
    assert include(path) is False
