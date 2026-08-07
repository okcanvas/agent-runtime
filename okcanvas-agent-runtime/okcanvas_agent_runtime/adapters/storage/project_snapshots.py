from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from okcanvas_agent_runtime.adapters.storage.protected_payload.store import ProtectedPayloadKey

from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotIntegrityError, ProjectSnapshotNotFound
from okcanvas_agent_runtime.domain.project_snapshots.models import PreparedProjectSnapshot, ProjectSnapshotMetadata, ProjectSnapshotRecord, ProtectedProjectSnapshotBinding
from okcanvas_agent_runtime.domain.project_snapshots.policy import ProjectSnapshotPolicy
from okcanvas_agent_runtime.domain.project_snapshots.validation import validate_project_snapshot_zip


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class EncryptedProjectSnapshotStore:
    algorithm = "AES-256-GCM"

    def __init__(
        self,
        root: str | Path,
        key: ProtectedPayloadKey,
        policy: ProjectSnapshotPolicy,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.policy = policy
        self._key = key.derive_subkey(b"okcanvas-project-snapshot-store-v1")
        self.key_id = hashlib.sha256(self._key).hexdigest()[:16]

    def initialize(self) -> None:
        for path in (self.root / "slots", self.root / "bound"):
            path.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() or not path.is_dir():
                raise ProjectSnapshotIntegrityError("Project snapshot storage root is unsafe")
            try:
                path.chmod(0o700)
            except OSError:
                pass

    def create_slot(self, data: bytes, filename: str) -> ProjectSnapshotRecord:
        self.initialize()
        self.cleanup_expired_slot_refs()
        metadata = validate_project_snapshot_zip(data, filename, self.policy)
        created_at = _now()
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=self.policy.slot_ttl_seconds)
        ).isoformat().replace("+00:00", "Z")
        return self._write_record(
            record_ref=f"project_snapshot_slot_{uuid.uuid4().hex}",
            record_type="slot",
            data=data,
            metadata=metadata,
            created_at=created_at,
            expires_at=expires_at,
            submission_id=None,
        )

    def inspect_slot(self, slot_ref: str) -> ProjectSnapshotRecord:
        record, data = self._read_record(slot_ref, expected_type="slot")
        if record.expires_at is None or datetime.fromisoformat(
            record.expires_at.replace("Z", "+00:00")
        ) <= datetime.now(UTC):
            self.delete(slot_ref)
            raise ProjectSnapshotIntegrityError("Project snapshot upload slot has expired")
        validated = validate_project_snapshot_zip(data, record.metadata.filename, self.policy)
        if validated != record.metadata:
            raise ProjectSnapshotIntegrityError("Project snapshot slot content no longer matches metadata")
        return record

    def bind_slot(
        self,
        slot_ref: str,
        submission_id: str,
    ) -> tuple[ProjectSnapshotRecord, ProtectedProjectSnapshotBinding]:
        slot, data = self._read_record(slot_ref, expected_type="slot")
        if slot.expires_at is None or datetime.fromisoformat(
            slot.expires_at.replace("Z", "+00:00")
        ) <= datetime.now(UTC):
            self.delete(slot_ref)
            raise ProjectSnapshotIntegrityError("Project snapshot upload slot has expired")
        validated = validate_project_snapshot_zip(data, slot.metadata.filename, self.policy)
        if validated != slot.metadata:
            raise ProjectSnapshotIntegrityError("Project snapshot slot content no longer matches metadata")
        bound = self._write_record(
            record_ref=f"project_snapshot_{uuid.uuid4().hex}",
            record_type="bound",
            data=data,
            metadata=slot.metadata,
            created_at=_now(),
            expires_at=None,
            submission_id=submission_id,
        )
        self.delete(slot_ref)
        return bound, ProtectedProjectSnapshotBinding(
            project_snapshot_ref=bound.record_ref,
            encrypted_file_sha256=bound.file_sha256,
            encrypted_byte_length=bound.envelope_byte_length,
            encryption_key_id=bound.key_id,
            filename=bound.metadata.filename,
            archive_sha256=bound.metadata.archive_sha256,
            archive_byte_length=bound.metadata.archive_byte_length,
            snapshot_sha256=bound.metadata.snapshot_sha256,
            file_count=bound.metadata.file_count,
            total_bytes=bound.metadata.total_bytes,
        )

    def read_bound(
        self,
        binding: ProtectedProjectSnapshotBinding,
        submission_id: str,
    ) -> PreparedProjectSnapshot:
        record, data = self._read_record(binding.project_snapshot_ref, expected_type="bound")
        if record.submission_id != submission_id:
            raise ProjectSnapshotIntegrityError("Project snapshot submission binding does not match")
        if (
            record.file_sha256 != binding.encrypted_file_sha256
            or record.envelope_byte_length != binding.encrypted_byte_length
            or record.key_id != binding.encryption_key_id
            or record.metadata.filename != binding.filename
            or record.metadata.archive_sha256 != binding.archive_sha256
            or record.metadata.archive_byte_length != binding.archive_byte_length
            or record.metadata.snapshot_sha256 != binding.snapshot_sha256
            or record.metadata.file_count != binding.file_count
            or record.metadata.total_bytes != binding.total_bytes
        ):
            raise ProjectSnapshotIntegrityError("Project snapshot encrypted binding does not match")
        validated = validate_project_snapshot_zip(data, record.metadata.filename, self.policy)
        if validated != record.metadata:
            raise ProjectSnapshotIntegrityError("Project snapshot content no longer matches validated metadata")
        return PreparedProjectSnapshot(metadata=record.metadata, archive=data)

    def delete(self, record_ref: str) -> bool:
        for record_type in ("slot", "bound"):
            try:
                path = self._path(record_ref, record_type=record_type, require_exists=False)
            except ProjectSnapshotIntegrityError:
                continue
            if path.exists():
                path.unlink()
                return True
        return False

    def slot_exists(self, slot_ref: str) -> bool:
        try:
            return self._path(slot_ref, record_type="slot", require_exists=False).is_file()
        except ProjectSnapshotIntegrityError:
            return False

    def cleanup_expired_slots(self) -> int:
        return len(self.cleanup_expired_slot_refs())

    def cleanup_expired_slot_refs(self) -> tuple[str, ...]:
        self.initialize()
        deleted: list[str] = []
        for path in sorted((self.root / "slots").glob("project_snapshot_slot_*.json")):
            if path.is_symlink():
                raise ProjectSnapshotIntegrityError("Project snapshot slot symbolic links are forbidden")
            record_ref = path.stem
            try:
                record, _ = self._read_record(record_ref, expected_type="slot")
                if record.expires_at is None:
                    continue
                expires_at = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
            except (ProjectSnapshotIntegrityError, OSError, ValueError):
                continue
            if expires_at <= datetime.now(UTC) and self.delete(record_ref):
                deleted.append(record_ref)
        return tuple(deleted)

    def _write_record(
        self,
        *,
        record_ref: str,
        record_type: str,
        data: bytes,
        metadata: ProjectSnapshotMetadata,
        created_at: str,
        expires_at: str | None,
        submission_id: str | None,
    ) -> ProjectSnapshotRecord:
        path = self._path(record_ref, record_type=record_type, require_exists=False)
        if path.exists():
            raise ProjectSnapshotIntegrityError("Project snapshot record already exists")
        aad_payload = {
            "schema_version": "okcanvas-project-snapshot-aad-v1",
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
            "schema_version": "okcanvas-project-snapshot-envelope-v1",
            "record_ref": record_ref,
            "record_type": record_type,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "created_at": created_at,
            "expires_at": expires_at,
            "submission_id": submission_id,
            "metadata": metadata.to_dict(),
            "aad": aad_payload,
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }
        encoded = _canonical(envelope) + b"\n"
        maximum = int(self.policy.max_archive_bytes * 1.5) + 1_000_000
        if len(encoded) > maximum:
            raise ProjectSnapshotIntegrityError("Encrypted project snapshot envelope exceeds bounded size")
        temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        return ProjectSnapshotRecord(
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

    def _read_record(
        self,
        record_ref: str,
        *,
        expected_type: str,
    ) -> tuple[ProjectSnapshotRecord, bytes]:
        path = self._path(record_ref, record_type=expected_type, require_exists=True)
        raw = path.read_bytes()
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectSnapshotIntegrityError("Project snapshot envelope is invalid JSON") from exc
        expected_keys = {
            "schema_version", "record_ref", "record_type", "key_id", "algorithm",
            "created_at", "expires_at", "submission_id", "metadata", "aad",
            "nonce_b64", "ciphertext_b64",
        }
        if not isinstance(envelope, dict) or set(envelope) != expected_keys:
            raise ProjectSnapshotIntegrityError("Project snapshot envelope fields are invalid")
        if (
            envelope["schema_version"] != "okcanvas-project-snapshot-envelope-v1"
            or envelope["record_ref"] != record_ref
            or envelope["record_type"] != expected_type
            or envelope["key_id"] != self.key_id
            or envelope["algorithm"] != self.algorithm
        ):
            raise ProjectSnapshotIntegrityError("Project snapshot envelope identity does not match")
        metadata_raw = envelope.get("metadata")
        if not isinstance(metadata_raw, dict):
            raise ProjectSnapshotIntegrityError("Project snapshot metadata is invalid")
        try:
            metadata = ProjectSnapshotMetadata.from_dict(metadata_raw)
        except (TypeError, ValueError) as exc:
            raise ProjectSnapshotIntegrityError("Project snapshot metadata contract is invalid") from exc
        expected_aad = {
            "schema_version": "okcanvas-project-snapshot-aad-v1",
            "record_ref": record_ref,
            "record_type": expected_type,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "created_at": envelope["created_at"],
            "expires_at": envelope["expires_at"],
            "submission_id": envelope["submission_id"],
            "metadata": metadata.to_dict(),
        }
        if envelope.get("aad") != expected_aad:
            raise ProjectSnapshotIntegrityError("Project snapshot AAD identity does not match")
        try:
            nonce = base64.urlsafe_b64decode(str(envelope["nonce_b64"]).encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(str(envelope["ciphertext_b64"]).encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ProjectSnapshotIntegrityError("Project snapshot envelope encoding is invalid") from exc
        if len(nonce) != 12:
            raise ProjectSnapshotIntegrityError("Project snapshot nonce is invalid")
        try:
            data = AESGCM(self._key).decrypt(nonce, ciphertext, _canonical(expected_aad))
        except InvalidTag as exc:
            raise ProjectSnapshotIntegrityError("Project snapshot authentication failed") from exc
        if (
            hashlib.sha256(data).hexdigest() != metadata.archive_sha256
            or len(data) != metadata.archive_byte_length
        ):
            raise ProjectSnapshotIntegrityError("Project snapshot archive identity does not match")
        return ProjectSnapshotRecord(
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
        prefix = "project_snapshot_slot_" if record_type == "slot" else "project_snapshot_"
        if not record_ref.startswith(prefix) or len(record_ref) != len(prefix) + 32:
            raise ProjectSnapshotIntegrityError("Project snapshot reference is invalid")
        try:
            int(record_ref[len(prefix):], 16)
        except ValueError as exc:
            raise ProjectSnapshotIntegrityError("Project snapshot reference is invalid") from exc
        directory = self.root / ("slots" if record_type == "slot" else "bound")
        path = (directory / f"{record_ref}.json").resolve()
        if path.parent != directory.resolve() or path.is_symlink():
            raise ProjectSnapshotIntegrityError("Project snapshot path is unsafe")
        if require_exists and not path.is_file():
            raise ProjectSnapshotNotFound(f"Project snapshot not found: {record_ref}")
        return path
