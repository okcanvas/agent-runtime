
## F004 — Full Runtime pytest exceeded the execution window

- **Observed:** `python -m pytest -q` progressed without an observed assertion failure through approximately 31% and was terminated by the 300-second command execution limit.
- **Incorrect conclusion avoided:** The partial run was not recorded as a pass.
- **Correction:** Collect the exact Runtime test-file inventory and execute all files in deterministic bounded partitions, then retain each partition result as full-suite evidence.
- **Recurrence gate:** STEP008 completion requires every collected Runtime test file to appear in exactly one passing partition; a partial monolithic run is never accepted as full-suite evidence.

## F005 — Historical STEP032 output-contract count drift surfaced by full-suite partitioning

- **Observed:** Runtime full-suite partition 04 failed `tests/test_step032_agent_output_contract_runtime_registry_baseline.py::test_step032_registry_and_gateway_boundary`; the historical assertion expected 7 contracts while the current runtime returned 8.
- **Status at discovery:** Root cause not yet assigned. The current file and the immutable STEP007R1 source must be compared before any correction.
- **Incorrect correction prohibited:** Do not simply change `7` to `8` unless the registry lineage and current contract inventory prove that the historical test is stale rather than a product regression.
- **Recurrence gate:** Retain a current-baseline output-contract inventory assertion and keep historical tests from silently hard-coding a count that later accepted contracts legitimately increase.

## F006 — Full-suite partition 05 exposed five retained-regression failures

- **Observed:** 5 failures / 263 tests in partition 05.
- **Cases:** one HANDOFF retained-capability marker removed during STEP089 documentation rewrite; two historical agent-count assertions froze a pre-later-step catalog size; two sandbox policy tests expected version `1.3.0` while the committed current policy reported `1.2.0`.
- **Correction rule:** Compare every failing current file with the immutable STEP007R1 source and inspect the owning accepted step before modifying source or tests. Documentation loss introduced by STEP089 must be restored; pre-existing historical drift must be corrected at the owning invariant and covered by a current-baseline assertion.

## F007 — Runtime partition 06 reached 100% output but did not terminate

- **Observed:** The 40-file partition printed progress to 100% and one failure marker, but pytest did not emit its summary before the 300-second execution limit.
- **Incorrect conclusion avoided:** Progress output was not treated as successful completion.
- **Correction:** Repartition files 200–239 into two 20-file runs, then subdivide any failing or non-terminating half until the exact test is identified.
- **Recurrence gate:** Every full-suite partition must return exit code 0 and an explicit pytest summary; a 100% progress marker alone is insufficient.

## Full-suite closure

- F004 closed by eight exact non-overlapping partitions covering all 243 collected Runtime test files.
- F005 closed by separating historical STEP032 ownership assertions from the STEP089 complete current registry inventory.
- F006 closed by restoring HANDOFF retained identities, removing invalid historical catalog-size freezes, and aligning Sandbox policy/provider versions to their actual accepted lineages.
- F007 closed by splitting the non-terminating 40-file group into two terminating 20-file partitions.
- Final partitioned Runtime result: **1,006 passed, 243/243 files covered, zero duplicate files, zero missing files, all eight exit codes zero**.

## F008 — Workspace pytest command omitted the owned-test boundary

- **Observed:** Running `python -m pytest -q` at the Workspace root recursively collected independent parent-project tests, fixture repository tests and retained upstream reference tests, producing 269 collection errors from missing project-local import environments.
- **Root cause:** The command ignored the Workspace constitution that each project owns its own environment and tests.
- **Correction:** Run Workspace-owned tests only as `python -m pytest -q tests`; parent projects are validated by their own acceptance commands and isolated environments.
- **Recurrence gate:** Workspace acceptance must invoke only the Workspace `tests/` directory and must run parent acceptances explicitly rather than recursively collecting their suites.

## F009 — Monolithic Workspace STEP008 acceptance exceeded the command window

