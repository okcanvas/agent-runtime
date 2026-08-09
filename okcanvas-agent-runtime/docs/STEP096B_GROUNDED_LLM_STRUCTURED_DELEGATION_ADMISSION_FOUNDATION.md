# STEP096B — Grounded LLM Structured Delegation Admission Foundation

Current Workspace: WORKSPACE_STEP008R4R12_RUNTIME_STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Workspace Version: 0.8.4-r12
Current Runtime: STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Runtime Version: 2.80.0

State: LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN

## Purpose

STEP096B lets the unified Session Root LLM interpret the current utterance and request at most one
of the two existing read specialists through a strict structured schema. The model does not gain
execution authority.

```text
STEP096A turn-local grounded hints
  -> Root LLM natural-language interpretation
  -> structured read-child request (0 or 1)
  -> Runtime admission
     -> parent non-read side-effect fence
     -> capability/readiness/delegated identity
     -> SessionFocus stable-ID injection only from Runtime
     -> exact MCP Tool choice from Product mapping
  -> selected child MCP lazy connect
  -> one stateless child
  -> existing MCP/SOT evidence + normalizer
```

## Boundaries

- Root still owns exactly two read-only Agent-as-Tool children and zero direct MCP servers.
- Structured delegation is enabled only by the exact Product marker
  `okcanvas-grounded-structured-delegation-v1` in the immutable routing envelope.
- Legacy route-v2 remains the top-level Session/root and hard safety envelope, but its child
  `required_capabilities` is not child-selection authority in grounded structured mode.
- The model can answer directly or request one read child. It cannot request two children in one Turn.
- Specialist request count and admitted child count are both bounded to one.
- A denied child request cannot fall back to the other specialist.
- Model schemas contain no stable entity ID or MCP Tool-name fields.
- `SESSION_FOCUS` is a reference token only; Runtime injects the existing server-owned stable ID.
- Organization GET without Runtime Session focus is denied.
- Groupware NOTICE/MAIL/CALENDAR maps server-side to one exact allowlisted MCP Tool.
- Product-owned DRAFT/WRITE_IRREVERSIBLE/AUTOMATION_DEFINITION boundaries cannot be downgraded to
  read-child execution.
- The selected child MCP is connected only after admission and cleaned after Root execution.
- STEP096A hint context remains turn-local, non-authoritative, and non-persisted by design.

## Deterministic acceptance

- STEP096B static contract: 20/20 PASS.
- focused regression: 63/63 PASS.
- deterministic acceptance: 6/6 PASS.
- launcher registry: 7/7 PASS.
- architecture constitution: 16/16 PASS.
- current architecture after successor identity exclusion: 39/40, with only historical STEP081
  identity intentionally different; current module inventory and RuntimeInfo count are exact.

The local analysis interpreter does not include the `agents` package, so real pinned-SDK execution is
not claimed. Retained pinned SDK 0.19.0 source contract was verified. Windows/OpenAI Live is NOT RUN.
