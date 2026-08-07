# STEP075G Product-owned deterministic evidence completion

## Identity

- Step: `STEP075G_PRODUCT_OWNED_DETERMINISTIC_EVIDENCE_COMPLETION`
- Version: `2.55.7`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Input evidence

STEP075F Windows live proved the full Sandbox lifecycle but failed after a separate no-tool correction model call. The run used three model calls and one Sandbox Tool call, retained complete verified evidence in memory, then failed with `ANSWER_COMPLETENESS_FAILED` because the repaired structured output still omitted exact evidence requirements.

## Goal

Remove probabilistic model repair from a deterministic evidence-completion problem. Complete exact evidence requirements directly from the single immutable, hash-verified `SandboxProjectReadonlyInspectOutput` before Artifact registration.

## Product flow

1. Run the existing read-only Sandbox Agent and one Sandbox Tool call.
2. Validate the structured `CodingAgentResult` against exact fragments derived from Tool evidence.
3. If already complete, register it unchanged.
4. If incomplete and all requirements are derivable, append one bounded `CONFIRMED` finding containing the exact fragments and repository-relative line evidence.
5. Remove evidence-backed paths from `unverified`.
6. Re-run the same validator.
7. Fail closed with `ANSWER_COMPLETENESS_FAILED` if completeness still fails.

## Bounds

- additional model calls: `0`
- additional Tool calls: `0`
- exact fragments: maximum `20`
- evidence references: maximum `20`
- findings: maximum `100`; the Product preserves the first `99` and reserves one slot for exact evidence when necessary
- finding detail: maximum `4,000` characters

## Security and persistence

No Docker, tar, tmpfs, snapshot, hash-domain, network, Shell, Apply Patch, Skill, mount, secret, or cleanup policy changes. Lifecycle Events contain only strategy, counts and booleans. Raw request, Tool evidence, draft and completed output are not persisted in completeness Events.

## Acceptance

Deterministic acceptance must prove:

- the STEP075F Windows failure is recorded exactly;
- exact formula and constant assignment are inserted from verified evidence;
- evidence-backed paths are removed from `unverified`;
- the gateway performs no second `Runner.run` call;
- no `agent.output.repair.*` Event is emitted;
- completion Events report zero added model calls and no Tool replay;
- non-derivable exact requirements fail closed;
- all historical Sandbox, Skill, trace, service, Node and Reference gates remain green.
