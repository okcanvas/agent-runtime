# OR-ISSUE-097 — Historical Sandbox and Agent catalog assertions drifted

## State

CLOSED_BY_STEP089

## Evidence

The immutable STEP007R1 source contained three invalid historical invariants:

1. STEP073/STEP074 asserted a 32-Agent current catalog and then asserted that removing the one Sandbox Agent left 29 Agents. The actual arithmetic and catalog lineage leave 31 because two later accepted Organization Agents were added.
2. STEP074/STEP075 asserted Sandbox policy version `1.3.0`, while the committed policy, parser, STEP075/STEP075A/STEP075B/STEP075C acceptance scripts and lineage prove that the policy intentionally remained `1.2.0`. Only the Docker provider advanced to `1.3.0` in STEP075C.
3. The STEP089 HANDOFF rewrite omitted the retained `document-review-v1` identity required by a prior service-client regression.

## Root cause

Historical tests froze total current catalog sizes and copied a provider version into a distinct policy contract. The STEP089 HANDOFF rewrite also replaced rather than retained the accepted identity ledger.

## Correction

- Historical Sandbox tests continue to prove that every non-Sandbox Agent has `workspace_access=none`, without freezing a count that later accepted Agents legitimately increase.
- Policy assertions use the committed and parser-enforced `1.2.0`; provider assertions remain `1.3.0`.
- The retained product identity section, including `document-review-v1`, and the retained `OR-ISSUE-091` corrective lineage are restored to HANDOFF.

## Recurrence gate

- Current-baseline tests own exact current catalog inventory.
- Historical tests assert retained ownership and safety properties, not future-extensible total counts.
- Distinct policy/provider versions must be asserted from their own accepted contract lineage.
- Handoff rewrites must preserve the retained product identity ledger.
