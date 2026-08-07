from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from okcanvas_agent_runtime.adapters.storage.protected_payload import ProtectedPayloadKey, generate_protected_payload_key
from okcanvas_agent_runtime.application.approvals import EncryptedRunStateStore, ToolApprovalIntegrityError


def _store(tmp_path: Path) -> EncryptedRunStateStore:
    store = EncryptedRunStateStore(
        tmp_path / "run-states",
        ProtectedPayloadKey.from_text(generate_protected_payload_key()),
    )
    store.initialize()
    return store


def test_runstate_envelope_rejects_unknown_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = store.write(
        approval_id="approval_fixture",
        run_id="run_fixture",
        state_json={"schema_version": "fixture-v1"},
    )
    path = store.root / f"{record.run_state_ref}.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["unexpected"] = True
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    path.write_bytes(raw)
    with pytest.raises(ToolApprovalIntegrityError, match="envelope keys"):
        store.read(
            approval_id="approval_fixture",
            run_id="run_fixture",
            ref=record.run_state_ref,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_byte_length=len(raw),
        )


def test_runstate_symbolic_link_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = store.write(
        approval_id="approval_fixture",
        run_id="run_fixture",
        state_json={"schema_version": "fixture-v1"},
    )
    original = store.root / f"{record.run_state_ref}.json"
    target = store.root / "target.json"
    original.replace(target)
    try:
        os.symlink(target.name, original)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable in this environment")
    with pytest.raises(ToolApprovalIntegrityError, match="symbolic links"):
        store.read(
            approval_id="approval_fixture",
            run_id="run_fixture",
            ref=record.run_state_ref,
            expected_sha256=record.file_sha256,
            expected_byte_length=record.byte_length,
        )
