from __future__ import annotations
import hashlib, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT=ROOT.parent/'okcanvas-agent-runtime-reference-pack-2.67.2.zip'
ARCHIVE_ROOT=Path('okcanvas-agent-runtime-reference')

def _include(path: Path) -> bool:
    return path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'}

def package(output: Path=DEFAULT_OUTPUT) -> dict[str, object]:
    output=output.resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): output.unlink()
    entries=[]
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
        for path in sorted((p for p in (ROOT/'reference').rglob('*') if _include(p)),key=lambda p:p.relative_to(ROOT).as_posix()):
            rel=path.relative_to(ROOT); entries.append(rel.as_posix())
            info=zipfile.ZipInfo((ARCHIVE_ROOT/rel).as_posix(),date_time=(2026,8,4,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(path.stat().st_mode & 0xFFFF)<<16
            zf.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(f'{digest}  {output.name}\n',encoding='utf-8')
    return {'path':str(output),'sha256':digest,'entry_count':len(entries),'root':ARCHIVE_ROOT.as_posix(),'entries':entries}

def main(argv=None)->int:
    args=sys.argv[1:] if argv is None else argv
    result=package(Path(args[0]) if args else DEFAULT_OUTPUT)
    print(result['path']); print(result['sha256']); print(result['entry_count']); return 0
if __name__=='__main__': raise SystemExit(main())
