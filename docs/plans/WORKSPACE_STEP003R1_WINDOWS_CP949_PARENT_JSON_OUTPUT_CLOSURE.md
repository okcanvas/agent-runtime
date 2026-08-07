# WORKSPACE_STEP003R1_WINDOWS_CP949_PARENT_JSON_OUTPUT_CLOSURE

Version: `0.3.1`

## Trigger

Real Windows STEP003 execution failed after generating its final payload because redirected parent stdout used CP949 and the aggregate JSON contained U+2714 `✔`.

## Scope

```text
Child process bytes
→ UTF-8-first / CP949-fallback decode                 retained
→ aggregate Workspace evidence                        retained
→ UTF-8 evidence file                                 retained
→ encoding-aware parent JSON stdout                   corrected
```

This corrective STEP does not alter the STEP003 Main Assistant Session, stateless Groupware child, Connector MCP, Node Example, persisted SSE or final Artifact behavior.

## Implementation

1. Centralize console-safe JSON rendering in `scripts/workspace_process.py`.
2. Emit readable Unicode JSON when the active stream supports it.
3. Emit standards-valid ASCII-escaped JSON when CP949 cannot encode the payload.
4. Apply the writer to all retained Workspace acceptance and E2E JSON emitters.
5. Add exact CP949 symbol, arrow, Korean and emoji regression coverage.
6. Preserve the original STEP003 command as a compatibility alias to STEP003R1.
7. Record the real Windows failure in `WORKSPACE-ISSUE-014`.

## Validation target

- Workspace unit suite: all tests pass.
- STEP003 full-process E2E: retained 14/14 pass.
- STEP003R1 integrated acceptance: all checks pass, including `parent_json_stdout_cp949_safe`.
- CP949 redirected local simulation: process exit 0 and last stdout document parses as exact JSON.
- Fresh ZIP acceptance and deterministic repack: pass.

## Promotion rule

The current official Windows baseline remains WORKSPACE STEP002R1 / 0.2.1 until STEP003R1 passes on real Windows. A local CP949 simulation is evidence for the corrected encoding contract, not a substitute for Windows acceptance.
