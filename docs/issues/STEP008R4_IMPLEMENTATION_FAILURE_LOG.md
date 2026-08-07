# STEP008R4 implementation failure log

## R4-F001 — Natural-language token assertion rejected a valid empty result

- Evidence: STEP008R3 Live Run was `SUCCEEDED`, status `ANSWERED`, Tool `search_organization_context`, candidate count `0`, but the answer used `검색되지 않았습니다`.
- Prevention: structured status/Tool/count/citation fields are now the SOT.

## R4-F002 — Current Session item count was mistaken for commit history

- Evidence: four `session.turn.completed` events reached turn counts 1–4; compaction then reduced 16 items to 5.
- Prevention: continuity uses the completed-turn event sequence and Session ID, not post-compaction item count parity or minimum.

## R4-F003 — Product modification was not justified

- Evidence: all four Product Runs, Agent-as-Tool calls, MCP calls and normalizations completed.
- Prevention: STEP008R4 changes only Workspace acceptance code, tests and documentation. Runtime STEP090R1 remains byte-preserved.

## R4-F004 — Windows deterministic evidence was CP949 JSON

- Evidence: direct UTF-8 decoding failed at a Korean byte while the same file parsed exactly as CP949 JSON; the Live evidence was UTF-8 JSON.
- Prevention: final approval packaging decodes each evidence file using its proven encoding and stores both retained evidence files as normalized UTF-8 JSON. Raw secrets are scanned before retention.

## R4-F005 — Unsupported Workspace `--quiet` option was passed during final packaging validation

- Evidence: `run_workspace_step008_acceptance.py` rejected `--quiet` before any Product or acceptance work started.
- Prevention: Workspace final validation uses only the script's declared arguments. Quiet mode remains a Runtime gate option, not a Workspace option.

## R4-F006 — Direct combined Runtime execution exceeded the container command window

- Evidence: Workspace tests completed successfully and the combined runner reached `runtime STEP090 acceptance start`, but the controlling command window ended before final evidence was emitted.
- Prevention: use the retained `run_workspace_step008_runtime_gate.py` to execute and hash the fresh Runtime 25/25 gate, then supply that immutable process/evidence pair to the Workspace 25/25 gate. This changes no validation predicate and preserves Runtime source-unchanged proof.
