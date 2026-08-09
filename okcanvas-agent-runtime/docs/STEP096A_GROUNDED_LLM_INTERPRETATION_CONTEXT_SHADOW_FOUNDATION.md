# STEP096A — Grounded LLM Interpretation Context Shadow Foundation

Current Workspace: WORKSPACE_STEP008R4R11_RUNTIME_STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION
Workspace Version: 0.8.4-r11
Current Runtime: STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION
Runtime Version: 2.79.0

State: LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN

## Purpose

STEP096A does not add a deterministic natural-language parser. It preserves the design rule that the LLM interprets user language while Product code and MCP provide bounded, verifiable context.

```text
raw user utterance
  -> Runtime Context Enrichment Plane
     -> organization-context-interpretation-hints MCP profile
        -> search_organization_context(raw utterance)
        -> search_organization_terms(raw utterance)
     -> minimum hint projection
  -> turn-local non-authoritative model context
  -> existing organization-assistant-session-agent
  -> existing v2 authoritative child selection
```

## Boundaries retained

- `okcanvas-assistant-route-v2` remains the top-level authoritative route contract.
- `okcanvas-assistant-route-v3` exists only as a nested non-authoritative shadow description for eligible bound Session turns.
- The Root still owns exactly two Agent-as-Tool children and no direct MCP server.
- Hint retrieval uses the same external Organization Context Connector and delegated identity boundary as execution, but a separate read-only Runtime profile exposes only `search_organization_context` and `search_organization_terms`.
- The raw utterance is forwarded unchanged. No new helper/alias/suffix/fallback parser was added.
- Hint projection omits canonical entity IDs, raw records, relations, tenant/principal/delegation values, contact details and provenance internals.
- Hint strings are untrusted data, never instructions or final execution evidence.
- Hints are injected with the SDK `call_model_input_filter` as turn-local user-role context and are not intentionally persisted into SDK Session history.
- Existing execution MCP output normalization and `SessionContextFocus` remain the only authority for stable entity continuity.

## Deterministic acceptance

`sh_run_step096a_acceptance.cmd` currently proves:

- STEP096A static contract: 19/19 PASS.
- Python compileall: PASS.
- focused Runtime regression: 48/48 PASS.
- STEP096A acceptance: 6/6 PASS.

Windows/OpenAI Live for STEP096A was not run. The broader historical routing suite is not claimed green; stale historical identity/root fixtures are separately recorded.

## Next implementation wave

STEP096B may introduce structured read-only child delegation plus a Runtime admission fence. The model must still never invent stable entity IDs or gain final execution authority. Child MCP connection should become lazy only after admission.
