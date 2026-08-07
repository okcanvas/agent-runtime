from __future__ import annotations

import ast
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.project_source_identity import force_project_root_first
force_project_root_first(ROOT)

from scripts.step081_architecture import (
    EXPECTED_ADMIN_ROUTES,
    EXPECTED_LEGACY_FIRST_LEVEL_ENTRIES,
    EXPECTED_LEGACY_RESOURCE_FILES,
    EXPECTED_OTHER_HTTP_ROUTES,
    EXPECTED_RUNTIME_INFO_FIELDS,
    CURRENT_VALIDATED_STEP,
    CURRENT_VALIDATED_VERSION,
    EXPECTED_SERVICE_ROUTES,
    EXPECTED_WEBSOCKET_ROUTES,
    PACKAGE_NAMES,
    STEP,
    VERSION,
    alias_registry,
    app_state_reads,
    canonical_modules,
    dependency_direction_violations,
    eager_import_graph,
    first_level_legacy_entries,
    import_cycles,
    import_graph,
    json_sha_without_self,
    read_json,
    resource_hash_validation,
    route_inventory,
    runtime_info_inventory,
    sha256_file,
)

SOURCE_INVENTORY = ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json"
RELOCATION_MANIFEST = ROOT / "specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json"
PHYSICAL_MANIFEST = ROOT / "specs/architecture/STEP081_PHYSICAL_RELOCATION_MANIFEST.json"




def _same_existing_path(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, OSError):
        return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))

def _manifest_hash_valid(payload: dict[str, Any], field: str) -> bool:
    return payload.get(field) == json_sha_without_self(payload, field)


def _physical_manifest_drift(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actual = canonical_modules(ROOT)
    committed = {str(item["module"]): item for item in payload.get("modules", [])}
    drift: list[dict[str, Any]] = []
    for module in sorted(set(actual) | set(committed)):
        path = actual.get(module)
        record = committed.get(module)
        if path is None:
            drift.append({"module": module, "reason": "committed_only"})
            continue
        if record is None:
            drift.append({"module": module, "reason": "actual_only"})
            continue
        relative = path.relative_to(ROOT).as_posix()
        actual_sha = sha256_file(path)
        if record.get("path") != relative or record.get("sha256") != actual_sha:
            drift.append(
                {
                    "module": module,
                    "reason": "path_or_sha_mismatch",
                    "expected_path": record.get("path"),
                    "actual_path": relative,
                    "expected_sha256": record.get("sha256"),
                    "actual_sha256": actual_sha,
                }
            )
    return drift


def _alias_target_failures() -> list[dict[str, Any]]:
    from scripts.step081_architecture import resolve_alias_target

    modules = canonical_modules(ROOT)
    aliases, _ = alias_registry(ROOT)
    failures: list[dict[str, Any]] = []
    for alias in sorted(aliases):
        target, chain = resolve_alias_target(alias, modules=modules, aliases=aliases)
        if target is None:
            failures.append({"alias": alias, "chain": list(chain)})
    return failures


def _declarative_module_reference_failures() -> list[dict[str, Any]]:
    modules = canonical_modules(ROOT)
    failures: list[dict[str, Any]] = []
    for path in sorted((ROOT / "specs" / "mcp" / "servers").glob("*/server.json")):
        payload = read_json(path)
        module = payload.get("module")
        if module is None:
            continue
        if not isinstance(module, str) or module not in modules:
            failures.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "module": module,
                    "reason": "canonical_module_missing",
                }
            )
    return failures


def _declarative_path_reference_failures() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    policy = read_json(policy_path)
    for value in policy.get("development_harnesses", []):
        if not isinstance(value, str) or value.startswith("/"):
            continue
        target = ROOT / value
        if not target.exists():
            failures.append(
                {
                    "path": policy_path.relative_to(ROOT).as_posix(),
                    "value": value,
                    "reason": "declared_path_missing",
                }
            )
    return failures


