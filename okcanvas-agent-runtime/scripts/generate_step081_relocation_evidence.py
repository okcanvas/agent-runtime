from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
if str(ROOT_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(ROOT_BOOTSTRAP))

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from scripts.step081_architecture import (
    ROOT,
    STEP,
    VERSION,
    alias_registry,
    canonical_modules,
    json_sha_without_self,
    module_name,
    sha256_file,
    write_json,
)

DEFAULT_BASELINE_ROOT = Path("/mnt/data/step081_work/okcanvas-agent-runtime")
SOURCE_INVENTORY = ROOT / "specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json"
RELOCATION_MANIFEST = ROOT / "specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json"
PHYSICAL_MANIFEST = ROOT / "specs/architecture/STEP081_PHYSICAL_RELOCATION_MANIFEST.json"

RESOURCE_TARGETS = {
    "src/okcanvas_agent_runtime/governance/resources/architecture_constitution.json":
        "okcanvas_agent_runtime/core/governance/resources/architecture_constitution.json",
    "src/okcanvas_agent_runtime/governance/resources/constitution_gate_catalog.json":
        "okcanvas_agent_runtime/core/governance/resources/constitution_gate_catalog.json",
    "src/okcanvas_agent_runtime/interactive_runner/assets/index.html":
        "okcanvas_agent_clients/dev_runner/assets/index.html",
    "src/okcanvas_agent_runtime/interactive_runner/assets/persisted-sse.js":
        "okcanvas_agent_clients/dev_runner/assets/persisted-sse.js",
    "src/okcanvas_agent_runtime/interactive_runner/assets/runner.css":
        "okcanvas_agent_clients/dev_runner/assets/runner.css",
    "src/okcanvas_agent_runtime/interactive_runner/assets/runner.js":
        "okcanvas_agent_clients/dev_runner/assets/runner.js",
    "src/okcanvas_agent_runtime/operations_console/assets/console.css":
        "okcanvas_agent_clients/dev_console/assets/console.css",
    "src/okcanvas_agent_runtime/operations_console/assets/console.js":
        "okcanvas_agent_clients/dev_console/assets/console.js",
    "src/okcanvas_agent_runtime/operations_console/assets/index.html":
        "okcanvas_agent_clients/dev_console/assets/index.html",
    "src/okcanvas_agent_runtime/operations_console/assets/persisted-sse.js":
        "okcanvas_agent_clients/dev_console/assets/persisted-sse.js",
}


