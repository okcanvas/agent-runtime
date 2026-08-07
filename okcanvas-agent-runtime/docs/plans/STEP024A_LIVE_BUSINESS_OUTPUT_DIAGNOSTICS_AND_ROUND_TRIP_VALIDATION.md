# STEP024A — Live business output diagnostics and round-trip validation

## Trigger

Windows deterministic STEP024 acceptance passed. The installed-SDK run then ended with a
`ValidationError` against `{}` in the acceptance script. Inspection showed that the script replaced
both zero and multiple Artifact matches with `{}` and validated that placeholder before reporting
the Product Run outcome. The traceback therefore did not prove that the SDK persisted an empty
object and could hide the original `run.failed` code.

## Scope

- preserve the original Product Run status and `/outcome` response in compact acceptance Evidence;
- record the exact final-output Artifact count and bounded validation error;
- skip recorded-Run evaluation when the Product Run failed;
- never index a missing `artifact.created` Event;
- force every SDK output through its declared Pydantic contract as JSON before Artifact creation;
- reject empty or invalid serialized output without creating an Artifact;
- keep the Agent, business formulas, authorization, MCP, approval, and console scope unchanged.

## Reference use

The implementation inspected `reference/upstream/openai-agents-python-0.19.0/src/agents/agent_output.py`.
The SDK uses a `TypeAdapter` to validate model JSON into the configured output type. STEP024A adopts
that contract and adds an independent product-boundary JSON round trip before persistence. Reference
code remains immutable and is not imported.

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`
