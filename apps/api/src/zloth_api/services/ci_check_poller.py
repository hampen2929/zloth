"""CI Check Poller Service for server-side CI status polling.

This service polls pending CI checks in the background to update their status
without requiring frontend polling.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from zloth_api.services.ci_check_service import (
    CI_CHECK_MAX_ATTEMPTS,
    CI_CHECK_POLL_INTERVAL_SECONDS,
)
from zloth_api.storage.dao import CICheckDAO

if TYPE_CHECKING:
    from zloth_api.services.ci_check_service import CICheckService

logger = logging.getLogger(__name__)


class CICheckPoller:
    """Background service for polling pending CI checks.

    This service periodically checks for pending CI checks that are due for
    polling and updates their status from GitHub.
    """

    def __init__(
        self,
        ci_check_dao: CICheckDAO,
        ci_check_service: "CICheckService",
    ):
        """Initialize CI check poller.

        Args:
            ci_check_dao: CICheck DAO for database operations.
            ci_check_service: CICheck service for GitHub API calls.
        """
        self.ci_check_dao = ci_check_dao
        self.ci_check_service = ci_check_service
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start the background polling task."""
        if self._running:
            logger.warning("CI check poller is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("CI check poller started")

    def stop(self) -> None:
        """Stop the background polling task."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("CI check poller stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_pending_checks()
            except asyncio.CancelledError:
                logger.info("CI check poller cancelled")
                break
            except Exception as e:
                logger.error(f"Error in CI check poller: {e}")

            # Wait before next poll cycle
            await asyncio.sleep(CI_CHECK_POLL_INTERVAL_SECONDS)

    async def _poll_pending_checks(self) -> None:
        """Poll all pending CI checks that are due for update."""
        pending_checks = await self.ci_check_dao.list_pending_due_for_check()

        if not pending_checks:
            return

        logger.debug(f"Polling {len(pending_checks)} pending CI checks")

        for check in pending_checks:
            try:
                # Check for timeout
                if check.check_count >= CI_CHECK_MAX_ATTEMPTS:
                    logger.info(f"CI check {check.id} timed out after {check.check_count} attempts")
                    await self.ci_check_dao.mark_as_timeout(check.id)
                    continue

                # Poll GitHub for updated status
                try:
                    await self.ci_check_service.check_ci(check.task_id, check.pr_id, force=True)
                    logger.debug(f"Updated CI check {check.id}")
                except ValueError as e:
                    # PR might be closed or other validation error
                    logger.warning(f"CI check {check.id} validation error: {e}")
                    # Mark as error status
                    await self.ci_check_dao.update(
                        id=check.id,
                        status="error",
                    )
                    continue

                # Schedule next check (check_ci already handles this for pending status)
                # but we need to increment the count
                next_check = datetime.utcnow() + timedelta(seconds=CI_CHECK_POLL_INTERVAL_SECONDS)
                await self.ci_check_dao.update_next_check(
                    check.id, next_check, increment_count=True
                )

            except Exception as e:
                logger.warning(f"Failed to poll CI check {check.id}: {e}")
                # Schedule retry
                next_check = datetime.utcnow() + timedelta(seconds=CI_CHECK_POLL_INTERVAL_SECONDS)
                await self.ci_check_dao.update_next_check(
                    check.id, next_check, increment_count=True
                )

    async def poll_once(self) -> int:
        """Run a single poll cycle (useful for testing).

        Returns:
            Number of checks polled.
        """
        pending_checks = await self.ci_check_dao.list_pending_due_for_check()
        await self._poll_pending_checks()
        return len(pending_checks)
