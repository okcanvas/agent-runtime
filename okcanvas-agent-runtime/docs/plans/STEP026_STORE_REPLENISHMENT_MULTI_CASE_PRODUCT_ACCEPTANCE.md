# STEP026 — Store replenishment multi-case product acceptance

## Status

`WINDOWS_LIVE_ACCEPTED`

## Code-audited reason

STEP025 is Windows live accepted, but repository inspection showed only one canonical business pack (`case001-shortage`) and one matching deterministic Evaluation case. Expanding to writes, remote source hosts, another Agent, browser mutation, or distributed execution at that point would have built capability breadth on a single overfitted example.

STEP026 therefore changes no production authority and adds no new external integration. It strengthens the same governed read-only ingress and `store-replenishment-review-agent` across a bounded canonical case matrix.

## Case matrix

- `case001-shortage`: existing mixed 12/7/0 baseline, total 19.
- `case002-covered`: every SKU covered, total 0, status `READY`.
- `case003-tie-ordering`: equal reorder quantities sorted by SKU ascending.
- `case004-single-shortage`: exactly one shortage, total 1.
- `case005-invalid-duplicate-sku`: invalid source response rejected before preflight persistence.

Each valid case has an immutable input/output pack and a deterministic recorded-Run Evaluation case. The invalid case has only an input fixture because no Product Run or Artifact is permitted.

## Deterministic acceptance

`docs/evidence/STEP026_ACCEPTANCE.json` proves:

- four valid source snapshots, each read exactly once;
- one invalid source snapshot read and rejected;
- five total source reads and zero writes;
- same-key replay causes no extra read;
- each valid preflight exists before its Task/Run;
- four submissions, four Tasks, four Runs, and four Artifacts;
- all four Product Runs `SUCCEEDED`;
- all four recorded-Run Evaluations `PASSED`;
- exact totals 19, 0, 10, and 1;
- `READY` behavior for the covered case;
- exact SKU tie ordering;
- invalid duplicate SKU creates no submission, Task, Run, or protected payload;
- no Tool or MCP Events;
- no raw source snapshots or credentials in SQLite or Events;
- every successful protected payload is deleted;
- references unchanged;
- Acceptance Workspace cleanup `COMPLETED`.

## Windows live acceptance

The user-reported Windows run passed all 22 checks with five reads, zero writes, four Artifacts, four PASSED Evaluations, exact totals 19/0/10/1, duplicate-SKU rejection before persistence, and cleanup `COMPLETED`. Compact Evidence is `docs/evidence/STEP026_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.
