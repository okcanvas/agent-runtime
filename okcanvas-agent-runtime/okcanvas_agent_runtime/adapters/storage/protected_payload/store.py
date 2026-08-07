from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from okcanvas_agent_runtime.application.submissions.protected_payload_errors import ProtectedPayloadIntegrityError, ProtectedPayloadKeyError, ProtectedPayloadNotFound, ProtectedPayloadPathError
from okcanvas_agent_runtime.application.submissions.protected_payload import ProtectedPayloadContent, ProtectedPayloadRecord
from okcanvas_agent_runtime.domain.attachments.models import ProtectedAttachmentBinding
from okcanvas_agent_runtime.domain.project_snapshots.models import ProtectedProjectSnapshotBinding
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity

_PAYLOAD_REF_RE = re.compile(r"^payload_[0-9a-f]{32}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ENVELOPE_BYTES = 512 * 1024
_ENVELOPE_KEYS = {
    "schema_version",
    "payload_ref",
    "algorithm",
    "key_id",
    "created_at",
    "aad",
    "nonce_b64",
    "ciphertext_b64",
}
_CONTENT_KEYS_V3 = {
    "schema_version",
    "submission_id",
    "agent_definition_id",
    "agent_definition_version",
    "agent_definition_sha256",
    "runtime_binding_sha256",
    "session_id",
    "model",
    "request",
    "input_sha256",
    "request_fingerprint_sha256",
    "created_at",
}
_CONTENT_KEYS_V4 = _CONTENT_KEYS_V3 | {"attachment"}
_CONTENT_KEYS_V5 = _CONTENT_KEYS_V4 | {"project_snapshot"}
_CONTENT_KEYS_V6 = _CONTENT_KEYS_V5 | {"delegated_mcp_identity"}



def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_key(value: str) -> bytes:
    normalized = value.strip()
    if not normalized:
        raise ProtectedPayloadKeyError("Protected payload key is required")
    if re.fullmatch(r"[0-9a-fA-F]{64}", normalized):
        raw = bytes.fromhex(normalized)
    else:
        padded = normalized + "=" * (-len(normalized) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ProtectedPayloadKeyError(
                "Protected payload key must be 32-byte URL-safe base64 or 64 hex characters"
            ) from exc
    if len(raw) != 32:
        raise ProtectedPayloadKeyError("Protected payload key must decode to exactly 32 bytes")
    return raw


def generate_protected_payload_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


@dataclass(frozen=True)
class ProtectedPayloadKey:
    key_id: str
    _raw: bytes = field(repr=False)

    @classmethod
    def from_text(cls, value: str) -> "ProtectedPayloadKey":
        raw = _decode_key(value)
        return cls(key_id=hashlib.sha256(raw).hexdigest()[:16], _raw=raw)

    def cipher(self) -> AESGCM:
        return AESGCM(self._raw)

    def derive_subkey(self, context: bytes) -> bytes:
        if not context or len(context) > 128:
            raise ProtectedPayloadKeyError("Protected payload subkey context is invalid")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=context,
        ).derive(self._raw)


class EncryptedFileProtectedPayloadStore:
    """Product-owned encrypted payload store. Raw input never enters SQLite or Events."""

    algorithm = "AES-256-GCM"

    def __init__(self, root: str | Path, key: ProtectedPayloadKey) -> None:
        self.root = Path(root).expanduser().resolve()
        self.key = key

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ProtectedPayloadPathError("Protected payload root must be a real directory")
        try:
            self.root.chmod(0o700)
        except OSError:
            # AES-GCM remains the protection boundary on platforms with limited POSIX mode support.
            pass

    def write(
        self,
        content: ProtectedPayloadContent,
        *,
        payload_ref: str | None = None,
    ) -> ProtectedPayloadRecord:
        self.initialize()
        payload_ref = payload_ref or f"payload_{uuid.uuid4().hex}"
        path = self._path(payload_ref, require_exists=False)
        if path.exists():
            raise ProtectedPayloadIntegrityError("Protected payload reference already exists")
        aad_payload = {
            "schema_version": "okcanvas-protected-payload-aad-v6",
            "payload_ref": payload_ref,
            "submission_id": content.submission_id,
            "agent_definition_id": content.agent_definition_id,
            "agent_definition_version": content.agent_definition_version,
            "agent_definition_sha256": content.agent_definition_sha256,
            "runtime_binding_sha256": content.runtime_binding_sha256,
            "session_id": content.session_id,
            "input_sha256": content.input_sha256,
            "request_fingerprint_sha256": content.request_fingerprint_sha256,
            "key_id": self.key.key_id,
            "algorithm": self.algorithm,
            "created_at": content.created_at,
            "attachment_sha256": (content.attachment.metadata.content_sha256 if content.attachment else None),
            "project_snapshot_sha256": (
                content.project_snapshot.snapshot_sha256 if content.project_snapshot else None
            ),
            "delegation_id": (
                content.delegated_mcp_identity.delegation_id if content.delegated_mcp_identity else None
            ),
        }
        aad = _canonical_json(aad_payload)
        plaintext = _canonical_json(content.to_dict())
        nonce = secrets.token_bytes(12)
        ciphertext = self.key.cipher().encrypt(nonce, plaintext, aad)
        envelope = {
            "schema_version": "okcanvas-protected-payload-envelope-v1",
            "payload_ref": payload_ref,
            "algorithm": self.algorithm,
            "key_id": self.key.key_id,
            "created_at": content.created_at,
            "aad": aad_payload,
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }
        encoded = _canonical_json(envelope) + b"\n"
        if len(encoded) > _MAX_ENVELOPE_BYTES:
            raise ProtectedPayloadIntegrityError("Protected payload envelope exceeds size limit")
        self._write_atomic(path, encoded)
        return ProtectedPayloadRecord(
            payload_ref=payload_ref,
            file_sha256=hashlib.sha256(encoded).hexdigest(),
            byte_length=len(encoded),
            key_id=self.key.key_id,
            algorithm=self.algorithm,
            created_at=content.created_at,
        )

    def read(
        self,
        payload_ref: str,
        *,
        expected_file_sha256: str,
        expected_byte_length: int,
    ) -> ProtectedPayloadContent:
        if not _SHA256_RE.fullmatch(expected_file_sha256):
            raise ProtectedPayloadIntegrityError("Expected protected payload SHA-256 is invalid")
        path = self._path(payload_ref, require_exists=True)
        raw = path.read_bytes()
        if len(raw) != expected_byte_length or len(raw) > _MAX_ENVELOPE_BYTES:
            raise ProtectedPayloadIntegrityError("Protected payload byte length does not match")
        if hashlib.sha256(raw).hexdigest() != expected_file_sha256:
            raise ProtectedPayloadIntegrityError("Protected payload file SHA-256 does not match")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtectedPayloadIntegrityError("Protected payload envelope is invalid JSON") from exc
        if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
            raise ProtectedPayloadIntegrityError("Protected payload envelope keys are invalid")
        if envelope["schema_version"] != "okcanvas-protected-payload-envelope-v1":
            raise ProtectedPayloadIntegrityError("Unsupported protected payload envelope schema")
        if envelope["payload_ref"] != payload_ref:
            raise ProtectedPayloadIntegrityError("Protected payload reference does not match")
        if envelope["algorithm"] != self.algorithm:
            raise ProtectedPayloadIntegrityError("Protected payload algorithm does not match")
        if envelope["key_id"] != self.key.key_id:
            raise ProtectedPayloadKeyError("Protected payload was encrypted with another key")
        aad_payload = envelope["aad"]
        if not isinstance(aad_payload, dict):
            raise ProtectedPayloadIntegrityError("Protected payload AAD is invalid")
        aad = _canonical_json(aad_payload)
        try:
            nonce = base64.urlsafe_b64decode(str(envelope["nonce_b64"]).encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(
                str(envelope["ciphertext_b64"]).encode("ascii")
            )
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ProtectedPayloadIntegrityError("Protected payload encoding is invalid") from exc
        if len(nonce) != 12:
            raise ProtectedPayloadIntegrityError("Protected payload nonce is invalid")
        try:
            plaintext = self.key.cipher().decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise ProtectedPayloadIntegrityError(
                "Protected payload authentication failed"
            ) from exc
        try:
            payload = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtectedPayloadIntegrityError("Protected payload content is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProtectedPayloadIntegrityError("Protected payload content is invalid")
        schema = payload.get("schema_version")
        project_snapshot = None
        if schema == "okcanvas-protected-payload-content-v3":
            if set(payload) != _CONTENT_KEYS_V3:
                raise ProtectedPayloadIntegrityError("Protected payload v3 content keys are invalid")
            attachment = None
            project_snapshot = None
            delegated_mcp_identity = None
            aad_schema = "okcanvas-protected-payload-aad-v3"
        elif schema in {"okcanvas-protected-payload-content-v4", "okcanvas-protected-payload-content-v5", "okcanvas-protected-payload-content-v6"}:
            if schema.endswith("v4"):
                expected_keys = _CONTENT_KEYS_V4
            elif schema.endswith("v5"):
                expected_keys = _CONTENT_KEYS_V5
            else:
                expected_keys = _CONTENT_KEYS_V6
            if set(payload) != expected_keys:
                raise ProtectedPayloadIntegrityError(
                    f"Protected payload {schema.rsplit('-', 1)[-1]} content keys are invalid"
                )
            raw_attachment = payload.get("attachment")
            if raw_attachment is None:
                attachment = None
            elif isinstance(raw_attachment, dict):
                try:
                    attachment = ProtectedAttachmentBinding.from_dict(raw_attachment)
                except (TypeError, ValueError) as exc:
                    raise ProtectedPayloadIntegrityError("Protected attachment binding is invalid") from exc
            else:
                raise ProtectedPayloadIntegrityError("Protected attachment binding is invalid")
            project_snapshot = None
            if schema.endswith(("v5", "v6")):
                raw_snapshot = payload.get("project_snapshot")
                if raw_snapshot is None:
                    project_snapshot = None
                elif isinstance(raw_snapshot, dict):
                    try:
                        project_snapshot = ProtectedProjectSnapshotBinding.from_dict(raw_snapshot)
                    except (TypeError, ValueError) as exc:
                        raise ProtectedPayloadIntegrityError(
                            "Protected project snapshot binding is invalid"
                        ) from exc
                else:
                    raise ProtectedPayloadIntegrityError(
                        "Protected project snapshot binding is invalid"
                    )
            delegated_mcp_identity = None
            if schema.endswith("v6"):
                raw_identity = payload.get("delegated_mcp_identity")
                if raw_identity is not None:
                    if not isinstance(raw_identity, dict):
                        raise ProtectedPayloadIntegrityError("Protected delegated MCP identity is invalid")
                    try:
                        delegated_mcp_identity = DelegatedMCPIdentity.from_protected_dict(raw_identity)
                    except ValueError as exc:
                        raise ProtectedPayloadIntegrityError("Protected delegated MCP identity is invalid") from exc
            aad_schema = (
                "okcanvas-protected-payload-aad-v4" if schema.endswith("v4")
                else ("okcanvas-protected-payload-aad-v5" if schema.endswith("v5") else "okcanvas-protected-payload-aad-v6")
            )
        else:
            raise ProtectedPayloadIntegrityError("Unsupported protected payload content schema")
        content = ProtectedPayloadContent(
            submission_id=self._string(payload, "submission_id"),
            agent_definition_id=self._string(payload, "agent_definition_id"),
            agent_definition_version=self._string(payload, "agent_definition_version"),
            agent_definition_sha256=self._sha(payload, "agent_definition_sha256"),
            runtime_binding_sha256=self._sha(payload, "runtime_binding_sha256"),
            session_id=(self._string(payload, "session_id") if payload["session_id"] is not None else None),
            model=self._string(payload, "model"),
            request=self._string(payload, "request"),
            input_sha256=self._sha(payload, "input_sha256"),
            request_fingerprint_sha256=self._sha(payload, "request_fingerprint_sha256"),
            created_at=self._string(payload, "created_at"),
            attachment=attachment,
            project_snapshot=project_snapshot,
            delegated_mcp_identity=delegated_mcp_identity,
        )
        expected_aad = {
            "schema_version": aad_schema,
            "payload_ref": payload_ref,
            "submission_id": content.submission_id,
            "agent_definition_id": content.agent_definition_id,
            "agent_definition_version": content.agent_definition_version,
            "agent_definition_sha256": content.agent_definition_sha256,
            "runtime_binding_sha256": content.runtime_binding_sha256,
            "session_id": content.session_id,
            "input_sha256": content.input_sha256,
            "request_fingerprint_sha256": content.request_fingerprint_sha256,
            "key_id": self.key.key_id,
            "algorithm": self.algorithm,
            "created_at": content.created_at,
        }
        if aad_schema in {
            "okcanvas-protected-payload-aad-v4",
            "okcanvas-protected-payload-aad-v5",
            "okcanvas-protected-payload-aad-v6",
        }:
            expected_aad["attachment_sha256"] = (
                content.attachment.metadata.content_sha256 if content.attachment else None
            )
        if aad_schema in {"okcanvas-protected-payload-aad-v5", "okcanvas-protected-payload-aad-v6"}:
            expected_aad["project_snapshot_sha256"] = (
                content.project_snapshot.snapshot_sha256 if content.project_snapshot else None
            )
        if aad_schema == "okcanvas-protected-payload-aad-v6":
            expected_aad["delegation_id"] = (
                content.delegated_mcp_identity.delegation_id if content.delegated_mcp_identity else None
            )
        if aad_payload != expected_aad:
            raise ProtectedPayloadIntegrityError("Protected payload AAD identity does not match")
        if hashlib.sha256(content.request.encode("utf-8")).hexdigest() != content.input_sha256:
            raise ProtectedPayloadIntegrityError("Protected payload request SHA-256 does not match")
        return content

    def delete(self, payload_ref: str) -> None:
        path = self._path(payload_ref, require_exists=False)
        if path.exists():
            path.unlink()

    def _path(self, payload_ref: str, *, require_exists: bool) -> Path:
        if not _PAYLOAD_REF_RE.fullmatch(payload_ref):
            raise ProtectedPayloadPathError("Protected payload reference is invalid")
        path = (self.root / f"{payload_ref}.json").resolve()
        if path.parent != self.root:
            raise ProtectedPayloadPathError("Protected payload path escaped the configured root")
        if path.is_symlink():
            raise ProtectedPayloadPathError("Protected payload symbolic links are forbidden")
        if require_exists and not path.is_file():
            raise ProtectedPayloadNotFound(f"Protected payload not found: {payload_ref}")
        return path

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            try:
                path.chmod(0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ProtectedPayloadIntegrityError(f"Protected payload {key} is invalid")
        return value

    @classmethod
    def _sha(cls, payload: dict[str, Any], key: str) -> str:
        value = cls._string(payload, key)
        if not _SHA256_RE.fullmatch(value):
            raise ProtectedPayloadIntegrityError(f"Protected payload {key} is not SHA-256")
        return value
