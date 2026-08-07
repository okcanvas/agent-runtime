# STEP057 — Node CLI Runtime Session Conversation

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Goal

Turn the persistent Node.js/TypeScript CLI shell into a real multi-Turn Agent conversation by binding every
governed preflight to a Runtime-owned installed-SDK SQLite Session. Preserve the Control-API/SSE-only client
boundary and add no Tool, MCP, workspace, Shell, network or Sandbox capability.

## Product flow

1. Start `sh_tui.cmd` once.
2. Select the product-owned `conversational-coding-agent` unless an explicit Agent is configured.
3. Create one Runtime Session automatically.
4. Send repeated prompts with the exact same `session_id`.
5. Use `/session`, `/sessions`, `/new`, `/resume`, `/clear` and `/history` for explicit lifecycle control.
6. Resume an existing Session after a CLI restart with `--session-id` or `/resume`.
7. Keep Evaluation off unless explicitly requested.

## Boundaries

- The Node CLI never opens Session SQLite files.
- Raw SDK Session history is not returned through the Control API.
- `/history` shows only text rendered in the current CLI process.
- A resumed Session restores model continuity without exposing historical raw items.
- `/new` creates an isolated Session and does not clear the old Session.
- `/clear` uses the existing governed Session clear API and then creates a new Session.
- Only text-only, workspace-free Agents with Session mode `disabled` or `sqlite-v1` are CLI compatible.

## Acceptance

- Process 1: remember `KEVIN-57`, then recall it in the same Session.
- Process 2: resume the exact Session and recall it after process restart.
- `/new`: create a second Session and prove the old name is not available.
- Exact Session metadata: first Session 3 Turns/6 items; second Session 1 Turn/2 items.
- Final Product counts: Task/Run/Submission/Invocation/Event/Artifact/Evaluation `4/4/4/4/48/4/1`.

## Windows packaging correction

The initial package omitted `OKCANVAS_DEFAULT_AGENT_ID` from the shared launcher environment allowlist while documenting it in `.env.local.example`. The corrected package adds the exact key, preserves rejection of arbitrary variables, and changes no Session or Runtime authority.
