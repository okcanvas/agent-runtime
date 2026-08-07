# STEP067 — Hosted Web Search Source Policy and Evidence Foundation

## Identity

- Version: `2.47.0`
- STEP: `STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION`
- Predecessor: STEP066 Windows-live accepted

## Problem proven by code audit

The installed SDK exposes Web Search and File Search as hosted Tools, but the Product has no hosted
Tool declaration, source-evidence result, or Artifact path. Web Search can be configured from an
immutable execution policy. File Search cannot: it requires pre-existing Vector Store IDs and a
resource lifecycle that the current Product does not own.

## Implemented slice

1. Add `hosted_tools` to immutable Agent definitions and permit only `web-search-v1` in an isolated
   Agent.
2. Add a strict hosted Web Search policy catalog and Product-owned URL/evidence normalizer.
3. Bind the policy, Product implementation and pinned SDK source SHA values into Runtime binding.
4. Construct installed-SDK `WebSearchTool` and exact `ModelSettings` with source include,
   `store=false`, required Tool choice and no parallel Tool calls.
5. Inspect SDK `result.new_items` after execution and fail closed on missing/multiple/incomplete calls,
   File Search, out-of-policy URLs, missing sources or missing citations.
6. Persist strict model output and source evidence as separate Artifacts without raw search material.
7. Add deterministic fake-SDK tests, acceptance, Windows launcher and ZIP-only documentation.

## Explicit non-goals

- File Search or Vector Store lifecycle;
- user-selected domains or location;
- Session, MCP, local Tool, Handoff, Agent-as-Tool or orchestration composition;
- raw query/result/snippet persistence;
- real provider/network execution in deterministic acceptance.

## Closure

`sh_run_step067_acceptance.cmd` must pass on Windows. That closes deterministic/Windows package
acceptance only. A separately authorized live provider test is required for
`HOSTED_WEB_SEARCH_LIVE_ACCEPTED`.
