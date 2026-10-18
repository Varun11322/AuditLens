"""Upload schemas for transaction datasets."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    """Detailed metadata for an uploaded dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    original_filename: str
    file_type: str | None = None
    row_count_total: int
    row_count_accepted: int
    row_count_rejected: int
    validation_summary: dict[str, Any]
    created_at: datetime


class UploadListResponse(BaseModel):
    """Paginated list of upload records."""

    total: int
    page: int
    page_size: int
    items: list[UploadResponse]
