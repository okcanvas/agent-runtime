# STEP008R4R10E implementation failure log

- User Windows focused cross-domain Live returned 19/19 PASSED and proved the intended Organization → Calendar → Notice behavior.
- Full evidence inspection found identity contradiction: CLI executed Runtime 2.78.2 while evidence footer claimed Workspace R10C, Runtime STEP094R1, version 2.78.1.
- R10D package inspection confirmed its canonical current baseline was R10D / STEP094R2 / 2.78.2, so the user run came from a mixed/stale Workspace SOT tree rather than the immutable R10D package as a whole.
- Root cause in acceptance governance: focused harness trusted Workspace current-baseline labels without independently comparing them to executable Runtime identity or live Service version.
- Corrective action: Workspace-only R10E provenance gate. Runtime Product source remains unchanged.
- No helper alias/fallback/compatibility shim was added.
- No executable tests were run while preparing R10E; focused Windows Live must be rerun from a clean R10E tree.
- Static inventory review found the R9 relation and R10 cross-domain focused Live output files were not explicitly registered as mutable acceptance evidence. R10E adds exactly those two paths; no wildcard/fallback exclusion is used. See WORKSPACE-ISSUE-057.
