"""Analysis service orchestrating run scheduling, background pipeline execution, and sign-off."""

import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.analytics.pipeline import run_analysis
from app.analytics.settings import Settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models.analysis_run import AnalysisRun
from app.db.models.user import User
from app.db.session import SessionLocal
from app.repositories.audit_log_repo import create_audit_log
from app.repositories.flagged_repo import (
    bulk_create_flagged_transactions,
    count_open_flagged_by_run,
)
from app.repositories.run_repo import (
    create_analysis_run,
    get_analysis_run_by_id,
    get_runs_by_upload,
    sign_off_run,
    update_analysis_run_status,
)
from app.repositories.transaction_repo import get_all_transactions_for_analysis
from app.repositories.upload_repo import get_upload_by_id
from app.schemas.run import AnalysisSettingsOverride, RunCreatedResponse
from app.services.upload_service import get_upload_detail

logger = logging.getLogger(__name__)


def execute_analysis_pipeline(run_id: int) -> None:
    """Background task executing the pure analytics pipeline and storing results.

    Uses an isolated database session to persist status, metrics, and flagged items.

    Args:
        run_id: ID of the pending analysis run to execute.
    """
    logger.info("Background analysis started for run %d", run_id)
    with SessionLocal() as db:
        run = get_analysis_run_by_id(db, run_id)
        if not run:
            logger.error("Analysis run %d not found in background task", run_id)
            return

        update_analysis_run_status(
            db,
            run_id=run_id,
            status="running",
            started_at=datetime.now(UTC),
        )

        try:
            # 1. Fetch transactions for upload
            txns = get_all_transactions_for_analysis(db, run.upload_id)
            if not txns:
                logger.warning(
                    "No transactions found for upload %d in run %d",
                    run.upload_id,
                    run_id,
                )
                update_analysis_run_status(
                    db,
                    run_id=run_id,
                    status="completed",
                    summary={"warning": "Upload contains no accepted transactions."},
                    finished_at=datetime.now(UTC),
                )
                return

            # Map transaction_id string to primary key database ID
            txn_id_to_pk = {t.transaction_id: t.id for t in txns}

            txn_data = [
                {
                    "transaction_id": t.transaction_id,
                    "posting_date": t.posting_date,
                    "amount": float(t.amount),
                    "vendor_id": t.vendor_id,
                    "department": t.department or "",
                    "account_code": t.account_code or "",
                    "created_by": t.created_by or "",
                    "approved_by": t.approved_by or "",
                    "description": t.description or "",
                }
                for t in txns
            ]
            df = pd.DataFrame(txn_data)

            # 2. Instantiate settings and execute pipeline
            settings = Settings(**run.settings)
            result = run_analysis(df, settings)

            # 3. Bulk insert flagged transactions
            if len(result.flagged_df) > 0:
                flagged_records = []
                for _, row in result.flagged_df.iterrows():
                    txn_id = str(row["transaction_id"])
                    txn_pk = txn_id_to_pk.get(txn_id)
                    if txn_pk is None:
                        continue

                    dup_id = row.get("duplicate_group_id")
                    dup_group = str(dup_id) if pd.notna(dup_id) and dup_id else None

                    triggered = row.get("triggered_rule_codes")
                    if triggered is None:
                        triggered = row.get("triggered_rules", [])

                    flagged_records.append(
                        {
                            "run_id": run.id,
                            "transaction_pk": txn_pk,
                            "risk_score": int(row["risk_score"]),
                            "risk_level": str(row["risk_level"]).lower(),
                            "rule_points": int(row.get("rule_points", 0)),
                            "ml_points": int(row.get("ml_points", 0)),
                            "ml_norm": float(row.get("ml_norm", 0.0)),
                            "triggered_rules": list(triggered),
                            "reasons": list(row.get("reasons", [])),
                            "duplicate_group_id": dup_group,
                            "review_status": "open",
                        }
                    )

                bulk_create_flagged_transactions(db, flagged_records)

            # 4. Save summary and Benford results
            summary = result.summary
            summary["benford"] = result.benford_result

            update_analysis_run_status(
                db,
                run_id=run_id,
                status="completed",
                summary=summary,
                finished_at=datetime.now(UTC),
            )

            create_audit_log(
                db,
                action="analyze",
                entity_type="analysis_run",
                entity_id=str(run.id),
                user_id=run.started_by,
                details={"upload_id": run.upload_id, "flagged_count": len(result.flagged_df)},
            )
            logger.info(
                "Analysis run %d completed successfully (%d flagged)",
                run.id,
                len(result.flagged_df),
            )

        except Exception as e:
            logger.exception("Analysis run %d failed: %s", run_id, e)
            db.rollback()
            update_analysis_run_status(
                db,
                run_id=run_id,
                status="failed",
                error_message="Analysis run failed due to an unexpected execution error.",
                finished_at=datetime.now(UTC),
            )


