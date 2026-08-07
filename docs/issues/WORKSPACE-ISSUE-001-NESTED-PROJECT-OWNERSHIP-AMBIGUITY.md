# WORKSPACE-ISSUE-001 — Nested project ownership ambiguity

## Failure

The previous management ZIP placed `okcanvas-connectors` and `okcanvas-connector-examples` inside the
`okcanvas-agent-runtime` directory. The code remained logically separate, but the physical layout made
the Connector and Example appear to be Runtime-owned modules and encouraged one shared environment.

## Correction

Create `okcanvas-agent-platform` as a non-product management root and place Runtime, Product CLI,
Connectors, and Connector Examples as sibling projects.

## Recurrence gates

- Runtime root must not contain `okcanvas-connectors` or `okcanvas-connector-examples`.
- Workspace root must contain all independent project roots.
- No cross-project source imports.
- No workspace-root `.venv` or `node_modules`.
- Parent Runtime, Connector, and Example file manifests must remain byte-identical in this structural step.
