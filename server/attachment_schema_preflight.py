"""Fail-fast validation for the opt-in direct attachment upload schema."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from db.engine import get_engine
from db.tables import DB_SCHEMA


@dataclass
class AttachmentSchemaPreflightError(RuntimeError):
    """Raised when direct upload is enabled before its migration is applied."""

    missing: tuple[str, ...]

    def __str__(self) -> str:
        details = ", ".join(self.missing)
        return (
            "Database schema is missing required direct-upload attachment changes: "
            f"{details}. Apply db/migrations/20260811_add_direct_s3_attachment_upload.sql "
            "before enabling ATTACHMENTS_DIRECT_UPLOAD_ENABLED."
        )


def validate_direct_upload_schema(
    *,
    engine: Engine | None = None,
    schema: str | None = None,
) -> None:
    """Require nullable sha256 plus uploading/deleting status constraints."""

    target_engine = engine or get_engine()
    target_schema = schema or DB_SCHEMA
    inspector = inspect(target_engine)
    if "uploaded_files" not in set(inspector.get_table_names(schema=target_schema)):
        raise AttachmentSchemaPreflightError((f"table {target_schema}.uploaded_files",))

    columns = {
        str(column["name"]): column
        for column in inspector.get_columns("uploaded_files", schema=target_schema)
    }
    missing: list[str] = []
    sha_column = columns.get("sha256")
    if sha_column is None:
        missing.append(f"column {target_schema}.uploaded_files.sha256")
    elif not bool(sha_column.get("nullable")):
        missing.append(f"nullable {target_schema}.uploaded_files.sha256")

    status_sql = " ".join(
        str(constraint.get("sqltext") or "").lower()
        for constraint in inspector.get_check_constraints(
            "uploaded_files",
            schema=target_schema,
        )
        if str(constraint.get("name") or "") == "uploaded_files_status_check"
    )
    for required_status in ("uploading", "deleting"):
        if required_status not in status_sql:
            missing.append(
                f"status {required_status} in {target_schema}.uploaded_files_status_check"
            )

    if missing:
        raise AttachmentSchemaPreflightError(tuple(missing))
