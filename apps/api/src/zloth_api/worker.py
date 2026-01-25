"""Standalone worker process for architecture v2.

This module provides a standalone worker that can be run as a separate process
from the API server, enabling horizontal scaling of job processing.

Usage:
    # Run as a standalone worker
    python -m zloth_api.worker

    # Or with uv
    uv run python -m zloth_api.worker

Environment variables:
    ZLOTH_WORKER_CONCURRENCY: Number of concurrent jobs (default: 4)
    ZLOTH_WORKER_POLL_INTERVAL_SECONDS: Poll interval in seconds (default: 1.0)
    ZLOTH_WORKER_ID_PREFIX: Prefix for worker ID (default: "worker")

Architecture v2 Reference: docs/architecture-v2.md
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import NoReturn

from zloth_api.config import settings
from zloth_api.dependencies import get_job_worker
from zloth_api.storage.dao import ReviewDAO, RunDAO
from zloth_api.storage.db import get_db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_worker() -> NoReturn:
    """Run the worker process."""
    logger.info("Starting zloth worker...")
    logger.info(
        "Configuration: concurrency=%d, poll_interval=%.1fs",
        settings.worker_concurrency,
        settings.worker_poll_interval_seconds,
    )

    # Initialize database
    db = await get_db()
    await db.initialize()
    logger.info("Database initialized")

    # Startup recovery for domain statuses
    run_dao = RunDAO(db)
    review_dao = ReviewDAO(db)
    await run_dao.fail_all_running(
        error="Worker restarted while run was running (startup recovery)"
    )
    await review_dao.fail_all_running(
        error="Worker restarted while review was running (startup recovery)"
    )

    # Get job worker
    job_worker = await get_job_worker()
    await job_worker.recover_startup()

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %s, initiating shutdown...", signal.Signals(signum).name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start worker
    job_worker.start()
    logger.info("Worker started (id=%s)", job_worker.worker_id)

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Graceful shutdown
    logger.info("Shutting down worker...")
    await job_worker.stop()
    await db.disconnect()
    logger.info("Worker stopped")

    sys.exit(0)


def main() -> None:
    """Entry point for the worker process."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
