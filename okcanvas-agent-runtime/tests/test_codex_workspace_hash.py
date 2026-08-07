from pathlib import Path

from okcanvas_agent_runtime.adapters.workspace import snapshot_tree


def test_tree_hash_changes_only_when_source_changes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "app.py"
    source.write_text("print('a')\n", encoding="utf-8")
    first = snapshot_tree(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(b"ignored")
    assert snapshot_tree(tmp_path).sha256 == first.sha256
    source.write_text("print('b')\n", encoding="utf-8")
    assert snapshot_tree(tmp_path).sha256 != first.sha256
