"""FastAPI application factory for AuditLens."""

from fastapi import FastAPI

from app.routers.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure an instance of the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    app = FastAPI(
        title="AuditLens API",
        description="Audit anomaly detection for financial transactions",
        version="0.1.0",
    )

    app.include_router(health_router)

    return app


app = create_app()
