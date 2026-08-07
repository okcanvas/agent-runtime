from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path, PurePosixPath

from okcanvas_agent_runtime.application.artifacts import ArtifactBlobContent, ArtifactBlobRecord
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError


class LocalFilesystemArtifactBlobStore:
    """Local Artifact blob adapter using opaque local-artifact-v1 references."""

    backend_id = "local-filesystem-artifact-v1"
    _PREFIX = "local-artifact-v1://"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        run_id: str,
        artifact_id: str,
        artifact_type: str,
        media_type: str,
        data: bytes,
    ) -> ArtifactBlobRecord:
        del artifact_type
        self.initialize()
        relative = PurePosixPath(run_id, f"{artifact_id}.blob")
        path = self._path_for_relative(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        fd, temporary_name = tempfile.mkstemp(prefix=".artifact-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return ArtifactBlobRecord(
            storage_ref=self._PREFIX + relative.as_posix(),
            sha256=digest,
            byte_length=len(data),
            media_type=media_type,
        )

    def read(
        self,
        storage_ref: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> ArtifactBlobContent:
        path = self._path_for_ref(storage_ref)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError(
                "Artifact blob is missing",
                details={"storage_ref": storage_ref, "reason": "missing"},
            ) from exc
        record = self._validate(
            storage_ref=storage_ref,
            data=data,
            expected_sha256=expected_sha256,
            expected_byte_length=expected_byte_length,
        )
        return ArtifactBlobContent(record=record, data=data)

    def verify(
        self,
        storage_ref: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> ArtifactBlobRecord:
        return self.read(
            storage_ref,
            expected_sha256=expected_sha256,
            expected_byte_length=expected_byte_length,
        ).record

    def delete(self, storage_ref: str) -> bool:
        path = self._path_for_ref(storage_ref)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, storage_ref: str) -> bool:
        return self._path_for_ref(storage_ref).is_file()

    def _validate(
        self,
        *,
        storage_ref: str,
        data: bytes,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> ArtifactBlobRecord:
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha256 or len(data) != expected_byte_length:
            raise ArtifactIntegrityError(
                "Artifact blob integrity mismatch",
                details={
                    "storage_ref": storage_ref,
                    "expected_sha256": expected_sha256,
                    "actual_sha256": digest,
                    "expected_bytes": expected_byte_length,
                    "actual_bytes": len(data),
                    "reason": "mismatch",
                },
            )
        return ArtifactBlobRecord(
            storage_ref=storage_ref,
            sha256=digest,
            byte_length=len(data),
            media_type="application/octet-stream",
        )

    def _path_for_ref(self, storage_ref: str) -> Path:
        if not storage_ref.startswith(self._PREFIX):
            raise ArtifactIntegrityError(
                "Artifact storage reference is unsupported",
                details={"reason": "unsupported-storage-reference"},
            )
        relative_text = storage_ref[len(self._PREFIX):]
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ArtifactIntegrityError(
                "Artifact storage reference is invalid",
                details={"reason": "invalid-storage-reference"},
            )
        return self._path_for_relative(relative)

    def _path_for_relative(self, relative: PurePosixPath) -> Path:
        path = (self.root / Path(*relative.parts)).resolve()
        if path == self.root or self.root not in path.parents:
            raise ArtifactIntegrityError(
                "Artifact storage reference escaped its configured root",
                details={"reason": "storage-reference-escape"},
            )
        return path
