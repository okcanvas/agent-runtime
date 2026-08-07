# STEP008R4R7A1 — Git Repository Hygiene and Retained Runtime Dist Tracking

```text
Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Version: 0.8.4-r7a1
Runtime retained: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 2.75.0
Parent Workspace: WORKSPACE_STEP008R4R7A_CURRENT_DOCUMENT_SOT_ALIGNMENT_AND_PER_FILE_IDENTITY_GATE / 0.8.4-r7a
Parent source ZIP SHA-256: ae940c8cdd46e4255be4c56c76579ee16b555c38ac2dd262178456026f19b721
Runtime Product source modifications: 0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
Promotion: NOT_READY
```

## Problem

The Workspace already had a root `.gitignore`, but no root `.gitattributes`. Static Git-policy inspection also found a contradictory ignore boundary:

- root `.gitignore` documented `okcanvas-agent-runtime/clients/cli/dist/` as an accepted committed source artifact;
- nested `okcanvas-agent-runtime/.gitignore` contained `dist/`;
- in a fresh Git repository, the nested rule wins and `git add .` omits the retained CLI dist.

This is recorded as `WORKSPACE-ISSUE-041`. A full-tree fresh Git scan then found two more unanchored-rule collisions, recorded as `WORKSPACE-ISSUE-042`: Runtime `artifacts/` hid eight Product Artifact source files and Workspace `.vscode/` hid two retained upstream files.

## Implementation

1. Add root `.gitattributes` with deterministic LF as the default text checkout policy.
2. Preserve the four already-retained CRLF Runtime CMD launcher byte contracts as explicit exceptions.
3. Strengthen root `.gitignore` for local environment secrets, Python/Node caches, generated first-party build output, Runtime mutable state, local release files, and root-scoped editor/OS noise.
4. Do not globally ignore `*.log`; `docs/evidence/*.log` is durable accepted evidence.
5. Do not globally ignore `**/dist/`; Runtime `clients/cli/dist/` is a committed source artifact.
6. Add explicit negation rules in nested Runtime `.gitignore` for `clients/cli/dist/` and its contents, and root-anchor the mutable `/artifacts/` rule so Product packages named `artifacts` stay trackable.
7. Keep `.env.local.example` trackable while `.env.local` and sibling local environment files remain ignored.
8. Regenerate Runtime parent manifest and Workspace manifest after metadata changes.

## Static validation contract

No unit, deterministic, Windows, Live OpenAI, PostgreSQL, or Object Storage tests are executed in this corrective wave because test execution remains user-deferred until MinIO is prepared.

Allowed static checks:

- `git check-ignore --no-index` against required ignored/trackable sentinel paths;
- `git check-attr` against LF/CRLF/binary sentinel paths;
- full-tree `git ls-files --others --ignored --exclude-standard` scan requiring zero canonical candidate files to be ignored;
- current-document SOT validator;
- Python AST and JSON parse checks;
- Runtime Product byte digest comparison to parent R7A;
- Runtime parent manifest and Workspace manifest parity;
- ZIP integrity, duplicate detection, fresh-extraction static validation, deterministic repack identity.

## Required Git-policy sentinels

```text
IGNORED    okcanvas-agent-runtime/.env.local
TRACKABLE  okcanvas-agent-runtime/.env.local.example
IGNORED    okcanvas-agent-runtime/.local/product.sqlite3
TRACKABLE  okcanvas-agent-runtime/clients/cli/dist/api-client.js
TRACKABLE  okcanvas-agent-runtime/docs/evidence/step091d-runtime-full-suite-partitions/partition-01.log
TRACKABLE  okcanvas-agent-runtime/okcanvas_agent_runtime/application/artifacts/service.py
TRACKABLE  okcanvas-agent-runtime/reference/upstream/openai-agents-python-0.19.0/.vscode/settings.json
IGNORED    okcanvas-agent-runtime/artifacts/blob.bin
IGNORED    .vscode/settings.json
IGNORED    okcanvas-agent-cli/dist/index.js
IGNORED    okcanvas-connectors/groupware-mcp-server/dist/pkg.js
IGNORED    node_modules/x/index.js
IGNORED    local-run.log
```

## Stop condition

R7A1 remains TEST_PENDING until deferred tests resume. Git metadata is statically validated, but current deterministic acceptance is not fabricated from parent evidence.
