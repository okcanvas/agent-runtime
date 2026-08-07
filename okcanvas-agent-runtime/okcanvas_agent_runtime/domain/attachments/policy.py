from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.attachments.errors import AttachmentPolicyError


@dataclass(frozen=True)
class LocalAttachmentPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_attachments: int
    max_bytes: int
    allowed_media_types: tuple[str, ...]
    max_pdf_pages: int
    max_image_width: int
    max_image_height: int
    max_image_pixels: int
    image_detail: str
    slot_ttl_seconds: int
    remote_urls_allowed: bool
    provider_file_ids_allowed: bool
    raw_bytes_in_product_events: bool
    raw_bytes_in_artifacts: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "max_attachments": self.max_attachments,
            "max_bytes": self.max_bytes,
            "allowed_media_types": list(self.allowed_media_types),
            "max_pdf_pages": self.max_pdf_pages,
            "max_image_width": self.max_image_width,
            "max_image_height": self.max_image_height,
            "max_image_pixels": self.max_image_pixels,
            "image_detail": self.image_detail,
            "slot_ttl_seconds": self.slot_ttl_seconds,
            "remote_urls_allowed": self.remote_urls_allowed,
            "provider_file_ids_allowed": self.provider_file_ids_allowed,
            "raw_bytes_in_product_events": self.raw_bytes_in_product_events,
            "raw_bytes_in_artifacts": self.raw_bytes_in_artifacts,
            "policy_sha256": self.policy_sha256,
        }


class LocalAttachmentPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "attachments" / "policies" / "local-pdf-image-v1.json"

    def resolve(self) -> LocalAttachmentPolicy:
        path = self.path.resolve()
        expected_parent = (self.project_root / "specs" / "attachments" / "policies").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise AttachmentPolicyError("Local attachment policy is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentPolicyError("Local attachment policy is invalid JSON") from exc
        expected = {
            "schema_version", "policy_id", "version", "max_attachments", "max_bytes",
            "allowed_media_types", "max_pdf_pages", "max_image_width", "max_image_height",
            "max_image_pixels", "image_detail", "slot_ttl_seconds", "remote_urls_allowed",
            "provider_file_ids_allowed", "raw_bytes_in_product_events", "raw_bytes_in_artifacts",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise AttachmentPolicyError("Local attachment policy fields are not exact")
        if payload["schema_version"] != "okcanvas-local-attachment-policy-v1":
            raise AttachmentPolicyError("Unsupported local attachment policy schema")
        if payload["policy_id"] != "bounded-local-pdf-image-input-v1" or payload["version"] != "1.0.0":
            raise AttachmentPolicyError("Local attachment policy identity is invalid")
        if payload["max_attachments"] != 1:
            raise AttachmentPolicyError("STEP068 permits exactly one local attachment")
        if payload["allowed_media_types"] != ["application/pdf", "image/png", "image/jpeg"]:
            raise AttachmentPolicyError("STEP068 media type set is invalid")
        if payload["image_detail"] != "auto":
            raise AttachmentPolicyError("STEP068 image detail must be auto")
        for key in ("remote_urls_allowed", "provider_file_ids_allowed", "raw_bytes_in_product_events", "raw_bytes_in_artifacts"):
            if payload[key] is not False:
                raise AttachmentPolicyError(f"{key} must be false")
        for key in ("max_bytes", "max_pdf_pages", "max_image_width", "max_image_height", "max_image_pixels", "slot_ttl_seconds"):
            if not isinstance(payload[key], int) or isinstance(payload[key], bool) or payload[key] <= 0:
                raise AttachmentPolicyError(f"{key} must be a positive integer")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        values = dict(payload)
        values["allowed_media_types"] = tuple(payload["allowed_media_types"])
        return LocalAttachmentPolicy(
            **values,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
