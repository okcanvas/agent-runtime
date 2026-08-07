from __future__ import annotations


class AttachmentError(RuntimeError):
    pass


class AttachmentPolicyError(AttachmentError):
    pass


class AttachmentValidationError(AttachmentError):
    pass


class AttachmentIntegrityError(AttachmentError):
    pass


class AttachmentNotFound(AttachmentError):
    pass
