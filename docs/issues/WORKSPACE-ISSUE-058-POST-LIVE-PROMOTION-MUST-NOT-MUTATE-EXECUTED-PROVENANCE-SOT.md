# WORKSPACE-ISSUE-058 — Post-Live promotion must not mutate executed provenance SOT

## Status

PREVENTED_IN_R10ER1_PROMOTION_PACKAGING

## Risk found during R10E closure

R10E's focused Live v2 harness hashes `specs/workspace/current-baseline.json` and `specs/workspace/project-catalog.json` before executing the functional Turns. The user then reported a terminal `24/24 PASSED` result from that R10E tree.

If promotion were implemented by editing those same R10E identity files in place from `NOT_READY` to an accepted state, the promoted ZIP would no longer contain the exact baseline/catalog bytes that the Live run hashed. That would recreate the class of provenance ambiguity R10E was specifically designed to eliminate.

## Canonical prevention

R10E is retained as the immutable Live-executed parent. R10ER1 is a promotion-only child:

- Runtime Product stays `STEP094R2 / 2.78.2`;
- the focused Live harness stays byte-identical;
- exact R10E baseline/catalog/Workspace-manifest bytes are retained under `docs/evidence/retained/step008r4r10e-live-source/`;
- the uploaded R10E package SHA-256 is retained;
- the user-reported terminal `24/24 PASSED` is stored separately without fabricating the missing full generated evidence JSON;
- R10ER1 current SOT is allowed to say `CURRENT_PROMOTED_BASELINE` because it explicitly points back to the immutable R10E execution source.

## Recurrence gate

Never rewrite an already executed release's hashed identity inputs to encode promotion state. Create a promotion-only child revision or retain exact pre-promotion identity snapshots and clearly distinguish `executed source` from `packaging state`.
