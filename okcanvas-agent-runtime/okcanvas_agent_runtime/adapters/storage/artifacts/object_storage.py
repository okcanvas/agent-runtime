from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import quote, unquote, urlparse

from okcanvas_agent_runtime.application.artifacts import ArtifactBlobContent, ArtifactBlobRecord
from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError


class ObjectStorageClient(Protocol):
    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Mapping[str, str],
    ) -> None: ...

    def get_object(self, *, bucket: str, key: str) -> bytes: ...

    def head_object(self, *, bucket: str, key: str) -> Mapping[str, object]: ...

    def delete_object(self, *, bucket: str, key: str) -> bool: ...


@dataclass(frozen=True)
class ObjectStorageArtifactSettings:
    bucket: str
    prefix: str = "okcanvas-artifacts"

    def normalized(self) -> "ObjectStorageArtifactSettings":
        bucket = self.bucket.strip()
        prefix = self.prefix.strip().strip("/")
        if not bucket:
            raise ValueError("Object Storage bucket is required")
        if not prefix or any(part in {"", ".", ".."} for part in prefix.split("/")):
            raise ValueError("Object Storage Artifact prefix is invalid")
        return ObjectStorageArtifactSettings(bucket=bucket, prefix=prefix)


class ObjectStorageArtifactBlobStore:
    """SDK-neutral object-storage Artifact adapter with opaque object-artifact-v1 refs."""

    backend_id = "object-storage-artifact-v1"
    _SCHEME = "object-artifact-v1"

    def __init__(self, settings: ObjectStorageArtifactSettings, client: ObjectStorageClient) -> None:
        self.settings = settings.normalized()
        self._client = client

    def initialize(self) -> None:
        return None

    def put(
        self,
        *,
        run_id: str,
        artifact_id: str,
        artifact_type: str,
        media_type: str,
        data: bytes,
    ) -> ArtifactBlobRecord:
        key = self._key(run_id=run_id, artifact_id=artifact_id)
        digest = hashlib.sha256(data).hexdigest()
        self._client.put_object(
            bucket=self.settings.bucket,
            key=key,
            data=data,
            content_type=media_type,
            metadata={
                "sha256": digest,
                "byte-length": str(len(data)),
                "artifact-type": artifact_type,
            },
        )
        return ArtifactBlobRecord(
            storage_ref=self._reference(key),
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
        bucket, key = self._parse_reference(storage_ref)
        try:
            data = self._client.get_object(bucket=bucket, key=key)
        except (FileNotFoundError, KeyError) as exc:
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
        bucket, key = self._parse_reference(storage_ref)
        try:
            head = self._client.head_object(bucket=bucket, key=key)
        except (FileNotFoundError, KeyError) as exc:
            raise ArtifactIntegrityError(
                "Artifact blob is missing",
                details={"storage_ref": storage_ref, "reason": "missing"},
            ) from exc
        metadata = head.get("metadata") if isinstance(head, Mapping) else None
        sha = metadata.get("sha256") if isinstance(metadata, Mapping) else None
        length_raw = metadata.get("byte-length") if isinstance(metadata, Mapping) else None
        try:
            length = int(length_raw) if length_raw is not None else int(head["content_length"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactIntegrityError(
                "Artifact object metadata is invalid",
                details={"storage_ref": storage_ref, "reason": "invalid-object-metadata"},
            ) from exc
        if sha == expected_sha256 and length == expected_byte_length:
            return ArtifactBlobRecord(
                storage_ref=storage_ref,
                sha256=expected_sha256,
                byte_length=expected_byte_length,
                media_type=str(head.get("content_type", "application/octet-stream")),
            )
        # A metadata mismatch must be confirmed from bytes before returning an integrity error.
        return self.read(
            storage_ref,
            expected_sha256=expected_sha256,
            expected_byte_length=expected_byte_length,
        ).record

    def delete(self, storage_ref: str) -> bool:
        bucket, key = self._parse_reference(storage_ref)
        return bool(self._client.delete_object(bucket=bucket, key=key))

    def exists(self, storage_ref: str) -> bool:
        bucket, key = self._parse_reference(storage_ref)
        try:
            self._client.head_object(bucket=bucket, key=key)
            return True
        except (FileNotFoundError, KeyError):
            return False

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

    def _key(self, *, run_id: str, artifact_id: str) -> str:
        for value, label in ((run_id, "run_id"), (artifact_id, "artifact_id")):
            if not value or "/" in value or value in {".", ".."}:
                raise ArtifactIntegrityError(
                    f"Artifact {label} is invalid",
                    details={"reason": "invalid-object-key-component"},
                )
        return f"{self.settings.prefix}/{run_id}/{artifact_id}.blob"

    def _reference(self, key: str) -> str:
        return f"{self._SCHEME}://{quote(self.settings.bucket, safe='')}/{quote(key, safe='/')}"

    def _parse_reference(self, storage_ref: str) -> tuple[str, str]:
        parsed = urlparse(storage_ref)
        if parsed.scheme != self._SCHEME or not parsed.netloc or not parsed.path:
            raise ArtifactIntegrityError(
                "Artifact storage reference is unsupported",
                details={"reason": "unsupported-storage-reference"},
            )
        bucket = unquote(parsed.netloc)
        key = unquote(parsed.path.lstrip("/"))
        expected_prefix = self.settings.prefix + "/"
        if bucket != self.settings.bucket or not key.startswith(expected_prefix):
            raise ArtifactIntegrityError(
                "Artifact storage reference is outside the configured Object Storage scope",
                details={"reason": "storage-reference-scope-mismatch"},
            )
        if any(part in {"", ".", ".."} for part in key.split("/")):
            raise ArtifactIntegrityError(
                "Artifact storage reference is invalid",
                details={"reason": "invalid-storage-reference"},
            )
        return bucket, key
