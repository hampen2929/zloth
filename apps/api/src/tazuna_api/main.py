"""dursor API - FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tazuna_api.config import settings
from tazuna_api.dependencies import get_pr_status_poller
from tazuna_api.routes import (
    backlog_router,
    breakdown_router,
    github_router,
    kanban_router,
    models_router,
    preferences_router,
    prs_router,
    repos_router,
    reviews_router,
    runs_router,
    tasks_router,
)
from tazuna_api.storage.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager."""
    # Startup: initialize database
    db = await get_db()
    await db.initialize()

    # Start PR status poller
    pr_status_poller = await get_pr_status_poller()
    pr_status_poller.start()

    yield

    # Shutdown: stop PR status poller
    await pr_status_poller.stop()

    # Shutdown: close database
    await db.disconnect()


app = FastAPI(
    title="dursor API",
    description="Multi-model parallel coding agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
# Allow all origins for SSE streaming support from various deployment scenarios
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(backlog_router, prefix="/v1")
app.include_router(breakdown_router, prefix="/v1")
app.include_router(github_router, prefix="/v1")
app.include_router(kanban_router, prefix="/v1")
app.include_router(models_router, prefix="/v1")
app.include_router(preferences_router, prefix="/v1")
app.include_router(repos_router, prefix="/v1")
app.include_router(reviews_router, prefix="/v1")
app.include_router(tasks_router, prefix="/v1")
app.include_router(runs_router, prefix="/v1")
app.include_router(prs_router, prefix="/v1")
# Note: webhooks_router removed - using CI polling instead (see ci_polling_service.py)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": "dursor API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dursor_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
