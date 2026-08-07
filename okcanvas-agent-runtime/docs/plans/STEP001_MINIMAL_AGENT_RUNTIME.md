# STEP001_MINIMAL_AGENT_RUNTIME

## Status
COMPLETE — source/runtime contract baseline. Live model acceptance remains NOT EXECUTED.

## Objective
Prove one controlled OpenAI Agents SDK integration boundary with a structured result contract and retained execution metadata.

## Implemented
- Exact runtime intent: `openai-agents==0.19.0`.
- One tool-free and handoff-free Coding Agent.
- Strict Pydantic `CodingAgentResult` and canonical run envelope.
- Run/request IDs, timestamps, input SHA-256, trace/response relation, usage, and canonical errors.
- `info`, `doctor`, and explicitly confirmed `run` CLI commands.
- SDK namespace/version readiness that rejects the root `agents/` namespace directory as an SDK installation.
- API key redaction by omission; request text is not copied into evidence.
- Atomic evidence JSON writer.
- SDK boundary test double covering Agent, Runner, RunConfig, structured output, trace metadata, and usage mapping.
- Opt-in live acceptance script gated by `OKCANVAS_STEP001_LIVE_ACCEPTANCE=1`.

## Explicit non-scope
Codex, MCP, tools, shell, workspace reads/writes, handoffs, API/SSE/UI, sessions, approval/resume, and production persistence.

## Validation
See `docs/evidence/STEP001_VALIDATION.txt`.

## Acceptance result
1. Dependency and model configuration explicit: PASS.
2. Missing SDK/key/model fail closed without secret leakage: PASS.
3. Test-double complete local result contract: PASS.
4. Live run opt-in and never automatic: PASS.
5. Live model execution claimed: NO — NOT EXECUTED.
6. Wheel build claimed: NO — offline build dependency unavailable.
