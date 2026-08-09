from __future__ import annotations

import copy
import json
from dataclasses import fields
from pathlib import Path

from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.step081_architecture import EXPECTED_RUNTIME_INFO_FIELDS
from scripts.step081_architecture import (
    ROOT,
    STEP,
    VERSION,
    canonical_modules,
    first_level_legacy_entries,
    json_sha_without_self,
    read_json,
    resolve_alias_target,
    resource_hash_validation,
)
from scripts.validate_step081_architecture import validate


def test_step081_architecture_validator_closes_all_static_gates() -> None:
    result = validate()
    assert result["state"] == "PASSED"
    assert result["passed_checks"] == result["total_checks"] == 40
    assert result["details"]["canonical_module_count"] >= 320
    assert result["details"]["alias_count"] >= 300
    assert result["details"]["import_cycles"] == []
    assert result["details"]["dependency_direction_violations"] == []
    assert result["details"]["route_inventory"]["admin_route_count"] == 54
    assert result["details"]["route_inventory"]["service_route_count"] == 39
    assert result["details"]["route_inventory"]["websocket_route_count"] == 0


def test_step081_identity_root_packages_and_runtime_info_groups_are_exact() -> None:
    assert CURRENT_STEP == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert PROJECT_VERSION == "2.77.0"
    assert STEP == "STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION"
    assert VERSION == "2.61.4"
    assert not (ROOT / "src/okcanvas_agent_runtime").exists()
    for package in (
        "okcanvas_agent_runtime",
        "okcanvas_agent_protocols",
        "okcanvas_agent_clients",
    ):
        assert (ROOT / package / "__init__.py").is_file()
    assert len(fields(RuntimeInfo)) == EXPECTED_RUNTIME_INFO_FIELDS
    for filename in (
        "foundation.py",
        "product.py",
        "agent_session.py",
        "model.py",
        "clients.py",
        "validation.py",
    ):
        assert (ROOT / "okcanvas_agent_runtime/core/runtime_info" / filename).is_file()


def test_step081_source_inventory_includes_governance_and_all_resources() -> None:
    inventory = read_json(ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json")
    entries = first_level_legacy_entries(inventory)
    assert inventory["file_count"] == 272
    assert inventory["python_file_count"] == 262
    assert inventory["resource_file_count"] == 10
    assert len(entries) == 65
    assert "governance" in entries
    assert inventory["inventory_sha256_without_self"] == json_sha_without_self(
        inventory, "inventory_sha256_without_self"
    )


def test_step081_every_legacy_python_source_resolves_to_canonical_files() -> None:
    inventory = read_json(ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json")
    python_files = [item for item in inventory["files"] if item["kind"] == "python"]
    assert len(python_files) == 262
    for item in python_files:
        contract = legacy_source_contract(ROOT, item["path"].removeprefix("src/"))
        assert contract.paths
        assert all(path.is_file() for path in contract.paths)
        assert all("/src/okcanvas_agent_runtime/" not in path.as_posix() for path in contract.paths)


def test_step081_relocated_resources_are_byte_identical() -> None:
    inventory = read_json(ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json")
    relocation = read_json(ROOT / "specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json")
    assert relocation["resource_relocation_count"] == 10
    assert resource_hash_validation(inventory, relocation, ROOT) == []


def test_step081_mutation_gate_detects_governance_omission() -> None:
    inventory = read_json(ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json")
    mutated = copy.deepcopy(inventory)
    mutated["files"] = [
        item
        for item in mutated["files"]
        if not item["path"].startswith("src/okcanvas_agent_runtime/governance/")
    ]
    entries = first_level_legacy_entries(mutated)
    assert "governance" not in entries
    assert len(entries) == 64


def test_step081_mutation_gate_detects_stale_manifest_hash() -> None:
    manifest = read_json(ROOT / "specs/architecture/STEP081_PHYSICAL_RELOCATION_MANIFEST.json")
    mutated = copy.deepcopy(manifest)
    mutated["module_count"] += 1
    assert mutated["manifest_sha256_without_self"] != json_sha_without_self(
        mutated, "manifest_sha256_without_self"
    )


def test_step081_mutation_gate_detects_missing_alias_target() -> None:
    modules = canonical_modules(ROOT)
    target, chain = resolve_alias_target(
        "okcanvas_agent_runtime.removed_component",
        modules=modules,
        aliases={"okcanvas_agent_runtime.removed_component": "okcanvas_agent_runtime.absent"},
    )
    assert target is None
    assert chain == (
        "okcanvas_agent_runtime.removed_component",
        "okcanvas_agent_runtime.absent",
    )


def test_step081_acceptance_reference_verification_serialization_contract() -> None:
    results = ReferenceCatalogService(ROOT).verify_all()
    serialized = [item.to_dict() for item in results]
    assert len(serialized) == 4
    assert all(item["verified"] is True for item in serialized)
    acceptance_source = (ROOT / "scripts/run_step081_acceptance.py").read_text(encoding="utf-8")
    assert "to_public_dict" not in acceptance_source
    assert "tests/test_operations_console_api.py" in acceptance_source
    assert "tests/test_operations_api.py" not in acceptance_source
    assert '"pending_external_gate_count"' in acceptance_source
    assert '"windows_only_pending"' in acceptance_source
    compliance_generator_source = (ROOT / "scripts/generate_step081_compliance.py").read_text(encoding="utf-8")
    assert "changed = sorted(set(changed) | {output_relative})" in compliance_generator_source
