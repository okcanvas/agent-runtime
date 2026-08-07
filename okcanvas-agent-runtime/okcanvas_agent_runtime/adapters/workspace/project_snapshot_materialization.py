from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotIntegrityError
from okcanvas_agent_runtime.domain.project_snapshots.models import PreparedProjectSnapshot


@contextmanager
def materialize_project_snapshot(
    prepared: PreparedProjectSnapshot,
    *,
    temporary_parent: str | Path | None = None,
) -> Iterator[Path]:
    base = Path(temporary_parent).expanduser().resolve() if temporary_parent is not None else None
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
        if base.is_symlink() or not base.is_dir():
            raise ProjectSnapshotIntegrityError("Project snapshot temporary parent is unsafe")
    root = Path(tempfile.mkdtemp(prefix="okcanvas-project-snapshot-", dir=str(base) if base else None)).resolve()
    try:
        expected = {item.path: item for item in prepared.metadata.files}
        observed: set[str] = set()
        with zipfile.ZipFile(io.BytesIO(prepared.archive), mode="r") as archive:
            for info in archive.infolist():
                path = info.filename.rstrip("/")
                if info.is_dir():
                    continue
                item = expected.get(path)
                if item is None or path in observed:
                    raise ProjectSnapshotIntegrityError("Project snapshot archive no longer matches its manifest")
                target = (root / Path(*path.split("/"))).resolve()
                if root not in target.parents:
                    raise ProjectSnapshotIntegrityError("Project snapshot materialization escaped the temporary root")
                target.parent.mkdir(parents=True, exist_ok=True)
                content = archive.read(info)
                if len(content) != item.byte_length or hashlib.sha256(content).hexdigest() != item.sha256:
                    raise ProjectSnapshotIntegrityError("Project snapshot materialized file identity does not match")
                target.write_bytes(content)
                observed.add(path)
        if observed != set(expected):
            raise ProjectSnapshotIntegrityError("Project snapshot manifest files were not all materialized")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=False)
