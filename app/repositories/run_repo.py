"""Analysis run repository functions."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.analysis_run import AnalysisRun


def create_analysis_run(
    db: Session,
    *,
    upload_id: int,
    started_by: int,
    settings: dict[str, Any],
    status: str = "pending",
) -> AnalysisRun:
    """Create and persist a new analysis run record.

    Args:
        db: Active database session.
        upload_id: Associated upload ID.
        started_by: User ID who initiated the run.
        settings: Analysis thresholds and parameters.
        status: Initial status string.

    Returns:
        AnalysisRun: Created analysis run instance.
    """
    run = AnalysisRun(
        upload_id=upload_id,
        started_by=started_by,
        settings=settings,
        status=status,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_analysis_run_by_id(db: Session, run_id: int) -> AnalysisRun | None:
    """Retrieve an analysis run by ID.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.

    Returns:
        AnalysisRun | None: AnalysisRun entity if found, else None.
    """
    return db.get(AnalysisRun, run_id)


def update_analysis_run_status(
    db: Session,
    run_id: int,
    *,
    status: str,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> AnalysisRun | None:
    """Update execution status and metrics for an analysis run.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.
        status: New status ('pending', 'running', 'completed', 'failed').
        summary: Output analysis metrics and Benford results.
        error_message: Failure details if status is failed.
        started_at: Execution start timestamp.
        finished_at: Execution end timestamp.

    Returns:
        AnalysisRun | None: Updated AnalysisRun instance if found, else None.
    """
    run = db.get(AnalysisRun, run_id)
    if not run:
        return None
    run.status = status
    if summary is not None:
        run.summary = summary
    if error_message is not None:
        run.error_message = error_message
    if started_at is not None:
        run.started_at = started_at
    if finished_at is not None:
        run.finished_at = finished_at
    db.commit()
    db.refresh(run)
    return run


def get_runs_by_upload(db: Session, upload_id: int) -> list[AnalysisRun]:
    """Retrieve all analysis runs for an upload ordered newest first.

    Args:
        db: Active database session.
        upload_id: Associated upload ID.

    Returns:
        list[AnalysisRun]: List of analysis runs.
    """
    from sqlalchemy import desc, select

    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.upload_id == upload_id)
        .order_by(desc(AnalysisRun.created_at))
    )
    return list(db.scalars(stmt).all())


def sign_off_run(
    db: Session,
    run_id: int,
    manager_id: int,
    signed_off_at: datetime,
) -> AnalysisRun | None:
    """Record manager sign-off on an analysis run.

    Args:
        db: Active database session.
        run_id: Analysis run ID.
        manager_id: User ID of manager.
        signed_off_at: Timestamp of sign-off.

    Returns:
        AnalysisRun | None: Updated AnalysisRun instance.
    """
    run = db.get(AnalysisRun, run_id)
    if not run:
        return None
    run.signed_off_by = manager_id
    run.signed_off_at = signed_off_at
    db.commit()
    db.refresh(run)
    return run
