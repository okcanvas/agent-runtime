from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import unicodedata
import zipfile
from pathlib import PurePosixPath

from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotValidationError
from okcanvas_agent_runtime.domain.project_snapshots.models import ProjectSnapshotFile, ProjectSnapshotMetadata
from okcanvas_agent_runtime.domain.project_snapshots.policy import ProjectSnapshotPolicy

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_INTERNAL_METADATA = ".okcanvas-snapshot-manifest.json"
_METHODS = {zipfile.ZIP_STORED: "stored", zipfile.ZIP_DEFLATED: "deflated"}


def normalize_snapshot_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized or len(normalized) > 120 or _CONTROL_RE.search(normalized):
        raise ProjectSnapshotValidationError("Project snapshot filename must contain 1..120 safe characters")
    if "/" in normalized or "\\" in normalized or normalized in {".", ".."} or normalized.startswith("."):
        raise ProjectSnapshotValidationError("Project snapshot filename must not contain a path")
    if not normalized.lower().endswith(".zip"):
        raise ProjectSnapshotValidationError("Project snapshot filename must end with .zip")
    return normalized


def _safe_path(value: str, policy: ProjectSnapshotPolicy) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or len(normalized) > policy.max_path_chars or _CONTROL_RE.search(normalized):
        raise ProjectSnapshotValidationError("Project snapshot entry path is invalid")
    if "\\" in normalized or normalized.startswith("/"):
        raise ProjectSnapshotValidationError("Project snapshot entry path must be relative POSIX form")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProjectSnapshotValidationError("Project snapshot entry path escapes the project root")
    canonical = path.as_posix()
    if canonical == _INTERNAL_METADATA:
        raise ProjectSnapshotValidationError("Internal snapshot metadata path is reserved")
    return canonical


def _manifest_sha(files: tuple[ProjectSnapshotFile, ...]) -> str:
    payload = {
        "schema_version": "okcanvas-project-snapshot-manifest-v1",
        "files": [item.to_dict() for item in files],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_project_snapshot_zip(
    data: bytes,
    filename: str,
    policy: ProjectSnapshotPolicy,
) -> ProjectSnapshotMetadata:
    safe_name = normalize_snapshot_filename(filename)
    if not data or len(data) > policy.max_archive_bytes:
        raise ProjectSnapshotValidationError(
            f"Project snapshot archive must be 1..{policy.max_archive_bytes} bytes"
        )
    archive_sha = hashlib.sha256(data).hexdigest()
    files: list[ProjectSnapshotFile] = []
    seen: set[str] = set()
    seen_casefold: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data), mode="r") as archive:
            if archive.testzip() is not None:
                raise ProjectSnapshotValidationError("Project snapshot ZIP CRC validation failed")
            for info in archive.infolist():
                path = _safe_path(info.filename.rstrip("/"), policy)
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1 and not policy.encrypted_entries_allowed:
                    raise ProjectSnapshotValidationError("Encrypted ZIP entries are forbidden")
                method = _METHODS.get(info.compress_type)
                if method not in policy.allowed_compression_methods:
                    raise ProjectSnapshotValidationError("ZIP compression method is outside policy")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode) and not policy.symbolic_links_allowed:
                    raise ProjectSnapshotValidationError("Symbolic links are forbidden in project snapshots")
                folded = path.casefold()
                if path in seen or folded in seen_casefold:
                    raise ProjectSnapshotValidationError("Duplicate or case-colliding project snapshot path")
                if info.file_size < 0 or info.file_size > policy.max_file_bytes:
                    raise ProjectSnapshotValidationError("Project snapshot file exceeds the per-file bound")
                if len(files) + 1 > policy.max_files:
                    raise ProjectSnapshotValidationError("Project snapshot file count exceeds policy")
                total += info.file_size
                if total > policy.max_total_bytes:
                    raise ProjectSnapshotValidationError("Project snapshot expanded bytes exceed policy")
                with archive.open(info, mode="r") as stream:
                    content = stream.read(policy.max_file_bytes + 1)
                if len(content) != info.file_size or len(content) > policy.max_file_bytes:
                    raise ProjectSnapshotValidationError("Project snapshot file size does not match ZIP metadata")
                files.append(
                    ProjectSnapshotFile(
                        path=path,
                        sha256=hashlib.sha256(content).hexdigest(),
                        byte_length=len(content),
                    )
                )
                seen.add(path)
                seen_casefold.add(folded)
    except ProjectSnapshotValidationError:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError) as exc:
        raise ProjectSnapshotValidationError("Project snapshot is not a valid bounded ZIP archive") from exc
    ordered = tuple(sorted(files, key=lambda item: item.path))
    if not ordered:
        raise ProjectSnapshotValidationError("Project snapshot must contain at least one file")
    return ProjectSnapshotMetadata(
        filename=safe_name,
        archive_sha256=archive_sha,
        archive_byte_length=len(data),
        snapshot_sha256=_manifest_sha(ordered),
        file_count=len(ordered),
        total_bytes=sum(item.byte_length for item in ordered),
        files=ordered,
    )
