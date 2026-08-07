from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .models import OrganizationCatalogState, OrganizationContextRecord


_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class OrganizationContextCatalogError(RuntimeError):
    code = "ORGANIZATION_CONTEXT_CATALOG_INVALID"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(payload: dict[str, Any], key: str, *, maximum: int = 2000) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise OrganizationContextCatalogError(f"{key} must be a bounded non-empty string")
    if "\x00" in value:
        raise OrganizationContextCatalogError(f"{key} may not contain NUL")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str, *, maximum: int = 2000) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum or "\x00" in value:
        raise OrganizationContextCatalogError(f"{key} must be null or a bounded non-empty string")
    return value.strip()


def _string_list(payload: dict[str, Any], key: str, *, maximum_items: int = 50, maximum_chars: int = 300) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or len(value) > maximum_items:
        raise OrganizationContextCatalogError(f"{key} must be a bounded list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > maximum_chars or "\x00" in item:
            raise OrganizationContextCatalogError(f"{key} contains an invalid string")
        result.append(item.strip())
    if len({item.casefold() for item in result}) != len(result):
        raise OrganizationContextCatalogError(f"{key} contains duplicates")
    return tuple(result)


class OrganizationContextCatalog:
    _MANIFEST_KEYS = {
        "schema_version", "catalog_id", "version", "effective_at", "state",
        "glossary_file", "knowledge_file", "directory_file",
        "glossary_sha256", "knowledge_sha256", "directory_sha256",
    }

    def __init__(self, project_root: str | Path, catalog_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        base = Path(catalog_root).expanduser().resolve() if catalog_root is not None else self.project_root / "specs" / "organization"
        self.catalog_root = base.resolve()
        self._load()

    def _load(self) -> None:
        if self.catalog_root.is_symlink() or not self.catalog_root.is_dir():
            raise OrganizationContextCatalogError("Organization context catalog root is missing or unsafe")
        manifest_path = self._safe_file("manifest.json")
        manifest = self._load_json(manifest_path)
        if set(manifest) != self._MANIFEST_KEYS:
            raise OrganizationContextCatalogError("Organization context manifest keys are not exact")
        if manifest["schema_version"] != "okcanvas-organization-context-manifest-v1":
            raise OrganizationContextCatalogError("Organization context manifest schema is unsupported")
        self.catalog_id = _text(manifest, "catalog_id", maximum=128)
        if not _ID_RE.fullmatch(self.catalog_id):
            raise OrganizationContextCatalogError("Organization catalog ID is invalid")
        self.version = _text(manifest, "version", maximum=32)
        if not _VERSION_RE.fullmatch(self.version):
            raise OrganizationContextCatalogError("Organization catalog version is invalid")
        self.effective_at = _text(manifest, "effective_at", maximum=32)
        if not _TIMESTAMP_RE.fullmatch(self.effective_at):
            raise OrganizationContextCatalogError("Organization catalog effective_at is invalid")
        try:
            self.state = OrganizationCatalogState(_text(manifest, "state", maximum=16))
        except ValueError as exc:
            raise OrganizationContextCatalogError("Organization catalog state is invalid") from exc
        paths: dict[str, Path] = {}
        for kind in ("glossary", "knowledge", "directory"):
            filename = _text(manifest, f"{kind}_file", maximum=128)
            path = self._safe_file(filename)
            expected = _text(manifest, f"{kind}_sha256", maximum=64)
            if not _SHA_RE.fullmatch(expected) or _sha(path) != expected:
                raise OrganizationContextCatalogError(f"Organization {kind} hash mismatch")
            paths[kind] = path
        self.manifest_sha256 = _sha(manifest_path)
        self.glossary_sha256 = _sha(paths["glossary"])
        self.knowledge_sha256 = _sha(paths["knowledge"])
        self.directory_sha256 = _sha(paths["directory"])
        glossary = self._load_json(paths["glossary"])
        knowledge = self._load_json(paths["knowledge"])
        directory = self._load_json(paths["directory"])
        self.glossary_records = self._parse_glossary(glossary)
        self.knowledge_records = self._parse_knowledge(knowledge)
        self.directory_records = self._parse_directory(directory)
        all_records = self.glossary_records + self.knowledge_records + self.directory_records
        ids = [record.record_id for record in all_records]
        if len(set(ids)) != len(ids):
            raise OrganizationContextCatalogError("Organization context record IDs must be globally unique")
        if self.state is OrganizationCatalogState.EMPTY and all_records:
            raise OrganizationContextCatalogError("EMPTY organization catalog may not contain records")
        if self.state is OrganizationCatalogState.READY and not all_records:
            raise OrganizationContextCatalogError("READY organization catalog must contain records")

    @property
    def record_count(self) -> int:
        return len(self.glossary_records) + len(self.knowledge_records) + len(self.directory_records)

    def _safe_file(self, filename: str) -> Path:
        pure = PurePosixPath(filename)
        if pure.is_absolute() or len(pure.parts) != 1 or pure.name in {"", ".", ".."}:
            raise OrganizationContextCatalogError("Organization catalog filenames must be simple relative names")
        raw = self.catalog_root / pure.name
        if raw.is_symlink():
            raise OrganizationContextCatalogError("Symbolic organization catalog files are forbidden")
        path = raw.resolve()
        if path.parent != self.catalog_root or not path.is_file():
            raise OrganizationContextCatalogError(f"Organization catalog file is missing or unsafe: {filename}")
        return path

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OrganizationContextCatalogError("Organization catalog JSON is invalid") from exc
        if not isinstance(payload, dict):
            raise OrganizationContextCatalogError("Organization catalog JSON root must be an object")
        return payload

    def _parse_glossary(self, payload: dict[str, Any]) -> tuple[OrganizationContextRecord, ...]:
        if set(payload) != {"schema_version", "records"} or payload["schema_version"] != "okcanvas-organization-glossary-v1":
            raise OrganizationContextCatalogError("Organization glossary contract is invalid")
        records = payload["records"]
        if not isinstance(records, list) or len(records) > 5000:
            raise OrganizationContextCatalogError("Organization glossary records are invalid")
        expected = {
            "term_id", "canonical_name", "aliases", "definition", "source_title",
            "source_version", "source_reference", "tenant_id", "allowed_principal_ids",
            "allowed_roles", "valid_from", "valid_until", "classification",
        }
        result = []
        for item in records:
            if not isinstance(item, dict) or set(item) != expected:
                raise OrganizationContextCatalogError("Organization glossary record keys are not exact")
            record_id = self._id(item, "term_id")
            label = _text(item, "canonical_name", maximum=200)
            aliases = _string_list(item, "aliases", maximum_items=30, maximum_chars=200)
            summary = _text(item, "definition", maximum=2000)
            result.append(self._record("GLOSSARY", record_id, label, aliases, summary, item, " ".join((label, *aliases, summary))))
        return tuple(result)

    def _parse_knowledge(self, payload: dict[str, Any]) -> tuple[OrganizationContextRecord, ...]:
        if set(payload) != {"schema_version", "records"} or payload["schema_version"] != "okcanvas-organization-knowledge-v1":
            raise OrganizationContextCatalogError("Organization knowledge contract is invalid")
        records = payload["records"]
        if not isinstance(records, list) or len(records) > 10000:
            raise OrganizationContextCatalogError("Organization knowledge records are invalid")
        expected = {
            "knowledge_id", "title", "aliases", "summary", "keywords", "source_title",
            "source_version", "source_reference", "tenant_id", "allowed_principal_ids",
            "allowed_roles", "valid_from", "valid_until", "classification",
        }
        result = []
        for item in records:
            if not isinstance(item, dict) or set(item) != expected:
                raise OrganizationContextCatalogError("Organization knowledge record keys are not exact")
            record_id = self._id(item, "knowledge_id")
            label = _text(item, "title", maximum=300)
            aliases = _string_list(item, "aliases", maximum_items=30, maximum_chars=200)
            keywords = _string_list(item, "keywords", maximum_items=50, maximum_chars=100)
            summary = _text(item, "summary", maximum=3000)
            searchable = " ".join((label, *aliases, *keywords, summary))
            result.append(self._record("KNOWLEDGE", record_id, label, aliases + keywords, summary, item, searchable))
        return tuple(result)

    def _parse_directory(self, payload: dict[str, Any]) -> tuple[OrganizationContextRecord, ...]:
        if set(payload) != {"schema_version", "units", "people"} or payload["schema_version"] != "okcanvas-organization-directory-v1":
            raise OrganizationContextCatalogError("Organization directory contract is invalid")
        units = payload["units"]
        people = payload["people"]
        if not isinstance(units, list) or not isinstance(people, list) or len(units) > 5000 or len(people) > 50000:
            raise OrganizationContextCatalogError("Organization directory entries are invalid")
        result: list[OrganizationContextRecord] = []
        unit_ids: set[str] = set()
        unit_expected = {
            "unit_id", "name", "aliases", "unit_type", "parent_unit_id", "summary",
            "source_title", "source_version", "source_reference", "tenant_id",
            "allowed_principal_ids", "allowed_roles", "valid_from", "valid_until", "classification",
        }
        for item in units:
            if not isinstance(item, dict) or set(item) != unit_expected:
                raise OrganizationContextCatalogError("Organization unit keys are not exact")
            record_id = self._id(item, "unit_id")
            unit_ids.add(record_id)
            parent = _optional_text(item, "parent_unit_id", maximum=128)
            label = _text(item, "name", maximum=200)
            aliases = _string_list(item, "aliases", maximum_items=30, maximum_chars=200)
            summary = _text(item, "summary", maximum=2000)
            unit_type = _text(item, "unit_type", maximum=64)
            searchable = " ".join((label, *aliases, unit_type, summary))
            result.append(self._record("DIRECTORY_UNIT", record_id, label, aliases, summary, item, searchable))
            if parent == record_id:
                raise OrganizationContextCatalogError("Organization unit cannot parent itself")
        person_expected = {
            "person_id", "display_name", "aliases", "title", "unit_id", "principal_id",
            "summary", "source_title", "source_version", "source_reference", "tenant_id",
            "allowed_principal_ids", "allowed_roles", "valid_from", "valid_until",
            "classification", "status",
        }
        for item in people:
            if not isinstance(item, dict) or set(item) != person_expected:
                raise OrganizationContextCatalogError("Organization person keys are not exact")
            record_id = self._id(item, "person_id")
            unit_id = self._id(item, "unit_id")
            if unit_id not in unit_ids:
                raise OrganizationContextCatalogError("Organization person references an unknown unit")
            label = _text(item, "display_name", maximum=200)
            aliases = _string_list(item, "aliases", maximum_items=30, maximum_chars=200)
            title = _text(item, "title", maximum=200)
            principal_id = _optional_text(item, "principal_id", maximum=128)
            status = _text(item, "status", maximum=32)
            if status not in {"ACTIVE", "INACTIVE"}:
                raise OrganizationContextCatalogError("Organization person status is invalid")
            summary = _text(item, "summary", maximum=2000)
            searchable = " ".join((label, *aliases, title, unit_id, principal_id or "", summary))
            result.append(self._record("DIRECTORY_PERSON", record_id, label, aliases + (title,), summary, item, searchable))
        return tuple(result)

    def _record(self, kind: str, record_id: str, label: str, aliases: tuple[str, ...], summary: str, item: dict[str, Any], searchable: str) -> OrganizationContextRecord:
        tenant_id = _optional_text(item, "tenant_id", maximum=128)
        valid_from = _optional_text(item, "valid_from", maximum=10)
        valid_until = _optional_text(item, "valid_until", maximum=10)
        if valid_from is not None and not _DATE_RE.fullmatch(valid_from):
            raise OrganizationContextCatalogError("valid_from is invalid")
        if valid_until is not None and not _DATE_RE.fullmatch(valid_until):
            raise OrganizationContextCatalogError("valid_until is invalid")
        if valid_from and valid_until and valid_from > valid_until:
            raise OrganizationContextCatalogError("Organization record validity range is invalid")
        return OrganizationContextRecord(
            kind=kind,
            record_id=record_id,
            label=label,
            aliases=aliases,
            summary=summary,
            source_title=_text(item, "source_title", maximum=300),
            source_version=_text(item, "source_version", maximum=100),
            source_reference=_text(item, "source_reference", maximum=500),
            tenant_id=tenant_id,
            allowed_principal_ids=_string_list(item, "allowed_principal_ids", maximum_items=100, maximum_chars=128),
            allowed_roles=_string_list(item, "allowed_roles", maximum_items=50, maximum_chars=64),
            valid_from=valid_from,
            valid_until=valid_until,
            classification=_text(item, "classification", maximum=64),
            searchable_text=searchable,
        )

    @staticmethod
    def _id(payload: dict[str, Any], key: str) -> str:
        value = _text(payload, key, maximum=128)
        if not _ID_RE.fullmatch(value):
            raise OrganizationContextCatalogError(f"{key} is invalid")
        return value
