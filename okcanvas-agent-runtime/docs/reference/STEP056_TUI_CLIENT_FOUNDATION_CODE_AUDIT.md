# STEP056 TUI Client Foundation — Code and Reference Audit

## Audit rule

No TUI framework, endpoint, or capability was selected from assumptions. The current product API,
existing browser runner, approval operator, Windows launchers, and retained UI/streaming references
were read before implementation.

## Product code inspected

### Existing governed client and authority surfaces

- `src/okcanvas_agent_runtime/control_api/app.py`
  - Agent catalog;
  - governed preflight and confirmation;
  - persisted Event SSE;
  - Run/Invocation/Artifact/Evaluation endpoints.
- `src/okcanvas_agent_runtime/control_api/contracts.py`
  - exact request and response schemas.
- `src/okcanvas_agent_runtime/control_api/auth.py`
  - separated local administrator and Run-submitter authorities.
- `src/okcanvas_agent_runtime/control_api/sse.py`
  - persisted cursor stream and terminal close behavior.
- `src/okcanvas_agent_runtime/interactive_runner/assets/runner.js`
  - existing browser flow and endpoint order.
- `src/okcanvas_agent_runtime/approval_operator/client.py`
  - loopback-only URL validation and explicit client close pattern.
- `scripts/windows_entrypoint.py`
  - local environment loading without executing `.env.local.cmd`.
- `sh_run_api.cmd`
  - existing Control API launcher.

### Product conclusion

All STEP056 functions already existed as governed HTTP contracts. A TUI-specific execution endpoint,
state store, Agent loader, confirmation calculator, or Artifact reader would duplicate authority and
was rejected.

## Immutable Reference inspected

Reference map:

- `reference/CODE_MAP.md`

Streaming adapter example:

- `reference/upstream/openai-agents-streaming-api/src/api/main.py`
- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`

Customer-service UI event surface:

- `reference/upstream/openai-cs-agents-demo/ui/components/chatkit-panel.tsx`

## Adopted

- separate client surface over an HTTP API;
- progressive Event rendering;
- Agent selection before execution;
- a final result panel after streaming.

## Adapted

The retained examples stream raw SDK-oriented events and allow broad browser concerns. STEP056 instead
uses the existing OKCanvas persisted canonical Event stream, retains loopback-only credentials,
requires governed preflight and exact confirmation, and retrieves only verified Product Artifacts
and recorded Evaluations.

## Deliberately rejected

- direct `Runner.run_streamed()` from the TUI;
- SDK raw response or item streaming as the authoritative record;
- CORS or remote client support;
- implicit Session defaults;
- broad exception-to-success responses;
- raw provider response IDs;
- browser storage of credentials;
- importing code from `/reference`;
- adding Textual, Rich, prompt-toolkit, or another UI dependency before the terminal workflow is
  validated.

## Implemented files

- `src/okcanvas_agent_runtime/tui_client/config.py`
- `src/okcanvas_agent_runtime/tui_client/client.py`
- `src/okcanvas_agent_runtime/tui_client/sse.py`
- `src/okcanvas_agent_runtime/tui_client/app.py`
- `src/okcanvas_agent_runtime/tui_client/__init__.py`
- `specs/evaluations/tui-client-foundation-v1/case.json`
- `scripts/run_step056_acceptance.py`
- `sh_tui.cmd`
- `sh_run_step056_acceptance.cmd`

## Safety result

The new TUI package contains no import of Product persistence, execution gateways, Agent SDK Runner,
Tool/MCP implementations, Session stores, protected payload stores, or Runtime binding code. It
uses existing REST and persisted SSE endpoints only.

## Post-package Windows startup audit

The first manual Windows API start failed in `ProtectedPayloadKey.from_text()` because the local value
failed the exact 32-byte decode contract. The product crypto boundary was correct. The defects were in
onboarding and launcher diagnostics: the CMD example omitted governed variables and the launcher did
not preflight the key before uvicorn. The correction adds an equivalent non-secret validation in
`scripts/windows_entrypoint.py`, keeps `src/okcanvas_agent_runtime/protected_payload/store.py`
unchanged, and adds regression tests proving invalid placeholders never start uvicorn or appear in the
error output.
