"""Upload service handling ingestion, validation, persistence, and cleanup."""

import io
import logging
import os
import uuid
import zipfile
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.analytics.validation import CANONICAL_COLUMNS, REQUIRED_COLUMNS, validate_and_clean_ledger
from app.core.config import get_settings
from app.core.exceptions import (
    FileTooLargeError,
    NotFoundError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.db.models.upload import Upload
from app.db.models.user import User
from app.repositories.audit_log_repo import create_audit_log
from app.repositories.transaction_repo import bulk_create_transactions
from app.repositories.upload_repo import (
    create_upload,
    get_upload_by_id,
    list_uploads,
)
from app.repositories.upload_repo import (
    delete_upload as repo_delete_upload,
)
from app.schemas.upload import UploadResponse

logger = logging.getLogger(__name__)


def get_template_csv() -> str:
    """Generate CSV template with canonical columns and a sample row.

    Returns:
        str: CSV string format template.
    """
    header = ",".join(CANONICAL_COLUMNS)
    sample_row = (
        "TXN-SAMPLE-001,2026-01-15 10:30:00,15000.00,VEND-1001,"
        "Finance,ACC-5001,john.doe,mary.smith,Office supplies"
    )
    return f"{header}\n{sample_row}\n"


def _validate_file_content(ext: str, file_bytes: bytes) -> None:
    """Validate raw file content bytes match the claimed file format.

    Enforces content inspection per docs/SECURITY.md Section 8.
    """
    if ext == ".xlsx":
        if not file_bytes.startswith(b"PK") or not zipfile.is_zipfile(io.BytesIO(file_bytes)):
            raise UnsupportedMediaTypeError(
                code="invalid_file_content",
                message="File content does not match Microsoft Excel (.xlsx) format.",
            )
    elif ext == ".csv":
        header = file_bytes[:1024]
        # Reject executable binaries (e.g. Windows PE, Linux ELF, Mach-O)
        if header.startswith(
            (
                b"MZ",
                b"\x7fELF",
                b"\xca\xfe\xba\xbe",
                b"\xce\xfa\xed\xfe",
                b"\xcf\xfa\xed\xfe",
            )
        ):
            raise UnsupportedMediaTypeError(
                code="invalid_file_content",
                message="File content is a binary executable, not valid CSV text.",
            )
        # Reject files with binary null bytes
        if b"\x00" in header:
            raise UnsupportedMediaTypeError(
                code="invalid_file_content",
                message="File contains binary null bytes and cannot be parsed as CSV.",
            )
        # Verify text decodability
        try:
            header.decode("utf-8")
        except UnicodeDecodeError:
            try:
                header.decode("latin-1")
            except Exception as e:
                raise UnsupportedMediaTypeError(
                    code="invalid_file_content",
                    message="File content is not readable text.",
                ) from e


def handle_file_upload(
    db: Session,
    file: UploadFile,
    current_user: User,
) -> UploadResponse:
    """Process, validate, store, and persist an uploaded transaction file.

    Args:
        db: Active database session.
        file: Multipart file object.
        current_user: Authenticated user uploading the file.

    Returns:
        UploadResponse: Summary of accepted and rejected records.

    Raises:
        FileTooLargeError: If file exceeds configured MAX_UPLOAD_MB.
        UnsupportedMediaTypeError: If format is not CSV or XLSX.
        ValidationError: If file is empty or missing required canonical columns.
    """
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".csv", ".xlsx"]:
        raise UnsupportedMediaTypeError(
            code="unsupported_media_type",
            message=f"Unsupported file format '{ext}'. Only .csv and .xlsx files are accepted.",
        )

    file_bytes = file.file.read()
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(
            code="file_too_large",
            message=f"File exceeds maximum allowed size of {settings.max_upload_mb}MB.",
        )

    if len(file_bytes) == 0:
        raise ValidationError(
            code="empty_file",
            message="Uploaded file is empty.",
        )

    # Content-based validation per docs/SECURITY.md Section 8
    _validate_file_content(ext, file_bytes)

    # Parse file into pandas DataFrame
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        logger.warning("Failed to parse uploaded file: %s", e)
        raise ValidationError(
            code="unparseable_file",
            message="Unable to parse file. Please verify CSV or Excel format.",
        ) from e

    if len(df) == 0:
        raise ValidationError(
            code="empty_file",
            message="Uploaded file contains no transaction rows.",
        )

    # Validate against canonical schema
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        raise ValidationError(
            code="missing_required_columns",
            message=f"Missing required columns: {', '.join(missing_required)}",
            details={"missing_columns": missing_required},
        )

    try:
        clean_df, val_summary = validate_and_clean_ledger(df)
    except ValueError as e:
        raise ValidationError(
            code="validation_failed",
            message=str(e),
        ) from e

    # Store file on disk in safe uploads/ directory
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = str(uploads_dir / stored_name)

    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    # Persist upload record in DB
    upload_record = create_upload(
        db,
        user_id=current_user.id,
        original_filename=filename,
        stored_path=stored_path,
        file_type=ext.lstrip("."),
        row_count_total=val_summary["total_rows"],
        row_count_accepted=val_summary["valid_rows"],
        row_count_rejected=val_summary["rejected_rows"],
        validation_summary=val_summary,
    )

    # Bulk insert accepted transactions
    if len(clean_df) > 0:
        txn_records = []
        for _, row in clean_df.iterrows():
            txn_records.append(
                {
                    "upload_id": upload_record.id,
                    "transaction_id": str(row["transaction_id"]),
                    "posting_date": row["posting_date"].to_pydatetime(),
                    "amount": float(row["amount"]),
                    "vendor_id": str(row["vendor_id"]),
                    "department": str(row["department"]) if row.get("department") else None,
                    "account_code": str(row["account_code"]) if row.get("account_code") else None,
                    "created_by": str(row["created_by"]) if row.get("created_by") else None,
                    "approved_by": str(row["approved_by"]) if row.get("approved_by") else None,
                    "description": str(row["description"]) if row.get("description") else None,
                }
            )
        bulk_create_transactions(db, txn_records)

    create_audit_log(
        db,
        action="upload",
        entity_type="upload",
        entity_id=str(upload_record.id),
        user_id=current_user.id,
        details={
            "original_filename": filename,
            "accepted_rows": upload_record.row_count_accepted,
            "rejected_rows": upload_record.row_count_rejected,
        },
    )

    logger.info(
        "Upload %d completed for user %s: %d accepted, %d rejected",
        upload_record.id,
        current_user.email,
        upload_record.row_count_accepted,
        upload_record.row_count_rejected,
    )
    return UploadResponse.model_validate(upload_record)


