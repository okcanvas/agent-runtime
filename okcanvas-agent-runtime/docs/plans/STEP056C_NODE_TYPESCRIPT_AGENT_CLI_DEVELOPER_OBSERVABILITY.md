# STEP056C — Node.js/TypeScript Agent CLI Developer Observability

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Trigger

Manual Windows use confirmed that STEP056B finally delivered the required persistent Node.js/TypeScript
client, but development still needs the governed evidence previously visible in the Python smoke:
preflight identity, exact server challenge, persisted SSE sequence, terminal Run state, verified Artifact
identity/raw JSON and optional Evaluation result.

The correction must preserve the answer-first product mode. Development evidence is opt-in and must not
force every user through internal IDs or exact-challenge copying.

## Scope

- `--debug` starts the CLI in developer mode;
- `/debug on`, `/debug off` toggle diagnostics without restarting the process;
- `/status` shows Runtime URL/version, active Agent/model, Session state, Evaluation default and last Run;
- debug preflight displays Submission, Agent/version, Runtime binding, execution mode, approval state,
  model and the exact server challenge;
- the user still confirms with local `Y/n`; the CLI sends the exact challenge internally;
- persisted SSE Events are displayed as they arrive;
- terminal Run, Invocation count, verified Artifact ID/SHA/raw JSON and Evaluation state are displayed;
- default Evaluation remains off and debug explicitly shows `NOT RUN`;
- `/evaluate <case-id>` evaluates the last Run through the existing Control API;
- `/details`, `/events`, `/json` remain available after the Run;
- with multiple compatible Agents and no explicit default, the CLI asks for a number or exact Agent ID;
- `OKCANVAS_DEFAULT_AGENT_ID` or `--agent-id` can provide an explicit startup selection;
- no Python Runtime imports, SQLite access, Tool execution or direct Artifact access are introduced.

## Deliberate limits

- tool-free, Session-disabled, workspace-free Agents only;
- persistent process still does not provide server conversation memory;
- no Tool, MCP, Handoff, Agent-as-Tool, Guardrail or Approval-inbox UX;
- no Sandbox, file, Shell or external network capability;
- no npm registry publication or installer work;
- STEP057 Runtime Session work remains blocked until STEP056C Windows acceptance is reported.

## Use

Normal mode:

```bat
sh_tui.cmd
```

Developer mode from startup:

```bat
sh_tui.cmd --debug
```

Or toggle inside the persistent process:

```text
/debug on
/status
/evaluate tui-client-foundation-v1
/debug off
```

## Deterministic acceptance

`sh_run_step056c_acceptance.cmd` starts a real loopback Control API and one compiled Node process. The
script performs one debug request and one normal request, toggles debug in-process, uses `/details`,
`/events`, `/json`, explicitly evaluates the last Run and exits.

Required proof:

- all 25 acceptance checks pass;
- debug is off by default and can be toggled without restart;
- only the debug request exposes preflight and exact challenge;
- no challenge is copied back by the user;
- persisted SSE sequence is visible in debug mode;
- Run/Artifact/raw JSON/`NOT RUN` Evaluation are visible in debug mode;
- normal mode remains friendly and answer-first;
- explicit post-Run Evaluation passes;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation counts are `2/2/2/2/20/2/1`;
- successful payload files are `0`;
- credentials and raw requests are not persisted;
- immutable References remain unchanged;
- cleanup completes once.
