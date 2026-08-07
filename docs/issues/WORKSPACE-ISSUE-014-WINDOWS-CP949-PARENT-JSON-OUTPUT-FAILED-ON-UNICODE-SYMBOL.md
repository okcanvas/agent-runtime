# WORKSPACE-ISSUE-014 — Windows CP949 parent JSON output failed on Unicode symbol

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## User evidence

On 2026-08-05 the real Windows command below completed the STEP003 work far enough to build and persist the final payload, then failed while printing that payload through redirected CP949 stdout.

```cmd
sh_run_workspace_step003_acceptance > log.txt
```

```text
Traceback (most recent call last):
  File "D:\NODE_AGENTS\okcanvas-agent-platform\scripts\run_workspace_step003_acceptance.py", line 251, in <module>
    raise SystemExit(main())
  File "D:\NODE_AGENTS\okcanvas-agent-platform\scripts\run_workspace_step003_acceptance.py", line 247, in main
    return run(args.output.resolve())
  File "D:\NODE_AGENTS\okcanvas-agent-platform\scripts\run_workspace_step003_acceptance.py", line 239, in run
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
UnicodeEncodeError: 'cp949' codec can't encode character '\u2714' in position 2328: illegal multibyte sequence
```

## Root cause

STEP001R2 closed subprocess **input decoding** by capturing bytes and decoding UTF-8 before CP949. STEP003 reused that boundary, but its parent process still serialized the final aggregate JSON with `ensure_ascii=False` and wrote it directly to `sys.stdout`.

When Windows `cmd.exe` redirected stdout to `log.txt`, Python selected CP949. A retained child stdout string contained U+2714 `✔`, which CP949 cannot encode. The UTF-8 detailed evidence file had already been written; only the final parent-console emission failed. Therefore the previous `subprocess_output_encoding_safe` check was incomplete: it proved child-output decoding, not parent-output encoding.

## Correction

- Add shared `render_json_for_console` and `write_json_stdout` functions in `scripts/workspace_process.py`.
- Preserve readable `ensure_ascii=False` JSON when the active stdout encoding can represent the complete payload.
- Fall back to `ensure_ascii=True` only when the selected console encoding cannot represent the payload.
- Require the fallback to remain valid JSON and round-trip exactly, including Korean, U+2714, U+2192 and supplementary-plane emoji.
- Replace direct Unicode JSON `print()` calls in all retained Workspace acceptance runners and both Workspace E2E harnesses.
- Add `WORKSPACE_STEP003R1_WINDOWS_CP949_PARENT_JSON_OUTPUT_CLOSURE / 0.3.1` and a dedicated launcher.
- Make the retained `sh_run_workspace_step003_acceptance.cmd` compatibility command delegate to STEP003R1.

The UTF-8 evidence files remain unchanged in representation. Only stdout rendering is encoding-aware.

## Product boundary

No Runtime, Product CLI, Connector, Example product implementation, API contract, routing policy, Session model, MCP contract or E2E product behavior is changed by this correction.

## Recurrence gates

- A CP949 render test proves fallback activation and exact JSON round-trip.
- A CP949 memory-stream writer test proves no `UnicodeEncodeError` is raised.
- A source guard requires every retained Workspace JSON emitter to use `write_json_stdout` and forbids the failed direct `print(json.dumps(... ensure_ascii=False` pattern.
- The STEP003 compatibility launcher must delegate to STEP003R1.
- The integrated STEP003R1 acceptance includes `parent_json_stdout_cp949_safe`.
- Final verification runs the complete acceptance with `PYTHONIOENCODING=cp949` and redirected stdout.

## Acceptance limit

Local CP949 simulation can prove the Python encoding boundary deterministically. Official Windows promotion still requires the user to run the corrective launcher on real Windows and retain the resulting evidence.
