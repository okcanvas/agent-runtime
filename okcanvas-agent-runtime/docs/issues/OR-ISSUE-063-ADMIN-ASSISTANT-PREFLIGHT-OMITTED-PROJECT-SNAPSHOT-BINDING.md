# OR-ISSUE-063 — Admin Assistant preflight omitted project snapshot binding

## Symptom

The new Admin Assistant preflight accepted `project_snapshot_id`, but the existing Admin governed-run preflight forwarded only the attachment slot to `RunSubmissionService.preflight`. A repository-analysis request could therefore route correctly while losing the immutable project snapshot binding at submission creation.

## Code-confirmed root cause

`AdminUseCases.preflight_governed_run` passed `attachment_slot_id=request.attachment_id` but did not pass `project_snapshot_slot_id=request.project_snapshot_id`, even though the protocol and submission service already supported that field.

## Impact

Admin callers could not preserve the immutable repository snapshot identity through the governed submission boundary. Service callers were not affected because their path already owned and forwarded the project snapshot.

## Correction

The Admin preflight now forwards `project_snapshot_slot_id=request.project_snapshot_id`. STEP083 Assistant tests exercise Agent-ID-free repository routing and the immutable snapshot-bound submission path.

## Recurrence gate

- `tests/test_step083_organization_assistant_main_agent_and_action_routing.py`;
- STEP083 Assistant routing validator;
- STEP083 integrated acceptance.
