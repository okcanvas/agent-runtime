from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import (
    ProductStoreReferenceAccessRecorder,
    ReferenceCatalogService,
    ReferenceIntegrityError,
    ReferencePathError,
    ReferenceQueryError,
)


def _tree_hash(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    total = 0
    for path in files:
        data = path.read_bytes()
        total += len(data)
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest(), len(files), total


def _mini_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    upstream = project / "reference" / "upstream" / "sample-ref"
    (upstream / "src").mkdir(parents=True)
    (upstream / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (upstream / "src" / "sample.py").write_text(
        "class Sample:\n    def run_state(self):\n        return 'RunState'\n",
        encoding="utf-8",
    )
    (upstream / "src" / "other.py").write_text(
        "def helper():\n    return 'other'\n",
        encoding="utf-8",
    )
    digest, count, byte_count = _tree_hash(upstream)
    manifest = {
        "schema_version": 1,
        "references": [
            {
                "id": "sample",
                "classification": "TEST_REFERENCE",
                "version": "1.0",
                "source_url": "https://example.invalid/sample",
                "sha256": "0" * 64,
                "tree_sha256": digest,
                "dest": "sample-ref",
                "file_count": count,
                "byte_count": byte_count,
                "notes": "test fixture",
            }
        ],
    }
    reference = project / "reference"
    (reference / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (reference / "CODE_MAP.md").write_text(
        "# Reference Code Map\n\n## Sample\n\n"
        "- RunState sample: `upstream/sample-ref/src/sample.py`\n",
        encoding="utf-8",
    )
    return project


def test_actual_reference_catalog_uses_code_map_first() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = ReferenceCatalogService(root)
    result = catalog.search(
        "RunState",
        reference_ids=("openai-agents-python",),
        max_results=5,
    )
    assert result.code_map_matches
    assert result.code_map_matches[0].relative_path == "src/agents/run_state.py"
    assert result.matches[0].relative_path == "src/agents/run_state.py"
    assert all(len(match.file_sha256) == 64 for match in result.matches)


def test_actual_reference_exact_line_read_has_file_sha() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = ReferenceCatalogService(root)
    result = catalog.read_lines(
        "openai-agents-python",
        "src/agents/run_state.py",
        start_line=1,
        end_line=3,
    )
    assert result.actual_start_line == 1
    assert result.actual_end_line == 3
    assert result.lines[0].line_number == 1
    assert "RunState" in result.lines[0].text
    assert result.file_sha256 == hashlib.sha256(
        (root / "reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py").read_bytes()
    ).hexdigest()


def test_manifest_declared_tree_is_verified_before_access(tmp_path: Path) -> None:
    project = _mini_project(tmp_path)
    catalog = ReferenceCatalogService(project)
    assert catalog.verify_reference("sample").verified is True

    (project / "reference/upstream/sample-ref/src/sample.py").write_text(
        "mutated\n", encoding="utf-8"
    )
    with pytest.raises(ReferenceIntegrityError):
        catalog.search("RunState", reference_ids=("sample",))


def test_absolute_traversal_and_windows_paths_are_rejected(tmp_path: Path) -> None:
    catalog = ReferenceCatalogService(_mini_project(tmp_path))
    for unsafe in ("../AGENTS.md", "/etc/passwd", r"C:\\Windows\\win.ini", "src/../LICENSE"):
        with pytest.raises(ReferencePathError):
            catalog.read_lines("sample", unsafe, start_line=1, end_line=1)


def test_symbolic_path_component_is_rejected_without_following_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _mini_project(tmp_path)
    catalog = ReferenceCatalogService(project)
    target = project / "reference/upstream/sample-ref/src/sample.py"
    original = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        return path == target or original(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    with pytest.raises(ReferenceIntegrityError, match="Symbolic links"):
        catalog.read_lines("sample", "src/sample.py", start_line=1, end_line=1)


def test_search_and_read_limits_fail_closed(tmp_path: Path) -> None:
    catalog = ReferenceCatalogService(_mini_project(tmp_path))
    with pytest.raises(ReferenceQueryError):
        catalog.search("x", reference_ids=("sample",))
    with pytest.raises(ReferenceQueryError):
        catalog.search("RunState", reference_ids=("sample",), max_results=101)
    with pytest.raises(ReferenceQueryError):
        catalog.read_lines("sample", "src/sample.py", start_line=1, end_line=500)
    with pytest.raises(ReferenceQueryError, match="exceeds the file length"):
        catalog.read_lines("sample", "src/sample.py", start_line=100, end_line=100)


def test_search_is_bounded_and_reports_truncation(tmp_path: Path) -> None:
    project = _mini_project(tmp_path)
    path = project / "reference/upstream/sample-ref/src/sample.py"
    path.write_text("\n".join(["RunState"] * 20) + "\n", encoding="utf-8")
    digest, count, byte_count = _tree_hash(path.parents[1])
    manifest_path = project / "reference/MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["references"][0]["tree_sha256"] = digest
    manifest["references"][0]["file_count"] = count
    manifest["references"][0]["byte_count"] = byte_count
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = ReferenceCatalogService(project).search(
        "RunState",
        reference_ids=("sample",),
        max_results=2,
        max_matches_per_file=10,
    )
    assert len(result.matches) == 2
    assert result.truncated is True


def test_product_store_records_reference_access_without_raw_query(tmp_path: Path) -> None:
    project = _mini_project(tmp_path)
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    task = store.create_task(
        task_type="REFERENCE_REVIEW",
        input_sha256=hashlib.sha256(b"request").hexdigest(),
        agent_definition_id="reference-reviewer",
        agent_definition_version="v1",
    )
    run = store.create_run(task_id=task.task_id)
    catalog = ReferenceCatalogService(
        project, recorder=ProductStoreReferenceAccessRecorder(store)
    )

    search = catalog.search("RunState", reference_ids=("sample",), run_id=run.run_id)
    catalog.read_lines(
        "sample",
        "src/sample.py",
        start_line=1,
        end_line=3,
        run_id=run.run_id,
    )

    events = store.list_events(run.run_id)
    assert [event.event_type for event in events] == [
        "run.created",
        "reference.search.completed",
        "reference.file.read",
    ]
    assert events[1].source is EventSource.REFERENCE
    assert events[1].payload["query_sha256"] == search.query_sha256
    assert "RunState" not in json.dumps(events[1].payload)
    assert events[2].payload["relative_path"] == "src/sample.py"


def test_run_id_requires_an_access_recorder(tmp_path: Path) -> None:
    catalog = ReferenceCatalogService(_mini_project(tmp_path))
    with pytest.raises(ReferenceQueryError, match="recorder"):
        catalog.search("RunState", reference_ids=("sample",), run_id="run_1")
