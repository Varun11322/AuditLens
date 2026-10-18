"""Uploads and upload-scoped analysis router."""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.run import AnalysisRunResponse, RunCreatedResponse, StartAnalysisRequest
from app.schemas.upload import UploadListResponse, UploadResponse
from app.services.analysis_service import list_runs_for_upload, start_analysis_run
from app.services.upload_service import (
    delete_upload_for_user,
    get_template_csv,
    get_upload_detail,
    handle_file_upload,
    list_uploads_for_user,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_file_route(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UploadResponse:
    """Upload and validate a transaction file (.csv or .xlsx)."""
    return handle_file_upload(db, file, current_user)


@router.get("", response_model=UploadListResponse)
def list_uploads_route(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> UploadListResponse:
    """List upload records (auditors view own uploads; managers view all)."""
    items, total = list_uploads_for_user(db, current_user, page=page, page_size=page_size)
    return UploadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UploadResponse.model_validate(u) for u in items],
    )


@router.get("/template")
def get_template_route() -> Response:
    """Download the canonical CSV ledger template file."""
    content = get_template_csv()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transaction_template.csv"'},
    )


@router.get("/{upload_id}", response_model=UploadResponse)
def get_upload_route(
    upload_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UploadResponse:
    """Retrieve detailed validation and metadata for an upload."""
    upload = get_upload_detail(db, upload_id, current_user)
    return UploadResponse.model_validate(upload)


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload_route(
    upload_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete an upload and all associated transactions, runs, and reviews."""
    delete_upload_for_user(db, upload_id, current_user)


@router.post(
    "/{upload_id}/analyze",
    response_model=RunCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis_route(
    upload_id: int,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    request: StartAnalysisRequest | None = None,
) -> RunCreatedResponse:
    """Trigger an asynchronous analysis run on an uploaded dataset."""
    settings_override = request.settings if request else None
    return start_analysis_run(db, upload_id, current_user, settings_override, background_tasks)


@router.get("/{upload_id}/runs", response_model=list[AnalysisRunResponse])
def list_upload_runs_route(
    upload_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AnalysisRunResponse]:
    """List all analysis runs associated with an upload."""
    runs = list_runs_for_upload(db, upload_id, current_user)
    return [AnalysisRunResponse.model_validate(r) for r in runs]
