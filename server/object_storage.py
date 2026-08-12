"""Object storage abstraction for attachment files.

This module keeps storage provider details out of route/service code.
Current implementation targets S3-compatible storage, including MinIO.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from utils.logger import get_logger

logger = get_logger(__name__)


class ObjectStorageError(RuntimeError):
    """Base object storage runtime error."""


class ObjectStorageConfigurationError(ObjectStorageError):
    """Raised when required storage configuration is missing/invalid."""


class ObjectStorageOperationError(ObjectStorageError):
    """Raised when object storage operations fail."""


class ObjectStorageNotFoundError(ObjectStorageOperationError):
    """Raised when a requested object does not exist."""


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_optional(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_prefix(value: str | None) -> str:
    normalized = str(value or "").strip().strip("/")
    return normalized


@dataclass(frozen=True)
class PresignedPost:
    """Browser-safe form target returned by an S3 presign operation."""

    url: str
    fields: dict[str, str]


@dataclass(frozen=True)
class ObjectMetadata:
    """Normalized metadata returned by an object HEAD request."""

    content_length: int
    content_type: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class S3StorageConfig:
    """S3-compatible storage settings."""

    bucket: str
    region: str | None
    endpoint_url: str | None
    access_key_id: str | None
    secret_access_key: str | None
    session_token: str | None
    use_ssl: bool
    force_path_style: bool
    key_prefix: str
    server_side_encryption: str | None = None
    sse_kms_key_id: str | None = None

    @classmethod
    def from_env(cls) -> "S3StorageConfig":
        bucket = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_BUCKET") or os.getenv("S3_BUCKET")
        )
        if not bucket:
            raise ObjectStorageConfigurationError(
                "Missing object storage bucket. Set ATTACHMENTS_S3_BUCKET."
            )

        endpoint_url = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_ENDPOINT_URL") or os.getenv("ATTACHMENTS_S3_ENDPOINT")
        )
        region = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
        )
        access_key_id = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
        )
        secret_access_key = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        session_token = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_SESSION_TOKEN") or os.getenv("AWS_SESSION_TOKEN")
        )

        use_ssl = _env_bool("ATTACHMENTS_S3_USE_SSL", default=True)
        if endpoint_url and endpoint_url.lower().startswith("http://"):
            use_ssl = False

        force_path_style = _env_bool(
            "ATTACHMENTS_S3_FORCE_PATH_STYLE",
            default=bool(endpoint_url),
        )
        key_prefix = _normalize_prefix(os.getenv("ATTACHMENTS_S3_KEY_PREFIX") or "attachments")
        server_side_encryption = _normalize_optional(
            os.getenv("ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION")
        )
        if server_side_encryption:
            normalized_encryption = server_side_encryption.lower()
            if normalized_encryption == "aes256":
                server_side_encryption = "AES256"
            elif normalized_encryption == "aws:kms":
                server_side_encryption = "aws:kms"
            else:
                raise ObjectStorageConfigurationError(
                    "ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION must be AES256 or aws:kms."
                )
        sse_kms_key_id = _normalize_optional(os.getenv("ATTACHMENTS_S3_SSE_KMS_KEY_ID"))
        if sse_kms_key_id and server_side_encryption != "aws:kms":
            raise ObjectStorageConfigurationError(
                "ATTACHMENTS_S3_SSE_KMS_KEY_ID requires "
                "ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION=aws:kms."
            )

        return cls(
            bucket=bucket,
            region=region,
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            use_ssl=use_ssl,
            force_path_style=force_path_style,
            key_prefix=key_prefix,
            server_side_encryption=server_side_encryption,
            sse_kms_key_id=sse_kms_key_id,
        )


class ObjectStorageClient(Protocol):
    """Interface used by attachment services."""

    @property
    def bucket(self) -> str:
        """Configured private object-storage bucket."""

    @property
    def key_prefix(self) -> str:
        """Configured server-owned attachment key prefix."""

    def put_bytes(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Store raw bytes in object storage."""

    def delete_object(self, *, key: str) -> None:
        """Delete one object key."""

    def get_bytes(self, *, key: str) -> bytes:
        """Read raw bytes for one object key."""

    def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        file_id: str,
        expires_in_seconds: int,
    ) -> PresignedPost:
        """Create a constrained browser POST policy for one exact object key."""

    def head_object(self, *, key: str) -> ObjectMetadata:
        """Read normalized metadata without downloading object bytes."""