def _relocation_target_failures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in payload.get("python_relocations", []):
        targets = [ROOT / str(value) for value in item.get("target_paths", [])]
        if not targets or not all(path.is_file() for path in targets):
            failures.append(
                {
                    "legacy_path": item.get("legacy_path"),
                    "target_paths": item.get("target_paths", []),
                }
            )
    for item in payload.get("resource_relocations", []):
        target = ROOT / str(item.get("target_path"))
        if not target.is_file():
            failures.append(
                {
                    "legacy_path": item.get("legacy_path"),
                    "target_path": item.get("target_path"),
                }
            )
    return failures


def _python_ast_failures() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    roots = [ROOT / name for name in PACKAGE_NAMES] + [ROOT / "scripts", ROOT / "tests"]
    for base in roots:
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError) as exc:
                failures.append(
                    {"path": path.relative_to(ROOT).as_posix(), "error": str(exc)}
                )
    return failures


def _project_root_contract_failures() -> list[dict[str, Any]]:
    from okcanvas_agent_runtime.core.paths import (
        CLIENTS_PACKAGE_ROOT,
        PACKAGE_ROOT,
        PROJECT_ROOT,
        PROTOCOLS_PACKAGE_ROOT,
        RUNTIME_PACKAGE_ROOT,
        require_project_root,
    )

    failures: list[dict[str, Any]] = []
    expected = {
        "PROJECT_ROOT": ROOT,
        "PACKAGE_ROOT": ROOT,
        "RUNTIME_PACKAGE_ROOT": ROOT / "okcanvas_agent_runtime",
        "PROTOCOLS_PACKAGE_ROOT": ROOT / "okcanvas_agent_protocols",
        "CLIENTS_PACKAGE_ROOT": ROOT / "okcanvas_agent_clients",
    }
    actual = {
        "PROJECT_ROOT": PROJECT_ROOT,
        "PACKAGE_ROOT": PACKAGE_ROOT,
        "RUNTIME_PACKAGE_ROOT": RUNTIME_PACKAGE_ROOT,
        "PROTOCOLS_PACKAGE_ROOT": PROTOCOLS_PACKAGE_ROOT,
        "CLIENTS_PACKAGE_ROOT": CLIENTS_PACKAGE_ROOT,
    }
    for name, expected_path in expected.items():
        actual_path = actual[name]
        if not _same_existing_path(actual_path, expected_path):
            failures.append(
                {
                    "name": name,
                    "expected": expected_path.as_posix(),
                    "actual": actual_path.as_posix(),
                }
            )
    try:
        resolved = require_project_root()
    except RuntimeError as exc:
        failures.append({"name": "require_project_root", "error": str(exc)})
    else:
        if not _same_existing_path(resolved, ROOT):
            failures.append(
                {
                    "name": "require_project_root",
                    "expected": ROOT.as_posix(),
                    "actual": resolved.as_posix(),
                }
            )

    forbidden = "Path(__file__).resolve().parents["
    allowed = "okcanvas_agent_runtime/core/paths.py"
    for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative == allowed:
            continue
        if forbidden in path.read_text(encoding="utf-8", errors="replace"):
            failures.append(
                {
                    "name": "runtime_parent_depth_project_root",
                    "path": relative,
                }
            )
    return failures


def _executable_legacy_path_coupling() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    tokens = (
        'ROOT / "src" / "okcanvas_agent_runtime"',
        "ROOT / 'src' / 'okcanvas_agent_runtime'",
        'ROOT / "src/okcanvas_agent_runtime',
        "ROOT / 'src/okcanvas_agent_runtime",
        "clients/okcanvas-agent-cli",
        "clients\\okcanvas-agent-cli",
    )
    paths = list((ROOT / "scripts").rglob("*.py"))
    paths.extend(ROOT.glob("*.cmd"))
    paths.extend((ROOT / "clients").rglob("*.py"))
    paths.extend((ROOT / "clients").rglob("*.js"))
    paths.extend((ROOT / "clients").rglob("*.ts"))
    excluded = {
        "scripts/generate_step081_relocation_evidence.py",
        "scripts/validate_step081_architecture.py",
        "scripts/step081_architecture.py",
    }
    for path in sorted(set(paths)):
        if path.relative_to(ROOT).as_posix() in excluded:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = [token for token in tokens if token in text]
        if found:
            failures.append(
                {"path": path.relative_to(ROOT).as_posix(), "tokens": found}
            )
    return failures


