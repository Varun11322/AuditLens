"""Health check router."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Liveness and database check endpoint.

    Returns:
        dict[str, str]: Status payload indicating health of the service.

    Raises:
        ServiceUnavailableError: If database connection fails.
    """
    try:
        db.execute(text("SELECT 1;"))
        return {"status": "ok"}
    except Exception as e:
        raise ServiceUnavailableError(
            code="database_unavailable",
            message="Database connectivity check failed.",
        ) from e