def start_analysis_run(
    db: Session,
    upload_id: int,
    current_user: User,
    settings_override: AnalysisSettingsOverride | None,
    background_tasks: BackgroundTasks,
) -> RunCreatedResponse:
    """Validate upload access, create pending run, and dispatch background analysis.

    Args:
        db: Active database session.
        upload_id: Associated upload ID.
        current_user: Authenticated user.
        settings_override: Optional threshold overrides.
        background_tasks: FastAPI background task manager.

    Returns:
        RunCreatedResponse: Acceptance payload with run_id and status 'pending'.
    """
    get_upload_detail(db, upload_id, current_user)

    base_settings = Settings()
    if settings_override:
        override_dict = settings_override.model_dump(exclude_unset=True)
        effective_settings = base_settings.model_copy(update=override_dict)
    else:
        effective_settings = base_settings

    run = create_analysis_run(
        db,
        upload_id=upload_id,
        started_by=current_user.id,
        settings=effective_settings.model_dump(),
        status="pending",
    )

    background_tasks.add_task(execute_analysis_pipeline, run.id)
    return RunCreatedResponse(run_id=run.id, status="pending")


def get_run_detail(db: Session, run_id: int, current_user: User) -> AnalysisRun:
    """Retrieve an analysis run enforcing ownership permissions.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.
        current_user: Authenticated user.

    Returns:
        AnalysisRun: AnalysisRun entity.

    Raises:
        NotFoundError: If run is not found or not visible to user.
    """
    run = get_analysis_run_by_id(db, run_id)
    if not run:
        raise NotFoundError(code="not_found", message=f"Analysis run {run_id} not found.")

    upload = get_upload_by_id(db, run.upload_id)
    if not upload:
        raise NotFoundError(
            code="not_found",
            message=f"Associated upload for run {run_id} not found.",
        )

    if current_user.role != "manager" and upload.user_id != current_user.id:
        raise NotFoundError(code="not_found", message=f"Analysis run {run_id} not found.")

    return run


def list_runs_for_upload(db: Session, upload_id: int, current_user: User) -> list[AnalysisRun]:
    """Retrieve all analysis runs for an upload respecting permissions."""
    get_upload_detail(db, upload_id, current_user)
    return get_runs_by_upload(db, upload_id)


def get_benford_results(db: Session, run_id: int, current_user: User) -> dict[str, Any]:
    """Extract and format Benford Law metrics for a completed run.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.
        current_user: Authenticated user.

    Returns:
        dict[str, Any]: Benford conformity metrics or unavailable explanation.
    """
    run = get_run_detail(db, run_id, current_user)

    if run.status != "completed":
        return {"available": False, "reason": "Analysis run is not yet completed."}

    summary = run.summary or {}
    benford = summary.get("benford")
    if (
        not benford
        or not benford.get("overall")
        or not benford["overall"].get("has_sufficient_data")
    ):
        return {
            "available": False,
            "reason": (
                "Insufficient transaction volume for Benford analysis "
                "(minimum 1,000 rows required)."
            ),
        }

    overall = benford["overall"]
    return {
        "available": True,
        "observed_counts": overall["observed_counts"],
        "observed_frequencies": overall["observed_frequencies"],
        "expected_frequencies": overall["expected_frequencies"],
        "chi_square": overall["chi_square"],
        "p_value": overall["p_value"],
        "mad": overall["mad"],
        "conformity_label": overall["conformity_label"],
        "sample_size": overall["sample_size"],
        "vendors": benford.get("vendors", {}),
        "non_conformant_vendors": benford.get("non_conformant_vendors", []),
    }


def sign_off_analysis_run(db: Session, run_id: int, current_user: User) -> AnalysisRun:
    """Sign off a completed analysis run (manager only).

    Enforces that run is completed and all flagged items have been reviewed.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.
        current_user: Authenticated manager.

    Returns:
        AnalysisRun: Updated AnalysisRun instance with sign-off metadata.

    Raises:
        ForbiddenError: If current user is not a manager.
        NotFoundError: If run does not exist.
        ConflictError: If run is not completed or open items remain.
    """
    if current_user.role != "manager":
        raise ForbiddenError(
            code="forbidden",
            message="Only managers can sign off on analysis runs.",
        )

    run = get_analysis_run_by_id(db, run_id)
    if not run:
        raise NotFoundError(code="not_found", message=f"Analysis run {run_id} not found.")

    if run.status != "completed":
        raise ConflictError(
            code="run_not_completed",
            message=f"Cannot sign off run with status '{run.status}'. Run must be completed.",
        )

    open_items_count = count_open_flagged_by_run(db, run_id)
    if open_items_count > 0:
        raise ConflictError(
            code="open_reviews_remaining",
            message=(
                f"Cannot sign off analysis run: {open_items_count} flagged "
                f"transaction(s) still have 'open' review status."
            ),
        )

    signed_run = sign_off_run(
        db,
        run_id=run_id,
        manager_id=current_user.id,
        signed_off_at=datetime.now(UTC),
    )

    create_audit_log(
        db,
        action="sign_off",
        entity_type="analysis_run",
        entity_id=str(run_id),
        user_id=current_user.id,
    )
    logger.info("Analysis run %d signed off by manager %s", run_id, current_user.email)
    return signed_run or run
