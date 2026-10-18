"""Upload repository functions."""

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.upload import Upload


def get_upload_by_id(db: Session, upload_id: int) -> Upload | None:
    """Retrieve an upload record by primary key ID.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.

    Returns:
        Upload | None: Upload entity if found, else None.
    """
    return db.get(Upload, upload_id)


def create_upload(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    stored_path: str,
    file_type: str,
    row_count_total: int = 0,
    row_count_accepted: int = 0,
    row_count_rejected: int = 0,
    validation_summary: dict[str, Any] | None = None,
) -> Upload:
    """Create and persist a new upload record.

    Args:
        db: Active database session.
        user_id: ID of the user uploading the file.
        original_filename: Original name of the uploaded file.
        stored_path: Disk or storage path where file is stored.
        file_type: Type of file ('csv' or 'xlsx').
        row_count_total: Total rows detected in file.
        row_count_accepted: Rows passing schema validation.
        row_count_rejected: Rows rejected during validation.
        validation_summary: Detailed JSON summary of rejections/warnings.

    Returns:
        Upload: Created upload instance.
    """
    upload = Upload(
        user_id=user_id,
        original_filename=original_filename,
        stored_path=stored_path,
        file_type=file_type,
        row_count_total=row_count_total,
        row_count_accepted=row_count_accepted,
        row_count_rejected=row_count_rejected,
        validation_summary=validation_summary or {},
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def delete_upload(db: Session, upload_id: int) -> bool:
    """Delete an upload record and trigger database cascade deletion.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.

    Returns:
        bool: True if deleted, False if upload was not found.
    """
    upload = db.get(Upload, upload_id)
    if not upload:
        return False
    db.delete(upload)
    db.commit()
    return True


def list_uploads(
    db: Session,
    *,
    user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Upload], int]:
    """Retrieve paginated uploads, optionally filtered by user ID.

    Args:
        db: Active database session.
        user_id: Optional user ID filter (used for auditors).
        limit: Maximum number of records to return.
        offset: Offset for pagination.

    Returns:
        tuple[list[Upload], int]: Tuple of (matching uploads list, total count).
    """
    from sqlalchemy import desc, func, select

    stmt = select(Upload)
    count_stmt = select(func.count(Upload.id))

    if user_id is not None:
        stmt = stmt.where(Upload.user_id == user_id)
        count_stmt = count_stmt.where(Upload.user_id == user_id)

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(desc(Upload.created_at)).limit(limit).offset(offset)
    items = list(db.scalars(stmt).all())
    return items, total
