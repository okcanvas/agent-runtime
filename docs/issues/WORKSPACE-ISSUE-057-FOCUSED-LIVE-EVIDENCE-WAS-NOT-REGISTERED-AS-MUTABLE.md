# WORKSPACE-ISSUE-057 — Focused Live evidence was not registered as mutable

The relation and cross-domain focused Windows Live harnesses write canonical output files under `docs/evidence/`, but those two paths were absent from `scripts/workspace_inventory.py::MUTABLE_ACCEPTANCE_EVIDENCE`.

That meant running a focused Live gate after extraction could add a local acceptance output to the Workspace file inventory even though acceptance evidence is intentionally mutable and must not change immutable source/package identity.

R10E explicitly registers exactly these two generated evidence files:

- `docs/evidence/WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE.json`
- `docs/evidence/WORKSPACE_STEP008R4R10_CROSS_DOMAIN_LIVE_ACCEPTANCE.json`

No wildcard or filename fallback was added. Retained immutable user-reported evidence uses a separate filename and remains included in the package/manifest.
