from __future__ import annotations

from io import BytesIO

import pytest

from okcanvas_agent_runtime.adapters.storage.artifacts import (
    Boto3S3CompatibleObjectStorageClient,
    S3CompatibleClientSettings,
)
from okcanvas_agent_runtime.bootstrap import application


class _MissingObject(Exception):
    def __init__(self) -> None:
        self.response = {
            "Error": {"Code": "NoSuchKey"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }
        super().__init__("missing")


class FakeS3SDKClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, object]] = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = {
            "Body": bytes(kwargs["Body"]),
            "ContentType": kwargs["ContentType"],
            "Metadata": dict(kwargs["Metadata"]),
        }

    def get_object(self, **kwargs):
        try:
            item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        except KeyError as exc:
            raise _MissingObject() from exc
        return {"Body": BytesIO(item["Body"])}

    def head_object(self, **kwargs):
        try:
            item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        except KeyError as exc:
            raise _MissingObject() from exc
        return {
            "ContentLength": len(item["Body"]),
            "ContentType": item["ContentType"],
            "Metadata": dict(item["Metadata"]),
        }

    def delete_object(self, **kwargs):
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)
        return {}


def test_s3_compatible_client_adapts_sdk_contract_and_missing_objects() -> None:
    sdk = FakeS3SDKClient()
    client = Boto3S3CompatibleObjectStorageClient(
        S3CompatibleClientSettings(
            endpoint_url="http://127.0.0.1:9000",
            region_name="us-east-1",
            addressing_style="path",
        ),
        sdk_client=sdk,
    )
    client.put_object(
        bucket="artifacts",
        key="prefix/run/artifact.blob",
        data=b"payload",
        content_type="application/octet-stream",
        metadata={"sha256": "a" * 64, "byte-length": "7"},
    )
    assert client.get_object(bucket="artifacts", key="prefix/run/artifact.blob") == b"payload"
    assert client.head_object(bucket="artifacts", key="prefix/run/artifact.blob") == {
        "content_length": 7,
        "content_type": "application/octet-stream",
        "metadata": {"sha256": "a" * 64, "byte-length": "7"},
    }
    assert client.delete_object(bucket="artifacts", key="prefix/run/artifact.blob") is True
    assert client.delete_object(bucket="artifacts", key="prefix/run/artifact.blob") is False
    with pytest.raises(FileNotFoundError):
        client.get_object(bucket="artifacts", key="prefix/run/artifact.blob")


def test_environment_composition_constructs_s3_client_only_for_object_backend(monkeypatch) -> None:
    captured = {}

    class FakeDeploymentClient:
        def __init__(self, settings):
            captured["settings"] = settings

    monkeypatch.setattr(application, "Boto3S3CompatibleObjectStorageClient", FakeDeploymentClient)
    assert application._object_storage_client_from_environment({}) is None
    result = application._object_storage_client_from_environment(
        {
            "OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND": "object-storage-artifact-v1",
            "OKCANVAS_ARTIFACT_OBJECT_ENDPOINT_URL": "http://127.0.0.1:9000",
            "OKCANVAS_ARTIFACT_OBJECT_REGION": "us-east-1",
            "OKCANVAS_ARTIFACT_OBJECT_ADDRESSING_STYLE": "path",
        }
    )
    assert isinstance(result, FakeDeploymentClient)
    assert captured["settings"].endpoint_url == "http://127.0.0.1:9000"
    assert captured["settings"].region_name == "us-east-1"
    assert captured["settings"].addressing_style == "path"


def test_s3_compatible_settings_reject_invalid_addressing_style() -> None:
    with pytest.raises(ValueError):
        S3CompatibleClientSettings(addressing_style="invalid").normalized()