def inventory_baseline(baseline_root: Path) -> dict[str, Any]:
    source_root = baseline_root / "src/okcanvas_agent_runtime"
    if not source_root.is_dir():
        raise FileNotFoundError(f"STEP080A source root missing: {source_root}")
    files: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(baseline_root).as_posix()
        files.append(
            {
                "path": relative,
                "kind": "python" if path.suffix == ".py" else "resource",
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    first_level: set[str] = set()
    for item in files:
        relative = item["path"].removeprefix("src/okcanvas_agent_runtime/")
        first = relative.split("/", 1)[0]
        if first == "__init__.py":
            first = "__package__"
        elif first.endswith(".py"):
            first = first[:-3]
        first_level.add(first)
    payload: dict[str, Any] = {
        "schema_version": "okcanvas-step081-source-baseline-inventory-v1",
        "step": STEP,
        "version": VERSION,
        "baseline_step": "STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES",
        "baseline_version": "2.60.1",
        "source_root": "src/okcanvas_agent_runtime",
        "file_count": len(files),
        "python_file_count": sum(item["kind"] == "python" for item in files),
        "resource_file_count": sum(item["kind"] == "resource" for item in files),
        "first_level_entry_count": len(first_level),
        "first_level_entries": sorted(first_level),
        "files": files,
    }
    payload["inventory_sha256_without_self"] = json_sha_without_self(
        payload, "inventory_sha256_without_self"
    )
    return payload


def build_relocation_manifest(inventory: dict[str, Any]) -> dict[str, Any]:
    python_relocations: list[dict[str, Any]] = []
    resource_relocations: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in inventory["files"]:
        legacy = str(item["path"])
        if item["kind"] == "python":
            logical_path = legacy.removeprefix("src/")
            try:
                contract = legacy_source_contract(ROOT, logical_path)
                targets = [path.relative_to(ROOT).as_posix() for path in contract.paths]
            except (FileNotFoundError, KeyError) as exc:
                missing.append(f"{legacy}: {exc}")
                targets = []
            python_relocations.append(
                {
                    "legacy_path": legacy,
                    "legacy_sha256": item["sha256"],
                    "target_paths": targets,
                    "status": "RELOCATED_AND_COMPATIBILITY_RESOLVED" if targets else "MISSING",
                }
            )
        else:
            target_relative = RESOURCE_TARGETS.get(legacy)
            target = ROOT / target_relative if target_relative else None
            preserved = bool(
                target is not None
                and target.is_file()
                and sha256_file(target) == item["sha256"]
            )
            if not preserved:
                missing.append(legacy)
            resource_relocations.append(
                {
                    "legacy_path": legacy,
                    "legacy_sha256": item["sha256"],
                    "target_path": target_relative,
                    "target_sha256": sha256_file(target) if target and target.is_file() else None,
                    "status": "RELOCATED_BYTE_IDENTICAL" if preserved else "MISSING_OR_HASH_MISMATCH",
                }
            )
    payload: dict[str, Any] = {
        "schema_version": "okcanvas-step081-executed-relocation-manifest-v1",
        "step": STEP,
        "version": VERSION,
        "legacy_source_root_removed": not (ROOT / "src/okcanvas_agent_runtime").exists(),
        "python_relocation_count": len(python_relocations),
        "resource_relocation_count": len(resource_relocations),
        "missing_relocation_count": len(missing),
        "missing_relocations": missing,
        "python_relocations": python_relocations,
        "resource_relocations": resource_relocations,
    }
    payload["manifest_sha256_without_self"] = json_sha_without_self(
        payload, "manifest_sha256_without_self"
    )
    return payload


def build_physical_manifest(relocation: dict[str, Any]) -> dict[str, Any]:
    modules = canonical_modules(ROOT)
    aliases, alias_metadata_count = alias_registry(ROOT)
    roots = Counter(name.split(".", 1)[0] for name in modules)
    module_records = [
        {
            "module": name,
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
        for name, path in sorted(modules.items())
    ]
    payload: dict[str, Any] = {
        "schema_version": "okcanvas-step081-physical-relocation-manifest-v2",
        "step": STEP,
        "version": VERSION,
        "legacy_source_root_removed": not (ROOT / "src/okcanvas_agent_runtime").exists(),
        "package_roots": list(roots),
        "package_module_counts": dict(sorted(roots.items())),
        "module_count": len(module_records),
        "alias_count": len(aliases),
        "alias_metadata_count": alias_metadata_count,
        "legacy_python_relocation_count": relocation["python_relocation_count"],
        "legacy_resource_relocation_count": relocation["resource_relocation_count"],
        "modules": module_records,
    }
    payload["manifest_sha256_without_self"] = json_sha_without_self(
        payload, "manifest_sha256_without_self"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    args = parser.parse_args()
    inventory = inventory_baseline(args.baseline_root.resolve())
    relocation = build_relocation_manifest(inventory)
    physical = build_physical_manifest(relocation)
    write_json(SOURCE_INVENTORY, inventory)
    write_json(RELOCATION_MANIFEST, relocation)
    write_json(PHYSICAL_MANIFEST, physical)
    print(
        f"source_files={inventory['file_count']} python={inventory['python_file_count']} "
        f"resources={inventory['resource_file_count']} first_level={inventory['first_level_entry_count']}"
    )
    print(
        f"relocations={relocation['python_relocation_count'] + relocation['resource_relocation_count']} "
        f"missing={relocation['missing_relocation_count']}"
    )
    print(f"canonical_modules={physical['module_count']} aliases={physical['alias_count']}")
    return 0 if relocation["missing_relocation_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