def get_upload_detail(db: Session, upload_id: int, current_user: User) -> Upload:
    """Retrieve upload record verifying ownership permissions.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.
        current_user: Authenticated user.

    Returns:
        Upload: Upload entity if found and authorized.

    Raises:
        NotFoundError: If upload not found or current user lacks view permissions.
    """
    upload = get_upload_by_id(db, upload_id)
    if not upload:
        raise NotFoundError(code="not_found", message=f"Upload {upload_id} not found.")

    if current_user.role != "manager" and upload.user_id != current_user.id:
        raise NotFoundError(code="not_found", message=f"Upload {upload_id} not found.")

    return upload


def list_uploads_for_user(
    db: Session,
    current_user: User,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Upload], int]:
    """List paginated uploads respecting user roles.

    Args:
        db: Active database session.
        current_user: Authenticated user (auditor sees own, manager sees all).
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        tuple[list[Upload], int]: (Uploads list, total count).
    """
    filter_user_id = None if current_user.role == "manager" else current_user.id
    offset = (page - 1) * page_size
    return list_uploads(db, user_id=filter_user_id, limit=page_size, offset=offset)


def delete_upload_for_user(db: Session, upload_id: int, current_user: User) -> None:
    """Delete upload and cascaded entities, verifying ownership.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.
        current_user: Authenticated user.

    Raises:
        NotFoundError: If upload not found or user lacks delete permissions.
    """
    upload = get_upload_detail(db, upload_id, current_user)
    stored_path = upload.stored_path

    # Delete from database (cascades transactions, runs, flagged items, reviews)
    repo_delete_upload(db, upload_id)

    # Clean up physical file if it exists
    if stored_path and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError as e:
            logger.warning("Could not delete physical upload file %s: %s", stored_path, e)

    create_audit_log(
        db,
        action="delete_upload",
        entity_type="upload",
        entity_id=str(upload_id),
        user_id=current_user.id,
        details={"upload_id": upload_id, "original_filename": upload.original_filename},
    )
    logger.info("Upload %d deleted by user %s", upload_id, current_user.email)
