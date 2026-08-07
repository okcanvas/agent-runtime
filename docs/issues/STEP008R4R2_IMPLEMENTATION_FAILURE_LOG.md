# STEP008R4R2 Implementation Failure Log

## Rule

Every failure discovered while implementing or packaging STEP008R4R2 is recorded here so that it is not repeated in a later conversation or host environment.

## F1 — Launcher registry current-record shape was guessed incorrectly

- Symptom: launcher registry validation rejected the new STEP091B1 current record.
- Cause: `required_current_records` was initially written as a path string instead of the existing `{kind, mode}` schema.
- Correction: inspected the registry schema and used the exact established object contract.
- Prevention: never infer registry record shape from names; inspect the validator and retained records first.

## F2 — Admission dependency was accidentally inserted into an unrelated lifecycle constructor

- Symptom: focused tests failed during initial dependency refactoring.
- Cause: a broad textual edit placed the new admission argument in the wrong constructor.
- Correction: reverted the unrelated lifecycle change and injected `GovernedRunAdmissionPort` only into read execution and approval execution services.
- Prevention: constructor changes must be applied by exact class/function context and followed immediately by focused import/construction tests.

## F3 — Evaluation type import introduced a circular import

- Symptom: Runtime import failed while loading the new typed Evaluation port.
- Cause: importing concrete Evaluation models through a package facade executed application imports recursively.
- Correction: moved leaf model references behind `TYPE_CHECKING` and string annotations.
- Prevention: application port modules may reference domain/leaf contract types but must not import an application package facade at runtime.

## F4 — Runtime HANDOFF rewrite removed identifiers retained by historical regression tests

- Symptom: full Runtime partitions failed historical documentation contract tests.
- Cause: the current HANDOFF was shortened and omitted retained Skill, Function Tool, Connector, Example and Issue identifiers.
- Correction: restored the exact retained identifiers while keeping the current STEP091B1 status.
- Prevention: current HANDOFF documents must preserve durable identifiers referenced by prior accepted contracts.

## F5 — Historical tests froze the previous current package filename

- Symptom: package-identity tests expected the STEP090R1 ZIP after the Runtime identity advanced.
- Cause: current-package assertions were located in tests named after historical Steps.
- Correction: changed only the current expectation to the STEP091B1 package filename; historical evidence and semantics remain untouched.
- Prevention: distinguish current-identity assertions from immutable historical-evidence assertions.

## F6 — Monolithic outer command exceeded the tool execution window

- Symptom: an outer command timed out while the partitioned Runtime suite continued.
- Cause: all 12 test partitions were launched under one bounded tool invocation.
- Correction: inspected generated evidence and resumed missing partitions individually.
- Prevention: long suites must use exact non-overlapping partitions with per-partition evidence and resumable execution.

## F7 — Historical R4R1 digest evidence was assumed to contain a Workspace version

- Symptom: the historical evidence retention test raised `KeyError: workspace_version`.
- Cause: the test inferred a field that was never present in the accepted evidence schema.
- Correction: validate only the fields actually recorded by the historical evidence: Workspace step, Runtime identity and equal before/after digest.
- Prevention: historical evidence tests must inspect the committed schema before asserting fields.

## F8 — New topology source assertion omitted the `self.` qualifiers

- Symptom: the test could not find the split-owner guard although the code contained it.
- Cause: the source assertion searched for `submission_store is not governed_admission` instead of the exact implementation `self.submission_store is not self.governed_admission`.
- Correction: align the test with the exact inspected source expression.
- Prevention: source-level contract assertions must copy exact code tokens rather than paraphrasing them.

## F9 — Workspace parent Runtime byte manifest was not regenerated after the intentional Runtime change

- Symptom: `test_parent_project_files_are_byte_identical` failed only for `okcanvas-agent-runtime.json`.
- Cause: the Workspace manifest was regenerated before the parent-project byte manifest.
- Correction: regenerate the Runtime parent-file manifest from `snapshot_files()` and then regenerate the Workspace manifest.
- Prevention: after an intentional parent project change, update parent manifest first and Workspace manifest second.

## F10 — Fresh Runtime gate exceeded one foreground tool-call window

- Symptom: the foreground Workspace Runtime gate was externally terminated during focused regression before writing final evidence.
- Cause: the gate legitimately takes longer than the bounded foreground tool invocation.
- Correction: run the exact same gate as a detached process, poll its evidence files, and verify return code, 25/25 state and unchanged source digest.
- Prevention: long deterministic gates must write progressive logs and final machine-readable evidence to external paths so they can be resumed or polled without rerunning Product work.

## F11 — Workspace retained Product check was read from the new Runtime top level

- Symptom: Workspace integration finished 28/29 with only `ambiguous_result_normalization_contract_exact=false`.
- Cause: STEP091B1 correctly retains the STEP090R1 acceptance under `step090r1_parent`, but the Workspace runner still looked for the retained normalization check in the new top-level STEP091B1 check set.
- Correction: read the Organization Context normalization check from `step090r1_parent.checks` while reading STEP091B1 storage checks from the new top level.
- Prevention: when a Runtime acceptance composes a parent acceptance, Workspace checks must follow the explicit parent evidence field rather than assume all historical checks are flattened.

## F12 — Workspace packager was invoked with a positional output path

- Symptom: `package_workspace.py` exited before packaging and reported that `--output` was required.
- Cause: the packager CLI contract was not inspected before invocation.
- Correction: invoke `python scripts/package_workspace.py --output <zip>`.
- Prevention: inspect `--help` or the parser before invoking project-owned packaging scripts.

## F13 — Supplied Runtime gate evidence was not cryptographically bound to the current Runtime tree

- Symptom: no test failed, but final Fresh review showed that the Workspace runner checked `source_unchanged=true` inside the supplied gate without comparing the gate's snapshot digest to the Runtime tree currently being accepted.
- Risk: valid evidence from a different Runtime tree could be supplied accidentally.
- Correction: bind `supplied_source_snapshot_digest` to the current pre-acceptance Runtime snapshot digest; direct execution records the same digest locally.
- Prevention: reusable subproject evidence must include and match an immutable source identity, not only a successful state and unchanged-before/after flag.
