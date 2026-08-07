from __future__ import annotations

import base64
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadContent,
    ProtectedPayloadIntegrityError,
    ProtectedPayloadKey,
    ProtectedPayloadKeyError,
    ProtectedPayloadPathError,
)

KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
CONTENT = ProtectedPayloadContent(
    submission_id="submission_" + "a" * 32,
    agent_definition_id="coding-agent",
    agent_definition_version="1.0.0",
    agent_definition_sha256="b" * 64,
    runtime_binding_sha256="d" * 64,
    session_id=None,
    model="gpt-test",
    request="raw request sentinel",
    input_sha256="4da7e11e9bd94f68016877fb53a84490f9e4b539f0ed234a6d737715c7c1581c",
    request_fingerprint_sha256="c" * 64,
    created_at="2026-07-29T00:00:00Z",
)


def _content() -> ProtectedPayloadContent:
    import hashlib

    return ProtectedPayloadContent(
        **{
            **CONTENT.__dict__,
            "input_sha256": hashlib.sha256(CONTENT.request.encode()).hexdigest(),
        }
    )


def test_encrypted_payload_round_trip_and_plaintext_absence(tmp_path: Path) -> None:
    store = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    record = store.write(_content())
    raw = (store.root / f"{record.payload_ref}.json").read_bytes()
    assert CONTENT.request.encode() not in raw
    restored = store.read(
        record.payload_ref,
        expected_file_sha256=record.file_sha256,
        expected_byte_length=record.byte_length,
    )
    assert restored == _content()
    assert record.algorithm == "AES-256-GCM"
    assert len(record.key_id) == 16


def test_payload_tamper_and_wrong_key_fail_closed(tmp_path: Path) -> None:
    store = EncryptedFileProtectedPayloadStore(
        tmp_path / "protected", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    record = store.write(_content())
    path = store.root / f"{record.payload_ref}.json"
    raw = bytearray(path.read_bytes())
    raw[-10] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ProtectedPayloadIntegrityError):
        store.read(
            record.payload_ref,
            expected_file_sha256=record.file_sha256,
            expected_byte_length=record.byte_length,
        )

    other_key = base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
    other = EncryptedFileProtectedPayloadStore(store.root, ProtectedPayloadKey.from_text(other_key))
    path.write_bytes(bytes(raw[:-1]) + b"\n")
    with pytest.raises((ProtectedPayloadIntegrityError, ProtectedPayloadKeyError)):
        other.read(
            record.payload_ref,
            expected_file_sha256=record.file_sha256,
            expected_byte_length=record.byte_length,
        )


def test_payload_key_and_reference_validation() -> None:
    with pytest.raises(ProtectedPayloadKeyError):
        ProtectedPayloadKey.from_text("short")
    store = EncryptedFileProtectedPayloadStore(".", ProtectedPayloadKey.from_text(KEY_TEXT))
    with pytest.raises(ProtectedPayloadPathError):
        store.read("../secret", expected_file_sha256="0" * 64, expected_byte_length=1)
