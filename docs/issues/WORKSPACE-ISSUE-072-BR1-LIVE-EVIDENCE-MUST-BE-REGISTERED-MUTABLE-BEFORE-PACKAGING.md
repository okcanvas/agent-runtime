# WORKSPACE-ISSUE-072 — BR1 Live evidence must be registered mutable before packaging

Status: PREVENTED_IN_R12R1_PACKAGING

## Risk

The new STEP096BR1 focused Live harness writes
`docs/evidence/WORKSPACE_STEP008R4R12R1_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json`.
During initial R12R1 harness construction that path had not yet been added to
`MUTABLE_ACCEPTANCE_EVIDENCE`. Packaging in that state would allow a later Windows Live run to mutate a
file that the immutable Workspace manifest/package identity could otherwise treat as release content,
repeating the class of provenance defect previously closed by WORKSPACE-ISSUE-057.

## Prevention

The BR1 Live evidence path is registered in `scripts/workspace_inventory.py` before R12R1 packaging.
The R12R1 static gate must assert this exact mutable registration.

## Recurrence gate

Every new Live acceptance output path must be registered as mutable before the first immutable manifest or
release ZIP for that harness is generated. A new Live harness without its mutable evidence registration is a
static-contract failure.
