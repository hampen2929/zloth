"""zloth API - FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zloth_api.config import settings
from zloth_api.dependencies import get_job_worker, get_pr_status_poller
from zloth_api.error_handling import install_error_handling
from zloth_api.routes import (
    backlog_router,
    breakdown_router,
    executors_router,
    github_router,
    kanban_router,
    metrics_router,
    models_router,
    preferences_router,
    prs_router,
    repos_router,
    reviews_router,
    runs_router,
    tasks_router,
)
from zloth_api.storage.dao import ReviewDAO, RunDAO
from zloth_api.storage.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager."""
    # Startup: initialize database
    db = await get_db()
    await db.initialize()

    # Startup recovery for durable queue and domain statuses.
    # Conservative behavior: mark orphaned RUNNING jobs/runs/reviews as FAILED.
    run_dao = RunDAO(db)
    review_dao = ReviewDAO(db)
    await run_dao.fail_all_running(
        error="Server restarted while run was running (startup recovery)"
    )
    await review_dao.fail_all_running(
        error="Server restarted while review was running (startup recovery)"
    )

    # Start PR status poller
    pr_status_poller = await get_pr_status_poller()
    pr_status_poller.start()

    # Start persistent job worker (only if worker is enabled)
    # Set ZLOTH_WORKER_ENABLED=false to run API-only mode (workers run separately)
    job_worker = None
    if settings.worker_enabled:
        job_worker = await get_job_worker()
        await job_worker.recover_startup()
        job_worker.start()

    yield

    # Shutdown: stop PR status poller
    await pr_status_poller.stop()

    # Shutdown: stop job worker (if running)
    if job_worker is not None:
        await job_worker.stop()

    # Shutdown: close database
    await db.disconnect()


app = FastAPI(
    title="zloth API",
    description="Multi-model parallel coding agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# Global error handling + request correlation
install_error_handling(app)

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
app.include_router(executors_router, prefix="/v1")
app.include_router(github_router, prefix="/v1")
app.include_router(kanban_router, prefix="/v1")
app.include_router(metrics_router)
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
        "name": "zloth API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "zloth_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
