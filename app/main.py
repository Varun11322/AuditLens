"""FastAPI application factory and middleware configuration for AuditLens."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.routers import (
    auth_router,
    flagged_router,
    health_router,
    runs_router,
    uploads_router,
    users_router,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Configures CORS, exception handlers, and API routers.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="AuditLens API",
        description="Audit anomaly detection and risk scoring for financial transactions",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration (allowing configured Streamlit origins and dev endpoints)
    origins = list(settings.cors_origins)
    if settings.app_env == "development":
        for dev_origin in ("http://localhost:8000", "http://127.0.0.1:8000"):
            if dev_origin not in origins:
                origins.append(dev_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom exception handlers for consistent error shapes per docs/API.md
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Sanitize validation errors to ensure clean serializability
        errors = []
        for err in exc.errors():
            cleaned_err = {
                "loc": [str(loc_item) for loc_item in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            errors.append(cleaned_err)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request parameters or payload.",
                    "details": {"errors": errors},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            413: "file_too_large",
            415: "unsupported_media_type",
            422: "validation_error",
            429: "rate_limited",
            503: "database_unavailable",
        }
        err_code = code_map.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": err_code,
                    "message": str(exc.detail),
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal server error occurred.",
                    "details": {},
                }
            },
        )

    # Register API routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(uploads_router)
    app.include_router(runs_router)
    app.include_router(flagged_router)

    return app


app = create_app()
