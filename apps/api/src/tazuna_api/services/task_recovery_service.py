"""Task recovery service for detecting and recovering stuck/orphaned tasks.

This service handles:
1. Detection of stuck tasks (running too long without progress)
2. Recovery of orphaned tasks (queued/running in DB but not in memory)
3. Periodic health checks for task queue
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from tazuna_api.config import settings
from tazuna_api.domain.enums import RunStatus

if TYPE_CHECKING:
    from tazuna_api.storage.dao import RunDAO

logger = logging.getLogger(__name__)


class TaskRecoveryService:
    """Service for recovering stuck and orphaned tasks.

    This service runs periodic health checks to:
    - Mark tasks stuck in RUNNING status as FAILED
    - Mark tasks stuck in QUEUED status as FAILED (orphaned)
    - Provide metrics on task queue health
    """

    def __init__(
        self,
        run_dao: "RunDAO",
        check_interval_seconds: int = 300,  # 5 minutes
    ) -> None:
        """Initialize the task recovery service.

        Args:
            run_dao: Run data access object.
            check_interval_seconds: Interval between health checks.
        """
        self.run_dao = run_dao
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the periodic health check task."""
        if self._running:
            logger.warning("TaskRecoveryService is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_periodic_check())
        logger.info(f"TaskRecoveryService started with {self.check_interval_seconds}s interval")

    async def stop(self) -> None:
        """Stop the periodic health check task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("TaskRecoveryService stopped")

    async def _run_periodic_check(self) -> None:
        """Run periodic health checks."""
        while self._running:
            try:
                await self.check_and_recover()
            except Exception as e:
                logger.error(f"Error in task recovery check: {e}")

            await asyncio.sleep(self.check_interval_seconds)

    async def check_and_recover(self) -> dict[str, int]:
        """Check for stuck/orphaned tasks and recover them.

        Returns:
            Dict with counts of recovered tasks by type.
        """
        stuck_threshold = datetime.utcnow() - timedelta(
            minutes=settings.stuck_task_threshold_minutes
        )

        results = {
            "stuck_running": 0,
            "orphaned_queued": 0,
        }

        # Find and mark stuck RUNNING tasks
        stuck_running = await self._find_stuck_running_tasks(stuck_threshold)
        for run in stuck_running:
            try:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=f"Task marked as stuck: running for over "
                    f"{settings.stuck_task_threshold_minutes} minutes without completion",
                    logs=[
                        f"Recovery: Task stuck in RUNNING state since {run.started_at}",
                        f"Recovery: Automatically marked as FAILED at {datetime.utcnow()}",
                    ],
                )
                results["stuck_running"] += 1
                logger.warning(
                    f"Marked stuck RUNNING task as FAILED: {run.id} (started at {run.started_at})"
                )
            except Exception as e:
                logger.error(f"Failed to recover stuck task {run.id}: {e}")

        # Find and mark orphaned QUEUED tasks (queued for too long)
        orphaned_queued = await self._find_orphaned_queued_tasks(stuck_threshold)
        for run in orphaned_queued:
            try:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=f"Task marked as orphaned: queued for over "
                    f"{settings.stuck_task_threshold_minutes} minutes without starting",
                    logs=[
                        f"Recovery: Task stuck in QUEUED state since {run.created_at}",
                        f"Recovery: Automatically marked as FAILED at {datetime.utcnow()}",
                    ],
                )
                results["orphaned_queued"] += 1
                logger.warning(
                    f"Marked orphaned QUEUED task as FAILED: {run.id} (created at {run.created_at})"
                )
            except Exception as e:
                logger.error(f"Failed to recover orphaned task {run.id}: {e}")

        if results["stuck_running"] > 0 or results["orphaned_queued"] > 0:
            logger.info(
                f"Task recovery completed: {results['stuck_running']} stuck running, "
                f"{results['orphaned_queued']} orphaned queued"
            )

        return results

    async def _find_stuck_running_tasks(self, threshold: datetime) -> list:
        """Find tasks stuck in RUNNING status.

        Args:
            threshold: Tasks started before this time are considered stuck.

        Returns:
            List of stuck Run objects.
        """
        return await self.run_dao.find_stuck_tasks(
            status=RunStatus.RUNNING,
            started_before=threshold,
        )

    async def _find_orphaned_queued_tasks(self, threshold: datetime) -> list:
        """Find tasks stuck in QUEUED status (orphaned).

        Args:
            threshold: Tasks created before this time are considered orphaned.

        Returns:
            List of orphaned Run objects.
        """
        return await self.run_dao.find_stuck_tasks(
            status=RunStatus.QUEUED,
            created_before=threshold,
        )

    async def get_health_status(self) -> dict:
        """Get current health status of the task queue.

        Returns:
            Dict with queue health metrics.
        """
        stuck_threshold = datetime.utcnow() - timedelta(
            minutes=settings.stuck_task_threshold_minutes
        )

        # Count tasks by status
        queued_count = await self.run_dao.count_by_status(RunStatus.QUEUED)
        running_count = await self.run_dao.count_by_status(RunStatus.RUNNING)

        # Count stuck tasks
        stuck_running = await self._find_stuck_running_tasks(stuck_threshold)
        orphaned_queued = await self._find_orphaned_queued_tasks(stuck_threshold)

        return {
            "queued": queued_count,
            "running": running_count,
            "stuck_running": len(stuck_running),
            "orphaned_queued": len(orphaned_queued),
            "healthy": len(stuck_running) == 0 and len(orphaned_queued) == 0,
            "stuck_threshold_minutes": settings.stuck_task_threshold_minutes,
            "check_interval_seconds": self.check_interval_seconds,
            "service_running": self._running,
        }

    async def recover_on_startup(self) -> dict[str, int]:
        """Recover orphaned tasks on application startup.

        This marks any tasks that were in QUEUED or RUNNING status when
        the application stopped as FAILED, since their execution state
        was lost.

        Returns:
            Dict with counts of recovered tasks.
        """
        if not settings.task_recovery_enabled:
            logger.info("Task recovery on startup is disabled")
            return {"recovered": 0}

        results = {"running_to_failed": 0, "queued_to_failed": 0}

        # Mark all RUNNING tasks as FAILED (they can't be running if we just started)
        running_tasks = await self.run_dao.find_by_status(RunStatus.RUNNING)
        for run in running_tasks:
            try:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error="Task interrupted: application restarted while task was running",
                    logs=[
                        "Recovery: Task was in RUNNING state when application restarted",
                        f"Recovery: Automatically marked as FAILED at {datetime.utcnow()}",
                    ],
                )
                results["running_to_failed"] += 1
                logger.info(f"Recovered interrupted RUNNING task: {run.id}")
            except Exception as e:
                logger.error(f"Failed to recover interrupted task {run.id}: {e}")

        # Mark old QUEUED tasks as FAILED (they won't be picked up)
        stuck_threshold = datetime.utcnow() - timedelta(
            minutes=settings.stuck_task_threshold_minutes
        )
        orphaned_queued = await self._find_orphaned_queued_tasks(stuck_threshold)
        for run in orphaned_queued:
            try:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error="Task orphaned: was queued before application restart",
                    logs=[
                        "Recovery: Task was in QUEUED state for too long",
                        f"Recovery: Automatically marked as FAILED at {datetime.utcnow()}",
                    ],
                )
                results["queued_to_failed"] += 1
                logger.info(f"Recovered orphaned QUEUED task: {run.id}")
            except Exception as e:
                logger.error(f"Failed to recover orphaned task {run.id}: {e}")

        total = results["running_to_failed"] + results["queued_to_failed"]
        if total > 0:
            logger.info(
                f"Startup recovery completed: {results['running_to_failed']} running, "
                f"{results['queued_to_failed']} queued tasks marked as FAILED"
            )

        return results