class S3ObjectStorage:
    """S3-compatible object storage client (AWS S3, MinIO, etc.)."""

    def __init__(self, config: S3StorageConfig):
        self._config = config
        self._client: Any | None = None

    @staticmethod
    def _hash_key(key: str) -> str:
        import hashlib

        text = str(key or "").strip()
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @property
    def bucket(self) -> str:
        return self._config.bucket

    @property
    def key_prefix(self) -> str:
        return self._config.key_prefix

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            import boto3
            from botocore.config import Config as BotocoreConfig
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            raise ObjectStorageConfigurationError(
                "boto3/botocore is required for S3 storage. Install boto3."
            ) from exc

        config_kwargs: dict[str, Any] = {}
        if self._config.region:
            config_kwargs["region_name"] = self._config.region
        if self._config.access_key_id:
            config_kwargs["aws_access_key_id"] = self._config.access_key_id
        if self._config.secret_access_key:
            config_kwargs["aws_secret_access_key"] = self._config.secret_access_key
        if self._config.session_token:
            config_kwargs["aws_session_token"] = self._config.session_token

        session = boto3.session.Session(**config_kwargs)
        botocore_config = BotocoreConfig(
            s3={"addressing_style": "path" if self._config.force_path_style else "virtual"}
        )
        self._client = session.client(
            "s3",
            endpoint_url=self._config.endpoint_url,
            use_ssl=self._config.use_ssl,
            config=botocore_config,
        )
        logger.info(
            "Initialized S3 object storage client",
            extra={
                "extra_fields": {
                    "event": "storage.client.initialized",
                    "storage_backend": "s3",
                    "region": self._config.region,
                    "endpoint_url": self._config.endpoint_url,
                    "use_ssl": bool(self._config.use_ssl),
                    "force_path_style": bool(self._config.force_path_style),
                    "bucket": self._config.bucket,
                    "key_prefix": self._config.key_prefix,
                    "server_side_encryption": self._config.server_side_encryption,
                }
            },
        )
        return self._client

    def put_bytes(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        object_key = str(key or "").strip()
        if not object_key:
            raise ObjectStorageOperationError("Storage key is required")

        import time

        started = time.perf_counter()
        object_key_hash = self._hash_key(object_key)
        logger.info(
            "Object storage upload started",
            extra={
                "extra_fields": {
                    "event": "storage.put.start",
                    "storage_backend": "s3",
                    "bucket": self._config.bucket,
                    "object_key_hash": object_key_hash,
                    "content_type": str(content_type or ""),
                    "size_bytes": len(payload or b""),
                }
            },
        )
        try:
            kwargs: dict[str, Any] = {
                "Bucket": self._config.bucket,
                "Key": object_key,
                "Body": payload,
                "ContentType": content_type,
            }
            if metadata:
                kwargs["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
            if self._config.server_side_encryption:
                kwargs["ServerSideEncryption"] = self._config.server_side_encryption
            if self._config.sse_kms_key_id:
                kwargs["SSEKMSKeyId"] = self._config.sse_kms_key_id
            response = self._get_client().put_object(**kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            request_metadata = response.get("ResponseMetadata") if isinstance(response, dict) else {}
            logger.info(
                "Object storage upload completed",
                extra={
                    "extra_fields": {
                        "event": "storage.put.success",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "http_status": (
                            request_metadata.get("HTTPStatusCode")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                        "provider_request_id": (
                            request_metadata.get("RequestId")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                    }
                },
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Object storage upload failed",
                extra={
                    "extra_fields": {
                        "event": "storage.put.failure",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise ObjectStorageOperationError(
                f"Failed to upload object to bucket '{self._config.bucket}' key '{object_key}'"
            ) from exc

    def create_presigned_post(
        self,
        *,
        key: str,
        content_type: str,
        max_size_bytes: int,
        file_id: str,
        expires_in_seconds: int,
    ) -> PresignedPost:
        object_key = str(key or "").strip()
        normalized_type = str(content_type or "").strip().lower()
        normalized_file_id = str(file_id or "").strip()
        size_limit = int(max_size_bytes)
        ttl_seconds = int(expires_in_seconds)
        if not object_key:
            raise ObjectStorageOperationError("Storage key is required")
        if not normalized_type:
            raise ObjectStorageOperationError("Content type is required")
        if not normalized_file_id:
            raise ObjectStorageOperationError("File ID is required")
        if size_limit <= 0 or ttl_seconds <= 0:
            raise ObjectStorageOperationError("Presign size and expiry must be positive")

        fields = {
            "key": object_key,
            "Content-Type": normalized_type,
            "x-amz-meta-cortex-file-id": normalized_file_id,
        }
        conditions: list[Any] = [
            {"key": object_key},
            {"Content-Type": normalized_type},
            {"x-amz-meta-cortex-file-id": normalized_file_id},
            ["content-length-range", 1, size_limit],
        ]
        if self._config.server_side_encryption:
            fields["x-amz-server-side-encryption"] = self._config.server_side_encryption
            conditions.append(
                {"x-amz-server-side-encryption": self._config.server_side_encryption}
            )
        if self._config.sse_kms_key_id:
            fields["x-amz-server-side-encryption-aws-kms-key-id"] = (
                self._config.sse_kms_key_id
            )
            conditions.append(
                {
                    "x-amz-server-side-encryption-aws-kms-key-id": (
                        self._config.sse_kms_key_id
                    )
                }
            )
        try:
            response = self._get_client().generate_presigned_post(
                Bucket=self._config.bucket,
                Key=object_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=ttl_seconds,
            )
            url = str(response.get("url") or "").strip()
            response_fields = response.get("fields")
            if not url or not isinstance(response_fields, dict):
                raise ObjectStorageOperationError("S3 returned an invalid presigned POST")
            logger.info(
                "Object storage presigned POST created",
                extra={
                    "extra_fields": {
                        "event": "storage.presign_post.success",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": self._hash_key(object_key),
                        "content_type": normalized_type,
                        "max_size_bytes": size_limit,
                        "expires_in_seconds": ttl_seconds,
                    }
                },
            )
            return PresignedPost(
                url=url,
                fields={str(name): str(value) for name, value in response_fields.items()},
            )
        except ObjectStorageOperationError:
            raise
        except Exception as exc:
            logger.exception(
                "Object storage presigned POST creation failed",
                extra={
                    "extra_fields": {
                        "event": "storage.presign_post.failure",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": self._hash_key(object_key),
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise ObjectStorageOperationError("Failed to authorize object upload") from exc

    @staticmethod
    def _is_not_found_error(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        error = response.get("Error")
        code = str(error.get("Code") if isinstance(error, dict) else "").strip()
        return code in {"404", "NoSuchKey", "NotFound"}

    def head_object(self, *, key: str) -> ObjectMetadata:
        object_key = str(key or "").strip()
        if not object_key:
            raise ObjectStorageOperationError("Storage key is required")
        try:
            response = self._get_client().head_object(
                Bucket=self._config.bucket,
                Key=object_key,
            )
            raw_metadata = response.get("Metadata")
            return ObjectMetadata(
                content_length=int(response.get("ContentLength") or 0),
                content_type=str(response.get("ContentType") or "").strip().lower(),
                metadata=(
                    {str(name).lower(): str(value) for name, value in raw_metadata.items()}
                    if isinstance(raw_metadata, dict)
                    else {}
                ),
            )
        except Exception as exc:
            if self._is_not_found_error(exc):
                raise ObjectStorageNotFoundError("Object does not exist") from exc
            logger.exception(
                "Object storage HEAD failed",
                extra={
                    "extra_fields": {
                        "event": "storage.head.failure",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": self._hash_key(object_key),
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise ObjectStorageOperationError("Failed to inspect object") from exc

    def delete_object(self, *, key: str) -> None:
        object_key = str(key or "").strip()
        if not object_key:
            return
        import time

        started = time.perf_counter()
        object_key_hash = self._hash_key(object_key)
        try:
            response = self._get_client().delete_object(Bucket=self._config.bucket, Key=object_key)
            latency_ms = int((time.perf_counter() - started) * 1000)
            request_metadata = response.get("ResponseMetadata") if isinstance(response, dict) else {}
            logger.info(
                "Object storage delete completed",
                extra={
                    "extra_fields": {
                        "event": "storage.delete.success",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "http_status": (
                            request_metadata.get("HTTPStatusCode")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                        "provider_request_id": (
                            request_metadata.get("RequestId")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                    }
                },
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Object storage delete failed",
                extra={
                    "extra_fields": {
                        "event": "storage.delete.failure",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise ObjectStorageOperationError(
                f"Failed to delete object '{object_key}' from bucket '{self._config.bucket}'"
            ) from exc

    def get_bytes(self, *, key: str) -> bytes:
        object_key = str(key or "").strip()
        if not object_key:
            raise ObjectStorageOperationError("Storage key is required")
        import time

        started = time.perf_counter()
        object_key_hash = self._hash_key(object_key)
        try:
            response = self._get_client().get_object(Bucket=self._config.bucket, Key=object_key)
            body = response.get("Body")
            if body is None:
                raise ObjectStorageOperationError(
                    f"Object body missing for key '{object_key}' in bucket '{self._config.bucket}'"
                )
            data = body.read()
            if not isinstance(data, (bytes, bytearray)):
                raise ObjectStorageOperationError(
                    f"Object read returned non-bytes payload for key '{object_key}'"
                )
            payload = bytes(data)
            latency_ms = int((time.perf_counter() - started) * 1000)
            request_metadata = response.get("ResponseMetadata") if isinstance(response, dict) else {}
            logger.info(
                "Object storage read completed",
                extra={
                    "extra_fields": {
                        "event": "storage.get.success",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "size_bytes": len(payload),
                        "http_status": (
                            request_metadata.get("HTTPStatusCode")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                        "provider_request_id": (
                            request_metadata.get("RequestId")
                            if isinstance(request_metadata, dict)
                            else None
                        ),
                    }
                },
            )
            return payload
        except ObjectStorageOperationError:
            raise
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Object storage read failed",
                extra={
                    "extra_fields": {
                        "event": "storage.get.failure",
                        "storage_backend": "s3",
                        "bucket": self._config.bucket,
                        "object_key_hash": object_key_hash,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise ObjectStorageOperationError(
                f"Failed to read object '{object_key}' from bucket '{self._config.bucket}'"
            ) from exc


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorageClient:
    """Return cached object storage client based on environment config."""
    backend = str(os.getenv("ATTACHMENTS_OBJECT_STORAGE_BACKEND") or "s3").strip().lower()
    if backend != "s3":
        raise ObjectStorageConfigurationError(
            f"Unsupported ATTACHMENTS_OBJECT_STORAGE_BACKEND '{backend}'. Supported: s3"
        )
    return S3ObjectStorage(S3StorageConfig.from_env())


def reset_object_storage_cache() -> None:
    """Test helper to refresh cached storage client after env changes."""
    get_object_storage.cache_clear()
