# OR-ISSUE-022 — Historical validators were coupled to removed physical source paths

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

Historical tests and acceptance scripts attempted to read paths such as:

```text
src/okcanvas_agent_runtime/control_api/app.py
src/okcanvas_agent_runtime/execution/openai_gateway.py
clients/okcanvas-agent-cli/
```

The files were intentionally removed or split, so source-contract tests failed even when the public behavior and compatibility imports were correct. The compatibility alias metadata also became stale after additional aliases were added.

## Code-confirmed root cause

Earlier validation encoded implementation locations as the contract. A split logical component had no single replacement file, and no generated resolver translated the historical logical component into its current canonical source set.

## Impact

Recreating the removed tree would defeat the architecture change, while ad-hoc test edits could stop validating the original behavior. Fresh ZIP execution could also depend accidentally on an absent `src` path.

## Fix

- added `LegacySourceContract` and logical source/asset mappings;
- resolves alias chains and deterministically concatenates split canonical components;
- changed launchers and acceptance scripts to use repository root as `PACKAGE_ROOT`;
- changed the Node CLI path to `clients/cli`;
- regenerated alias metadata from the actual 301 mappings;
- preserved historical evidence text without treating it as an executable path.

## Recurrence-prevention gate

`executable_legacy_path_coupling_absent`, `compatibility_alias_metadata_current`, `compatibility_alias_targets_complete`, and the 262-file legacy source resolver regression prevent a removed physical path from returning as an execution dependency.
