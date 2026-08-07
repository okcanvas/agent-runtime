# STEP008R4R3 Implementation Failure Log

## Environment limitation

The build environment had no PostgreSQL server, Docker, or installable psycopg package. The package
therefore records PostgreSQL adapter implementation and deterministic contract acceptance only. It
must not be described as PostgreSQL-live accepted.

## Runtime full-suite packaging regressions

Two historical current-package tests pinned the STEP091B1 ZIP filename. They were aligned to the
STEP091B2 current package identity. Product semantics were unchanged.

## Partition execution time limits

The full Runtime suite exceeded bounded single-command windows. Existing exact 12-partition execution
was retained; each partition produced hashed evidence and aggregate coverage proved no missing or
duplicate test files.

## Workspace current-contract alignment

The first Workspace unit run reported three packaging alignment failures after the Runtime was
advanced to STEP091B2: one retained test still expected `run_step091b1_acceptance.py`, the Runtime
parent byte manifest still described STEP091B1, and `WORKSPACE_MANIFEST.json` had not yet been
regenerated. The test was aligned to the current Runtime gate and both manifests were regenerated
from the actual source trees. The next full Workspace run passed 115/115.

## Final Fresh Runtime rerun tool time limit

A final redundant Runtime gate invocation on the final ZIP reached all visible STEP091B2 stages through
`compileall` but the external execution tool terminated the command at its bounded time limit before
it wrote the process summary. This was not accepted as a Runtime pass. The already-passed Fresh
Runtime 25/25 evidence was instead reused only after the Workspace runner verified that its recorded
Runtime snapshot digest exactly matched the final ZIP Runtime snapshot digest. The final Workspace
gate then passed 29/29 with zero drift. This prevents an unbound or stale Runtime evidence file from
being used as proof for a different package.
