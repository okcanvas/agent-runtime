from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from okcanvas_agent_runtime.domain.sessions.errors import SessionConfigurationError, SessionIntegrityError

_ENVELOPE_MARKER = "__okcanvas_session_encrypted__"
_ENVELOPE_VERSION = 1
_ENVELOPE_KEYS = {
    _ENVELOPE_MARKER,
    "version",
    "key_id",
    "nonce_b64",
    "ciphertext_b64",
}
_HKDF_INFO = b"okcanvas.session-history.aes-256-gcm.hkdf-sha256.v1"


def _decode_key_text(value: str) -> bytes:
    normalized = value.strip()
    if not normalized:
        raise SessionConfigurationError("Session history encryption key is not configured")
    if len(normalized) == 64:
        try:
            raw = bytes.fromhex(normalized)
        except ValueError:
            raw = b""
        if len(raw) == 32:
            return raw
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise SessionConfigurationError(
            "Session history encryption key must be 64 hex characters or 32-byte URL-safe base64"
        ) from exc
    if len(raw) != 32:
        raise SessionConfigurationError(
            "Session history encryption key must decode to exactly 32 bytes"
        )
    return raw


def generate_session_history_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


@dataclass(frozen=True)
class SessionHistoryKey:
    key_id: str
    _raw: bytes

    @classmethod
    def from_text(cls, value: str) -> "SessionHistoryKey":
        raw = _decode_key_text(value)
        return cls(key_id=hashlib.sha256(raw).hexdigest()[:16], _raw=raw)

    def derive(self, session_id: str) -> bytes:
        if not session_id or len(session_id) > 200:
            raise SessionIntegrityError("Session ID is invalid for history key derivation")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=session_id.encode("utf-8"),
            info=_HKDF_INFO,
        ).derive(self._raw)


class StrictEncryptedSession:
    """Fail-closed encrypted Session wrapper over an installed SDK Session backend.

    Unlike the upstream optional EncryptedSession example, this wrapper does not permit
    legacy plaintext, does not silently skip invalid ciphertext, and does not expire
    history by wall-clock TTL. Every persisted item must be one exact authenticated
    envelope bound to the product Session ID and current non-secret key ID.
    """

    def __init__(self, *, session_id: str, underlying_session: Any, key: SessionHistoryKey) -> None:
        self.session_id = session_id
        self.underlying_session = underlying_session
        self.key = key
        self._cipher = AESGCM(key.derive(session_id))

    @property
    def session_settings(self) -> Any:
        return getattr(self.underlying_session, "session_settings", None)

    @session_settings.setter
    def session_settings(self, value: Any) -> None:
        setattr(self.underlying_session, "session_settings", value)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.underlying_session, name)

    def _aad(self) -> bytes:
        payload = {
            "schema_version": "okcanvas-session-history-aad-v1",
            "session_id": self.session_id,
            "key_id": self.key.key_id,
            "envelope_version": _ENVELOPE_VERSION,
        }
        return json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")

    @staticmethod
    def _json_payload(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            payload = item
        elif hasattr(item, "model_dump"):
            payload = item.model_dump(mode="json")
        elif hasattr(item, "__dict__"):
            payload = vars(item)
        else:
            try:
                payload = dict(item)
            except Exception as exc:
                raise SessionIntegrityError("Session item cannot be serialized as an object") from exc
        if not isinstance(payload, dict):
            raise SessionIntegrityError("Session item must serialize to a JSON object")
        try:
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise SessionIntegrityError("Session item is not JSON serializable") from exc
        return cast(dict[str, Any], payload)

    def _encrypt(self, item: Any) -> dict[str, Any]:
        payload = self._json_payload(item)
        plaintext = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext, self._aad())
        return {
            _ENVELOPE_MARKER: 1,
            "version": _ENVELOPE_VERSION,
            "key_id": self.key.key_id,
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }

    def _decrypt(self, envelope: Any) -> dict[str, Any]:
        if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
            raise SessionIntegrityError(
                "Session history contains plaintext or an unsupported encryption envelope"
            )
        if envelope.get(_ENVELOPE_MARKER) != 1 or envelope.get("version") != _ENVELOPE_VERSION:
            raise SessionIntegrityError("Session history encryption envelope version is unsupported")
        if envelope.get("key_id") != self.key.key_id:
            raise SessionIntegrityError("Session history encryption key ID does not match")
        try:
            nonce_text = str(envelope["nonce_b64"])
            ciphertext_text = str(envelope["ciphertext_b64"])
            nonce = base64.b64decode(
                (nonce_text + "=" * (-len(nonce_text) % 4)).encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
            ciphertext = base64.b64decode(
                (ciphertext_text + "=" * (-len(ciphertext_text) % 4)).encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
        except (UnicodeEncodeError, binascii.Error, ValueError, KeyError) as exc:
            raise SessionIntegrityError("Session history encryption envelope is malformed") from exc
        if len(nonce) != 12 or len(ciphertext) < 16:
            raise SessionIntegrityError("Session history encryption envelope lengths are invalid")
        try:
            plaintext = self._cipher.decrypt(nonce, ciphertext, self._aad())
        except InvalidTag as exc:
            raise SessionIntegrityError("Session history ciphertext integrity validation failed") from exc
        try:
            payload = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SessionIntegrityError("Session history decrypted payload is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SessionIntegrityError("Session history decrypted payload must be an object")
        return cast(dict[str, Any], payload)

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        encrypted_items = await self.underlying_session.get_items(limit)
        return [self._decrypt(item) for item in encrypted_items]

    async def add_items(self, items: list[Any]) -> None:
        await self.underlying_session.add_items([self._encrypt(item) for item in items])

    async def pop_item(self) -> dict[str, Any] | None:
        encrypted = await self.underlying_session.pop_item()
        if encrypted is None:
            return None
        return self._decrypt(encrypted)

    async def clear_session(self) -> None:
        await self.underlying_session.clear_session()

    async def validate_storage(self) -> int:
        return len(await self.get_items())

    def close(self) -> None:
        close = getattr(self.underlying_session, "close", None)
        if callable(close):
            close()
