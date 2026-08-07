# STEP081B — Live Architecture Validator Process Isolation and Diagnostic Evidence

## Identity

```text
STEP081B_LIVE_ARCHITECTURE_VALIDATOR_PROCESS_ISOLATION_AND_DIAGNOSTIC_EVIDENCE
version: 2.61.2
```

## Input evidence

The real Windows STEP081A live run completed the model, Tool and Sandbox path but ended `75/77 FAILED`. The only false checks were:

```text
step081_static_architecture_gate_complete
step081_transport_topology_runtime_bound
```

The runtime result itself was `terminal_status=SUCCEEDED`, with two model calls, one Tool call, Sandbox cleanup `COMPLETED`, orphan count zero and no runtime failure diagnostics. The summary did not include the architecture validator result or child-process diagnostics.

## Scope

1. Preserve the STEP081 physical architecture and STEP081A Windows npm/tsc command fix.
2. Execute the complete STEP081 architecture validator in an isolated Python subprocess before the live Product workflow.
3. Explicitly bind `cwd`, `PYTHONPATH`, bytecode isolation, timeout and UTF-8 capture.
4. Parse and preserve the complete validator JSON.
5. Fail closed for child start failure, timeout, non-zero exit, invalid JSON or failed architecture checks.
6. Include the validator payload, failed check names, route inventory, stdout and stderr diagnostics in the live evidence.
7. Correct the separately duplicated Service capability `next_selected_step` identity discovered by full regression.
8. Register STEP081B deterministic/live scripts and Windows launchers.
9. Re-run full Python, non-Python, installation, Compliance, Acceptance and Fresh-ZIP validation.

## Non-goals

- No route, Tool, model, Sandbox, persistence or authority expansion.
- No WebSocket activation.
- No removal of compatibility aliases.
- No change to the ratified constitution text.
- No inference that STEP081A passed Windows live; its preserved result is 75/77 FAILED.

## Promotion Gate

STEP081B remains a candidate until a fresh Windows run reports:

```text
state: PASSED
passed_checks: 80
total_checks: 80
terminal_status: SUCCEEDED
sandbox cleanup_state: COMPLETED
sandbox orphan_count: 0
```


## Implementation status

```text
Implementation: COMPLETE
Deterministic Python: 911/911 PASS
Architecture: 38/38 PASS
Portability: 7/7 PASS
Compliance: 16/16 PASS
Acceptance: 18/18 PASS
Fresh ZIP: 911/911 PASS
Windows live: PENDING 80/80
```
