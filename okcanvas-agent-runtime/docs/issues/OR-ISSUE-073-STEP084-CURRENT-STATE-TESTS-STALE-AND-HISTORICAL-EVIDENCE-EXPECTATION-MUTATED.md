# OR-ISSUE-073 — STEP084 current-state tests were stale and one historical evidence expectation was mutated

## Symptom

The full STEP084 Python regression failed five tests in the 200–219 file segment. Current-state tests still expected pre-STEP084 RuntimeInfo, route and launcher values, while one preserved STEP081B failure assertion incorrectly expected 39 instead of its immutable recorded 36 architecture checks.

## Code-confirmed root cause

Additive STEP084 identity updates were not propagated to all current-state regressions. A broad numerical replacement also changed an assertion over historical evidence, which must remain fixed to the original Windows failure summary.

## Impact

The Product Architecture and STEP084 focused gates passed, but full cumulative regression could neither validate the current topology nor protect historical evidence accurately.

## Correction

- current RuntimeInfo expectation: 861 fields;
- current route evidence: Admin 54 and Service 39;
- current launcher pair: STEP084;
- STEP080A superseding Product identity: current STEP084;
- preserved STEP081B architecture evidence restored to 36/38.

## Recurrence gate

- STEP080A retained Compliance regression;
- STEP081/081C/081D current and historical boundary regressions;
- full STEP084 Python regression and Fresh-ZIP rerun.
