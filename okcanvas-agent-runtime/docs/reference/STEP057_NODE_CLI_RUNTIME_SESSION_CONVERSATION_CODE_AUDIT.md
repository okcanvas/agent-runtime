# STEP057 Code Audit — Node CLI Runtime Session Conversation

## Audited sources

- `clients/okcanvas-agent-cli/src/app.ts`
- `clients/okcanvas-agent-cli/src/api-client.ts`
- `clients/okcanvas-agent-cli/src/render.ts`
- `src/okcanvas_agent_runtime/control_api/app.py`
- `src/okcanvas_agent_runtime/control_api/contracts.py`
- `src/okcanvas_agent_runtime/sessions/service.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `specs/runtime/sqlite-session-policy.json`
- immutable `reference/upstream/openai-agents-python-0.19.0`

## Findings

1. Runtime Session create/list/get/clear APIs already existed and were separately authorized.
2. Governed preflight already accepted `session_id` and validated exact Agent/Runtime binding.
3. The generic gateway already passed the installed-SDK `SQLiteSession` to `Runner.run_streamed`.
4. Successful Turns persisted two SDK history items and failed Turns rolled back to the pre-Turn boundary.
5. The STEP056B/C Node CLI never called `/v1/sessions` and never included `session_id` in preflight.
6. Therefore the missing product behavior was a client wiring and lifecycle problem, not a new Runtime engine.

## Implementation decision

- Add `conversational-coding-agent`, a text-only `sqlite-v1` Agent.
- Add Session API methods only to the independent Node client.
- Use a product-owned canonical default rather than catalog-order selection.
- Auto-create a Session for a Session Agent; support exact resume after restart.
- Never expose raw SDK Session history through a new endpoint.
- Keep disabled Agents selectable for intentionally independent requests.

## Non-goals

- Session compaction or encryption.
- remote/distributed Session backend.
- Tool, MCP, Handoff, Agent-as-Tool, Guardrail or Sandbox UI.
- automatic last-Session persistence on the client filesystem.

## Post-package Windows finding

Manual `sh_run_api` proved that `scripts/windows_entrypoint.py::_ALLOWED_KEYS` did not include the documented `OKCANVAS_DEFAULT_AGENT_ID`. The corrected source adds only the two documented missing keys: OKCANVAS_DEFAULT_AGENT_ID and OKCANVAS_SESSION_ROOT. Regression tests prove canonical parsing succeeds and unsupported names remain rejected.
