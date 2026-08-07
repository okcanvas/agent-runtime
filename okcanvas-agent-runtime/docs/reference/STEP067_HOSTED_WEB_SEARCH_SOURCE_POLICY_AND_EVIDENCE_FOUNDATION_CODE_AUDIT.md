# STEP067 Code Audit and Scope Review

## Review status

- Baseline ZIP: `okcanvas-agent-runtime-step066-remote-mcp-streamable-http-mvp-foundation-v1.zip`
- Baseline version: `2.46.0`
- Baseline STEP: `STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION`
- Reported Windows state: `WINDOWS_LIVE_ACCEPTED` (28/28)
- Review mode: code/source audit only; no project files modified
- Proposed next STEP: `STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION`
- `FileSearchTool`: explicitly not included in STEP067

## 1. Existing roadmap evidence

`docs/plans/ROADMAP.md` places “Hosted Web/File Search foundation” immediately after STEP066, but ends with `STEP067 is not selected`.

The STEP061 matrix classifies these three examples as DEFER under `HOSTED_READONLY_TOOLS`:

- `examples/tools/web_search.py`
- `examples/tools/web_search_filters.py`
- `examples/tools/file_search.py`

The recorded rationale requires source, retention, citation and tenant/source policy before enablement.

## 2. Pinned SDK facts

Pinned SDK: OpenAI Agents SDK `0.19.0`.

Source hashes:

- `src/agents/tool.py`: `1ba4d71d2e6b59638ce2bfee53529b36373ba6e8dadd1fdf68c6fea040bf6a3e`
- `src/agents/models/openai_responses.py`: `37817cc1ba836f5cdfc59d4ab519f19f29432b0fb60d7c713cc5fba7a682a252`
- `src/agents/run_internal/turn_resolution.py`: `3bf639e8730785a591a0c70210f80cc1022be43b59b297df7c64a40387df36ae`

Example hashes:

- `examples/tools/web_search.py`: `67724928f8fe65de2f4f7c9cadf9e9918017a1b212e92f941c16fbc23e02a1f7`
- `examples/tools/web_search_filters.py`: `3a98e390d08162be2cde3517fbe1b7c9de216ba93a9972ba42e033691efe20c3`
- `examples/tools/file_search.py`: `5257ce35c447595b465f74addd7bba195e3c5a7b8908e3071072d5970fa12234`

### WebSearchTool

`reference/.../src/agents/tool.py:728-768` confirms:

- OpenAI Responses only;
- `user_location`;
- `filters`;
- `search_context_size` (`low|medium|high`);
- `external_web_access`.

`reference/.../examples/tools/web_search_filters.py:84-128` demonstrates:

- static `allowed_domains`;
- `tool_choice="required"`;
- `response_include=["web_search_call.action.sources"]`;
- extraction of URL citations and retrieved source URLs;
- rejection when cited/retrieved source evidence is absent.

### FileSearchTool

`reference/.../src/agents/tool.py:702-725` confirms:

- required `vector_store_ids`;
- optional `max_num_results`;
- optional included search results;
- ranking and metadata filters.

`reference/.../examples/tools/file_search.py:8-30` creates an OpenAI File, creates a Vector Store and indexes the File before the Agent is constructed. The Agent-side tool only searches an already existing Vector Store.

### Hosted call observation

`reference/.../src/agents/run_internal/turn_resolution.py:2071-2088` converts hosted file/web calls into `ToolCallItem` objects in `result.new_items`; it does not schedule a local Tool execution.

Hosted tools do not use the Function Tool guardrail pipeline. Therefore STEP067 cannot rely on existing Function Tool input/output Guardrails or on local `RunHooks.on_tool_start/on_tool_end` as its authorization/evidence boundary.

## 3. Current OKCanvas gaps

### 3.1 No hosted Tool declaration exists

`src/okcanvas_agent_runtime/agent_definitions/models.py:7-31` contains:

