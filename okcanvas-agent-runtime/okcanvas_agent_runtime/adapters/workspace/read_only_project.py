from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class ReadOnlyProjectInspectionError(RuntimeError):
    pass


_EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".local",
    "reference",
}
_TEXT_FILENAMES = {
    "README",
    "README.md",
    "AGENTS.md",
    "HANDOFF.md",
    "PLANS.md",
    "ROADMAP.md",
    "Makefile",
    "Dockerfile",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "pom.xml",
    "build.gradle",
    "settings.gradle",
    "go.mod",
    "Cargo.toml",
}
_TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".kt", ".kts",
    ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".rb", ".scala",
    ".sql", ".graphql", ".proto", ".xml", ".html", ".css", ".scss", ".vue", ".svelte",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties", ".md", ".txt",
    ".sh", ".bash", ".zsh", ".cmd", ".bat", ".ps1",
}
_STOP_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "what", "where", "how", "please",
    "project", "code", "source", "file", "files", "analysis", "analyze", "inspect", "structure",
    "find", "show", "tell", "give", "location", "line", "lines", "evidence",
    "코드", "소스", "파일", "프로젝트", "분석", "구조", "확인", "해주세요", "해줘", "어디", "무엇",
    "어디에서", "어디에", "있는지", "등록되는지", "파일과", "라인", "근거로", "알려줘", "알려주세요", "찾아줘", "찾아주세요",
    "테스트", "테스트가", "문서", "문서가",
}
_GENERIC_CODE_TERMS = {
    "api", "app", "application", "route", "routes", "router", "endpoint", "endpoints",
    "service", "module", "method", "function", "class",
}
_IMPLEMENTATION_PREFIXES = (
    "src/", "app/", "lib/", "server/", "backend/", "frontend/", "packages/", "modules/",
)
_CLIENT_PREFIXES = ("clients/", "client/", "web/", "ui/")
_TEST_PREFIXES = ("tests/", "test/", "spec/")
_DOCUMENT_PREFIXES = ("docs/", "doc/")
_ROUTE_PATTERN = re.compile(
    r"(?:@[A-Za-z_][A-Za-z0-9_\.]*\.(?:get|post|put|patch|delete|options|head|route)\s*\(|"
    r"\b(?:app|router|routes?)\.(?:get|post|put|patch|delete|options|head|route)\s*\(|"
    r"\b(?:add_api_route|add_route|map_get|map_post|requestmapping|getmapping|postmapping|putmapping|deletemapping)\b)",
    re.IGNORECASE,
)
_DEFINITION_PATTERN = re.compile(
    r"^\s*(?:async\s+def|def|class|interface|enum|record|function|export\s+(?:async\s+)?function)\b",
    re.IGNORECASE,
)
_MAX_FILES = 3_000
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_MAX_FILE_BYTES = 512 * 1024
_MAX_EVIDENCE_FILES = 4
_MAX_EXCERPT_CHARS = 1_600
_MAX_EXCERPT_LINES = 16
_MAX_EVIDENCE_CHARS = 5_000


@dataclass(frozen=True)
class ProjectEvidence:
    path: str
    line_start: int
    line_end: int
    excerpt: str


@dataclass(frozen=True)
class ProjectInspection:
    workspace_label: str
    snapshot_sha256: str
    files_considered: int
    bytes_considered: int
    inspected_files: tuple[str, ...]
    evidence: tuple[ProjectEvidence, ...]
    evidence_characters: int
    query_terms_considered: int
    truncated: bool


@dataclass(frozen=True)
class _QueryProfile:
    terms: tuple[str, ...]
    route_registration: bool
    definition_lookup: bool
    test_target: bool
    document_target: bool
    client_target: bool


@dataclass(frozen=True)
class _Candidate:
    path: str
    text: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class _RankedCandidate:
    score: float
    path: str
    text: str
    lines: tuple[str, ...]
    match_index: int


def _safe_root(root: str | Path) -> Path:
    raw = Path(root).expanduser()
    if raw.is_symlink():
        raise ReadOnlyProjectInspectionError("Read-only project root must not be a symbolic link")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise ReadOnlyProjectInspectionError("Read-only project root does not exist") from exc
    if not resolved.is_dir():
        raise ReadOnlyProjectInspectionError("Read-only project root must be a directory")
    return resolved


def _relative(path: Path, root: Path) -> str:
    try:
        value = path.resolve(strict=True).relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ReadOnlyProjectInspectionError("Project file escaped the configured root") from exc
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts:
        raise ReadOnlyProjectInspectionError("Project file path is unsafe")
    return value


def _is_text_candidate(path: Path) -> bool:
    return path.name in _TEXT_FILENAMES or path.suffix.lower() in _TEXT_SUFFIXES


def _allowed_relative_path_domain(paths: Iterable[str] | None) -> frozenset[str] | None:
    if paths is None:
        return None
    normalized: set[str] = set()
    for raw in paths:
        value = str(raw).replace("\\", "/").strip()
        pure = PurePosixPath(value)
        if not value or pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
            raise ReadOnlyProjectInspectionError("Allowed project file path is unsafe")
        normalized.add(value)
    return frozenset(normalized)