def validate() -> dict[str, Any]:
    from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION

    source = read_json(SOURCE_INVENTORY)
    relocation = read_json(RELOCATION_MANIFEST)
    physical = read_json(PHYSICAL_MANIFEST)
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    modules = canonical_modules(ROOT)
    aliases, alias_metadata_count = alias_registry(ROOT)
    graph, missing_imports, import_edge_count = import_graph(ROOT)
    eager_graph, eager_missing, eager_edge_count = eager_import_graph(ROOT)
    cycles = import_cycles(eager_graph)
    direction_violations = dependency_direction_violations(graph)
    route = route_inventory(ROOT)
    runtime_info = runtime_info_inventory()
    physical_drift = _physical_manifest_drift(physical)
    alias_failures = _alias_target_failures()
    relocation_failures = _relocation_target_failures(relocation)
    declarative_module_failures = _declarative_module_reference_failures()
    declarative_path_failures = _declarative_path_reference_failures()
    resource_failures = resource_hash_validation(source, relocation, ROOT)
    ast_failures = _python_ast_failures()
    path_coupling = _executable_legacy_path_coupling()
    project_root_failures = _project_root_contract_failures()
    first_level = first_level_legacy_entries(source)

    wheel_packages = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    pytest_path = (
        pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("pythonpath", [])
    )
    coverage_source = pyproject.get("tool", {}).get("coverage", {}).get("run", {}).get("source", [])

    checks = {
        "identity_exact": CURRENT_STEP == CURRENT_VALIDATED_STEP and PROJECT_VERSION == CURRENT_VALIDATED_VERSION,
        "required_root_packages_present": all((ROOT / name / "__init__.py").is_file() for name in PACKAGE_NAMES),
        "project_root_path_sot_exact": not project_root_failures,
        "legacy_src_package_absent": not (ROOT / "src/okcanvas_agent_runtime").exists(),
        "hatch_root_packages_exact": wheel_packages == list(PACKAGE_NAMES),
        "pytest_root_import_path_exact": pytest_path == ["."],
        "coverage_root_packages_exact": coverage_source == list(PACKAGE_NAMES),
        "source_inventory_identity_exact": source.get("step") == STEP and source.get("version") == VERSION,
        "source_inventory_hash_valid": _manifest_hash_valid(source, "inventory_sha256_without_self"),
        "source_inventory_first_level_exact": len(first_level) == EXPECTED_LEGACY_FIRST_LEVEL_ENTRIES and "governance" in first_level,
        "source_inventory_resources_exact": source.get("resource_file_count") == EXPECTED_LEGACY_RESOURCE_FILES,
        "relocation_manifest_identity_exact": relocation.get("step") == STEP and relocation.get("version") == VERSION,
        "relocation_manifest_hash_valid": _manifest_hash_valid(relocation, "manifest_sha256_without_self"),
        "all_legacy_files_relocated": relocation.get("missing_relocation_count") == 0 and not relocation_failures,
        "declarative_module_references_current": not declarative_module_failures,
        "declarative_path_references_current": not declarative_path_failures,
        "relocated_resources_byte_identical": not resource_failures,
        "physical_manifest_identity_exact": physical.get("step") == STEP and physical.get("version") == VERSION,
        "physical_manifest_hash_valid": _manifest_hash_valid(physical, "manifest_sha256_without_self"),
        "physical_module_inventory_current": physical.get("module_count") == len(modules) and not physical_drift,
        "python_ast_parse_clean": not ast_failures,
        "internal_import_targets_complete": not missing_imports and not eager_missing,
        "eager_import_cycles_absent": not cycles,
        "dependency_direction_violations_absent": not direction_violations,
        "protocol_to_runtime_absent": not any(item["source_zone"] == "protocols" and item["target_zone"] == "runtime" for item in direction_violations),
        "client_to_runtime_absent": not any(item["source_zone"] == "clients" and item["target_zone"] not in {"clients", "protocols"} for item in direction_violations),
        "transport_to_client_absent": not any(item["source_zone"] == "transport" and item["target_zone"] == "clients" for item in direction_violations),
        "transport_concrete_authority_absent": not any(item["source_zone"] == "transport" and item["target_zone"] in {"adapters", "bootstrap", "agent", "domain"} for item in direction_violations),
        "transport_app_state_reads_absent": not app_state_reads(ROOT),
        "compatibility_alias_metadata_current": alias_metadata_count == len(aliases) == physical.get("alias_count"),
        "compatibility_alias_targets_complete": not alias_failures,
        "runtime_info_feature_groups_exact": runtime_info["field_count"] == EXPECTED_RUNTIME_INFO_FIELDS and not runtime_info["missing_group_paths"],
        "runtime_module_origins_exact": route["runtime"].get("source_identity", {}).get("all_under_project_root") is True,
        "router_registration_evidence_exact": {
            item.get("owner"): item.get("registered_route_count")
            for item in route["runtime"].get("router_registration_evidence", [])
        } == {"admin": EXPECTED_ADMIN_ROUTES, "service": EXPECTED_SERVICE_ROUTES}
        and all(
            not item.get("missing_after_reconciliation")
            and not item.get("duplicate_method_paths")
            for item in route["runtime"].get("router_registration_evidence", [])
        ),
        "admin_route_inventory_exact": route["source"]["admin_route_count"] == EXPECTED_ADMIN_ROUTES and not route["missing_runtime_v1_routes"] and not route["unexpected_runtime_v1_routes"],
        "service_route_inventory_exact": route["source"]["service_route_count"] == EXPECTED_SERVICE_ROUTES and not route["missing_runtime_v1_routes"] and not route["unexpected_runtime_v1_routes"],
        "other_http_route_inventory_exact": route["other_http_route_count"] == EXPECTED_OTHER_HTTP_ROUTES,
        "route_method_path_duplicates_absent": not route["source"]["duplicates"] and not route["runtime"]["duplicates"],
        "websocket_runtime_disabled": route["runtime"]["websocket_route_count"] == EXPECTED_WEBSOCKET_ROUTES and not route["source"]["websocket_decorators"],
        "executable_legacy_path_coupling_absent": not path_coupling,
    }
    details = {
        "canonical_module_count": len(modules),
        "alias_count": len(aliases),
        "legacy_source_file_count": source.get("file_count"),
        "legacy_python_file_count": source.get("python_file_count"),
        "legacy_resource_file_count": source.get("resource_file_count"),
        "legacy_first_level_entry_count": len(first_level),
        "import_edge_count": import_edge_count,
        "eager_import_edge_count": eager_edge_count,
        "missing_imports": missing_imports,
        "eager_missing_imports": eager_missing,
        "import_cycles": cycles,
        "dependency_direction_violations": direction_violations,
        "transport_app_state_reads": app_state_reads(ROOT),
        "alias_target_failures": alias_failures,
        "relocation_target_failures": relocation_failures,
        "declarative_module_reference_failures": declarative_module_failures,
        "declarative_path_reference_failures": declarative_path_failures,
        "resource_hash_failures": resource_failures,
        "physical_manifest_drift": physical_drift,
        "ast_failures": ast_failures,
        "executable_legacy_path_coupling": path_coupling,
        "project_root_contract_failures": project_root_failures,
        "runtime_info": runtime_info,
        "route_inventory": route,
    }
    return {
        "schema_version": "okcanvas-step081-architecture-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "checks": checks,
        "details": details,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
