from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parent
ARCHIVE_ROOT = Path("okcanvas-connectors")
DEFAULT_OUTPUT = REPOSITORY.parent / "okcanvas-connectors-groupware-mcp-server-step001r1.zip"
FIXED_TIME = (2026, 8, 4, 0, 0, 0)


def include(path: Path) -> bool:
    relative = path.relative_to(REPOSITORY)
    return (
        path.is_file()
        and "__pycache__" not in relative.parts
        and ".pytest_cache" not in relative.parts
        and relative.suffix not in {".pyc", ".pyo"}
        and not any(part in {".venv", "dist", "build"} for part in relative.parts)
    )


def package(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    entries: list[str] = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted((item for item in REPOSITORY.rglob("*") if include(item)), key=lambda item: item.relative_to(REPOSITORY).as_posix()):
            relative = path.relative_to(REPOSITORY)
            name = (ARCHIVE_ROOT / relative).as_posix()
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            entries.append(name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return {"path": str(output), "sha256": digest, "entry_count": len(entries), "root": ARCHIVE_ROOT.as_posix()}


def main() -> int:
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1].startswith("-")):
        raise SystemExit("package_source accepts at most one positional output path")
    result = package(Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_OUTPUT)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
