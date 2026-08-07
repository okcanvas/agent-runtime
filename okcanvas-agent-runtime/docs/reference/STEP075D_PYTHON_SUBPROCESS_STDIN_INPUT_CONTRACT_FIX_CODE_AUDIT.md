# STEP075D code audit

## Audited baseline

STEP075C version 2.55.3 and its preserved Windows live failure were inspected from code and evidence. The run reached `tool.started`, emitted no `tool.failed`, and was normalized by the SDK as `UserError`.

## Confirmed defect

`SubprocessDockerCommandRunner._run()` supplied both `stdin=subprocess.PIPE` and `input=input_bytes` to `subprocess.run()`. Python rejects this before child-process creation. A direct real-process reproduction against the packaged implementation produced the exact `ValueError`.

The STEP075C mock accepted arbitrary kwargs and explicitly asserted the invalid combination, so it did not model the Python API contract.

## Implemented correction

- input-bearing calls: `input=input_bytes`, no `stdin` keyword;
- no-input calls: `stdin=subprocess.DEVNULL`, no `input` keyword;
- bounded `ValueError` conversion to `DOCKER_RUNNER_CONFIGURATION_INVALID` / `container.extract_snapshot` / `INVALID_ARGUMENT`;
- real child-process stdin echo regression;
- updated mock contract assertions.

## Security audit

No Product Sandbox capability changed. The tar archive, root materializer, non-root evidence reads, immutable selected-file hash verification, network-none container, no mounts/secrets/runtime pull, bounded output, forced cleanup and orphan reconciliation remain unchanged. Raw Python exception text and stdin bytes are not persisted.

## Validation

The authoritative counts and fresh ZIP results are recorded in `docs/evidence/STEP075D_VALIDATION.txt` and `docs/evidence/STEP075D_ACCEPTANCE.json`.
