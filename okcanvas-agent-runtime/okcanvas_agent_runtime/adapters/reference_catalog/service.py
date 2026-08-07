from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from okcanvas_agent_runtime.adapters.reference_catalog.errors import ReferenceContentError, ReferenceIntegrityError, ReferenceManifestError, ReferenceNotFoundError, ReferencePathError, ReferenceQueryError
from okcanvas_agent_runtime.adapters.reference_catalog.models import CodeMapEntry, ReferenceDescriptor, ReferenceFileMatch, ReferenceLine, ReferenceReadResult, ReferenceSearchResult, ReferenceVerification

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_PATH_RE = re.compile(r"`([^`]+)`")
_MAX_QUERY_LENGTH = 200
_DEFAULT_MAX_FILE_BYTES = 1_048_576
_DEFAULT_MAX_READ_LINES = 400
_DEFAULT_MAX_READ_BYTES = 2_097_152
_DEFAULT_MAX_MATCHES_PER_FILE = 3
_MAX_RESULTS_LIMIT = 100


class ReferenceAccessRecorder(Protocol):
    def record_search(self, run_id: str, result: ReferenceSearchResult) -> None: ...

    def record_read(self, run_id: str, result: ReferenceReadResult) -> None: ...


@dataclass(frozen=True)
class _ManifestEntry:
    descriptor: ReferenceDescriptor
    root: Path


