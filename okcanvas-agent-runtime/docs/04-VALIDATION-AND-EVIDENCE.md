# Validation and Evidence

## Evidence classes

- `SOURCE`: exact inspected path, version, or hash.
- `COMMAND`: command data emitted by the Codex CLI JSONL stream.
- `TEST`: collected test count and assertion result.
- `ARTIFACT`: file path, size, SHA-256, and producing command.
- `OBSERVATION`: readiness, event sequence, thread ID, or runtime state.

Model-generated prose is never an evidence class.

## STEP002 evidence

- immutable upstream reference verification;
- fixture source tree SHA-256;
- expected failing fixture test showing `15000 != 25000`;
- 35 deterministic runtime tests;
- Codex Tool construction contract with test doubles;
- fail-closed local `codex-doctor` output;
- source ZIP extraction and repeated validation.

Live model and Codex CLI evidence is intentionally absent until `scripts/run_step002_live_acceptance.py` succeeds in a connected environment.
