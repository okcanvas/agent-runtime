from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_optional_example_is_not_imported_by_connector_product() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "organization_context_mcp_server").rglob("*.py")
    )
    assert "okcanvas-connector-examples" not in source
    assert "organization-context-api-fake" not in source
    assert "FAKE_MODE" not in source
