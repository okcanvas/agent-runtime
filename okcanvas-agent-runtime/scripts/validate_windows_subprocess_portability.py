from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BATCH_COMMAND_NAMES = {"npm", "npx", "pnpm", "tsc"}
SUBPROCESS_CALLS = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.check_call",
    "subprocess.check_output",
}
ALLOWED_BATCH_HELPER_PATHS = {"scripts/node_acceptance.py"}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _first_program(node: ast.AST, assignments: dict[str, ast.AST]) -> ast.AST | None:
    value = node
    if isinstance(value, ast.Name):
        value = assignments.get(value.id, value)
    if isinstance(value, (ast.List, ast.Tuple)) and value.elts:
        return value.elts[0]
    return None


def _which_candidates(node: ast.AST | None) -> set[str]:
    candidates: set[str] = set()
    if node is None:
        return candidates
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or _call_name(child.func) != "shutil.which" or not child.args:
            continue
        argument = child.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            candidates.add(argument.value.lower())
    return candidates


def find_violations(root: Path = ROOT) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for base in (root / "scripts", root / "okcanvas_agent_runtime", root / "okcanvas_agent_clients"):
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                violations.append({"path": relative, "line": 0, "reason": f"parse-error:{exc}"})
                continue
            assignments: dict[str, ast.AST] = {}
            batch_which_variables: set[str] = set()
            for item in ast.walk(tree):
                if isinstance(item, ast.Assign):
                    names = [target.id for target in item.targets if isinstance(target, ast.Name)]
                    for name in names:
                        assignments[name] = item.value
                        which_values = _which_candidates(item.value)
                        if any(
                            value.endswith((".cmd", ".bat"))
                            or value.removesuffix(".cmd").removesuffix(".bat") in BATCH_COMMAND_NAMES
                            for value in which_values
                        ):
                            batch_which_variables.add(name)
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    assignments[item.target.id] = item.value
                    which_values = _which_candidates(item.value)
                    if any(
                        value.endswith((".cmd", ".bat"))
                        or value.removesuffix(".cmd").removesuffix(".bat") in BATCH_COMMAND_NAMES
                        for value in which_values
                    ):
                        batch_which_variables.add(item.target.id)

            for item in ast.walk(tree):
                if not isinstance(item, ast.Call) or not item.args:
                    continue
                call = _call_name(item.func)
                if call not in SUBPROCESS_CALLS:
                    continue
                first = _first_program(item.args[0], assignments)
                reason: str | None = None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    program = first.value.lower()
                    base_name = Path(program).name.lower()
                    normalized = base_name.removesuffix(".cmd").removesuffix(".bat")
                    if normalized in BATCH_COMMAND_NAMES:
                        reason = f"direct-batch-command:{first.value}"
                elif isinstance(first, ast.Name) and first.id in batch_which_variables:
                    reason = f"batch-which-result-passed-directly:{first.id}"
                if reason:
                    violations.append({"path": relative, "line": item.lineno, "call": call, "reason": reason})
    return violations


def validate(root: Path = ROOT) -> dict[str, Any]:
    violations = find_violations(root)
    node_source = (root / "scripts/node_acceptance.py").read_text(encoding="utf-8")
    step_source = (root / "scripts/run_step081_acceptance.py").read_text(encoding="utf-8")
    non_python_source = (root / "scripts/validate_step081_non_python.py").read_text(encoding="utf-8")
    manifest_source = (root / "scripts/generate_node_cli_release_manifest.py").read_text(encoding="utf-8")
    checks = {
        "unsafe_direct_batch_invocations_absent": not violations,
        "portable_resolver_present": "def resolve_subprocess_command(" in node_source,
        "windows_batch_uses_cmd_call": 'return [command_processor, "/d", "/c", "call", resolved, *arguments]' in node_source,
        "subprocess_oserror_is_bounded": "except (OSError, RuntimeError) as exc:" in node_source,
        "step081_acceptance_uses_npm_pack_helper": "npm_pack_ok, npm_pack_output = run_npm_pack(node_root)" in step_source,
        "non_python_validator_uses_npm_pack_helper": "npm_pack_ok, npm_pack_output = run_npm_pack(node_root)" in non_python_source,
        "typescript_manifest_uses_portable_runner": "ok, output = run_command([command, \"--version\"], CLI)" in manifest_source
        and "subprocess.run" not in manifest_source,
    }
    return {
        "schema_version": "okcanvas-windows-subprocess-portability-validation-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "violations": violations,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
