from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey

from okcanvas_agent_runtime.domain.attachments.errors import AttachmentIntegrityError, AttachmentNotFound
from okcanvas_agent_runtime.domain.attachments.models import AttachmentMetadata, AttachmentRecord, PreparedLocalAttachment, ProtectedAttachmentBinding
from okcanvas_agent_runtime.domain.attachments.policy import LocalAttachmentPolicy
from okcanvas_agent_runtime.domain.attachments.validation import validate_local_attachment


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class EncryptedLocalAttachmentStore:
    algorithm = "AES-256-GCM"

    def __init__(self, root: str | Path, root_key: ProtectedPayloadKey, policy: LocalAttachmentPolicy) -> None:
        self.root = Path(root).expanduser().resolve()
        self.policy = policy
        raw = root_key.derive_subkey(b"okcanvas-local-attachment-store-v1")
        self._key = raw
        self.key_id = hashlib.sha256(raw).hexdigest()[:16]

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise AttachmentIntegrityError("Attachment root must be a real directory")
        for name in ("slots", "bound"):
            directory = self.root / name
            directory.mkdir(exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise AttachmentIntegrityError("Attachment storage directory is unsafe")

    def create_slot(self, data: bytes, filename: str) -> AttachmentRecord:
        self.initialize()
        self.cleanup_expired_slot_refs()
        metadata = validate_local_attachment(data, filename, self.policy)
        created_at = _now()
        expires_at = (datetime.now(UTC) + timedelta(seconds=self.policy.slot_ttl_seconds)).isoformat().replace("+00:00", "Z")
        return self._write_record(
            record_ref=f"attachment_slot_{uuid.uuid4().hex}",
            record_type="slot",
            data=data,
            metadata=metadata,
            created_at=created_at,
            expires_at=expires_at,
            submission_id=None,
        )

    def inspect_slot(self, slot_ref: str) -> AttachmentRecord:
        slot, _ = self._read_record(slot_ref, expected_type="slot")
        if slot.expires_at is None or datetime.fromisoformat(slot.expires_at.replace("Z", "+00:00")) <= datetime.now(UTC):
            self.delete(slot_ref)
            raise AttachmentIntegrityError("Attachment upload slot has expired")
        return slot

    def bind_slot(self, slot_ref: str, submission_id: str) -> tuple[AttachmentRecord, ProtectedAttachmentBinding]:
        slot, data = self._read_record(slot_ref, expected_type="slot")
        if slot.expires_at is None or datetime.fromisoformat(slot.expires_at.replace("Z", "+00:00")) <= datetime.now(UTC):
            self.delete(slot_ref)
            raise AttachmentIntegrityError("Attachment upload slot has expired")
        bound = self._write_record(
            record_ref=f"attachment_{uuid.uuid4().hex}",
            record_type="bound",
            data=data,
            metadata=slot.metadata,
            created_at=_now(),
            expires_at=None,
            submission_id=submission_id,
        )
        self.delete(slot_ref)
        return bound, ProtectedAttachmentBinding(
            attachment_ref=bound.record_ref,
            encrypted_file_sha256=bound.file_sha256,
            encrypted_byte_length=bound.envelope_byte_length,
            encryption_key_id=bound.key_id,
            metadata=bound.metadata,
        )

    def read_bound(self, binding: ProtectedAttachmentBinding, submission_id: str) -> PreparedLocalAttachment:
        record, data = self._read_record(binding.attachment_ref, expected_type="bound")
        if record.submission_id != submission_id:
            raise AttachmentIntegrityError("Attachment submission binding does not match")
        if record.file_sha256 != binding.encrypted_file_sha256 or record.envelope_byte_length != binding.encrypted_byte_length:
            raise AttachmentIntegrityError("Attachment encrypted file binding does not match")
        if record.key_id != binding.encryption_key_id or record.metadata != binding.metadata:
            raise AttachmentIntegrityError("Attachment metadata binding does not match")
        validated = validate_local_attachment(data, record.metadata.filename, self.policy)
        if validated != record.metadata:
            raise AttachmentIntegrityError("Attachment content no longer matches validated metadata")
        return PreparedLocalAttachment(metadata=record.metadata, data=data)

    def delete(self, record_ref: str) -> bool:
        for record_type in ("slot", "bound"):
            try:
                path = self._path(record_ref, record_type=record_type, require_exists=False)
            except AttachmentIntegrityError:
                continue
            if path.exists():
                path.unlink()
                return True
        return False

    def slot_exists(self, slot_ref: str) -> bool:
        try:
            return self._path(slot_ref, record_type="slot", require_exists=False).is_file()
        except AttachmentIntegrityError:
            return False

    def cleanup_expired_slots(self) -> int:
        return len(self.cleanup_expired_slot_refs())

    def cleanup_expired_slot_refs(self) -> tuple[str, ...]:
        self.initialize()
        deleted: list[str] = []
        for path in sorted((self.root / "slots").glob("attachment_slot_*.json")):
            if path.is_symlink():
                raise AttachmentIntegrityError("Attachment slot symbolic links are forbidden")
            record_ref = path.stem
            try:
                record, _ = self._read_record(record_ref, expected_type="slot")
                if record.expires_at is None:
                    continue
                expires_at = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
            except (AttachmentIntegrityError, OSError, ValueError):
                continue
            if expires_at <= datetime.now(UTC) and self.delete(record_ref):
                deleted.append(record_ref)
        return tuple(deleted)

    def _write_record(self, *, record_ref: str, record_type: str, data: bytes, metadata: AttachmentMetadata, created_at: str, expires_at: str | None, submission_id: str | None) -> AttachmentRecord:
        path = self._path(record_ref, record_type=record_type, require_exists=False)
        if path.exists():
            raise AttachmentIntegrityError("Attachment record already exists")
        aad_payload = {
            "schema_version": "okcanvas-local-attachment-aad-v1",
            "record_ref": record_ref,
            "record_type": record_type,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "created_at": created_at,
            "expires_at": expires_at,
            "submission_id": submission_id,
            "metadata": metadata.to_dict(),
        }
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, data, _canonical(aad_payload))
        envelope = {
            "schema_version": "okcanvas-local-attachment-envelope-v1",
            **{key: aad_payload[key] for key in ("record_ref", "record_type", "key_id", "algorithm", "created_at", "expires_at", "submission_id")},
            "metadata": metadata.to_dict(),
            "aad": aad_payload,
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }
        encoded = _canonical(envelope) + b"\n"
        max_envelope = int(self.policy.max_bytes * 1.5) + 64_000
        if len(encoded) > max_envelope:
            raise AttachmentIntegrityError("Encrypted attachment envelope exceeds bounded size")
        temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        return AttachmentRecord(
            record_ref=record_ref,
            record_type=record_type,  # type: ignore[arg-type]
            file_sha256=hashlib.sha256(encoded).hexdigest(),
            envelope_byte_length=len(encoded),
            key_id=self.key_id,
            created_at=created_at,
            expires_at=expires_at,
            submission_id=submission_id,
            metadata=metadata,
        )

    def _read_record(self, record_ref: str, *, expected_type: str) -> tuple[AttachmentRecord, bytes]:
        path = self._path(record_ref, record_type=expected_type, require_exists=True)
        raw = path.read_bytes()
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentIntegrityError("Attachment envelope is invalid JSON") from exc
        expected_keys = {
            "schema_version", "record_ref", "record_type", "key_id", "algorithm", "created_at",
            "expires_at", "submission_id", "metadata", "aad", "nonce_b64", "ciphertext_b64",
        }
        if not isinstance(envelope, dict) or set(envelope) != expected_keys:
            raise AttachmentIntegrityError("Attachment envelope fields are invalid")
        if envelope["schema_version"] != "okcanvas-local-attachment-envelope-v1" or envelope["record_ref"] != record_ref or envelope["record_type"] != expected_type:
            raise AttachmentIntegrityError("Attachment envelope identity does not match")
        if envelope["key_id"] != self.key_id or envelope["algorithm"] != self.algorithm:
            raise AttachmentIntegrityError("Attachment encryption identity does not match")
        metadata_raw = envelope["metadata"]
        if not isinstance(metadata_raw, dict):
            raise AttachmentIntegrityError("Attachment metadata is invalid")
        try:
            metadata = AttachmentMetadata(**metadata_raw)
        except (TypeError, ValueError) as exc:
            raise AttachmentIntegrityError("Attachment metadata contract is invalid") from exc
        aad_payload = envelope["aad"]
        expected_aad = {
            "schema_version": "okcanvas-local-attachment-aad-v1",
            "record_ref": record_ref,
            "record_type": expected_type,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "created_at": envelope["created_at"],
            "expires_at": envelope["expires_at"],
            "submission_id": envelope["submission_id"],
            "metadata": metadata.to_dict(),
        }
        if aad_payload != expected_aad:
            raise AttachmentIntegrityError("Attachment AAD identity does not match")
        try:
            nonce = base64.urlsafe_b64decode(str(envelope["nonce_b64"]).encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(str(envelope["ciphertext_b64"]).encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise AttachmentIntegrityError("Attachment envelope encoding is invalid") from exc
        if len(nonce) != 12:
            raise AttachmentIntegrityError("Attachment nonce is invalid")
        try:
            data = AESGCM(self._key).decrypt(nonce, ciphertext, _canonical(expected_aad))
        except InvalidTag as exc:
            raise AttachmentIntegrityError("Attachment authentication failed") from exc
        if hashlib.sha256(data).hexdigest() != metadata.content_sha256 or len(data) != metadata.byte_length:
            raise AttachmentIntegrityError("Attachment plaintext identity does not match")
        return AttachmentRecord(
            record_ref=record_ref,
            record_type=expected_type,  # type: ignore[arg-type]
            file_sha256=hashlib.sha256(raw).hexdigest(),
            envelope_byte_length=len(raw),
            key_id=self.key_id,
            created_at=str(envelope["created_at"]),
            expires_at=str(envelope["expires_at"]) if envelope["expires_at"] is not None else None,
            submission_id=str(envelope["submission_id"]) if envelope["submission_id"] is not None else None,
            metadata=metadata,
        ), data

    def _path(self, record_ref: str, *, record_type: str, require_exists: bool) -> Path:
        prefix = "attachment_slot_" if record_type == "slot" else "attachment_"
        if not record_ref.startswith(prefix) or len(record_ref) != len(prefix) + 32:
            raise AttachmentIntegrityError("Attachment reference is invalid")
        try:
            int(record_ref[len(prefix):], 16)
        except ValueError as exc:
            raise AttachmentIntegrityError("Attachment reference is invalid") from exc
        directory = self.root / ("slots" if record_type == "slot" else "bound")
        path = (directory / f"{record_ref}.json").resolve()
        if path.parent != directory.resolve() or path.is_symlink():
            raise AttachmentIntegrityError("Attachment path is unsafe")
        if require_exists and not path.is_file():
            raise AttachmentNotFound(f"Attachment not found: {record_ref}")
        return path
