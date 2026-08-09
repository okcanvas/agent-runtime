# WORKSPACE-ISSUE-065 — Static validator mutated packaged nested evidence

## Status

FIXED_IN_R11

## STEP

Workspace R11 / Runtime STEP096A

## Observation

The initial R11 Workspace static validator invoked the Runtime architecture-constitution validator at its default packaged evidence path. Its timestamped output changed the Runtime tree during verification and invalidated the freshly generated Runtime parent manifest.

## Correction / recurrence gate

Nested validators that emit mutable/timestamped evidence are redirected to a temporary path outside the source tree during Workspace static verification. Manifest verification must be observational and non-mutating.
