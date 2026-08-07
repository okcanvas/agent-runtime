# STEP008R4R7A1 Implementation Failure Log

```text
Step: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Version: 0.8.4-r7a1
Runtime Product modifications: 0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
```

## R7A1-ISSUE-001 — Root ignore intent was overridden by nested Runtime rule

**Failure mechanism:** root `.gitignore` deliberately did not globally ignore Runtime `clients/cli/dist`, but nested `okcanvas-agent-runtime/.gitignore` contained `dist/`, which recursively ignored the retained artifact for a fresh `git add .`.

**Correction:** add explicit Runtime negation rules for `clients/cli/dist/` and validate with `git check-ignore --no-index` from a fresh Git repository.

**Recurrence rule:** whenever an artifact is intentionally committed despite a generic ignore class, validate the effective merged Git ignore stack from repository root and nested `.gitignore` files.

**Status:** FIX_IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER.

## R7A1-ISSUE-002 — Global log/dist ignores would discard durable accepted artifacts

**Failure mechanism avoided:** a generic `*.log` would hide durable `docs/evidence/*.log`; a generic `**/dist/` would hide Runtime retained CLI dist.

**Correction:** ignore only package-manager diagnostic logs and known generated first-party dist directories; keep durable evidence and retained Runtime dist trackable.

**Recurrence rule:** Git hygiene rules must be based on ownership semantics, not only filename extensions or directory basenames.

**Status:** PREVENTED_BY_STATIC_POLICY.

## R7A1-ISSUE-003 — Cross-platform line-ending normalization can cause manifest/hash drift

**Failure mechanism avoided:** relying on Windows `core.autocrlf` could rewrite LF source/CMD files and invalidate deterministic package hashes. Conversely, forcing every CMD to CRLF would alter the accepted baseline where most CMD files are LF.

**Correction:** root `.gitattributes` sets LF as the canonical checkout for text, with four explicit retained Runtime CMD CRLF exceptions discovered from the accepted R7A ZIP.

**Recurrence rule:** line-ending policy must follow observed accepted bytes; do not apply platform-wide assumptions to all CMD files.

**Status:** STATIC_POLICY_IMPLEMENTED.

## R7A1-ISSUE-004 — `git check-ignore -v` was misread as the ignore decision

**Observed:** the first static validator reported `.env.local.example` and retained `clients/cli/dist` as ignored even though the verbose provenance line showed a negated `!` rule.

**Cause:** `git check-ignore -v` is a rule-provenance command. A matched negation can still produce a successful lookup status, so its return code alone is not the effective ignored/not-ignored decision.

**Correction:** use `git check-ignore --no-index -q` for the effective decision and a separate `-v` call only for provenance.

**Recurrence rule:** never infer effective ignore state from verbose rule lookup alone; separate decision from provenance.

**Status:** FIXED_STATIC_VALIDATOR.

## R7A1-ISSUE-005 — Wrong Runtime inventory helper excluded Product `artifacts` package

**Observed:** an intermediate parent-manifest regeneration produced 4,276 files instead of the retained 4,284-file policy and omitted eight real Product files under `okcanvas_agent_runtime/.../artifacts/`.

**Cause:** `scripts.step081_product_inventory.file_map()` treats any path component named `artifacts` as generated local residue. That helper is suitable for its STEP081 product-inventory purpose but is not the Workspace parent-project manifest policy.

**Correction:** discard the intermediate manifest and regenerate with Workspace `scripts.workspace_inventory.snapshot_files(..., workspace=False)`, which reproduces the parent-project inclusion contract and retains all Product artifact source files.

**Recurrence rule:** parent-file manifests must use the Workspace parent-project inventory SOT; never substitute a narrower historical Product inventory helper merely because its output shape looks compatible.

**Status:** FIXED_BEFORE_PACKAGE.

## R7A1-ISSUE-006 — Runtime `artifacts/` ignore rule hid eight Product source files

**Observed:** full-tree fresh Git scan classified eight files below `okcanvas_agent_runtime/adapters/storage/artifacts/` and `okcanvas_agent_runtime/application/artifacts/` as ignored.

**Cause:** Runtime `.gitignore` used unanchored `artifacts/` for the mutable Runtime root output directory, so Git applied it recursively to Product packages with the same basename.

**Correction:** change the mutable-output rule to `/artifacts/` and retain a full-tree ignored-existing-file scan.

**Status:** FIXED_STATIC_POLICY.

## R7A1-ISSUE-007 — Workspace `.vscode/` ignore rule hid retained upstream files

**Observed:** two retained `reference/upstream/.../.vscode/*.json` files were ignored in a fresh repository.

**Cause:** the newly strengthened root `.gitignore` used unanchored `.vscode/`, applying workspace-local editor policy recursively to vendored reference source.

**Correction:** anchor editor rules to `/.vscode/` and `/.idea/` at Workspace root.

**Recurrence rule:** local-development ignore rules must be scope-anchored when the repository intentionally vendors external source trees.

**Status:** FIXED_STATIC_POLICY.
