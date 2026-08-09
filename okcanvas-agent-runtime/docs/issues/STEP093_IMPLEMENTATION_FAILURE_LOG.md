# STEP093 Implementation Failure Log

Step: `STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL`
Version: `2.77.0`
Validation policy: executable tests deferred by user until MinIO is prepared.

## F1 — Relationship GET could be silently incomplete

Code inspection found the Organization Context Example bounded detailed `relations` to 100 without publishing total/returned/truncated evidence. Relation-aware follow-up would therefore be unable to distinguish a complete relation set from a partial page.

Correction:
- Example GET publishes `relation_count`, `relations_returned_count`, `relations_truncated`;
- Connector validates these fields and fails closed on inconsistency;
- Runtime relation projection refuses truncated/incomplete evidence.

Prevention: any bounded collection used as authority for deterministic routing must publish completeness evidence.

## F2 — Runtime package metadata SOT drift inherited from STEP092

Code inspection found `core/baseline.py` at STEP092 / 2.76.0 while Runtime `pyproject.toml` still declared 2.75.0. STEP092 was TEST_PENDING, so the drift had not been closed by executable acceptance.

Correction: STEP093 aligns both executable baseline and package metadata at 2.77.0 and the STEP093 static contract validator checks both.

Prevention: current package metadata must be validated independently from executable baseline constants.

## F3 — Initial STEP093 acceptance copy retained STEP092 names/limitations

The first source copy referenced the STEP092 focused test filename, STEP092 package filename, and said relational follow-up was not implemented.

Correction: current STEP093 source uses the relation-aware test filename/package identity and marks the implemented capability accurately while keeping acceptance flags false.

Prevention: never treat mechanical Step-number replacement as a completed current acceptance source; inspect every identity, test target and limitation.

## F4 — Initial launcher registry edit shape was invalid

An intermediate edit used fields incompatible with the v2 launcher-registry schema. It was corrected before packaging to the canonical `records[]` objects and `required_current_records` pair contract.

Prevention: inspect the registry validator before modifying current launcher classification.

## F5 — Current Workspace runner still targeted STEP091D / old Connector identity

After adding STEP093/Connector STEP003 source, the generic Workspace acceptance runner still executed Runtime STEP091D and Connector `run_acceptance.py`, and expected Example 0.2.2.

Correction: the future current runner now targets Runtime STEP093, Connector STEP003, Example STEP003 and current relation-completeness E2E identities. It is source-prepared only and has not been executed.

Prevention: when a current subproject identity changes, update the Workspace current runner and cross-project identity assertions in the same change.

## F6 — New Workspace relation Live launcher initially violated canonical LF policy

- **Symptom:** `sh_run_workspace_step008r4r9_relation_live_acceptance.cmd` was first emitted with CRLF bytes even though the repository `.gitattributes` allows CRLF only for four retained historical Runtime launchers.
- **Cause:** the source-generation shell heredoc embedded explicit CRLF while preparing the future Windows Live launcher.
- **Correction:** rewrote the new launcher to canonical LF and retained the existing four historical CRLF exceptions unchanged.
- **Prevention:** every newly generated CMD must be checked against `.gitattributes` before manifest generation; never infer Windows line endings from the file extension.

## F7 — Focused Live route checker used an unhashable dict in a membership set

- **Symptom:** static source compilation succeeded, but the first focused Live route check would raise `TypeError` when evaluating `hint.get("relation_traversal") in {None, {}}` because a dict cannot be a set member.
- **Cause:** source-only harness authoring used a set literal for a nullable/dict shape check; AST/compile validation cannot detect this runtime expression error.
- **Correction:** replaced the set membership with tuple membership, `in (None, {})`.
- **Prevention:** future acceptance-harness static review must inspect executable predicate semantics in addition to AST compilation; source-prepared does not mean executable-accepted.