- **Observed:** `python scripts/run_workspace_step008_acceptance.py` exceeded the 300-second execution limit before returning a result.
- **Incorrect conclusion avoided:** The integration gate was not recorded as pass or fail without its final evidence.
- **Correction:** Re-run unbuffered in an interactive process and poll output so long-running parent acceptances can complete without losing stage diagnostics. If a stage itself hangs, isolate that exact child command.
- **Recurrence gate:** Workspace acceptance output must expose stage boundaries immediately and complete with an explicit evidence file and exit code.

## F010 — Wrong-scope pytest contaminated immutable reference trees with bytecode

- **Observed:** The F008 root-level pytest collection created 29 `*.pyc` files in nine `__pycache__` directories under the retained `openai-agents-python` reference. ReferenceCatalogService then correctly rejected the tree hash, causing Runtime architecture, focused regression and distribution startup checks to fail inside Workspace acceptance.
- **Root cause:** Python import side effects were allowed inside a reference tree that is part of an immutable hash contract.
- **Correction:** Remove generated cache/bytecode directories only, verify all four reference descriptors, and never collect tests recursively from the Workspace root.
- **Recurrence gate:** Workspace-owned tests remain scoped to `tests/`; parent/reference trees are invoked only through explicit project acceptance. Fresh ZIP acceptance must verify reference catalog integrity before promotion.

## F011 — Stage-marker instrumentation initially broke Python indentation

- **Observed:** A broad text replacement inserted the final-state marker into the early workspace-root failure branch and de-indented `output.parent`, causing an `IndentationError` before the acceptance runner could start.
- **Root cause:** A non-structural replacement targeted the first repeated output-write sequence rather than the final payload block.
- **Correction:** Restore the early failure branch explicitly, place the final marker only before the final output write, and compile the script before execution.
- **Recurrence gate:** Any acceptance-runner instrumentation change must pass `python -m py_compile` before being run or packaged.

## F012 — Diagnostic instrumentation intentionally invalidated manifests before rerun

- **Observed:** The stage-instrumented Workspace acceptance completed all child processes successfully but ended 19/21 because `workspace_unit_tests_passed` and `workspace_manifest_exact` observed the acceptance script and issue-log changes made after the previous manifest generation.
- **Root cause:** The manifest was correctly stale after diagnostic source/document changes.
- **Correction:** Preserve the stage markers, regenerate both affected parent manifests and the Workspace manifest, rerun Workspace-owned tests, then execute STEP008 acceptance again without further source changes.
- **Recurrence gate:** Final manifest generation occurs only after the last source/document edit and immediately before final Workspace tests and acceptance.

## F013 — In-place unit-test logging invalidated the manifest before the test ran

- **Observed:** Piping Workspace pytest output directly to `docs/evidence/WORKSPACE_STEP008_UNIT_TESTS.txt` created a new included file before `test_workspace_manifest_is_current` executed, so the otherwise passing suite ended 88/89.
- **Root cause:** Evidence capture mutated the identity domain before the identity test completed.
- **Correction:** Capture test output outside the Workspace, verify the suite, copy the completed log into the evidence directory, then regenerate manifests and rerun the final suite without modifying included files.
- **Recurrence gate:** Identity-sensitive test logs are never created inside the package tree until after that test run has completed.

## F014 — Fresh ZIP extraction command selected a workdir before creating it

- **Observed:** The first Fresh ZIP validation command asked the container to start in `/mnt/data/fresh_step008_validation/okcanvas-agent-platform` before the command itself had created and extracted that directory, so command startup failed with `ENOENT`.
- **Root cause:** Workdir validation occurs before shell commands execute.
- **Correction:** Extract the ZIP from an already existing directory first, then start validation commands from the extracted Workspace root. Background acceptance launch status is read from its explicit status file because the container wrapper may return a client error even when the detached process starts and completes.
- **Recurrence gate:** Fresh validation is always two-phase: (1) create/extract from an existing workdir; (2) execute tests from the verified extracted root.
