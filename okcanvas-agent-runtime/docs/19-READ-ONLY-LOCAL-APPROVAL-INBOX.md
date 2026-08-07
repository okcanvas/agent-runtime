# Read-only local approval inbox

STEP021 adds an observation surface around STEP020 approvals. It does not add a decision surface.

## API

```text
GET /v1/tool-approvals
  ?state=PENDING
  &limit=100
  &offset=0
```

The endpoint requires `X-OKCanvas-Admin-Key` and returns bounded operator metadata. It deliberately omits encrypted RunState references, storage hashes, key fingerprints, raw Tool call IDs, Tool arguments, and Tool results.

## Console

`/console` includes an **승인 대기** tab showing state, Tool, Run, Task, decision, execution count, and creation time. The browser uses only authenticated GET requests and never reads or stores `X-OKCanvas-Run-Submitter-Key`.

## Authority boundary

```text
Operations read authority
→ approval observation only

Run submitter authority
+ local admin authority
→ existing API decision path
```

The current console has no approve or reject buttons. This keeps the first operator surface simple and prevents a read-only monitoring session from becoming a mutation authority.

## STEP020 live SDK acceptance

The Windows launchers were corrected to use named `windows_entrypoint.py` commands:

```bat
sh_run_step020_acceptance.cmd
sh_run_step020_live_acceptance.cmd
```

The live result remains pending until the user reports both approve and reject branches passing with separate process IDs.

## Safe operator lookup

`GET /v1/tool-approvals/{approval_id}/inbox` returns the same bounded metadata as the Inbox list for the local operator CLI. It does not expose encrypted RunState location, hashes, key IDs, Tool arguments, or Tool-call identifiers.

