# OR-ISSUE-064 — Historical STEP082B exact identity and Agent count blocked additive Product evolution

## Symptom

After adding two STEP083 Product Agent definitions, the retained STEP082B execution-plane validator and current-state tests failed because they required the current Product identity to remain STEP082B and the Agent catalog to contain exactly 27 definitions.

## Code-confirmed root cause

A historical policy regression gate mixed two responsibilities: preserving the STEP082B execution-plane decision and asserting the then-current Product revision and exact catalog size. The latter made any additive Agent definition look like an execution-plane regression.

## Impact

A valid Organization Assistant addition could not pass cumulative regression even though `GenericAgentExecutionService` remained the sole Product control plane and no fourth Coding plane was introduced.

## Correction

The retained STEP082B validator now proves its policy under the current 08x Product identity and requires the original 27 definitions to be retained rather than requiring an exact total. STEP083 owns the exact current identity and 29-Agent/34-binding topology.

## Recurrence gate

- `scripts/validate_step082b_execution_plane.py` 13/13;
- `scripts/validate_step083_assistant_routing.py` 18/18;
- STEP080 capability-topology current-state regression;
- STEP083 integrated acceptance.