class ReferenceCatalogService:
    """Bounded, read-only access to manifest-declared immutable reference trees."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        recorder: ReferenceAccessRecorder | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=True)
        self.reference_root = self.project_root / "reference"
        self.manifest_path = self.reference_root / "MANIFEST.json"
        self.code_map_path = self.reference_root / "CODE_MAP.md"
        self.upstream_root = self.reference_root / "upstream"
        self._recorder = recorder
        self._entries = self._load_manifest()
        self._code_map_entries = self._load_code_map()

    def list_references(self) -> tuple[ReferenceDescriptor, ...]:
        return tuple(entry.descriptor for entry in self._entries.values())

    def verify_reference(self, reference_id: str) -> ReferenceVerification:
        entry = self._entry(reference_id)
        actual_hash, actual_count, actual_bytes = self._tree_hash(entry.root)
        descriptor = entry.descriptor
        verified = (
            actual_hash == descriptor.tree_sha256
            and actual_count == descriptor.file_count
            and actual_bytes == descriptor.byte_count
        )
        result = ReferenceVerification(
            reference_id=reference_id,
            expected_tree_sha256=descriptor.tree_sha256,
            actual_tree_sha256=actual_hash,
            expected_file_count=descriptor.file_count,
            actual_file_count=actual_count,
            expected_byte_count=descriptor.byte_count,
            actual_byte_count=actual_bytes,
            verified=verified,
        )
        if not verified:
            raise ReferenceIntegrityError(
                f"Reference integrity mismatch: {reference_id}",
                details=result.to_dict(),
            )
        return result

    def verify_all(self) -> tuple[ReferenceVerification, ...]:
        return tuple(self.verify_reference(reference_id) for reference_id in self._entries)

    def code_map_entries(
        self,
        query: str | None = None,
        *,
        reference_ids: tuple[str, ...] | None = None,
    ) -> tuple[CodeMapEntry, ...]:
        selected_ids = self._selected_reference_ids(reference_ids)
        for reference_id in selected_ids:
            self.verify_reference(reference_id)
        return self._matching_code_map_entries(query, selected_ids)

    def search(
        self,
        query: str,
        *,
        reference_ids: tuple[str, ...] | None = None,
        max_results: int = 20,
        max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
        max_matches_per_file: int = _DEFAULT_MAX_MATCHES_PER_FILE,
        run_id: str | None = None,
    ) -> ReferenceSearchResult:
        query = query.strip()
        if len(query) < 2 or len(query) > _MAX_QUERY_LENGTH:
            raise ReferenceQueryError(
                "Reference query length must be between 2 and 200 characters",
                details={"query_length": len(query)},
            )
        if not 1 <= max_results <= _MAX_RESULTS_LIMIT:
            raise ReferenceQueryError(
                "max_results must be between 1 and 100",
                details={"max_results": max_results},
            )
        if max_file_bytes < 1:
            raise ReferenceQueryError("max_file_bytes must be positive")
        if not 1 <= max_matches_per_file <= 10:
            raise ReferenceQueryError("max_matches_per_file must be between 1 and 10")

        selected_ids = self._selected_reference_ids(reference_ids)
        for reference_id in selected_ids:
            self.verify_reference(reference_id)

        code_map_matches = self._matching_code_map_entries(query, selected_ids)
        priority_paths: dict[str, list[str]] = {reference_id: [] for reference_id in selected_ids}
        for match in code_map_matches:
            priority_paths[match.reference_id].append(match.relative_path)

        needle = query.casefold()
        matches: list[ReferenceFileMatch] = []
        scanned_files = 0
        skipped_oversized = 0
        skipped_non_text = 0
        truncated = False

        for reference_id in selected_ids:
            entry = self._entry(reference_id)
            candidates = self._ordered_files(entry.root, priority_paths[reference_id])
            for path in candidates:
                if len(matches) >= max_results:
                    truncated = True
                    break
                scanned_files += 1
                size = path.stat().st_size
                if size > max_file_bytes:
                    skipped_oversized += 1
                    continue
                try:
                    data = path.read_bytes()
                    if b"\x00" in data:
                        skipped_non_text += 1
                        continue
                    text = data.decode("utf-8-sig")
                except (OSError, UnicodeDecodeError):
                    skipped_non_text += 1
                    continue

                file_sha = hashlib.sha256(data).hexdigest()
                per_file = 0
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if needle not in line.casefold():
                        continue
                    matches.append(
                        ReferenceFileMatch(
                            reference_id=reference_id,
                            classification=entry.descriptor.classification,
                            version=entry.descriptor.version,
                            relative_path=path.relative_to(entry.root).as_posix(),
                            line_number=line_number,
                            excerpt=self._bounded_excerpt(line),
                            file_sha256=file_sha,
                        )
                    )
                    per_file += 1
                    if len(matches) >= max_results:
                        truncated = True
                        break
                    if per_file >= max_matches_per_file:
                        break
            if len(matches) >= max_results:
                break

        result = ReferenceSearchResult(
            query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            reference_ids=selected_ids,
            code_map_matches=code_map_matches,
            matches=tuple(matches),
            scanned_files=scanned_files,
            skipped_oversized_files=skipped_oversized,
            skipped_non_text_files=skipped_non_text,
            truncated=truncated,
        )
        if run_id is not None:
            self._require_recorder().record_search(run_id, result)
        return result

    def read_lines(
        self,
        reference_id: str,
        relative_path: str,
        *,
        start_line: int,
        end_line: int,
        max_lines: int = _DEFAULT_MAX_READ_LINES,
        max_file_bytes: int = _DEFAULT_MAX_READ_BYTES,
        run_id: str | None = None,
    ) -> ReferenceReadResult:
        if start_line < 1 or end_line < start_line:
            raise ReferenceQueryError(
                "Invalid line range",
                details={"start_line": start_line, "end_line": end_line},
            )
        requested_count = end_line - start_line + 1
        if max_lines < 1 or requested_count > max_lines:
            raise ReferenceQueryError(
                "Requested line range exceeds the configured limit",
                details={"requested_lines": requested_count, "max_lines": max_lines},
            )
        self.verify_reference(reference_id)
        entry = self._entry(reference_id)
        path = self._resolve_file(reference_id, relative_path)
        data = path.read_bytes()
        if len(data) > max_file_bytes:
            raise ReferenceContentError(
                "Reference file exceeds the read byte limit",
                details={"path": relative_path, "bytes": len(data), "limit": max_file_bytes},
            )
        if b"\x00" in data:
            raise ReferenceContentError(
                "Reference file is binary",
                details={"path": relative_path},
            )
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ReferenceContentError(
                "Reference file is not UTF-8 text",
                details={"path": relative_path},
            ) from exc
        all_lines = text.splitlines()
        if start_line > len(all_lines):
            raise ReferenceQueryError(
                "Requested start line exceeds the file length",
                details={
                    "path": relative_path,
                    "start_line": start_line,
                    "total_lines": len(all_lines),
                },
            )
        actual_start = start_line
        actual_end = min(end_line, len(all_lines))
        selected_lines = tuple(
            ReferenceLine(line_number=index, text=all_lines[index - 1])
            for index in range(actual_start, actual_end + 1)
        )
        result = ReferenceReadResult(
            reference_id=reference_id,
            classification=entry.descriptor.classification,
            version=entry.descriptor.version,
            relative_path=PurePosixPath(relative_path).as_posix(),
            requested_start_line=start_line,
            requested_end_line=end_line,
            actual_start_line=actual_start,
            actual_end_line=actual_end,
            total_lines=len(all_lines),
            file_sha256=hashlib.sha256(data).hexdigest(),
            byte_length=len(data),
            lines=selected_lines,
        )
        if run_id is not None:
            self._require_recorder().record_read(run_id, result)
        return result

    def _matching_code_map_entries(
        self, query: str | None, selected_ids: tuple[str, ...]
    ) -> tuple[CodeMapEntry, ...]:
        selected = set(selected_ids)
        normalized_query = query.casefold() if query is not None else None
        results: list[CodeMapEntry] = []
        for section, label, reference_id, relative_path in self._code_map_entries:
            if reference_id not in selected:
                continue
            if normalized_query is not None and normalized_query not in (
                f"{section} {label} {relative_path}".casefold()
            ):
                continue
            path = self._resolve_file(reference_id, relative_path)
            results.append(
                CodeMapEntry(
                    section=section,
                    label=label,
                    reference_id=reference_id,
                    relative_path=relative_path,
                    file_sha256=self._file_sha256(path),
                )
            )
        return tuple(results)

    def _load_manifest(self) -> dict[str, _ManifestEntry]:
        if not self.manifest_path.is_file() or not self.code_map_path.is_file():
            raise ReferenceManifestError(
                "Reference manifest or code map is missing",
                details={
                    "manifest": str(self.manifest_path),
                    "code_map": str(self.code_map_path),
                },
            )
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReferenceManifestError("Unable to load reference manifest") from exc
        if payload.get("schema_version") != 1 or not isinstance(payload.get("references"), list):
            raise ReferenceManifestError("Unsupported reference manifest schema")

        entries: dict[str, _ManifestEntry] = {}
        destinations: set[str] = set()
        for raw in payload["references"]:
            try:
                reference_id = str(raw["id"])
                destination = str(raw["dest"])
                tree_sha = str(raw["tree_sha256"])
                descriptor = ReferenceDescriptor(
                    reference_id=reference_id,
                    classification=str(raw["classification"]),
                    version=str(raw["version"]),
                    source_url=str(raw["source_url"]),
                    destination=destination,
                    tree_sha256=tree_sha,
                    file_count=int(raw["file_count"]),
                    byte_count=int(raw["byte_count"]),
                    notes=str(raw.get("notes", "")),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ReferenceManifestError("Invalid reference manifest entry") from exc
            if reference_id in entries or destination in destinations:
                raise ReferenceManifestError(
                    "Duplicate reference ID or destination",
                    details={"reference_id": reference_id, "destination": destination},
                )
            if (
                not reference_id
                or not destination
                or "/" in destination
                or "\\" in destination
                or destination in {".", ".."}
                or not _SHA256_RE.fullmatch(tree_sha)
                or descriptor.file_count < 1
                or descriptor.byte_count < 1
            ):
                raise ReferenceManifestError(
                    "Unsafe or invalid reference manifest entry",
                    details={"reference_id": reference_id, "destination": destination},
                )
            root = self.upstream_root / destination
            if root.is_symlink() or not root.is_dir():
                raise ReferenceManifestError(
                    "Manifest-declared reference root is missing or symbolic",
                    details={"reference_id": reference_id, "root": str(root)},
                )
            entries[reference_id] = _ManifestEntry(descriptor=descriptor, root=root)
            destinations.add(destination)
        return entries

    def _load_code_map(self) -> tuple[tuple[str, str, str, str], ...]:
        text = self.code_map_path.read_text(encoding="utf-8")
        section = "Reference Code Map"
        entries: list[tuple[str, str, str, str]] = []
        by_destination = {
            entry.descriptor.destination: reference_id
            for reference_id, entry in self._entries.items()
        }
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if not line.startswith("- "):
                continue
            paths = _CODE_PATH_RE.findall(line)
            if not paths:
                continue
            label = line[2:].split(":", 1)[0].strip()
            for mapped_path in paths:
                parts = PurePosixPath(mapped_path).parts
                if len(parts) < 3 or parts[0] != "upstream":
                    continue
                reference_id = by_destination.get(parts[1])
                if reference_id is None:
                    raise ReferenceManifestError(
                        "Code map points to an undeclared reference",
                        details={"path": mapped_path},
                    )
                entries.append((section, label, reference_id, PurePosixPath(*parts[2:]).as_posix()))
        return tuple(entries)

    def _entry(self, reference_id: str) -> _ManifestEntry:
        try:
            return self._entries[reference_id]
        except KeyError as exc:
            raise ReferenceNotFoundError(
                f"Unknown reference ID: {reference_id}",
                details={"reference_id": reference_id},
            ) from exc

    def _selected_reference_ids(
        self, reference_ids: tuple[str, ...] | None
    ) -> tuple[str, ...]:
        if reference_ids is None or not reference_ids:
            return tuple(self._entries)
        selected: list[str] = []
        for reference_id in reference_ids:
            self._entry(reference_id)
            if reference_id not in selected:
                selected.append(reference_id)
        return tuple(selected)

    def _resolve_file(self, reference_id: str, relative_path: str) -> Path:
        if not relative_path or "\\" in relative_path or "\x00" in relative_path:
            raise ReferencePathError(
                "Reference path must be a non-empty POSIX relative path",
                details={"path": relative_path},
            )
        rel = PurePosixPath(relative_path)
        if rel.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in rel.parts):
            raise ReferencePathError(
                "Absolute, traversal, or drive-qualified reference paths are forbidden",
                details={"path": relative_path},
            )
        entry = self._entry(reference_id)
        root = entry.root.resolve(strict=True)
        candidate = entry.root.joinpath(*rel.parts)
        current = entry.root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ReferencePathError(
                    "Symbolic links are forbidden in reference paths",
                    details={"path": relative_path, "component": part},
                )
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ReferenceNotFoundError(
                "Reference file not found",
                details={"reference_id": reference_id, "path": relative_path},
            ) from exc
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ReferencePathError(
                "Reference path does not resolve to a regular file under its immutable root",
                details={"reference_id": reference_id, "path": relative_path},
            )
        return resolved

    def _tree_hash(self, root: Path) -> tuple[str, int, int]:
        digest = hashlib.sha256()
        files: list[Path] = []
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ReferenceIntegrityError(
                    "Symbolic links are forbidden in immutable reference trees",
                    details={"path": str(path)},
                )
            if path.is_file():
                files.append(path)
        files.sort(key=lambda path: path.relative_to(root).as_posix())
        total = 0
        for path in files:
            data = path.read_bytes()
            total += len(data)
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
        return digest.hexdigest(), len(files), total

    def _ordered_files(self, root: Path, priority_paths: list[str]) -> tuple[Path, ...]:
        priority: list[Path] = []
        seen: set[Path] = set()
        reference_id = next(
            reference_id for reference_id, entry in self._entries.items() if entry.root == root
        )
        for relative_path in priority_paths:
            path = self._resolve_file(reference_id, relative_path)
            if path not in seen:
                priority.append(path)
                seen.add(path)
        remainder = sorted(
            (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
        return tuple(priority + [path for path in remainder if path not in seen])

    def _require_recorder(self) -> ReferenceAccessRecorder:
        if self._recorder is None:
            raise ReferenceQueryError(
                "A run_id was supplied without a reference access recorder"
            )
        return self._recorder

    @staticmethod
    def _file_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _bounded_excerpt(line: str, limit: int = 300) -> str:
        compact = line.strip()
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 1]}…"
