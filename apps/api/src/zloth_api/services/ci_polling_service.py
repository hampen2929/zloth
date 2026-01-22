"""CI Polling Service for polling GitHub CI status.

This service polls GitHub API to check CI status instead of relying on webhooks.
This is useful for self-hosted zloth instances that are not exposed to the internet.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from zloth_api.config import settings
from zloth_api.domain.models import CIJobResult, CIResult

if TYPE_CHECKING:
    from zloth_api.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class CIPollingService:
    """Service for polling GitHub CI status.

    Polls the GitHub API at regular intervals to check if CI has completed.
    When CI completes (success or failure), triggers a callback with the result.
    """

    def __init__(self, github_service: "GitHubService"):
        """Initialize CI polling service.

        Args:
            github_service: GitHub service for API calls.
        """
        self.github = github_service

        # Active polling tasks keyed by task_id
        self._polling_tasks: dict[str, asyncio.Task[None]] = {}

        # Configuration
        self._poll_interval = settings.ci_polling_interval_seconds
        self._timeout_minutes = settings.ci_polling_timeout_minutes

    async def start_polling(
        self,
        task_id: str,
        pr_number: int,
        repo_full_name: str,
        on_complete: Callable[[CIResult], Coroutine[Any, Any, None]],
        on_timeout: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Start polling for CI status.

        Args:
            task_id: Task ID to track the polling.
            pr_number: PR number to check CI status for.
            repo_full_name: Full repository name (owner/repo).
            on_complete: Callback when CI completes (success or failure).
            on_timeout: Optional callback when polling times out.
        """
        # Cancel any existing polling for this task
        await self.stop_polling(task_id)

        # Create polling task
        task = asyncio.create_task(
            self._poll_loop(
                task_id=task_id,
                pr_number=pr_number,
                repo_full_name=repo_full_name,
                on_complete=on_complete,
                on_timeout=on_timeout,
            )
        )
        self._polling_tasks[task_id] = task

        logger.info(
            f"Started CI polling for task {task_id}, PR #{pr_number} "
            f"(interval: {self._poll_interval}s, timeout: {self._timeout_minutes}m)"
        )

    async def stop_polling(self, task_id: str) -> bool:
        """Stop polling for a task.

        Args:
            task_id: Task ID to stop polling for.

        Returns:
            True if polling was stopped, False if no active polling.
        """
        task = self._polling_tasks.pop(task_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"Stopped CI polling for task {task_id}")
            return True
        return False

    def is_polling(self, task_id: str) -> bool:
        """Check if polling is active for a task.

        Args:
            task_id: Task ID to check.

        Returns:
            True if polling is active.
        """
        task = self._polling_tasks.get(task_id)
        return task is not None and not task.done()

    async def _poll_loop(
        self,
        task_id: str,
        pr_number: int,
        repo_full_name: str,
        on_complete: Callable[[CIResult], Coroutine[Any, Any, None]],
        on_timeout: Callable[[], Coroutine[Any, Any, None]] | None,
    ) -> None:
        """Main polling loop.

        Args:
            task_id: Task ID.
            pr_number: PR number.
            repo_full_name: Full repository name.
            on_complete: Callback for CI completion.
            on_timeout: Callback for timeout.
        """
        start_time = datetime.utcnow()
        timeout = timedelta(minutes=self._timeout_minutes)

        logger.debug(f"Starting poll loop for task {task_id}")

        while True:
            try:
                # Check timeout
                elapsed = datetime.utcnow() - start_time
                if elapsed > timeout:
                    logger.warning(f"CI polling timed out for task {task_id}")
                    self._polling_tasks.pop(task_id, None)
                    if on_timeout:
                        await on_timeout()
                    return

                # Poll CI status
                status = await self.github.get_pr_check_status(pr_number, repo_full_name)
                logger.debug(f"CI status for task {task_id}: {status}")

                if status in ("success", "failure", "error"):
                    # CI completed - build result and trigger callback
                    ci_result = await self._build_ci_result(
                        pr_number=pr_number,
                        repo_full_name=repo_full_name,
                        status=status,
                    )

                    logger.info(
                        f"CI completed for task {task_id}: {status} "
                        f"(took {elapsed.total_seconds():.1f}s)"
                    )

                    self._polling_tasks.pop(task_id, None)
                    await on_complete(ci_result)
                    return

                # CI still pending - wait and poll again
                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                logger.debug(f"Polling cancelled for task {task_id}")
                raise
            except Exception as e:
                logger.error(f"Error polling CI status for task {task_id}: {e}")
                # Continue polling on error (GitHub API might be temporarily unavailable)
                await asyncio.sleep(self._poll_interval)

    async def _build_ci_result(
        self,
        pr_number: int,
        repo_full_name: str,
        status: str,
    ) -> CIResult:
        """Build CIResult from GitHub API data.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.
            status: Combined CI status.

        Returns:
            CIResult object.
        """
        owner, repo = repo_full_name.split("/", 1)

        # Get PR to find head SHA
        try:
            pr_data = await self.github._github_request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}",
            )
            head_sha = pr_data.get("head", {}).get("sha", "")
        except Exception:
            head_sha = ""

        # Get check runs for detailed job info
        jobs: dict[str, str] = {}
        failed_jobs: list[CIJobResult] = []

        if head_sha:
            try:
                check_runs_data = await self.github._github_request(
                    "GET",
                    f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                )

                for check_run in check_runs_data.get("check_runs", []):
                    name = check_run.get("name", "unknown")
                    conclusion = check_run.get("conclusion") or check_run.get("status", "unknown")
                    jobs[name] = conclusion

                    if conclusion in ("failure", "cancelled", "timed_out"):
                        # Get error log from check run output
                        error_log = check_run.get("output", {}).get("summary", "")
                        if not error_log:
                            error_log = check_run.get("output", {}).get("text", "")

                        failed_jobs.append(
                            CIJobResult(
                                job_name=name,
                                result=conclusion,
                                error_log=error_log[:2000] if error_log else None,
                            )
                        )
            except Exception as e:
                logger.warning(f"Failed to get check runs: {e}")

        return CIResult(
            success=status == "success",
            workflow_run_id=0,  # Not available from status API
            sha=head_sha,
            jobs=jobs,
            failed_jobs=failed_jobs,
        )

    async def shutdown(self) -> None:
        """Shutdown polling service and cancel all active polls."""
        task_ids = list(self._polling_tasks.keys())
        for task_id in task_ids:
            await self.stop_polling(task_id)
        logger.info("CI polling service shutdown complete")