- Function Tools;
- MCP servers;
- Handoffs;
- Agent-as-Tool children;
- orchestration children;
- Guardrails.

It has no hosted Tool field.

`src/okcanvas_agent_runtime/agent_definitions/catalog.py:32-50` rejects unknown definition keys. A `hosted_tools` field cannot be added to a JSON Agent definition without a schema/catalog implementation.

### 3.2 Existing Tool hooks cannot normalize hosted calls

`src/okcanvas_agent_runtime/execution/openai_gateway.py:663-807` handles only:

- Agent-as-Tool;
- MCP calls with a server ID;
- local Function Tools present in `local_tools`.

Hosted Web/File calls are provider outputs, not local invocations. They require post-run inspection of `result.new_items`.

### 3.3 No source evidence crosses the Gateway boundary

`src/okcanvas_agent_runtime/execution/contracts.py:82-88` returns only:

- structured output;
- usage;
- trace ID;
- minimized response ID;
- SDK version.

There is no source/citation evidence field.

`src/okcanvas_agent_runtime/execution/openai_gateway.py:1231-1248` validates the final structured output and then discards `result.new_items`.

### 3.4 Current Artifact path persists only final structured output

`src/okcanvas_agent_runtime/execution/service.py:1039-1083` creates only `final-output.json` as `agent.final-output`.

Source URLs, citation titles, search call counts and source-policy evidence have no Product Artifact contract.

### 3.5 Existing response minimization conflicts with source retrieval evidence

`src/okcanvas_agent_runtime/reasoning_evidence/runtime.py:6-11` forces `response_include=[]`.

The pinned Web Search filters example requires `web_search_call.action.sources` to retrieve the source URL list. STEP067 therefore needs a narrowly merged hosted-search include policy while continuing to request no reasoning summary/content.

### 3.6 No OpenAI Vector Store lifecycle exists

A repository search finds no Product service/catalog for:

- OpenAI File upload;
- Vector Store creation;
- indexing state;
- source ownership;
- expiration/retention;
- deletion;
- external provider resource reconciliation.

Combining File Search into STEP067 would either introduce all of this in one STEP or silently depend on unmanaged external resources. Neither matches the current immutable Product boundary.

## 4. Decision

### Selected STEP067 candidate

`STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION`

### Rejected STEP067 scope

Do not implement `WebSearchTool` and `FileSearchTool` together.

### Why Web Search is first

Web Search requires a new hosted Tool policy and source-evidence path, but does not require Product-managed provider resource creation.

File Search requires either:

1. a separate Product-owned File/Vector Store lifecycle; or
2. an explicit pre-provisioned Vector Store binding contract.

That decision must be audited independently after STEP067.

## 5. Recommended STEP067 V1 contract

### Agent graph

- exactly one hosted Tool: `web_search`;
- Session disabled;
- workspace none;
- no local Function Tool;
- no MCP;
- no Handoff;
- no Agent-as-Tool;
- no bounded orchestration;
- no Guardrail mixing;
- one dedicated immutable Web Search Agent.

### Source policy

- one immutable policy referenced by the Agent definition;
- non-empty static domain allowlist;
- domain identifiers validated and canonicalized;
- no request-supplied domains;
- no user location in V1;
- fixed `search_context_size`;
- explicit `external_web_access` value;
- policy and implementation SHA included in Runtime binding.

The upstream example URL normalization should be adapted rather than replaced by an unverified rule:

- `http|https` only;
- hostname required;
- userinfo and explicit port rejected;
- canonical path required;
- query and fragment removed from persisted evidence;
- control characters and known binary/static suffixes rejected;
- exact domain or subdomain of an allowlisted domain only.

### Model settings

