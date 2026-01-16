"""Background service for polling PR status from GitHub."""

import asyncio
import logging

from tazuna_api.services.github_service import GitHubService
from tazuna_api.storage.dao import PRDAO

logger = logging.getLogger(__name__)

# Default polling interval in seconds
DEFAULT_POLL_INTERVAL = 60


class PRStatusPoller:
    """Background service that polls GitHub for PR status updates.

    Periodically checks all open PRs and updates their status in the database
    when they are merged or closed on GitHub.
    """

    def __init__(
        self,
        pr_dao: PRDAO,
        github_service: GitHubService,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ):
        """Initialize the PR status poller.

        Args:
            pr_dao: PR data access object.
            github_service: GitHub service for API calls.
            poll_interval: Polling interval in seconds (default: 60).
        """
        self.pr_dao = pr_dao
        self.github_service = github_service
        self.poll_interval = poll_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """Start the background polling task."""
        if self._task is not None:
            logger.warning("PR status poller is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("PR status poller started (interval: %ds)", self.poll_interval)

    async def stop(self) -> None:
        """Stop the background polling task."""
        if self._task is None:
            return

        self._running = False
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("PR status poller stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_open_prs()
            except Exception:
                logger.exception("Error polling PR statuses")

            await asyncio.sleep(self.poll_interval)

    async def _poll_open_prs(self) -> None:
        """Poll all open PRs and update their status if changed."""
        open_prs = await self.pr_dao.list_open()

        if not open_prs:
            return

        logger.debug("Polling %d open PRs for status updates", len(open_prs))

        for pr in open_prs:
            try:
                await self._check_and_update_pr(pr.id, pr.url, pr.number)
            except Exception:
                logger.exception("Error checking PR %s (url=%s)", pr.id, pr.url)

    async def _check_and_update_pr(self, pr_id: str, pr_url: str, pr_number: int) -> None:
        """Check a single PR's status and update if changed.

        Args:
            pr_id: Local PR ID.
            pr_url: GitHub PR URL.
            pr_number: GitHub PR number.
        """
        # Parse owner/repo from PR URL
        # URL format: https://github.com/{owner}/{repo}/pull/{number}
        url_parts = pr_url.split("/")
        if len(url_parts) < 5:
            logger.warning("Invalid PR URL format: %s", pr_url)
            return

        owner = url_parts[-4]
        repo = url_parts[-3]

        # Get PR status from GitHub
        try:
            pr_data = await self.github_service.get_pull_request_status(owner, repo, pr_number)
        except Exception:
            logger.debug("Failed to get PR status from GitHub for %s/%s#%d", owner, repo, pr_number)
            return

        # Determine new status
        if pr_data.get("merged"):
            new_status = "merged"
        elif pr_data.get("state") == "closed":
            new_status = "closed"
        else:
            # Still open, no update needed
            return

        # Update local PR status
        await self.pr_dao.update_status(pr_id, new_status)
        logger.info(
            "Updated PR %s status to '%s' (GitHub %s/%s#%d)",
            pr_id,
            new_status,
            owner,
            repo,
            pr_number,
        )
