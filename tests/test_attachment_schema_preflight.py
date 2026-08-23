from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from server.attachment_schema_preflight import (
    AttachmentSchemaPreflightError,
    validate_direct_upload_schema,
)


def test_direct_upload_schema_preflight_rejects_legacy_attachment_shape():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE uploaded_files ("
                "id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, status TEXT NOT NULL, "
                "CONSTRAINT uploaded_files_status_check CHECK (status IN ('ready', 'failed'))"
                ")"
            )
        )

    with pytest.raises(AttachmentSchemaPreflightError) as exc:
        validate_direct_upload_schema(engine=engine, schema="main")

    assert "nullable main.uploaded_files.sha256" in exc.value.missing
    assert "status uploading" in str(exc.value)
    assert "status deleting" in str(exc.value)


def test_direct_upload_schema_preflight_accepts_migrated_attachment_shape():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE uploaded_files ("
                "id TEXT PRIMARY KEY, sha256 TEXT NULL, status TEXT NOT NULL, "
                "CONSTRAINT uploaded_files_status_check "
                "CHECK (status IN ('uploading', 'ready', 'deleting', 'deleted'))"
                ")"
            )
        )

    validate_direct_upload_schema(engine=engine, schema="main")
