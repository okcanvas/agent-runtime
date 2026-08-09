from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.step081_product_inventory import included_relative_path

DEFAULT_OUTPUT = ROOT.parent / "okcanvas-agent-runtime-step096a-grounded-llm-interpretation-context-shadow-foundation.zip"
ARCHIVE_ROOT = Path("okcanvas-agent-runtime")
PACKAGE_STEP = "STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION"



def include(path: Path) -> bool:
    return included_relative_path(path.relative_to(ROOT))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0].startswith("-"):
        raise SystemExit("package_source accepts one positional output path; option-like arguments are rejected")
    if len(args) > 1:
        raise SystemExit("package_source accepts at most one positional output path")
    output = Path(args[0]).resolve() if args else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted((p for p in ROOT.rglob("*") if p.is_file() and include(p)), key=lambda p: p.relative_to(ROOT).as_posix()):
            arcname = ARCHIVE_ROOT / path.relative_to(ROOT)
            info = zipfile.ZipInfo(arcname.as_posix(), date_time=(2026, 8, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sha_path = output.with_suffix(output.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(output)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
