from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, FastAPI

from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.bootstrap.router_registration import include_router_exact
from scripts.project_source_identity import force_project_root_first, validate_module_origins
from scripts.step081_architecture import route_inventory
from scripts.step081_product_inventory import classified_workspace_residue, file_map

ROOT = Path(__file__).resolve().parents[1]


def test_product_owned_router_registration_recovers_silent_framework_noop() -> None:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    router = APIRouter()

    @router.get("/v1/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    app.include_router = lambda _router: None  # type: ignore[method-assign]
    evidence = include_router_exact(app, router, owner="probe")

    assert evidence.fallback_applied is True
    assert evidence.missing_after_include == (("GET", "/v1/probe"),)
    assert evidence.missing_after_reconciliation == ()
    assert evidence.registered_route_count == 1
    assert any(getattr(route, "path", None) == "/v1/probe" for route in app.routes)


def test_composed_application_records_exact_router_registration() -> None:
    with TemporaryDirectory(prefix="step081d-router-registration-") as temporary:
        temp = Path(temporary)
        app = create_app(
            project_root=ROOT,
            product_db=temp / "product.sqlite3",
            evaluation_db=temp / "evaluation.sqlite3",
            artifact_root=temp / "artifacts",
            session_root=temp / "sessions",
            admin_key="step081d-router-registration-key-0001",
        )
    evidence = {item["owner"]: item for item in app.state.router_registration_evidence}
    assert evidence["admin"]["expected_route_count"] == 54
    assert evidence["admin"]["registered_route_count"] == 54
    assert evidence["service"]["expected_route_count"] == 39
    assert evidence["service"]["registered_route_count"] == 39
    assert evidence["admin"]["missing_after_reconciliation"] == []
    assert evidence["service"]["missing_after_reconciliation"] == []


def test_runtime_route_inventory_preserves_source_identity_and_registration_evidence() -> None:
    inventory = route_inventory(ROOT)
    runtime = inventory["runtime"]
    assert runtime["source_identity"]["all_under_project_root"] is True
    assert {item["owner"]: item["registered_route_count"] for item in runtime["router_registration_evidence"]} == {
        "admin": 54,
        "service": 39,
    }
    assert runtime["admin_route_count"] == 54
    assert runtime["service_route_count"] == 39
    assert inventory["missing_runtime_v1_routes"] == []
    assert inventory["unexpected_runtime_v1_routes"] == []


def test_project_root_is_forced_ahead_of_stale_source_paths() -> None:
    original = list(sys.path)
    stale = str(ROOT.parent / "stale-installed-copy")
    try:
        sys.path[:] = [stale, *sys.path, str(ROOT)]
        force_project_root_first(ROOT)
        assert Path(sys.path[0]).resolve() == ROOT.resolve()
        assert sys.path.count(str(ROOT.resolve())) == 1
        identity = validate_module_origins(
            ROOT,
            (
                "okcanvas_agent_runtime",
                "okcanvas_agent_runtime.bootstrap.application",
                "okcanvas_agent_protocols",
                "okcanvas_agent_clients",
            ),
        )
        assert identity["all_under_project_root"] is True
    finally:
        sys.path[:] = original


def test_known_overlay_residue_is_classified_and_excluded_from_product_inventory() -> None:
    with TemporaryDirectory(prefix="step081d-workspace-residue-") as temporary:
        root = Path(temporary)
        (root / "yarn.lock").write_text("stale", encoding="utf-8")
        (root / "old-step.zip").write_bytes(b"zip")
        evidence = root / "docs/evidence/step081b-python-regression/chunk-000-019.txt"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("stale", encoding="utf-8")
        product = root / "okcanvas_agent_runtime/__init__.py"
        product.parent.mkdir(parents=True)
        product.write_text("", encoding="utf-8")

        residue = classified_workspace_residue(root)
        assert {item["reason"] for item in residue} == {
            "root_local_archive",
            "root_local_lockfile",
            "superseded_local_regression_evidence",
        }
        assert set(file_map(root)) == {"okcanvas_agent_runtime/__init__.py"}
