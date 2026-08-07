# OR-ISSUE-037 — Package `__main__` executed the CLI during canonical import

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The first integrated STEP081 Acceptance terminated with argparse exit code 2 while importing all canonical modules:

```text
okcanvas-agent-runtime: error: the following arguments are required: command
```

No Acceptance JSON was produced because `SystemExit` is not an `Exception` and escaped the import scanner.

## Code-confirmed root cause

`okcanvas_agent_runtime/__main__.py` unconditionally executed `raise SystemExit(main())` at module import time. The file worked only when treated exclusively as `python -m okcanvas_agent_runtime`; it violated normal Python module import safety.

## Impact

Canonical import validation and any introspection/import tooling could execute the CLI unexpectedly and terminate the host process.

## Fix

CLI execution is now protected by `if __name__ == "__main__"`. Importing `okcanvas_agent_runtime.__main__` only defines the entrypoint reference; module execution still calls the CLI.

## Recurrence-prevention gate

`tests/test_step081_direct_script_bootstrap.py` imports the package `__main__` module and asserts no `SystemExit`. Integrated STEP081 Acceptance imports every canonical module.
