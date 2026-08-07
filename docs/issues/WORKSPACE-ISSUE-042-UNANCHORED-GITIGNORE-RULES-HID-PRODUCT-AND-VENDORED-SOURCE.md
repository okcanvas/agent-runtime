# WORKSPACE-ISSUE-042 — Unanchored .gitignore rules hid Product and vendored source

```text
Discovered in: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Status: FIX_IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER
Product runtime behavior change: NONE
```

## Failure

A full fresh-repository scan of every physically present candidate file found that effective Git ignore rules hid accepted source files:

```text
8 Runtime Product files under okcanvas_agent_runtime/**/artifacts/
2 retained upstream files under reference/upstream/**/.vscode/
```

The causes were basename rules applied recursively:

- Runtime `.gitignore`: `artifacts/` — intended for the Runtime root mutable artifact directory, but it also matched Product Python packages named `artifacts`.
- Workspace `.gitignore`: `.vscode/` — intended for workspace-local editor state, but it also matched retained upstream `.vscode` source/configuration.

## Correction

Use root-anchored local-directory rules:

```gitignore
# Workspace root only
/.vscode/
/.idea/

# Runtime project root only
/artifacts/
```

The existing Runtime retained CLI dist exception remains explicit.

## Recurrence prevention

Do not validate Git hygiene only with hand-picked sentinels. After changing ignore policy, initialize a fresh repository and enumerate **all existing ignored files** with:

```text
git ls-files --others --ignored --exclude-standard
```

Any ignored file that belongs to the canonical package inventory must be classified and corrected before packaging. Generated cache/environment files are allowed; Product source, durable evidence, current governance and retained upstream reference files are not.

## Test status

Static Git-policy/full-tree validation is executed. Unit/deterministic/live acceptance remains deferred by user direction until MinIO is prepared.
