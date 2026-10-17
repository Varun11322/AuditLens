"""Health check router."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Liveness check endpoint.

    Returns:
        dict[str, str]: Status payload indicating health of the service.
    """
    return {"status": "ok"}
