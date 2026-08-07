from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReferenceDescriptor:
    reference_id: str
    classification: str
    version: str
    source_url: str
    destination: str
    tree_sha256: str
    file_count: int
    byte_count: int
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceVerification:
    reference_id: str
    expected_tree_sha256: str
    actual_tree_sha256: str
    expected_file_count: int
    actual_file_count: int
    expected_byte_count: int
    actual_byte_count: int
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodeMapEntry:
    section: str
    label: str
    reference_id: str
    relative_path: str
    file_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceFileMatch:
    reference_id: str
    classification: str
    version: str
    relative_path: str
    line_number: int
    excerpt: str
    file_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceSearchResult:
    query_sha256: str
    reference_ids: tuple[str, ...]
    code_map_matches: tuple[CodeMapEntry, ...]
    matches: tuple[ReferenceFileMatch, ...]
    scanned_files: int
    skipped_oversized_files: int
    skipped_non_text_files: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_sha256": self.query_sha256,
            "reference_ids": list(self.reference_ids),
            "code_map_matches": [item.to_dict() for item in self.code_map_matches],
            "matches": [item.to_dict() for item in self.matches],
            "scanned_files": self.scanned_files,
            "skipped_oversized_files": self.skipped_oversized_files,
            "skipped_non_text_files": self.skipped_non_text_files,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class ReferenceLine:
    line_number: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceReadResult:
    reference_id: str
    classification: str
    version: str
    relative_path: str
    requested_start_line: int
    requested_end_line: int
    actual_start_line: int
    actual_end_line: int
    total_lines: int
    file_sha256: str
    byte_length: int
    lines: tuple[ReferenceLine, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "classification": self.classification,
            "version": self.version,
            "relative_path": self.relative_path,
            "requested_start_line": self.requested_start_line,
            "requested_end_line": self.requested_end_line,
            "actual_start_line": self.actual_start_line,
            "actual_end_line": self.actual_end_line,
            "total_lines": self.total_lines,
            "file_sha256": self.file_sha256,
            "byte_length": self.byte_length,
            "lines": [item.to_dict() for item in self.lines],
        }