def _decode_text(raw: bytes) -> str | None:
    if b"\x00" in raw:
        return None
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _keywords(query: str) -> tuple[str, ...]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_.:/-]{1,95}|[가-힣]{2,32}", query.lower())
    unique: list[str] = []
    for token in tokens:
        normalized = token.strip("._-:/")
        if len(normalized) < 2 or normalized in _STOP_WORDS or normalized in unique:
            continue
        unique.append(normalized)
        if len(unique) >= 12:
            break
    return tuple(unique)


def _query_profile(query: str) -> _QueryProfile:
    lowered = query.lower()
    terms = _keywords(query)
    route_registration = any(
        marker in lowered
        for marker in (
            "register", "registered", "registration", "route", "routing", "endpoint",
            "등록", "라우트", "라우팅", "엔드포인트", "매핑",
        )
    )
    definition_lookup = any(
        marker in lowered
        for marker in (
            "defined", "definition", "implemented", "implementation", "class", "function", "method",
            "정의", "구현", "클래스", "함수", "메서드",
        )
    )
    test_target = any(marker in lowered for marker in ("test", "tests", "pytest", "junit", "테스트"))
    document_target = any(
        marker in lowered
        for marker in ("document", "documentation", "docs", "readme", "roadmap", "plan", "문서", "계획")
    )
    client_target = any(
        marker in lowered
        for marker in ("client", "frontend", "typescript", "javascript", "vue", "react", "클라이언트", "프런트")
    )
    return _QueryProfile(
        terms=terms,
        route_registration=route_registration,
        definition_lookup=definition_lookup,
        test_target=test_target,
        document_target=document_target,
        client_target=client_target,
    )



def _path_category(path: str) -> str:
    if path.startswith(_TEST_PREFIXES):
        return "test"
    if path.startswith(_DOCUMENT_PREFIXES) or PurePosixPath(path).name in _TEXT_FILENAMES:
        return "document"
    if path.startswith(_CLIENT_PREFIXES):
        return "client"
    if path.startswith(_IMPLEMENTATION_PREFIXES):
        return "implementation"
    return "other"

def _path_category_score(path: str, profile: _QueryProfile) -> int:
    if path.startswith(_IMPLEMENTATION_PREFIXES):
        return 28
    if path.startswith(_CLIENT_PREFIXES):
        return 24 if profile.client_target else 4
    if path.startswith(_TEST_PREFIXES):
        return 28 if profile.test_target else -18
    if path.startswith(_DOCUMENT_PREFIXES):
        return 28 if profile.document_target else -24
    name = PurePosixPath(path).name
    if name in _TEXT_FILENAMES:
        return 22 if profile.document_target else -12
    return 0


def _contains_term(value: str, term: str) -> bool:
    if term.isascii() and re.fullmatch(r"[a-z_][a-z0-9_]*", term):
        if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", value) is not None:
            return True
        # Code identifiers commonly embed a meaningful term in snake/camel names or route
        # literals (for example test_health_route and /healthz). Keep this fallback for
        # specific terms only; short generic terms such as api still require boundaries.
        return len(term) >= 4 and term in value
    return term in value


def _term_weights(candidates: list[_Candidate], terms: tuple[str, ...]) -> dict[str, float]:
    total = len(candidates)
    weights: dict[str, float] = {}
    for term in terms:
        present = sum(
            1
            for candidate in candidates
            if _contains_term(candidate.path.lower(), term) or _contains_term(candidate.text.lower(), term)
        )
        idf = 1.0 + math.log2((total + 1) / (present + 1))
        if term in _GENERIC_CODE_TERMS:
            idf *= 0.45
        weights[term] = max(0.5, idf)
    return weights


def _path_match_score(path: str, weights: dict[str, float]) -> float:
    lowered = path.lower()
    return sum(24.0 * weight for term, weight in weights.items() if _contains_term(lowered, term))


def _line_match_score(
    lines: tuple[str, ...],
    index: int,
    profile: _QueryProfile,
    weights: dict[str, float],
) -> float:
    current = lines[index].lower()
    start = max(0, index - 2)
    end = min(len(lines), index + 3)
    window = "\n".join(lines[start:end]).lower()
    score = 0.0
    matched_terms = 0
    rare_term_on_current = False
    for term, weight in weights.items():
        if _contains_term(current, term):
            score += 22.0 * weight
            matched_terms += 1
            if term not in _GENERIC_CODE_TERMS:
                rare_term_on_current = True
        elif _contains_term(window, term):
            score += 8.0 * weight
            matched_terms += 1
    if matched_terms > 1:
        score += min(36.0, matched_terms * 7.0)
    if profile.route_registration and _ROUTE_PATTERN.search(window):
        score += 90.0
        if rare_term_on_current or any(
            term not in _GENERIC_CODE_TERMS and _contains_term(window, term)
            for term in weights
        ):
            score += 120.0
    if profile.definition_lookup and _DEFINITION_PATTERN.search(lines[index]):
        score += 55.0
    return score


