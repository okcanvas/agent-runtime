# STEP062A Windows Node Acceptance Portability Fix — Code Audit

## Audited baseline

Source: `okcanvas-agent-runtime-step062-bounded-multi-agent-orchestration-foundation-v1.zip`

Reported Windows result: STEP062 `27/29`; failed checks were exactly
`node_typescript_build_pass` and `node_tests_pass`.

## Confirmed call path before correction

`sh_run_step062_acceptance.cmd`
→ `.venv\\Scripts\\python.exe scripts\\run_step062_acceptance.py`
→ `shutil.which("npm.cmd") or shutil.which("npm")`
→ `_run([npm, "run", "build"], cli_root)`
→ `_run([npm, "test"], cli_root)`

`package.json` defined:

```json
"test": "node --test test/*.test.mjs"
```

The reported test tail proves Node received the literal Windows path ending in
`test\\*.test.mjs`. Therefore the shell did not expand the wildcard.

The build tail is the forced-UTF-8 rendering `��ġ ������ �ƴմϴ�.`. Encoding the Korean phrase
`배치 파일이 아닙니다.` as CP949 and decoding it as UTF-8 with replacement produces that exact
rendering. This is consistent with direct execution of the resolved `npm.cmd` batch path at the
Python subprocess boundary.

## Corrected call path

`run_step062_acceptance.py` now delegates to `scripts/node_acceptance.py`.

Build:

```text
resolve npm.cmd
→ on Windows construct cmd.exe /d /c call "<npm.cmd>" run build
→ capture bytes
→ decode UTF-8, platform locale, then Windows fallbacks
```

Tests:

```text
resolve node.exe
→ enumerate cli_root/test/*.test.mjs in Python
→ sort actual files
→ node --test test/config.test.mjs test/render.test.mjs
```

No shell wildcard is present in the executed test command.

## Scope review

Changed executable behavior is limited to acceptance-side Node command execution and the CLI's
cross-platform `npm test` script. No files under the following product paths were changed from the
STEP062 source:

```text
src/okcanvas_agent_runtime/orchestration/
src/okcanvas_agent_runtime/execution/
src/okcanvas_agent_runtime/invocations/
specs/runtime/
specs/agents/bounded-orchestration-*/
clients/okcanvas-agent-cli/src/
```

`baseline.py`, `model.py`, tests and current documents changed only to identify and prove the
STEP062A correction baseline.

## Decision

The first Windows result does not invalidate the STEP062 orchestration implementation. It proves
that its orchestration-specific checks passed, while exposing two acceptance harness portability
defects. STEP062A corrects only those defects and requires a fresh Windows rerun before STEP063 can
be selected.
