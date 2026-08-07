from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "src", ROOT / "scripts")


def _text(node: ast.AST, source: str) -> str:
    segment = ast.get_source_segment(source, node)
    return segment or ""


def find_violations(root: Path = ROOT) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for base in (root / "src", root / "scripts"):
        for path in sorted(base.rglob("*.py")):
            if path.name == Path(__file__).name:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                reason: str | None = None
                if isinstance(node, ast.Import):
                    if any(alias.name == "reference" or alias.name.startswith("reference.") for alias in node.names):
                        reason = "imports the local reference namespace"
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "reference" or module.startswith("reference."):
                        reason = "imports from the local reference namespace"
                elif isinstance(node, ast.Call) and "reference/upstream" in source.lower():
                    call_text = _text(node, source).replace("\\", "/").lower()
                    if "reference/upstream" in call_text and any(
                        token in call_text
                        for token in (
                            "sys.path",
                            "import_module",
                            "spec_from_file_location",
                            "module_from_spec",
                            "run_path",
                        )
                    ):
                        reason = "loads executable code from reference/upstream"
                if reason:
                    violations.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "line": getattr(node, "lineno", 0),
                            "reason": reason,
                        }
                    )
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8").lower().replace("\\", "/")
    if "path = \"reference/" in pyproject or "path='reference/" in pyproject:
        violations.append(
            {"path": "pyproject.toml", "line": 0, "reason": "declares a path dependency on reference"}
        )
    return violations


def main() -> int:
    violations = find_violations()
    print(json.dumps({"ok": not violations, "violations": violations}, indent=2, sort_keys=True))
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
