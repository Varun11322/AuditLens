"""Audit log repository functions."""

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit trail event for security and compliance.

    Args:
        db: Active database session.
        action: Action name (e.g., 'login', 'upload', 'analyze', 'review',
            'sign_off', 'delete_upload').
        entity_type: Target domain entity (e.g., 'upload', 'analysis_run', 'user').
        entity_id: Target entity identifier.
        user_id: ID of actor initiating the action, if applicable.
        details: Additional context dictionary (never sensitive data).

    Returns:
        AuditLog: Persisted audit log entry.
    """
    log_entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=details or {},
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def get_audit_logs(
    db: Session,
    *,
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Retrieve audit log entries with pagination.

    Args:
        db: Active database session.
        user_id: Optional filter by user ID.
        action: Optional filter by action name.
        limit: Max records to return.
        offset: Offset for pagination.

    Returns:
        list[AuditLog]: List of matching audit log entries.
    """
    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())
