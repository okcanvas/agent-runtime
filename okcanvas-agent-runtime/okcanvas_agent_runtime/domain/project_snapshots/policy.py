from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotPolicyError


@dataclass(frozen=True)
class ProjectSnapshotPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_archive_bytes: int
    max_files: int
    max_total_bytes: int
    max_file_bytes: int
    max_path_chars: int
    slot_ttl_seconds: int
    allowed_compression_methods: tuple[str, ...]
    encrypted_entries_allowed: bool
    symbolic_links_allowed: bool
    policy_sha256: str


class ProjectSnapshotPolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "project_snapshots" / "project-snapshot-policy.json"

    def resolve(self) -> ProjectSnapshotPolicy:
        path = self.path.resolve()
        expected_parent = (self.project_root / "specs" / "project_snapshots").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise ProjectSnapshotPolicyError("Project snapshot policy is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectSnapshotPolicyError("Project snapshot policy is invalid JSON") from exc
        expected = {
            "schema_version", "policy_id", "version", "max_archive_bytes", "max_files",
            "max_total_bytes", "max_file_bytes", "max_path_chars", "slot_ttl_seconds",
            "allowed_compression_methods", "encrypted_entries_allowed", "symbolic_links_allowed",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ProjectSnapshotPolicyError("Project snapshot policy fields are not exact")
        if payload["schema_version"] != "okcanvas-project-snapshot-policy-v1":
            raise ProjectSnapshotPolicyError("Unsupported project snapshot policy schema")
        if payload["policy_id"] != "bounded-project-zip-snapshot-v1" or payload["version"] != "1.0.0":
            raise ProjectSnapshotPolicyError("Project snapshot policy identity is invalid")
        numeric = {
            "max_archive_bytes": (1, 33_554_432),
            "max_files": (1, 3000),
            "max_total_bytes": (1, 33_554_432),
            "max_file_bytes": (1, 524_288),
            "max_path_chars": (1, 512),
            "slot_ttl_seconds": (60, 86_400),
        }
        for key, (minimum, maximum) in numeric.items():
            value = payload[key]
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ProjectSnapshotPolicyError(f"Project snapshot policy {key} is invalid")
        if payload["max_file_bytes"] > payload["max_total_bytes"]:
            raise ProjectSnapshotPolicyError("Project snapshot file bound exceeds total bound")
        if payload["allowed_compression_methods"] != ["stored", "deflated"]:
            raise ProjectSnapshotPolicyError("Project snapshot compression allowlist is invalid")
        if payload["encrypted_entries_allowed"] is not False or payload["symbolic_links_allowed"] is not False:
            raise ProjectSnapshotPolicyError("Encrypted entries and symbolic links must remain disabled")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        values = dict(payload)
        values["allowed_compression_methods"] = tuple(payload["allowed_compression_methods"])
        return ProjectSnapshotPolicy(
            **values,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
