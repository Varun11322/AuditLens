"""Analysis runs, Benford metrics, and flagged list router."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.flagged import FlaggedListResponse
from app.schemas.run import AnalysisRunResponse
from app.services.analysis_service import (
    evaluate_analysis_run,
    get_benford_results,
    get_run_detail,
    sign_off_analysis_run,
)
from app.services.flagged_service import list_flagged_transactions
from app.services.report_service import generate_excel_report

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=AnalysisRunResponse)
def get_run_status_route(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisRunResponse:
    """Retrieve status, configuration settings, and summary metrics for an analysis run."""
    run = get_run_detail(db, run_id, current_user)
    return AnalysisRunResponse.model_validate(run)


@router.get("/{run_id}/benford")
def get_run_benford_route(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Retrieve Benford's Law analysis metrics and vendor conformity results."""
    return get_benford_results(db, run_id, current_user)


@router.post("/{run_id}/sign-off", response_model=AnalysisRunResponse)
def sign_off_run_route(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalysisRunResponse:
    """Sign off an audit analysis run (Manager only; requires all flagged items reviewed)."""
    run = sign_off_analysis_run(db, run_id, current_user)
    return AnalysisRunResponse.model_validate(run)


@router.get("/{run_id}/flagged", response_model=FlaggedListResponse)
def get_flagged_transactions_route(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    risk_level: Annotated[
        list[str] | None, Query(description="Filter by risk levels (repeatable)")
    ] = None,
    rule: Annotated[
        list[str] | None, Query(description="Filter by triggered rules R1..R6 (repeatable)")
    ] = None,
    vendor_id: Annotated[str | None, Query(description="Filter by exact vendor ID")] = None,
    department: Annotated[str | None, Query(description="Filter by department")] = None,
    review_status: Annotated[str | None, Query(description="Filter by review status")] = None,
    date_from: Annotated[datetime | None, Query(description="Earliest posting date")] = None,
    date_to: Annotated[datetime | None, Query(description="Latest posting date")] = None,
    amount_min: Annotated[float | None, Query(description="Minimum transaction amount")] = None,
    amount_max: Annotated[float | None, Query(description="Maximum transaction amount")] = None,
    sort_by: Annotated[str, Query(pattern="^(risk_score|amount|posting_date)$")] = "risk_score",
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> FlaggedListResponse:
    """Retrieve paginated, filtered, and sorted flagged transactions for a run."""
    items, total = list_flagged_transactions(
        db,
        run_id=run_id,
        current_user=current_user,
        risk_levels=risk_level,
        rules=rule,
        vendor_id=vendor_id,
        department=department,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return FlaggedListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{run_id}/report")
def get_run_report_route(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    format: Annotated[
        str, Query(description="Report file format (only 'xlsx' supported)")
    ] = "xlsx",
) -> Response:
    """Download the multi-sheet Excel exceptions report for a completed analysis run."""
    if format.lower() != "xlsx":
        raise ValidationError(
            code="unsupported_format",
            message=f"Unsupported report format '{format}'. Only 'xlsx' is supported.",
        )

    xlsx_bytes, filename = generate_excel_report(db, run_id, current_user)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{run_id}/evaluate")
async def evaluate_run_route(
    run_id: int,
    file: Annotated[UploadFile, File(description="Ground truth CSV file")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Compare the analysis run against a ground_truth CSV."""
    file_bytes = await file.read()
    return evaluate_analysis_run(
        db=db,
        run_id=run_id,
        file_bytes=file_bytes,
        filename=file.filename or "ground_truth.csv",
        current_user=current_user,
    )
