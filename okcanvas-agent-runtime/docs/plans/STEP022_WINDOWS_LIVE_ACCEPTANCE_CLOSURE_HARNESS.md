# STEP022 — Windows live-acceptance closure harness

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Close the pending STEP021 Windows Inbox acceptance and STEP020 installed-SDK approval acceptance through one safe, bounded command without adding product breadth.

## Scope

- run STEP021 acceptance first;
- run STEP020 approve/reject acceptance in actual installed-SDK mode second;
- preserve separate child summaries and logs;
- emit one compact secret-free closure summary;
- verify child cleanup, process restart, approve exactly once, reject zero times, and Reference integrity;
- provide deterministic and live Windows launchers through the non-executing local environment loader.

## Non-scope

- browser decision controls;
- general approval platform;
- multiple Tool interruptions;
- approval expiry or escalation;
- new Agent or Tool capabilities;
- changing STEP020 or STEP021 product contracts.

## Reference adoption

- ADAPT `reference/upstream/openai-agents-python-0.19.0/examples/tools/shell_human_in_the_loop.py`: approval completion requires an explicit approve or reject result rather than inference from partial output.
- ADAPT `reference/upstream/openai-agents-python-0.19.0/examples/sandbox/extensions/temporal/temporal_sandbox_tui.py`: keep approval observation and execution lifecycle visibly separate.
- REJECT a combined browser decision surface in the general Operations Console.
- REJECT direct `/reference` import or execution.

## Acceptance

- deterministic STEP021 and STEP020 child runs pass;
- child cleanup states are `COMPLETED`;
- live mode cannot be confused with deterministic mode;
- approve and reject branches prove separate process resume;
- Tool execution counts are exact;
- API key does not appear in child logs or closure summary;
- Reference integrity remains 4/4.
