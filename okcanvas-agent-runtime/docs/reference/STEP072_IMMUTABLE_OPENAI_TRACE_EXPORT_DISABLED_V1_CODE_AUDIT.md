# STEP072 code audit

## Audited baseline

- STEP071 source ZIP SHA-256: `06d0862aa345bd985e581994ba1cde685608dc8aa38e4622ef7a99b7571a9d1c`;
- STEP071 deterministic Windows acceptance: 28/28 PASS;
- STEP071 real provider Windows acceptance: 28/28 PASS;
- model: `gpt-4.1`, one model call, 1,145 total tokens;
- observed trailing SDK diagnostic: `Tracing client error 400`.

## Pinned upstream evidence

Inspected immutable Reference source:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_config.py` declares
  `tracing_disabled: bool = False` and documents per-run disablement;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tracing/processors.py` defaults to an
  OpenAI exporter and prints the exact non-fatal 4xx diagnostic observed on Windows;
- `reference/upstream/openai-agents-python-0.19.0/docs/config.md` states tracing is enabled by default
  and may be disabled.

Reference files remain read-only and are never imported by Product code.

## Product finding

Before STEP072, all seven `RunConfig` paths supplied `trace_id`, `group_id`, metadata and
`trace_include_sensitive_data=False`, but did not set `tracing_disabled`. Consequently the SDK built
spans and attempted a separate trace upload at process shutdown. This network side effect was not a
Product-owned capability and was not part of persisted Product evidence.

## Implementation

Added:

- `specs/runtime/openai-trace-export-policy.json`;
- `src/okcanvas_agent_runtime/trace_export/{models,catalog,runtime,errors}.py`;
- trace policy and Product runtime SHA in `AgentRuntimeBinding`;
- explicit policy resolution in all seven SDK RunConfig paths;
- `scripts/run_step072_acceptance.py`;
- `scripts/run_step072_live_acceptance.py`;
- Windows deterministic/live launchers;
- STEP071 compact Windows-live closure evidence.

The runtime helper returns exactly:

```python
{"tracing_disabled": True, "trace_include_sensitive_data": False}
```

Trace metadata remains present in source for local diagnostic meaning, but the disabled SDK does not
create/export provider spans. The separately generated Product `trace_id` continues to be recorded in
Product Run execution metadata.

## Security and integrity

- no API Key is written to policy, binding, Event or Artifact;
- provider trace export is fail-closed;
- policy mutation or symlink replacement is rejected;
- policy and runtime implementation hashes are bound before confirmation;
- Skill package identity is unchanged;
- model route, retry, reasoning, response-storage and provider-ID policies remain intact.
