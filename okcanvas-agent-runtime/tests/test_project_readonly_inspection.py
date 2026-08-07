from __future__ import annotations

from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, execute_product_tool
from okcanvas_agent_runtime.adapters.workspace import ReadOnlyProjectInspectionError, inspect_readonly_project

ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "node_modules" / "hidden").mkdir(parents=True)
    (root / "README.md").write_text("# Demo\nRouter lives in src/router.py.\n", encoding="utf-8")
    (root / "src" / "router.py").write_text(
        "def register_routes(app):\n    app.get('/healthz')\n",
        encoding="utf-8",
    )
    (root / "src" / "service.py").write_text("class Service:\n    pass\n", encoding="utf-8")
    (root / "node_modules" / "hidden" / "secret.js").write_text("ROUTER_SECRET", encoding="utf-8")
    return root


def test_bounded_project_inspection_returns_relative_line_evidence(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = inspect_readonly_project(root, "Where are routes registered?")
    after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    assert result.workspace_label == "project"
    assert result.files_considered == 3
    assert result.bytes_considered > 0
    assert result.snapshot_sha256
    assert "src/router.py" in result.inspected_files
    assert all(not path.startswith("/") and ".." not in Path(path).parts for path in result.inspected_files)
    router = next(item for item in result.evidence if item.path == "src/router.py")
    assert router.line_start >= 1
    assert "register_routes" in router.excerpt
    assert "ROUTER_SECRET" not in "\n".join(item.excerpt for item in result.evidence)
    assert before == after


def test_project_tool_catalog_has_exact_readonly_capabilities(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    assert runtime.approval_mode.value == "NEVER"
    assert runtime.read_only is True
    assert runtime.filesystem_access == "read-only"
    assert runtime.network_access == "none"
    assert runtime.shell_access == "none"
    output = execute_product_tool(runtime, "Find register_routes", workspace_root=root)
    assert "src/router.py" in output.inspected_files
    assert output.evidence


def test_project_tool_requires_configured_real_directory(tmp_path: Path) -> None:
    runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
    with pytest.raises(Exception, match="not configured"):
        execute_product_tool(runtime, "inspect")
    with pytest.raises(ReadOnlyProjectInspectionError, match="does not exist"):
        inspect_readonly_project(tmp_path / "missing", "inspect")


def test_project_root_symlink_is_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    link = tmp_path / "project-link"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ReadOnlyProjectInspectionError, match="symbolic link"):
        inspect_readonly_project(link, "inspect")


def test_query_directed_health_lookup_prefers_exact_registration_and_bounds_evidence(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src" / "okcanvas_agent_runtime" / "control_api").mkdir(parents=True)
    (root / "clients" / "cli" / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    app_path = root / "src" / "okcanvas_agent_runtime" / "control_api" / "app.py"
    app_path.write_text(
        "\n".join(
            ["from fastapi import FastAPI", "", "app = FastAPI()"]
            + [f"# unrelated implementation line {index}" for index in range(1, 30)]
            + [
                "@app.get('/healthz')",
                "async def health():",
                "    return {'status': 'ok'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "clients" / "cli" / "src" / "api-client.ts").write_text(
        "export async function health() { return request('/healthz'); }\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_control_api.py").write_text(
        "def test_health(client):\n    assert client.get('/healthz').status_code == 200\n",
        encoding="utf-8",
    )
    (root / "docs" / "plans" / "legacy-health-api.md").write_text(
        ("health api route endpoint registration historical plan\n" * 80),
        encoding="utf-8",
    )
    (root / "src" / "okcanvas_agent_runtime" / "control_api" / "auth.py").write_text(
        ("# api authentication boundary\n" * 100),
        encoding="utf-8",
    )

    result = inspect_readonly_project(
        root,
        "Health API가 어디에서 등록되는지 파일과 라인 근거로 알려줘",
    )

    assert result.inspected_files[0] == "src/okcanvas_agent_runtime/control_api/app.py"
    assert len(result.inspected_files) <= 4
    assert result.evidence_characters <= 5_000
    assert result.query_terms_considered == 2
    primary = result.evidence[0]
    assert "@app.get('/healthz')" in primary.excerpt
    assert "async def health" in primary.excerpt
    assert primary.line_start <= 33 <= primary.line_end
    assert "docs/plans/legacy-health-api.md" not in result.inspected_files
    assert "src/okcanvas_agent_runtime/control_api/auth.py" not in result.inspected_files
    assert all(len(item.excerpt) <= 1_600 for item in result.evidence)
    assert all(item.line_end - item.line_start + 1 <= 16 for item in result.evidence)


def test_query_target_can_prefer_tests_or_documentation_when_explicit(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / "tests" / "test_routes.py").write_text(
        "def test_health_route(client):\n    assert client.get('/healthz').status_code == 200\n",
        encoding="utf-8",
    )
    (root / "docs" / "routing.md").write_text(
        "The health route is documented as GET /healthz.\n",
        encoding="utf-8",
    )

    test_result = inspect_readonly_project(root, "Health API 테스트가 어디에 있는지 알려줘")
    doc_result = inspect_readonly_project(root, "Health API 문서가 어디에 있는지 알려줘")

    assert test_result.inspected_files[0] == "tests/test_routes.py"
    assert doc_result.inspected_files[0] == "docs/routing.md"
