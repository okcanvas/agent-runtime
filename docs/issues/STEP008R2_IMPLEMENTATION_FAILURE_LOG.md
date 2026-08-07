# STEP008R2 Implementation Failure Log

## F001 — Historical STEP088 Fake Child omitted actual MCP evidence

The new normalizer correctly rejects a Fake Child result with no observed MCP Tool output. The test
Fixture was changed to include one bounded `tool_call_output_item` matching the actual execution
shape. Product fail-closed behavior was retained.

## F002 — Historical successor validators accepted only `STEP08*`

STEP080A and STEP082B current-product validators treated STEP090 as an invalid successor even
though its version and retained policies are newer. They now require a normal `STEP` identity plus
the existing minimum-version conditions.

## F003 — Historical current-package assertions froze STEP089

Retained STEP084/STEP089 tests asserted the superseded package basename. Current package identity
is now owned by STEP090 acceptance while the historical feature contracts remain retained.

## F004 — Workspace and parent manifests are intentionally stale during implementation

Manifest failures before finalization are expected and are not accepted. Parent and Workspace
manifests are regenerated only after source, tests, evidence and documentation are closed.

## F005 — Runtime HANDOFF finalization must retain prior product identities

The current HANDOFF explicitly retains `document-review-v1`, local analysis Tools, sandbox,
reference catalog, Groupware Connector/Example identifiers and `OR-ISSUE-091`. Full regression
checks these identities.

## F006 — Single full Runtime pytest may exceed the execution command window

An incomplete single run is never counted. All Runtime test files are assigned exactly once to 12
partitions, each with its own log, return code and file inventory, followed by an exact aggregate
coverage check.

## F007 — Ephemeral implementation directory was lost during tool-session reset

The first un-packaged STEP008R2 working tree disappeared while the immutable STEP008R1 ZIP and user
logs remained. No missing output was claimed. The tree was reconstructed from the immutable ZIP,
all code changes were reapplied from proven source findings, and every validation is rerun from the
reconstructed tree. Future handoff never relies on an un-packaged working directory.


## F008 — Partition evidence verification used a non-zero-padded filename

The first grouped verification read `partition-2.json` although the runner correctly writes
`partition-02.json`. Completed partition evidence was preserved, the verifier was corrected, and
all 12 partitions were independently rerun and aggregated with exact coverage.

## F009 — Unbounded cache cleanup traversed excluded virtual environments

A broad `find .` cleanup entered excluded `.venv` trees and exceeded the command window before
Workspace tests started. Cache cleanup is now limited to owned source/test/script paths; virtual
environments remain excluded from identity and packages.

## F010 — Monolithic local Workspace orchestration exceeded the bounded tool command window

The accepted Windows launcher remains a complete orchestration, but local/Fresh verification can
exceed the available single-command window. STEP008R2 adds a fail-closed two-phase verification
boundary: a fresh Runtime gate records source digests, process result and 24/24 evidence without
source mutation; the Workspace gate consumes both files and still runs all remaining checks. It
rejects missing pairs, failed process evidence, changed source or non-24/24 Runtime evidence. No
subproject acceptance is skipped.

## F011 — Pipe-backed subprocess capture waited on inherited descendant handles

Runtime acceptance itself completed, but pipe EOF can be delayed by an exercised descendant that
inherits stdout/stderr. Workspace added file-backed direct-child capture and STEP090 `--quiet`; the
full payload remains in the explicit UTF-8 evidence file while console capture is bounded.
