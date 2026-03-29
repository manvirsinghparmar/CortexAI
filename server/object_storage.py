"""Object storage abstraction for attachment files.

This module keeps storage provider details out of route/service code.
Current implementation targets S3-compatible storage, including MinIO.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol


class ObjectStorageError(RuntimeError):
    """Base object storage runtime error."""


class ObjectStorageConfigurationError(ObjectStorageError):
    """Raised when required storage configuration is missing/invalid."""


class ObjectStorageOperationError(ObjectStorageError):
    """Raised when object storage operations fail."""


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
        )


class ObjectStorageClient(Protocol):
    """Interface used by attachment services."""

    bucket: str
    key_prefix: str

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


class S3ObjectStorage:
    """S3-compatible object storage client (AWS S3, MinIO, etc.)."""

    def __init__(self, config: S3StorageConfig):
        self._config = config
        self._client: Any | None = None

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

        try:
            kwargs: dict[str, Any] = {
                "Bucket": self._config.bucket,
                "Key": object_key,
                "Body": payload,
                "ContentType": content_type,
            }
            if metadata:
                kwargs["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
            self._get_client().put_object(**kwargs)
        except Exception as exc:
            raise ObjectStorageOperationError(
                f"Failed to upload object to bucket '{self._config.bucket}' key '{object_key}'"
            ) from exc

    def delete_object(self, *, key: str) -> None:
        object_key = str(key or "").strip()
        if not object_key:
            return
        try:
            self._get_client().delete_object(Bucket=self._config.bucket, Key=object_key)
        except Exception as exc:
            raise ObjectStorageOperationError(
                f"Failed to delete object '{object_key}' from bucket '{self._config.bucket}'"
            ) from exc

    def get_bytes(self, *, key: str) -> bytes:
        object_key = str(key or "").strip()
        if not object_key:
            raise ObjectStorageOperationError("Storage key is required")
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
            return bytes(data)
        except ObjectStorageOperationError:
            raise
        except Exception as exc:
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
