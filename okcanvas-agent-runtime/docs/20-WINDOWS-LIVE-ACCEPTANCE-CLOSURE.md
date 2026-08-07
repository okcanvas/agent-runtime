# Windows live-acceptance closure harness

STEP022 adds no new Agent, Tool, approval decision surface, or product mutation capability. It closes the two pending Windows checks from STEP021 through one bounded launcher.

## Flow

```text
STEP021 deterministic Inbox acceptance
→ STEP020 installed-SDK approve/reject live acceptance
→ compact closure summary
```

The two child acceptances still own their own workspaces and assertions. STEP022 only coordinates them and records a safe summary.

## Commands

Deterministic harness validation:

```bat
sh_run_step022_acceptance.cmd
```

Windows installed-SDK closure:

```bat
sh_run_step022_live_closure.cmd
```

Live Evidence is written below:

```text
docs/evidence/step022-live/<acceptance-id>/
├─ closure-summary.json
├─ step021-summary.json
├─ step021.log
├─ step020-live-summary.json
└─ step020-live.log
```

The live Evidence directory is local operational state and is excluded from source ZIPs.

## Completion contract

The closure passes only when:

- STEP021 state is `PASSED`;
- STEP021 acceptance cleanup is `COMPLETED`;
- STEP020 is explicitly in live SDK mode;
- STEP020 approve and reject branches both pass;
- prepare and decision process IDs differ in both branches;
- approval executes the Tool exactly once;
- rejection executes the Tool zero times;
- STEP020 acceptance cleanup is `COMPLETED`;
- all four immutable Reference trees remain unchanged;
- the API key is absent from child logs and the compact closure summary.

## Boundaries

- no approve/reject browser controls;
- no new Tool registry;
- no new authorization model;
- no retry that changes a failed child result into success;
- no secret values in command arguments or summary metadata;
- no direct import or execution from `/reference`.
