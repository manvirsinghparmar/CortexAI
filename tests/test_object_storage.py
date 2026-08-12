from __future__ import annotations

import pytest

from server.object_storage import (
    ObjectStorageNotFoundError,
    S3ObjectStorage,
    S3StorageConfig,
)


def _storage(client) -> S3ObjectStorage:
    storage = S3ObjectStorage(
        S3StorageConfig(
            bucket="cortex-files",
            region="us-east-1",
            endpoint_url=None,
            access_key_id=None,
            secret_access_key=None,
            session_token=None,
            use_ssl=True,
            force_path_style=False,
            key_prefix="attachments",
        )
    )
    storage._client = client
    return storage


def test_presigned_post_is_constrained_to_key_type_size_and_file_id():
    captured = {}

    class Client:
        def generate_presigned_post(self, **kwargs):
            captured.update(kwargs)
            return {
                "url": "https://cortex-files.s3.amazonaws.com",
                "fields": {**kwargs["Fields"], "policy": "secret-policy"},
            }

    result = _storage(Client()).create_presigned_post(
        key="attachments/users/user-a/2026/08/11/file-a-report.pdf",
        content_type="application/pdf",
        max_size_bytes=1234,
        file_id="file-a",
        expires_in_seconds=300,
    )

    assert result.url == "https://cortex-files.s3.amazonaws.com"
    assert result.fields["x-amz-meta-cortex-file-id"] == "file-a"
    assert captured["Bucket"] == "cortex-files"
    assert captured["Key"].endswith("file-a-report.pdf")
    assert {"key": captured["Key"]} in captured["Conditions"]
    assert {"Content-Type": "application/pdf"} in captured["Conditions"]
    assert {"x-amz-meta-cortex-file-id": "file-a"} in captured["Conditions"]
    assert ["content-length-range", 1, 1234] in captured["Conditions"]
    assert captured["ExpiresIn"] == 300


def test_head_object_normalizes_metadata():
    class Client:
        def head_object(self, **kwargs):
            assert kwargs == {"Bucket": "cortex-files", "Key": "attachments/file-a"}
            return {
                "ContentLength": 42,
                "ContentType": "Application/PDF",
                "Metadata": {"Cortex-File-Id": "file-a"},
            }

    result = _storage(Client()).head_object(key="attachments/file-a")

    assert result.content_length == 42
    assert result.content_type == "application/pdf"
    assert result.metadata == {"cortex-file-id": "file-a"}


def test_head_object_maps_s3_missing_to_normalized_exception():
    class Missing(Exception):
        response = {"Error": {"Code": "NoSuchKey"}}

    class Client:
        def head_object(self, **_kwargs):
            raise Missing("private provider detail")

    with pytest.raises(ObjectStorageNotFoundError, match="does not exist"):
        _storage(Client()).head_object(key="attachments/missing")
