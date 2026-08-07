# STEP008R4R1 Implementation Failure Log

## F001 — Historical PENDING text cannot be globally replaced

A broad search found many PENDING states in historical Issue, Plan and Evidence files. Rewriting
those values would corrupt the chronology. The correction is limited to current README, HANDOFF,
PLANS, project catalog and current integration contract.

## F002 — Product storage pluggability cannot be inferred from ProductStore alone

The audit initially appeared to have a strong ProductStore port. Code review proved that governed
Submission directly writes Product tables and Artifact application services directly write files.
The next step is therefore typed ports and transaction ownership, not a PostgreSQL adapter.

## F003 — Runtime documentation changes are not Product source changes

Runtime README and HANDOFF are aligned, but Runtime Python, Agent specs, routing, Tool/MCP and Skill
sources remain unchanged. A dedicated source digest evidence file is generated and checked.

## F004 — New document-alignment test had an escaped newline syntax error

The first Workspace run failed before assertions because the generated test source split the
`"\\n".join(...)` literal across two physical lines. The test source was corrected, manifest was
regenerated, and the full suite was rerun. No Product source was involved.

## F005 — Deterministic acceptance still required the pre-approval pending Live marker

The first integrated R4R1 run passed Runtime, Connector, Example, E2E, tests and manifest but failed
24/25 because the retained deterministic predicate was still named `live_acceptance_not_claimed` and
required the old R4 rerun-pending contract value. R4R1 records actual parent acceptance, so the
predicate was replaced with `parent_live_acceptance_retained` and requires the exact 29/29 marker.
