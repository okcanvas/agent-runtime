# STEP039_NATIVE_SDK_STREAMING_ADAPTER_V1

Version: `2.19.0`

## Goal

Expose the actual OpenAI Agents SDK semantic stream without weakening the governed Product execution path or confusing ephemeral model deltas with durable Product evidence.

## Implemented architecture

- `OpenAIGenericAgentGateway` receives an optional product-owned native stream broker.
- Default Control API construction injects the broker and therefore uses `Runner.run_streamed()`.
- The Gateway consumes `result.stream_events()` independently of clients.
- `streaming.adapter` converts only safe SDK event shapes.
- `streaming.broker` keeps bounded per-Run memory history and subscriber queues.
- `GET /v1/runs/{run_id}/sdk-stream` exposes authenticated SSE.
- `/runner` shows native ephemeral and canonical persisted streams separately.

## Event mapping

- `RawResponsesStreamEvent` + `response.output_text.delta` → `model.text.delta`.
- other raw response events, including Tool arguments and reasoning → dropped.
- `RunItemStreamEvent` → `run.item` with name/type/Agent metadata only.
- `AgentUpdatedStreamEvent` → `agent.updated` with display name only.

## Disconnect and restart semantics

Subscriber disconnect removes only its queue. The scheduler/Gateway continues. Completed streams may be replayed from bounded memory in the same process. Process restart/eviction produces `NATIVE_SDK_STREAM_UNAVAILABLE`; canonical Events remain available separately.

## Runtime binding

The generic Agent and generic Function Tool execution bindings include the native adapter and broker source. Approval-required Tool execution remains on its separate RunState path in V1.

## Deterministic acceptance

`docs/evidence/STEP039_ACCEPTANCE.json` passes 20/20. See `HANDOFF.md` for exact checks and the Windows closure command.

## Explicit non-scope

Handoff, Agent-as-Tool, Session, Guardrails, approval RunState native stream continuation, raw Tool argument/result stream, reasoning stream, persistent token deltas, cross-process stream replay, WebSocket, remote multi-user fanout, and distributed broker.
