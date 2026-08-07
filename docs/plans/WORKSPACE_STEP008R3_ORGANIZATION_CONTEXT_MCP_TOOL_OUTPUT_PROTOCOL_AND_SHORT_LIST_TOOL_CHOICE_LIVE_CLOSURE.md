# WORKSPACE STEP008R3 — MCP Tool Output Protocol and Short-list Tool Choice Live Closure

## Goal

Close the actual Windows STEP008R2 Live failures without adding a Skill, Agent, MCP Tool, model retry, Tool retry, or alias fallback.

## Proven causes

1. `openai-agents==0.19.0` returns MCP results as a model-visible text ToolOutput dictionary (`type=text`, `text=<JSON>`) or a list of those dictionaries when structured content is disabled. The STEP008R2 normalizer handled direct JSON but did not unwrap this exact SDK protocol shape.
2. `과장들 목록` carried `preferred_operation=SEARCH`, but the Child only had `tool_choice=required`; the model selected `resolve_organization_context`.
3. The Live diagnostic allowlist omitted the common `invocation_id` event field.

## Correction

- Add an exact protocol adapter for SDK MCP text ToolOutput dictionaries and lists.
- Bind admitted `RESOLVE`/`SEARCH` request hints to named Child function Tool choices. The hint remains operation metadata, never Entity evidence.
- Preserve fail-closed one-Tool evidence normalization and bounded diagnostics.
- Add `invocation_id` and the bounded normalization category to the Live diagnostic allowlist.

## Exclusions

- No helper/alias Agent fallback.
- No prompt-derived Entity result.
- No model or Tool retry.
- No Tool re-execution.
- No Agent topology, Skill, or MCP Tool changes.
