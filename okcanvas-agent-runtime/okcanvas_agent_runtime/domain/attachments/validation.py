from __future__ import annotations

import hashlib
import re
import struct
import unicodedata
from pathlib import PurePath

from okcanvas_agent_runtime.domain.attachments.errors import AttachmentValidationError
from okcanvas_agent_runtime.domain.attachments.models import AttachmentMetadata
from okcanvas_agent_runtime.domain.attachments.policy import LocalAttachmentPolicy

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page\b")


def normalize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized or len(normalized) > 120 or _CONTROL_RE.search(normalized):
        raise AttachmentValidationError("Attachment filename must contain 1..120 safe characters")
    if PurePath(normalized).name != normalized or any(sep in normalized for sep in ("/", "\\")):
        raise AttachmentValidationError("Attachment filename must not contain a path")
    if normalized in {".", ".."} or normalized.startswith("."):
        raise AttachmentValidationError("Attachment filename is unsafe")
    return normalized


def validate_local_attachment(data: bytes, filename: str, policy: LocalAttachmentPolicy) -> AttachmentMetadata:
    safe_name = normalize_filename(filename)
    if not data or len(data) > policy.max_bytes:
        raise AttachmentValidationError(
            f"Attachment bytes must be 1..{policy.max_bytes}"
        )
    lower = safe_name.lower()
    if data.startswith(b"%PDF-"):
        if not lower.endswith(".pdf"):
            raise AttachmentValidationError("PDF content requires a .pdf filename")
        return _validate_pdf(data, safe_name, policy)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if not lower.endswith(".png"):
            raise AttachmentValidationError("PNG content requires a .png filename")
        return _validate_png(data, safe_name, policy)
    if data.startswith(b"\xff\xd8"):
        if not lower.endswith((".jpg", ".jpeg")):
            raise AttachmentValidationError("JPEG content requires a .jpg or .jpeg filename")
        return _validate_jpeg(data, safe_name, policy)
    raise AttachmentValidationError("Only PDF, PNG, and JPEG signatures are supported")


def _base(filename: str, media_type: str, input_kind: str, data: bytes, **extra: int | None) -> AttachmentMetadata:
    return AttachmentMetadata(
        filename=filename,
        media_type=media_type,  # type: ignore[arg-type]
        input_kind=input_kind,  # type: ignore[arg-type]
        content_sha256=hashlib.sha256(data).hexdigest(),
        byte_length=len(data),
        **extra,
    )


def _validate_pdf(data: bytes, filename: str, policy: LocalAttachmentPolicy) -> AttachmentMetadata:
    if b"%%EOF" not in data[-2048:]:
        raise AttachmentValidationError("PDF EOF marker is missing")
    if re.search(rb"/Encrypt\b", data):
        raise AttachmentValidationError("Encrypted or password-protected PDFs are not supported")
    page_count = len(_PDF_PAGE_RE.findall(data))
    if not 1 <= page_count <= policy.max_pdf_pages:
        raise AttachmentValidationError(
            f"PDF structural page count must be 1..{policy.max_pdf_pages}"
        )
    return _base(filename, "application/pdf", "input_file", data, page_count=page_count)


def _validate_png(data: bytes, filename: str, policy: LocalAttachmentPolicy) -> AttachmentMetadata:
    if len(data) < 33 or data[12:16] != b"IHDR":
        raise AttachmentValidationError("PNG IHDR is missing")
    width, height = struct.unpack(">II", data[16:24])
    if b"acTL" in data:
        raise AttachmentValidationError("Animated PNG is not supported")
    _validate_dimensions(width, height, policy)
    if b"IEND" not in data[-64:]:
        raise AttachmentValidationError("PNG IEND is missing")
    return _base(filename, "image/png", "input_image", data, width=width, height=height)


def _validate_jpeg(data: bytes, filename: str, policy: LocalAttachmentPolicy) -> AttachmentMetadata:
    if len(data) < 4 or not data.endswith(b"\xff\xd9"):
        raise AttachmentValidationError("JPEG end marker is missing")
    offset = 2
    width = height = None
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            raise AttachmentValidationError("JPEG segment length is truncated")
        segment_length = struct.unpack(">H", data[offset:offset + 2])[0]
        if segment_length < 2 or offset + segment_length > len(data):
            raise AttachmentValidationError("JPEG segment is invalid")
        if marker in sof_markers:
            if segment_length < 7:
                raise AttachmentValidationError("JPEG SOF segment is invalid")
            height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            break
        offset += segment_length
    if width is None or height is None:
        raise AttachmentValidationError("JPEG dimensions were not found")
    _validate_dimensions(width, height, policy)
    return _base(filename, "image/jpeg", "input_image", data, width=width, height=height)


def _validate_dimensions(width: int, height: int, policy: LocalAttachmentPolicy) -> None:
    if width <= 0 or height <= 0:
        raise AttachmentValidationError("Image dimensions must be positive")
    if width > policy.max_image_width or height > policy.max_image_height:
        raise AttachmentValidationError("Image dimensions exceed policy")
    if width * height > policy.max_image_pixels:
        raise AttachmentValidationError("Image pixel count exceeds policy")
