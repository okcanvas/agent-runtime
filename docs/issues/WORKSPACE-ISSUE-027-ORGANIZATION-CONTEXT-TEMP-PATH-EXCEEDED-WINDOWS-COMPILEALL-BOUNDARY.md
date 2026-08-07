# WORKSPACE-ISSUE-027 — Organization Context temporary path exceeded the Windows compileall boundary

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Observed evidence

The actual Windows STEP005 Connector acceptance passed pytest `8/8` but failed standard `compileall`. The failing target combined:

```text
Workspace PYTHONPYCACHEPREFIX
+ full absolute temporary Workspace path
+ okcanvas-connectors/organization-context-mcp-server
+ module path
+ generated pyc suffix
```

The resulting path was long enough that Python raised `FileNotFoundError` while writing the `.pyc` file.

## Incorrect response avoided

A bespoke source compiler would make Organization Context diverge further from the already accepted Groupware Connector pattern. Product source compilation semantics were not defective.

## Correction

STEP005R1 keeps the same standard Connector command:

```text
python -m compileall -q organization_context_mcp_server tests scripts
```

The Workspace executes copied projects under short temp names:

```text
<temp>/c
<temp>/e
```

This fixes the Windows execution path without introducing a custom compiler or changing product source.

## Recurrence gate

- Unit test forbids `scripts/compile_source_tree.py`.
- Unit test requires the standard Groupware `compileall` shape.
- STEP005R1 acceptance asserts short `c/` and `e/` execution copies.
