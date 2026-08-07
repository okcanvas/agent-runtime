# CLI-ISSUE-003 — Product CLI foundation had no request execution

## Failure

The independent Product CLI project existed only as a boundary declaration. It could not authenticate a
user, create or resume an Assistant Session, submit a routed request, confirm a governed Run, consume
persisted SSE, or render the final Artifact.

## Correction

`CLI_STEP001_PRODUCT_SERVICE_INTERACTIVE_CONVERSATION_CLIENT` implements the complete Service API flow
with External Bearer authentication and no administrator boundary.

## Recurrence gates

- consecutive scripted prompts must reuse one Runtime Assistant Session;
- all HTTP paths must remain under `/v1/service/**`;
- all requests must carry only the external Bearer authority;
- persisted SSE, terminal outcome, invocation list, and `agent.final-output` Artifact must be consumed;
- Runtime and Connector source imports remain forbidden.
