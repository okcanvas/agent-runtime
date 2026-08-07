import json
from pathlib import Path


def test_reference_manifest_and_licenses() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "reference" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert len(payload["references"]) == 4
    for item in payload["references"]:
        reference = root / "reference" / "upstream" / item["dest"]
        assert reference.is_dir()
        assert (reference / "LICENSE").is_file()


def test_specification_directories_are_not_python_packages() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not (root / "agents").exists()
    assert not (root / "mcp").exists()
    assert not (root / "tools").exists()
    assert not any((root / "specs").rglob("__init__.py"))
