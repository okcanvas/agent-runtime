# STEP008R3 Implementation Failure Log

## F001 — STEP008R2 Live normalizer rejected all actual SDK Tool outputs

**Evidence:** Windows Live 19/29. All four MCP calls completed; all four normalizations failed with ValueError.

**Cause:** tests represented `ToolCallOutputItem.output` as a direct JSON string, while the pinned SDK returns a text ToolOutput dictionary/list when structured content is disabled.

**Prevention:** exact SDK-shaped fixtures and bundled upstream source assertions.

## F002 — Explicit list request selected resolve

**Evidence:** `과장들 목록` carried `preferred_operation=SEARCH`, but the Child invoked resolve.

**Cause:** `tool_choice=required` did not constrain which Tool must be selected.

**Prevention:** admitted RESOLVE/SEARCH operations map to named Child Tool choices; unknown operations fall back to required without guessing.

## F003 — Live diagnostic allowlist rejected common event metadata

**Cause:** `invocation_id` was present on lifecycle events but absent from the harness allowlist.

**Prevention:** allow bounded common metadata and the safe normalization category only; raw payloads remain prohibited.

## F004 — Local workspace acceptance exceeded a single tool-call window

**Handling:** the unmodified acceptance was executed as a detached local process and its final JSON/stderr were collected in the same response. It passed 25/25. This is an execution-environment limit, not a product pass claim by timeout.
