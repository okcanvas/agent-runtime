# OR-ISSUE-023 — Project-root parent-depth drift after root-package relocation

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

After the package root moved from `src/okcanvas_agent_runtime` to the repository root, the Codex/OpenAI gateway contract tests failed while resolving Product-owned policy files. Moved modules still calculated the repository root with expressions such as:

```python
Path(__file__).resolve().parents[3]
```

The same parent index now resolved to the `okcanvas_agent_runtime` package directory rather than the project root, so policy resources were reported missing even though they existed in the repository.

## Code-confirmed root cause

Repository-root identity was encoded independently in moved modules as a fixed number of parent traversals. Physical relocation changed file depth without changing those expressions. Python import and AST validation could not detect the semantic path error because every path expression remained syntactically valid.

## Impact

OpenAI/Codex gateway construction and workspace inspection could fail only at runtime. Fresh-ZIP validation on the new flat package layout could therefore fail after static architecture checks had passed.

## Fix

- added `okcanvas_agent_runtime/core/paths.py` as the single source of truth for `PROJECT_ROOT`, `PACKAGE_ROOT`, and all three root package paths;
- changed moved gateway, workspace inspection, Bootstrap asset, and Sandbox consumers to import the canonical path constants;
- added `require_project_root()` to verify package owners and `pyproject.toml`;
- corrected historical project-inspection assertions to distinguish fixture-relative paths from the canonical STEP081 repository path.

## Detailed evidence

The focused Codex gateway regression passed `3/3` after the path SOT fix. The project-readonly catalog, query-directed inspection, and STEP060 compatibility regressions subsequently passed `14/14`.

## Recurrence-prevention gate

`project_root_path_sot_exact` verifies every canonical root path, executes `require_project_root()`, and rejects any new `Path(__file__).resolve().parents[n]` root calculation inside Runtime modules outside the single canonical path owner.
