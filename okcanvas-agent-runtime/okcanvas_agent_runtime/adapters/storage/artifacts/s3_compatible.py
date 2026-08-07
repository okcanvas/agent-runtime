from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class S3CompatibleClientSettings:
    """Deployment-only S3-compatible client settings; credentials stay in the SDK chain."""

    endpoint_url: str | None = None
    region_name: str | None = None
    addressing_style: str = "auto"

    def normalized(self) -> "S3CompatibleClientSettings":
        endpoint = self.endpoint_url.strip() if self.endpoint_url else None
        region = self.region_name.strip() if self.region_name else None
        style = self.addressing_style.strip().lower()
        if style not in {"auto", "path", "virtual"}:
            raise ValueError("Object Storage addressing style must be auto, path, or virtual")
        return S3CompatibleClientSettings(
            endpoint_url=endpoint or None,
            region_name=region or None,
            addressing_style=style,
        )


class Boto3S3CompatibleObjectStorageClient:
    """ObjectStorageClient implementation for AWS S3 and S3-compatible deployments."""

    def __init__(
        self,
        settings: S3CompatibleClientSettings | None = None,
        *,
        sdk_client=None,
    ) -> None:
        self.settings = (settings or S3CompatibleClientSettings()).normalized()
        if sdk_client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError(
                    'S3-compatible Object Storage requires optional dependency "object-storage"'
                ) from exc
            sdk_client = boto3.client(
                "s3",
                endpoint_url=self.settings.endpoint_url,
                region_name=self.settings.region_name,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": self.settings.addressing_style},
                ),
            )
        self._client = sdk_client

    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Mapping[str, str],
    ) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=dict(metadata),
        )

    def get_object(self, *, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
        except Exception as exc:
            self._translate_missing(exc, key)
            raise
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise RuntimeError("Object Storage get_object response has no readable Body")
        data = body.read()
        if not isinstance(data, (bytes, bytearray)):
            raise RuntimeError("Object Storage get_object Body did not return bytes")
        return bytes(data)

    def head_object(self, *, bucket: str, key: str) -> Mapping[str, object]:
        try:
            response = self._client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            self._translate_missing(exc, key)
            raise
        metadata = response.get("Metadata")
        return {
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType", "application/octet-stream"),
            "metadata": dict(metadata) if isinstance(metadata, Mapping) else {},
        }

    def delete_object(self, *, bucket: str, key: str) -> bool:
        try:
            self.head_object(bucket=bucket, key=key)
        except FileNotFoundError:
            return False
        self._client.delete_object(Bucket=bucket, Key=key)
        return True

    @staticmethod
    def _translate_missing(exc: Exception, key: str) -> None:
        response = getattr(exc, "response", None)
        error = response.get("Error") if isinstance(response, Mapping) else None
        code = str(error.get("Code", "")) if isinstance(error, Mapping) else ""
        status = (
            response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if isinstance(response, Mapping)
            else None
        )
        if code in {"404", "NoSuchKey", "NotFound", "NoSuchObject"} or status == 404:
            raise FileNotFoundError(key) from exc
