"""FastAPI routers package exports."""

from app.routers.auth import router as auth_router
from app.routers.flagged import router as flagged_router
from app.routers.health import router as health_router
from app.routers.runs import router as runs_router
from app.routers.uploads import router as uploads_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "flagged_router",
    "health_router",
    "runs_router",
    "uploads_router",
    "users_router",
]
