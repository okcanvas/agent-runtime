# STEP096A Plan — Grounded LLM Interpretation Context Shadow Foundation

Current Workspace: WORKSPACE_STEP008R4R11_RUNTIME_STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION
Workspace Version: 0.8.4-r11
Current Runtime: STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION
Runtime Version: 2.79.0

## Implemented scope

1. Preserve current v2 authoritative routing.
2. Build grounded interpretation context from the raw utterance without Runtime NLP parsing.
3. Use the existing Organization Context MCP server through a separate Runtime-only hint profile.
4. Project only bounded entity/term hints for the Root LLM.
5. Inject hints turn-locally through `call_model_input_filter`, not system instructions and not model-visible MCP tools.
6. Publish a nested route-v3 shadow descriptor for eligible bound Session turns.
7. Keep all execution, stable-ID, authorization and Session-focus authority unchanged.

## Explicitly not implemented

- LLM-selected child execution.
- structured delegation admission.
- new durable RoutingMemory.
- long-term conversational memory.
- write capability execution.
- direct Root MCP attachment.
- helper/alias/suffix/fallback language parser.
- Windows/OpenAI Live acceptance for STEP096A.

## Follow-on

STEP096B should implement structured read-only delegation and admission in shadow/limited form only after STEP096A remains deterministic. STEP095A durable-memory audit remains a separate backlog item and must not be silently merged into this work.
