from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.mcp.definitions import (
    MCPDefinitionContractError,
    MCPDefinitionIntegrityError,
    MCPServerCatalog,
)

ROOT = Path(__file__).resolve().parents[1]


def test_resolves_only_allowlisted_readonly_reference_server() -> None:
    definition = MCPServerCatalog(ROOT).resolve("reference-catalog")
    assert definition.server_id == "reference-catalog"
    assert definition.kind == "builtin-stdio"
    assert definition.read_only is True
    assert definition.allowed_tools == ("search_reference", "read_reference_file")
    assert definition.module == "okcanvas_agent_runtime.adapters.mcp.servers.reference_catalog"
    assert len(definition.definition_sha256) == 64


def test_rejects_server_not_in_allowlist(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    source = project / "specs/mcp/servers/reference-catalog"
    target = project / "specs/mcp/servers/other-server"
    shutil.copytree(source, target)
    payload = json.loads((target / "server.json").read_text(encoding="utf-8"))
    payload["server_id"] = "other-server"
    (target / "server.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MCPDefinitionContractError):
        MCPServerCatalog(project).resolve("other-server")


def test_rejects_writable_server_definition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    path = project / "specs/mcp/servers/reference-catalog/server.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["read_only"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MCPDefinitionContractError):
        MCPServerCatalog(project).resolve("reference-catalog")


def test_rejects_symlinked_definition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    path = project / "specs/mcp/servers/reference-catalog/server.json"
    target = tmp_path / "outside.json"
    target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(MCPDefinitionIntegrityError):
        MCPServerCatalog(project).resolve("reference-catalog")
