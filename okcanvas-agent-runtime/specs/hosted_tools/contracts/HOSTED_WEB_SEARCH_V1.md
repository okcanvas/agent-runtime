# Hosted Web Search V1 Contract

## Capability

The Product may attach exactly one installed-SDK `WebSearchTool` to an immutable, Session-disabled
Agent. The Tool is configured only from `specs/runtime/hosted-web-search-policy.json`.

## Fixed limits

- domains: one to eight canonical domains; STEP067 contains only `developers.openai.com`;
- search calls: exactly one completed call;
- retrieved sources: 1..8;
- inline citations: 1..8;
- title length: at most 200 characters;
- search context: fixed by policy;
- user location: disabled;
- model turns: two;
- `tool_choice=required`, `parallel_tool_calls=false`, `store=false`;
- provider retries: zero through the existing immutable retry policy.

## Source validation

Only HTTP/HTTPS URLs with a hostname and an explicit non-static path are accepted. Userinfo,
explicit ports, control characters and static/binary suffixes are rejected. Query and fragment are
removed. A hostname must equal or be a subdomain of an allowed domain.

The Runtime inspects SDK `result.new_items` and requires one completed `web_search_call`, retrieved
source evidence and at least one inline URL citation. File Search or any other hosted Tool item fails
closed.

## Evidence

The Product creates `agent.final-output` and `agent.hosted-search-evidence` separately. The evidence
Artifact may contain policy identity, canonical source URL, bounded title, source/citation counts and
cited state. It must not contain raw query, raw result content, snippets, provider call ID, provider
response ID or raw SDK response.

The model-owned structured output must not contain URLs. Product source evidence is authoritative.

## Exclusions

File Search, OpenAI File upload, Vector Store lifecycle, user-selected domains, user location,
Session composition, Function Tool/MCP mixing, Handoff, Agent-as-Tool, orchestration, Guardrails and
workspace access are outside V1.
