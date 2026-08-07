# WORKSPACE STEP001R3 — Local Environment and Test Import Boundary Closure

## Scope

Correct only the two failures observed in the real Windows STEP001R2 run:

1. local environment configuration must not count as accepted parent source drift;
2. Workspace tests must import management scripts from the exact Workspace root.

No Runtime, Product CLI, Connector, or Example product source is changed.

## Acceptance

- shared inventory policy for identity, manifest, and packaging;
- `.env`, `.env.local`, and `.env.local.cmd` excluded while templates remain included;
- unittest discovery uses `-t .` and exact Workspace script origins;
- retained child acceptances and Connector→Example integration remain green;
- Fresh extraction and deterministic repack pass.