def _rank_candidate(
    candidate: _Candidate,
    profile: _QueryProfile,
    weights: dict[str, float],
) -> _RankedCandidate:
    best_index = 0
    best_line_score = -1.0
    for index in range(len(candidate.lines)):
        score = _line_match_score(candidate.lines, index, profile, weights)
        if score > best_line_score:
            best_line_score = score
            best_index = index
    total_score = (
        best_line_score
        + _path_match_score(candidate.path, weights)
        + _path_category_score(candidate.path, profile)
    )
    return _RankedCandidate(
        score=total_score,
        path=candidate.path,
        text=candidate.text,
        lines=candidate.lines,
        match_index=best_index,
    )


def _excerpt(lines: tuple[str, ...], match_index: int, remaining_chars: int) -> tuple[int, int, str]:
    if not lines:
        return 1, 1, ""
    before = 4
    start = max(0, match_index - before)
    end = min(len(lines), start + _MAX_EXCERPT_LINES)
    if end - start < _MAX_EXCERPT_LINES:
        start = max(0, end - _MAX_EXCERPT_LINES)
    selected = lines[start:end]
    rendered = "\n".join(f"{start + offset + 1}: {line}" for offset, line in enumerate(selected))
    limit = min(_MAX_EXCERPT_CHARS, max(1, remaining_chars))
    if len(rendered) > limit:
        rendered = rendered[: max(0, limit - 1)] + "…"
    actual_line_count = rendered.count("\n") + 1 if rendered else 1
    return start + 1, min(end, start + actual_line_count), rendered


def inspect_readonly_project(
    root: str | Path,
    query: str,
    *,
    allowed_relative_paths: Iterable[str] | None = None,
) -> ProjectInspection:
    workspace = _safe_root(root)
    allowed_paths = _allowed_relative_path_domain(allowed_relative_paths)
    profile = _query_profile(query)
    digest = hashlib.sha256()
    candidates: list[_Candidate] = []
    files_considered = 0
    bytes_considered = 0
    truncated = False

    for directory, directory_names, file_names in os.walk(workspace, topdown=True, followlinks=False):
        directory_path = Path(directory)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in _EXCLUDED_DIRECTORY_NAMES and not (directory_path / name).is_symlink()
        )
        for name in sorted(file_names):
            path = directory_path / name
            if path.is_symlink() or not _is_text_candidate(path):
                continue
            try:
                relative = _relative(path, workspace)
            except ReadOnlyProjectInspectionError:
                continue
            if allowed_paths is not None and relative not in allowed_paths:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > _MAX_FILE_BYTES:
                continue
            if files_considered >= _MAX_FILES or bytes_considered + stat.st_size > _MAX_TOTAL_BYTES:
                truncated = True
                break
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            text = _decode_text(raw)
            if text is None:
                continue
            files_considered += 1
            bytes_considered += len(raw)
            content_sha = hashlib.sha256(raw).hexdigest()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(content_sha.encode("ascii"))
            digest.update(b"\0")
            candidates.append(_Candidate(relative, text, tuple(text.splitlines())))
        if truncated:
            break

    if not candidates:
        raise ReadOnlyProjectInspectionError("No bounded text files were available in the configured project")

    weights = _term_weights(candidates, profile.terms)
    ranked = sorted(
        (_rank_candidate(candidate, profile, weights) for candidate in candidates),
        key=lambda item: (-item.score, item.path),
    )
    positive = [item for item in ranked if item.score > 0]
    if profile.test_target:
        preferred = [item for item in positive if _path_category(item.path) == "test"]
    elif profile.document_target:
        preferred = [item for item in positive if _path_category(item.path) == "document"]
    elif profile.client_target:
        preferred = [item for item in positive if _path_category(item.path) == "client"]
    else:
        preferred = [
            item
            for item in positive
            if _path_category(item.path) not in {"test", "document"}
        ]
    pool = preferred or positive
    if pool:
        relevance_floor = max(1.0, pool[0].score * 0.40)
        selected = [item for item in pool if item.score >= relevance_floor][:_MAX_EVIDENCE_FILES]
    else:
        selected = []
    if not selected:
        selected = ranked[: min(3, len(ranked))]

    evidence: list[ProjectEvidence] = []
    evidence_characters = 0
    for item in selected:
        remaining = _MAX_EVIDENCE_CHARS - evidence_characters
        if remaining <= 0:
            break
        line_start, line_end, rendered = _excerpt(item.lines, item.match_index, remaining)
        evidence.append(
            ProjectEvidence(
                path=item.path,
                line_start=line_start,
                line_end=line_end,
                excerpt=rendered,
            )
        )
        evidence_characters += len(rendered)

    if not evidence:
        raise ReadOnlyProjectInspectionError("No bounded project evidence matched the query")

    return ProjectInspection(
        workspace_label=workspace.name or "project",
        snapshot_sha256=digest.hexdigest(),
        files_considered=files_considered,
        bytes_considered=bytes_considered,
        inspected_files=tuple(item.path for item in evidence),
        evidence=tuple(evidence),
        evidence_characters=evidence_characters,
        query_terms_considered=len(profile.terms),
        truncated=truncated,
    )
