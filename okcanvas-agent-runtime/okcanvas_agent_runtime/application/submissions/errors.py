from __future__ import annotations


class RunSubmissionError(RuntimeError):
    code = "RUN_SUBMISSION_ERROR"


class RunSubmissionPolicyError(RunSubmissionError):
    code = "RUN_SUBMISSION_POLICY_INVALID"


class RunSubmissionValidationError(RunSubmissionError):
    code = "RUN_SUBMISSION_INVALID"


class RunSubmissionAuthorityError(RunSubmissionError):
    code = "RUN_SUBMISSION_AUTHORITY_REQUIRED"


class RunSubmissionIdempotencyConflict(RunSubmissionError):
    code = "RUN_SUBMISSION_IDEMPOTENCY_CONFLICT"


class RunSubmissionNotFound(RunSubmissionError):
    code = "RUN_SUBMISSION_NOT_FOUND"


class RunSubmissionConfirmationError(RunSubmissionError):
    code = "RUN_SUBMISSION_CONFIRMATION_INVALID"


class RunSubmissionStateError(RunSubmissionError):
    code = "RUN_SUBMISSION_STATE_INVALID"


class RunSubmissionIntegrityError(RunSubmissionError):
    code = "RUN_SUBMISSION_INTEGRITY_FAILED"
