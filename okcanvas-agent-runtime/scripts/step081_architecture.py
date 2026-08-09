from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import platform
from collections import Counter, defaultdict
from dataclasses import fields
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAMES = (
    "okcanvas_agent_runtime",
    "okcanvas_agent_protocols",
    "okcanvas_agent_clients",
)
STEP = "STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION"
VERSION = "2.61.4"
CURRENT_VALIDATED_STEP = "STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION"
CURRENT_VALIDATED_VERSION = "2.79.0"
EXPECTED_RUNTIME_INFO_FIELDS = 1058
EXPECTED_ADMIN_ROUTES = 54
EXPECTED_SERVICE_ROUTES = 39
EXPECTED_OTHER_HTTP_ROUTES = 5
EXPECTED_WEBSOCKET_ROUTES = 0
EXPECTED_LEGACY_FIRST_LEVEL_ENTRIES = 65
EXPECTED_LEGACY_RESOURCE_FILES = 10


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object JSON: {path}")
    return payload


def module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def canonical_python_files(root: Path = ROOT) -> tuple[Path, ...]:
    return tuple(
        path
        for package in PACKAGE_NAMES
        for path in sorted((root / package).rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def canonical_modules(root: Path = ROOT) -> dict[str, Path]:
    return {module_name(root, path): path for path in canonical_python_files(root)}


def alias_registry(root: Path = ROOT) -> tuple[dict[str, str], int]:
    payload = read_json(root / "okcanvas_agent_runtime/compatibility/aliases.json")
    aliases = payload.get("aliases")
    if not isinstance(aliases, dict):
        raise TypeError("aliases.json aliases must be an object")
    return ({str(k): str(v) for k, v in aliases.items()}, int(payload.get("alias_count", -1)))


def resolve_alias_target(
    name: str,
    *,
    modules: dict[str, Path],
    aliases: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    current = name
    chain: list[str] = []
    while current not in chain:
        chain.append(current)
        if current in modules:
            return current, tuple(chain)
        target = aliases.get(current)
        if target is None:
            return None, tuple(chain)
        current = target
    return None, tuple(chain)


def _source_package(module: str, path: Path) -> str:
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def imported_internal_modules(
    root: Path,
    path: Path,
    tree: ast.AST,
    module: str,
    modules: dict[str, Path],
    aliases: dict[str, str],
) -> tuple[set[str], list[dict[str, Any]]]:
    imports: set[str] = set()
    missing: list[dict[str, Any]] = []
    package = _source_package(module, path)

    def register(candidate: str, lineno: int) -> None:
        if not candidate.startswith(PACKAGE_NAMES):
            return
        resolved, chain = resolve_alias_target(candidate, modules=modules, aliases=aliases)
        if resolved is None:
            missing.append(
                {
                    "source": module,
                    "line": lineno,
                    "import": candidate,
                    "resolution_chain": list(chain),
                }
            )
            return
        imports.add(resolved)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                register(alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = "." * node.level + (node.module or "")
                try:
                    base = importlib.util.resolve_name(relative, package)
                except (ImportError, ValueError):
                    missing.append(
                        {
                            "source": module,
                            "line": node.lineno,
                            "import": relative,
                            "resolution_chain": [],
                        }
                    )
                    continue
            else:
                base = node.module or ""
            register(base, node.lineno)
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in modules or candidate in aliases:
                    register(candidate, node.lineno)
    return imports, missing


def import_graph(root: Path = ROOT) -> tuple[dict[str, set[str]], list[dict[str, Any]], int]:
    modules = canonical_modules(root)
    aliases, _ = alias_registry(root)
    graph: dict[str, set[str]] = {name: set() for name in modules}
    missing: list[dict[str, Any]] = []
    edge_count = 0
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports, unresolved = imported_internal_modules(root, path, tree, module, modules, aliases)
        graph[module].update(imports)
        missing.extend(unresolved)
        edge_count += len(imports)
    return graph, missing, edge_count


def import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph.get(node, ()):
            if target not in graph:
                continue
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1 or node in graph.get(node, set()):
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return sorted(components)


def zone(module: str) -> str:
    if module.startswith("okcanvas_agent_protocols"):
        return "protocols"
    if module.startswith("okcanvas_agent_clients"):
        return "clients"
    if not module.startswith("okcanvas_agent_runtime"):
        return "external"
    parts = module.split(".")
    if len(parts) > 1 and parts[1] == "__main__":
        return "bootstrap"
    return parts[1] if len(parts) > 1 else "runtime"


ALLOWED_ZONE_IMPORTS: dict[str, set[str]] = {
    "clients": {"clients", "protocols"},
    "protocols": {"protocols"},
    "transport": {"transport", "application", "protocols", "core"},
    "application": {"application", "agent", "domain", "core", "protocols", "verticals"},
    "agent": {"agent", "domain", "core", "protocols"},
    "domain": {"domain", "core", "protocols"},
    "adapters": {"adapters", "application", "agent", "domain", "core", "protocols", "verticals"},
    "bootstrap": {
        "bootstrap", "transport", "adapters", "application", "agent", "domain",
        "core", "protocols", "clients", "support", "verticals",
    },
    "support": {
        "support", "bootstrap", "transport", "adapters", "application", "agent",
        "domain", "core", "protocols", "clients", "verticals",
    },
    "core": {"core", "protocols"},
    "compatibility": {
        "compatibility", "bootstrap", "transport", "adapters", "application", "agent",
        "domain", "core", "protocols", "clients", "support", "verticals",
    },
    "verticals": {"verticals", "application", "agent", "domain", "core", "protocols"},
    "runtime": {"core", "compatibility"},
}


def dependency_direction_violations(graph: dict[str, set[str]]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for source, targets in graph.items():
        source_zone = zone(source)
        allowed = ALLOWED_ZONE_IMPORTS.get(source_zone, {source_zone})
        for target in targets:
            target_zone = zone(target)
            if target_zone not in allowed:
                violations.append(
                    {
                        "source": source,
                        "target": target,
                        "source_zone": source_zone,
                        "target_zone": target_zone,
                    }
                )
    return sorted(violations, key=lambda item: (item["source"], item["target"]))


def app_state_reads(root: Path = ROOT) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    transport = root / "okcanvas_agent_runtime/transport"
    for path in sorted(transport.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "state":
                value = node.value
                if isinstance(value, ast.Attribute) and value.attr == "app":
                    violations.append(
                        {"path": path.relative_to(root).as_posix(), "line": node.lineno}
                    )
    return violations


HTTP_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _source_router_records(path: Path, *, default_prefix: str = "") -> list[dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    prefix = default_prefix
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        for keyword in call.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                prefix = keyword.value.value
    records: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
                continue
            method = decorator.func.attr.casefold()
            if method not in HTTP_DECORATORS or not decorator.args:
                continue
            value = decorator.args[0]
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            records.append({"method": method.upper(), "path": f"{prefix}{value.value}"})
    return sorted(records, key=lambda item: (item["path"], item["method"]))


def source_route_inventory(root: Path = ROOT) -> dict[str, Any]:
    admin_records = _source_router_records(root / "okcanvas_agent_runtime/transport/admin/rest/routes.py")
    service_records = _source_router_records(root / "okcanvas_agent_runtime/transport/service/rest/routes.py")
    records = admin_records + service_records
    pairs = [(item["method"], item["path"]) for item in records]
    duplicates = [
        {"method": method, "path": path, "count": count}
        for (method, path), count in sorted(Counter(pairs).items())
        if count > 1
    ]
    websocket_decorators: list[dict[str, Any]] = []
    for base in (
        root / "okcanvas_agent_runtime/transport",
        root / "okcanvas_agent_runtime/bootstrap",
    ):
        for path in sorted(base.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr.casefold() in {"websocket", "websocket_route"}:
                    websocket_decorators.append(
                        {"path": path.relative_to(root).as_posix(), "line": getattr(node, "lineno", None)}
                    )
    return {
        "admin_route_count": len(admin_records),
        "service_route_count": len(service_records),
        "duplicates": duplicates,
        "routes": sorted(records, key=lambda item: (item["path"], item["method"])),
        "websocket_decorators": websocket_decorators,
    }


def runtime_route_inventory(root: Path = ROOT) -> dict[str, Any]:
    import fastapi
    import pydantic
    import starlette
    from okcanvas_agent_runtime.bootstrap import application as application_module
    from okcanvas_agent_runtime.bootstrap.application import create_app
    from okcanvas_agent_runtime.transport.admin.rest import routes as admin_routes_module
    from okcanvas_agent_runtime.transport.service.rest import routes as service_routes_module
    from scripts.project_source_identity import validate_module_origins

    source_identity = validate_module_origins(
        root,
        (
            "okcanvas_agent_runtime",
            "okcanvas_agent_runtime.bootstrap.application",
            "okcanvas_agent_runtime.bootstrap.router_registration",
            "okcanvas_agent_runtime.transport.admin.rest.routes",
            "okcanvas_agent_runtime.transport.service.rest.routes",
            "okcanvas_agent_protocols",
            "okcanvas_agent_clients",
        ),
    )
    with TemporaryDirectory(prefix="step081-route-inventory-") as temporary:
        temp = Path(temporary)
        app = create_app(
            project_root=root,
            product_db=temp / "product.sqlite3",
            evaluation_db=temp / "evaluation.sqlite3",
            artifact_root=temp / "artifacts",
            session_root=temp / "sessions",
            admin_key="step081-route-inventory-key-0001",
        )
        records: list[dict[str, str]] = []
        pairs: list[tuple[str, str]] = []
        websocket_count = 0
        for route in app.routes:
            route_path = str(getattr(route, "path", ""))
            class_name = route.__class__.__name__.casefold()
            if "websocket" in class_name:
                websocket_count += 1
                continue
            methods = {
                str(method).upper()
                for method in (getattr(route, "methods", set()) or set())
            } - {"HEAD", "OPTIONS"}
            for method in sorted(methods):
                pairs.append((method, route_path))
                records.append({"method": method, "path": route_path})
        duplicates = [
            {"method": method, "path": path, "count": count}
            for (method, path), count in sorted(Counter(pairs).items())
            if count > 1
        ]
        service = sum(1 for item in records if item["path"].startswith("/v1/service"))
        admin = sum(
            1
            for item in records
            if item["path"].startswith("/v1")
            and not item["path"].startswith("/v1/service")
        )
        other = len(records) - admin - service
        return {
            "admin_route_count": admin,
            "service_route_count": service,
            "other_http_route_count": other,
            "http_route_count": len(records),
            "websocket_route_count": websocket_count,
            "duplicates": duplicates,
            "routes": sorted(records, key=lambda item: (item["path"], item["method"])),
            "router_registration_evidence": list(
                getattr(app.state, "router_registration_evidence", ())
            ),
            "source_identity": source_identity,
            "runtime_versions": {
                "python": platform.python_version(),
                "fastapi": fastapi.__version__,
                "starlette": starlette.__version__,
                "pydantic": pydantic.__version__,
            },
            "object_origins": {
                "create_app": str(Path(application_module.__file__).resolve()),
                "admin_routes": str(Path(admin_routes_module.__file__).resolve()),
                "service_routes": str(Path(service_routes_module.__file__).resolve()),
            },
        }


def route_inventory(root: Path = ROOT) -> dict[str, Any]:
    source = source_route_inventory(root)
    runtime = runtime_route_inventory(root)
    source_pairs = {(item["method"], item["path"]) for item in source["routes"]}
    runtime_v1_pairs = {
        (item["method"], item["path"])
        for item in runtime["routes"]
        if item["path"].startswith("/v1")
    }
    return {
        **runtime,
        "source": source,
        "runtime": runtime,
        "missing_runtime_v1_routes": [
            {"method": method, "path": path}
            for method, path in sorted(source_pairs - runtime_v1_pairs)
        ],
        "unexpected_runtime_v1_routes": [
            {"method": method, "path": path}
            for method, path in sorted(runtime_v1_pairs - source_pairs)
        ],
    }

def runtime_info_inventory() -> dict[str, Any]:
    from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

    group_paths = (
        "okcanvas_agent_runtime/core/runtime_info/foundation.py",
        "okcanvas_agent_runtime/core/runtime_info/product.py",
        "okcanvas_agent_runtime/core/runtime_info/agent_session.py",
        "okcanvas_agent_runtime/core/runtime_info/model.py",
        "okcanvas_agent_runtime/core/runtime_info/clients.py",
        "okcanvas_agent_runtime/core/runtime_info/validation.py",
    )
    return {
        "field_count": len(fields(RuntimeInfo)),
        "group_paths": list(group_paths),
        "missing_group_paths": [path for path in group_paths if not (ROOT / path).is_file()],
    }


def first_level_legacy_entries(inventory: dict[str, Any]) -> set[str]:
    entries: set[str] = set()
    for record in inventory.get("files", []):
        path = str(record["path"])
        prefix = "src/okcanvas_agent_runtime/"
        relative = path[len(prefix):] if path.startswith(prefix) else path
        first = relative.split("/", 1)[0]
        if first == "__init__.py":
            first = "__package__"
        elif first.endswith(".py"):
            first = first[:-3]
        entries.add(first)
    return entries


def resource_hash_validation(
    source_inventory: dict[str, Any], relocation_manifest: dict[str, Any], root: Path = ROOT
) -> list[dict[str, Any]]:
    source_by_path = {str(item["path"]): item for item in source_inventory.get("files", [])}
    failures: list[dict[str, Any]] = []
    for item in relocation_manifest.get("resource_relocations", []):
        legacy = str(item["legacy_path"])
        target = root / str(item["target_path"])
        baseline = source_by_path.get(legacy)
        actual_sha = sha256_file(target) if target.is_file() else None
        expected_sha = baseline.get("sha256") if baseline else None
        if actual_sha != expected_sha:
            failures.append(
                {
                    "legacy_path": legacy,
                    "target_path": str(item["target_path"]),
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                }
            )
    return failures


def json_sha_without_self(payload: dict[str, Any], self_field: str) -> str:
    copy = dict(payload)
    copy.pop(self_field, None)
    encoded = json.dumps(copy, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def eager_import_graph(root: Path = ROOT) -> tuple[dict[str, set[str]], list[dict[str, Any]], int]:
    """Build the executable module-initialization graph.

    Imports inside functions/classes and TYPE_CHECKING blocks are intentionally
    excluded because they do not participate in module initialization cycles.
    """
    modules = canonical_modules(root)
    aliases, _ = alias_registry(root)
    graph: dict[str, set[str]] = {name: set() for name in modules}
    missing: list[dict[str, Any]] = []

    def statements(body: list[ast.stmt]) -> Iterable[ast.stmt]:
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(statement, ast.If):
                if isinstance(statement.test, ast.Name) and statement.test.id == "TYPE_CHECKING":
                    continue
                yield from statements(statement.body)
                yield from statements(statement.orelse)
                continue
            if isinstance(statement, ast.Try):
                yield from statements(statement.body)
                for handler in statement.handlers:
                    yield from statements(handler.body)
                yield from statements(statement.orelse)
                yield from statements(statement.finalbody)
                continue
            if isinstance(statement, (ast.With, ast.AsyncWith)):
                yield from statements(statement.body)
                continue
            yield statement

    edge_count = 0
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        shallow = ast.Module(body=list(statements(tree.body)), type_ignores=[])
        imports, unresolved = imported_internal_modules(
            root, path, shallow, module, modules, aliases
        )
        graph[module].update(imports)
        missing.extend(unresolved)
        edge_count += len(imports)
    return graph, missing, edge_count
