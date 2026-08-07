# Minimal local approval operator CLI

STEP023 adds a small command-line decision surface over the existing governed local Tool approval flow. It does not add a browser decision page or broaden the Tool boundary.

## Prerequisites

Run the local Control API first:

```bat
sh_run_api.cmd
```

The local environment must contain distinct values for:

```text
OKCANVAS_CONTROL_ADMIN_KEY
OKCANVAS_RUN_SUBMITTER_KEY
```

The operator client defaults to:

```text
http://127.0.0.1:8765
```

An explicit loopback address can be configured with:

```text
OKCANVAS_CONTROL_BASE_URL=http://127.0.0.1:8765
```

Remote URLs are rejected before any authority key is sent.

## List pending approvals

```bat
sh_approval_operator.cmd approval-inbox-list --state PENDING --pretty
```

Each pending entry includes exact strings shaped as:

```text
approve_confirmation = APPROVE <approval_id> <run_id>
reject_confirmation  = REJECT <approval_id> <run_id>
```

The list excludes encrypted RunState paths, hashes, keys, Tool arguments, Tool-call IDs, and Tool results.

## Approve one item

```bat
sh_approval_operator.cmd approval-decide ^
  --approval-id approval_... ^
  --decision APPROVE ^
  --confirmation "APPROVE approval_... run_..." ^
  --pretty
```

## Reject one item

```bat
sh_approval_operator.cmd approval-decide ^
  --approval-id approval_... ^
  --decision REJECT ^
  --confirmation "REJECT approval_... run_..." ^
  --pretty
```

The exact confirmation is checked by both the CLI and the server. Wrong confirmation does not transition Product Task/Run state and does not execute the Tool.

## Boundaries

- one approval per command;
- no batch approval;
- no `always approve` mode;
- no authority keys in command arguments;
- no browser decision controls;
- the Operations Console remains read-only;
- `/reference` is consulted but never imported or executed.
