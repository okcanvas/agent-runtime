# STEP039 — Native SDK streaming code audit

## Retained Reference paths

Primary inspected paths under `reference/upstream/openai-agents-python-0.19.0`:

- `src/agents/run.py` — `Runner.run_streamed()`;
- `src/agents/result.py` — `RunResultStreaming.stream_events()` lifecycle and cancellation behavior;
- `src/agents/stream_events.py` — `RawResponsesStreamEvent`, `RunItemStreamEvent`, `AgentUpdatedStreamEvent`;
- `examples/basic/stream_text.py`;
- `examples/basic/stream_items.py`;
- `examples/basic/stream_function_call_args.py`;
- `examples/agent_patterns/human_in_the_loop_stream.py`;
- `tests/test_agent_runner_streamed.py`;
- `tests/test_cancel_streaming.py`;
- `tests/test_stream_events.py`;
- `tests/test_streaming_tool_call_arguments.py`.

## Adopt

- `Runner.run_streamed()` and `stream_events()`;
- official three event classes;
- semantic text delta handling;
- stream completion/error propagation.

## Adapt

- SDK events become a bounded safe product envelope;
- Product execution consumes the stream, not the HTTP client;
- a process-local broker allows same-process replay and multiple subscribers;
- canonical lifecycle hooks remain separately persisted;
- only text delta and bounded metadata are exposed.

## Reject in V1

- direct passthrough of raw response events;
- function-call argument delta exposure;
- Tool output exposure;
- reasoning content exposure;
- cancellation of Product execution on client disconnect;
- native stream persistence in SQLite;
- pretending persisted SSE is native streaming;
- cross-process durability claims.

## Confirmed current-code distinction

`/v1/runs/{run_id}/events/stream` remains cursor-based durable Product evidence. `/v1/runs/{run_id}/sdk-stream` is authenticated, process-local, ephemeral SDK observation. The two are intentionally not merged.