- OpenAI Responses route only;
- `store=false` preserved;
- retry 0 preserved;
- reasoning summary/content disabled;
- `tool_choice="required"` for the first turn;
- `parallel_tool_calls=false`;
- Agent `reset_tool_choice=true` retained;
- bounded `max_turns=2`;
- include only `web_search_call.action.sources` in addition to the existing minimization policy.

Do not use undocumented `max_tool_calls` through `extra_args` in this STEP.

### Post-run validation

Inspect `result.new_items` and require:

- exactly one completed `web_search_call`;
- no File Search or other hosted call;
- bounded retrieved source count;
- every persisted source URL passes canonicalization and domain policy;
- non-empty retrieved source evidence;
- no raw search query, source body, snippet, provider call ID or response object persisted.

Inline URL-citation annotations may be extracted and counted, but a real live test must prove their behavior with strict structured output before making annotation presence the only success condition.

### Product evidence

The current Gateway/Artifact contract must be extended. The recommended minimal design is:

- `GenericGatewayRunResult` gains a bounded product-owned hosted-search evidence object;
- final structured output remains the existing strict output contract;
- a second immutable Artifact, `agent.hosted-search-evidence`, stores only canonical source metadata;
- Event metadata records policy ID/SHA, call count, source count, citation count and persistence flags;
- the final Run event references both Artifacts or a bounded evidence-artifact list;
- raw provider output and snippets are never stored.

This avoids trusting model-generated URLs as the authoritative source list.

## 6. Deterministic and live acceptance

### Deterministic acceptance

Use fake SDK/provider objects to prove:

- exact `WebSearchTool` construction;
- exact model settings merge;
- hosted calls are read from `result.new_items`, not local Tool hooks;
- domain and URL normalization;
- missing/multiple/foreign-domain calls fail closed;
- source evidence is bounded;
- no raw query/body/provider IDs in Events/Artifacts;
- Runtime binding changes on policy/source implementation drift;
- all STEP066 and prior regression tests remain green;
- no external network or model calls.

### Explicit live acceptance

A separate explicit command should make one real OpenAI call against a stable allowlisted official documentation domain and verify:

- hosted Web Search actually ran;
- exactly one completed search call is observed;
- at least one policy-valid retrieved source is captured;
- structured output is valid;
- evidence Artifact contains canonical metadata only;
- response storage remains disabled;
- no File Search or other hosted Tool is used.

Deterministic acceptance alone must not be described as live Web Search acceptance.

## 7. Deferred after STEP067

### Proposed STEP068 review target

`PREPROVISIONED_HOSTED_FILE_SEARCH_SOURCE_BINDING_FOUNDATION` or a separate Product-managed Vector Store lifecycle STEP, selected only after a fresh audit.

Required decisions before File Search:

- who creates/uploads/deletes Files and Vector Stores;
- whether V1 accepts only pre-provisioned stores;
- source ownership and organization/tenant binding;
- retention/expiration and deletion proof;
- static vector-store allowlist and maximum store count;
- result/snippet persistence policy;
- file citation/source identity normalization;
- handling of provider IDs under the identifier minimization constitution.

## 8. Final verdict

STEP067 should be Web Search only. A combined Web/File implementation is not supported by the current Product code and would hide an unmanaged Vector Store lifecycle behind a read-only Tool label.

No source files were modified during this review.


# Implemented STEP067 delta

- Agent definition now owns `hosted_tools`; only `web-search-v1` is accepted and it must be isolated.
- `hosted_search` policy/catalog/runtime modules own SDK construction, canonical URL validation and bounded evidence extraction.
- `HostedWebSearchResult` prevents model-owned URLs.
- Runtime binding contains policy data, Product implementation SHA and pinned SDK source SHA values.
- Gateway adds one `WebSearchTool`, exact ModelSettings and post-run `result.new_items` validation.
- Execution stores `agent.final-output` and `agent.hosted-search-evidence` separately.
- No `FileSearchTool` is imported into Product runtime code.
- Deterministic validation uses fake SDK items; provider/network calls remain zero.
