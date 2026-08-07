from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey

from okcanvas_agent_runtime.application.approvals.errors import ToolApprovalIntegrityError
from okcanvas_agent_runtime.application.approvals.models import PersistedRunStateRecord

_REF_RE = re.compile(r"^runstate_[0-9a-f]{32}$")
_MAX_BYTES = 4 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_KEYS = {
    "schema_version",
    "run_state_ref",
    "algorithm",
    "key_id",
    "aad",
    "nonce_b64",
    "ciphertext_b64",
}


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class EncryptedRunStateStore:
    algorithm = "AES-256-GCM"

    def __init__(self, root: str | Path, key: ProtectedPayloadKey) -> None:
        self.root = Path(root).expanduser().resolve()
        self.key = key

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ToolApprovalIntegrityError("RunState root must be a real directory")
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def write(self, *, approval_id: str, run_id: str, state_json: dict[str, Any]) -> PersistedRunStateRecord:
        self.initialize()
        ref = f"runstate_{uuid.uuid4().hex}"
        path = self._path(ref)
        aad_payload = {
            "schema_version": "okcanvas-encrypted-runstate-aad-v1",
            "run_state_ref": ref,
            "approval_id": approval_id,
            "run_id": run_id,
            "key_id": self.key.key_id,
            "algorithm": self.algorithm,
        }
        plaintext = _canonical(state_json)
        nonce = secrets.token_bytes(12)
        ciphertext = self.key.cipher().encrypt(nonce, plaintext, _canonical(aad_payload))
        envelope = {
            "schema_version": "okcanvas-encrypted-runstate-envelope-v1",
            "run_state_ref": ref,
            "algorithm": self.algorithm,
            "key_id": self.key.key_id,
            "aad": aad_payload,
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }
        encoded = _canonical(envelope) + b"\n"
        if len(encoded) > _MAX_BYTES:
            raise ToolApprovalIntegrityError("Encrypted RunState exceeds size limit")
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            temp.replace(path)
            try:
                path.chmod(0o600)
            except OSError:
                pass
        finally:
            temp.unlink(missing_ok=True)
        return PersistedRunStateRecord(ref, hashlib.sha256(encoded).hexdigest(), len(encoded), self.key.key_id)

    def read(
        self,
        *,
        approval_id: str,
        run_id: str,
        ref: str,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> dict[str, Any]:
        if not _SHA256_RE.fullmatch(expected_sha256):
            raise ToolApprovalIntegrityError("Expected RunState SHA-256 is invalid")
        if expected_byte_length <= 0 or expected_byte_length > _MAX_BYTES:
            raise ToolApprovalIntegrityError("Expected RunState byte length is invalid")
        path = self._path(ref, require=True)
        raw = path.read_bytes()
        if (
            len(raw) != expected_byte_length
            or len(raw) > _MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != expected_sha256
        ):
            raise ToolApprovalIntegrityError("Encrypted RunState integrity does not match")
        try:
            envelope = json.loads(raw.decode("utf-8"))
            if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
                raise ToolApprovalIntegrityError("Encrypted RunState envelope keys are invalid")
            if envelope["schema_version"] != "okcanvas-encrypted-runstate-envelope-v1":
                raise ToolApprovalIntegrityError("Encrypted RunState schema is unsupported")
            if envelope["run_state_ref"] != ref or envelope["algorithm"] != self.algorithm:
                raise ToolApprovalIntegrityError("Encrypted RunState envelope identity does not match")
            aad = envelope["aad"]
            expected_aad = {
                "schema_version": "okcanvas-encrypted-runstate-aad-v1",
                "run_state_ref": ref,
                "approval_id": approval_id,
                "run_id": run_id,
                "key_id": self.key.key_id,
                "algorithm": self.algorithm,
            }
            if aad != expected_aad or envelope["key_id"] != self.key.key_id:
                raise ToolApprovalIntegrityError("Encrypted RunState identity does not match")
            nonce = base64.b64decode(
                str(envelope["nonce_b64"]).encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
            ciphertext = base64.b64decode(
                str(envelope["ciphertext_b64"]).encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
            if len(nonce) != 12 or len(ciphertext) < 16:
                raise ToolApprovalIntegrityError("Encrypted RunState cipher material is invalid")
            plaintext = self.key.cipher().decrypt(nonce, ciphertext, _canonical(aad))
            state = json.loads(plaintext.decode("utf-8"))
        except ToolApprovalIntegrityError:
            raise
        except (
            KeyError,
            UnicodeEncodeError,
            UnicodeDecodeError,
            binascii.Error,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            InvalidTag,
        ) as exc:
            raise ToolApprovalIntegrityError("Encrypted RunState authentication failed") from exc
        if not isinstance(state, dict):
            raise ToolApprovalIntegrityError("RunState payload must be an object")
        return state

    def delete(self, ref: str) -> None:
        self._path(ref).unlink(missing_ok=True)

    def _path(self, ref: str, require: bool = False) -> Path:
        if not _REF_RE.fullmatch(ref):
            raise ToolApprovalIntegrityError("RunState reference is invalid")
        candidate = self.root / f"{ref}.json"
        if candidate.is_symlink():
            raise ToolApprovalIntegrityError("RunState symbolic links are forbidden")
        path = candidate.resolve()
        if path.parent != self.root:
            raise ToolApprovalIntegrityError("RunState path is unsafe")
        if require and not path.is_file():
            raise ToolApprovalIntegrityError("RunState file is missing")
        return path
