# WORKSPACE-ISSUE-009 — unittest discovery did not fix the workspace top-level

## Observed Windows failure

`python -m unittest discover -s tests -v` imported the test module as a top-level module and failed to
resolve `scripts.package_workspace` on the user's Runtime virtual environment.

## Root cause

The Workspace `scripts` directory was not an explicit Python package and discovery did not declare the
Workspace root as its top-level directory. Local execution succeeded only because of incidental `sys.path`
ordering.

## Correction

- add `scripts/__init__.py`;
- tests insert and verify the exact Workspace root;
- run discovery as `python -m unittest discover -s tests -t . -v`;
- verify imported management modules originate under the Workspace root.

## Recurrence gate

`test_workspace_scripts_import_from_workspace_root` and the acceptance check
`workspace_test_import_root_exact` must pass.
