# STEP056B — Node.js/TypeScript Persistent Agent CLI Foundation

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Problem corrected

STEP056 proved the loopback Control API, governed preflight/confirmation, persisted SSE, Artifact and
Evaluation path, but its Python `input()/print()` program was a single-run smoke. It exited after one
prompt, exposed internal identifiers and exact confirmation text, required an Evaluation case in the
normal path, and could not grow naturally into an installable terminal Agent client.

The user requirement is a Node.js/TypeScript CLI that starts once, accepts repeated prompts until the
user exits, and can later be packaged like Codex CLI. npm registry publication and installer work are
not part of this STEP.

## Scope

- separate `clients/okcanvas-agent-cli` Node.js/TypeScript package;
- package `bin` contract `okcanvas-agent -> dist/cli.js`;
- no runtime npm dependencies;
- Node.js 22 or newer;
- one process handles repeated requests and returns to the prompt;
- one-line prompt by default and `/paste` for multiline input;
- `/help`, `/agents`, `/use`, `/capabilities`, `/model`, `/details`, `/events`, `/json`, `/quit`;
- server default model is used without asking on every request;
- exact server confirmation challenge is never copied by the user or printed by the CLI;
- a simple `Run with <agent>? [Y/n]` decision preserves governed confirmation authority;
- general mode does not create a recorded Evaluation unless explicitly requested;
- normal output renders the structured Artifact as readable text;
- internal Run/Event/JSON data is hidden until the user asks for it;
- loopback Control API and persisted SSE are the only Runtime integration surfaces;
- one canonical environment template: `.env.local.example`;
- `sh_init_local_env.cmd` creates `.env.local` with distinct authority keys and a valid payload key.

## Deliberate limits

- this is still a tool-free, Session-disabled, workspace-free Agent client;
- repeated prompts share one CLI process but not server conversation memory;
- no Tool, MCP, Handoff, Agent-as-Tool, Guardrail, Approval, file, Shell, network, or Sandbox UX;
- no npm registry publication, global installation, auto-update, or single executable packaging;
- no React/Ink dependency in this foundation. The terminal loop uses Node standard APIs so the first
  installable package has zero runtime dependencies. Richer screen layout can be added later without
  changing the HTTP/SSE client boundary.

## Canonical use

```bat
sh_setup.cmd
sh_init_local_env.cmd
rem Set OPENAI_API_KEY and OKCANVAS_AGENT_MODEL in .env.local
sh_run_api.cmd
```

In a second terminal:

```bat
sh_tui.cmd
```

The CLI remains active until `/quit` or Ctrl+C.

## Deterministic acceptance

`sh_run_step056b_acceptance.cmd` starts a real loopback uvicorn Control API and launches the compiled
Node CLI once with a scripted input stream containing three requests, `/details`, `/events`, `/json`,
and `/quit`.

Required proof:

- one Node process executes exactly three governed Runs;
- prompt returns after every response;
- no repeated model question;
- exact confirmation challenges are absent from the transcript;
- general mode creates no Evaluation;
- detail/Event/JSON output appears only after the matching command;
- final Product counts are Tasks/Runs/Submissions/Invocations/Events/Artifacts/Evaluations
  `3/3/3/3/30/3/0`;
- all successful payloads are deleted;
- credentials and raw requests are absent from Product/Evaluation DB;
- Reference trees remain unchanged;
- cleanup completes in one attempt.
