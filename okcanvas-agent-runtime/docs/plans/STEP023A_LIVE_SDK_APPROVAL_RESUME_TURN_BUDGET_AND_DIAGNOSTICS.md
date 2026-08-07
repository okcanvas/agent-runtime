# STEP023A — Live SDK approval resume turn budget and diagnostics

Status: **IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING**

## Scope

- correct the persisted Agents SDK turn budget from one turn to two;
- preserve a bounded approval workflow;
- make prepare/decision child failures produce explicit redacted Evidence;
- retain all existing approval, encryption, fencing, and read-only-console boundaries;
- do not add Agents, Tools, MCP, UI mutations, or approval breadth.

## Reference adoption

- ADOPT: `RunState` serializes `current_turn` and `max_turns`.
- ADOPT: resumed `Runner.run` restores `run_state._max_turns`.
- ADAPT: reserve exactly two turns for one approval interruption plus finalization.
- REJECT: unbounded turn budgets and direct `/reference` imports.

## Completion

Deterministic tests and STEP020–STEP023 regressions must pass. Windows live completion requires rerunning `sh_run_step022_live_closure.cmd` and observing approve/reject PASS.
