# STEP048 — SQLite Session Native Guardrail Composition V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.28.0`.

## Closed prerequisite

The user-reported Windows `sh_run_step047_acceptance` output exactly matched all 29 STEP047 conditions. STEP047 is now `WINDOWS_LIVE_ACCEPTED`; its Session transitions were `1/4 → 2/8`, native Handoff count was two, final Product counts were `2/2/2/4/32/2/1`, protected payload count was zero, and cleanup completed.

## Problem

STEP043 SQLite Session and STEP044 native Guardrails were independently Windows-live accepted, but product code intentionally rejected their composition in the Agent catalog, Runtime binding, generic execution preflight, Session creation path and OpenAI gateway. The installed SDK demonstrates that a streamed input-Guardrail tripwire can persist the current user item in Session history before raising. Without an explicit product rollback contract, a rejected guarded Turn could pollute later conversational history even though Product `turn_count` did not advance.

## Goal

Permit one exact language-only composition:

- one installed-SDK `sqlite-v1` Session;
- one Agent input Guardrail and one Agent output Guardrail at most;
- no Function Tool or Tool Guardrail;
- no MCP, Handoff, Agent-as-Tool, workspace, Shell, file, network or secret capability;
- successful Turns committed normally;
- input/output tripwire Turns rolled back to the pre-Turn SDK item boundary;
- safe canonical Guardrail and Session evidence only.

## Accepted Agent

```text
session-guardrail-language-agent
├─ session_mode = sqlite-v1
├─ block-input-marker  (INPUT, run_in_parallel=false)
└─ block-output-marker (OUTPUT)
```

The Agent uses `CodingAgentResult`, `workspace_access=none`, no Tools, no children and no MCP.

## Product contracts

1. Runtime execution path is exactly `sqlite-session-native-guardrail-execution-v1`.
2. Runtime binding includes the SQLite Session policy, STEP048 composition policy, both Guardrail definitions and implementation SHAs, Session/Guardrail Runtime SHAs and generic execution-engine SHA.
3. Session creation pins Agent definition SHA and composed Runtime binding SHA.
4. Every governed request binds the exact Product Session ID into request fingerprint, confirmation and protected payload.
5. Product acquires the active-Turn lease before the SDK Runner and captures the pre-Turn `item_count` rollback boundary.
6. A successful Turn creates one Artifact, releases the lease with `succeeded=true`, increments `turn_count` once and synchronizes final item count.
7. Any input/output tripwire rolls SDK history back to the captured pre-Turn item count before releasing the lease with no Turn increment.
8. Rejected Turns create no Artifact or Evaluation and retain protected payload under the existing failure-investigation policy.
9. Each rejected Run records one exact Guardrail error code and one safe `guardrail.tripped` Event; no guarded content or SDK output info is persisted.
10. Confirmation replay schedules no second execution and adds no Session items, Turn, Artifact or Evaluation.
11. Raw Session history, requests, markers, prompts, instructions and API keys remain outside Product Events and Product/Evaluation databases.

## Explicit non-scope

- Tool-input or Tool-output Guardrails in a Session Agent;
- Session mixed with Function Tool, approval, Handoff, Agent-as-Tool or MCP;
- retry, operator override or fallback after a tripwire;
- committing a rejected Guardrail Turn as conversational history;
- multiple Guardrails of one kind, dynamic Guardrail code or model-judged policy;
- physical workspace, filesystem, Shell, network, hosted Tool or Sandbox capability;
- process-loss automatic resume, distributed lease, remote Session backend, encryption, compaction or export;
- cross-database atomic transaction claims.

## Deterministic acceptance

Run:

```text
python scripts/run_step048_acceptance.py
```

The acceptance executes four governed requests against one Product Session:

1. clean Turn stores `ORBIT-48` and commits `1/2`;
2. input tripwire persists one partial user item, then Product rollback restores `1/2`;
3. output tripwire persists a worst-case user+assistant pair, then Product rollback restores `1/2`;
4. clean continuity Turn sees only the first successful history and commits `2/4`.

Required result:

- 32/32 checks true;
- `Runner.run_streamed=4`, `Runner.run=0`;
- model calls `3`;
- Guardrail runs INPUT/OUTPUT `4/3`;
- SQLiteSession instances/closes `8/8`;
- case events `12/8/11/12`;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation `4/4/4/4/43/2/1`;
- two failed protected payloads retained;
- exact history item count `4`, containing only two successful Turns;
- Reference unchanged and cleanup `COMPLETED`.

## Windows closure gate

From a fresh extracted ZIP:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step048_acceptance.cmd
```

Do not select or implement STEP049 until this complete Windows result is reported and recorded.
