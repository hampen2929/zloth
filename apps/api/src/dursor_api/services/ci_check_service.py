"""CI Check Service for checking PR CI status.

This service provides on-demand CI status checking for PRs.
"""

import logging
from typing import TYPE_CHECKING

from dursor_api.domain.models import CICheck, CICheckResponse, CIJobResult
from dursor_api.storage.dao import PRDAO, CICheckDAO, RepoDAO, TaskDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class CICheckService:
    """Service for checking CI status of PRs."""

    def __init__(
        self,
        ci_check_dao: CICheckDAO,
        pr_dao: PRDAO,
        task_dao: TaskDAO,
        repo_dao: RepoDAO,
        github_service: "GitHubService",
    ):
        """Initialize CI check service.

        Args:
            ci_check_dao: CICheck DAO.
            pr_dao: PR DAO.
            task_dao: Task DAO.
            repo_dao: Repo DAO.
            github_service: GitHub service for API calls.
        """
        self.ci_check_dao = ci_check_dao
        self.pr_dao = pr_dao
        self.task_dao = task_dao
        self.repo_dao = repo_dao
        self.github = github_service

    async def check_ci(self, task_id: str, pr_id: str) -> CICheckResponse:
        """Check CI status for a PR.

        Fetches current CI status from GitHub and creates/updates a CICheck record.

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            CICheckResponse with current status and completion flag.

        Raises:
            ValueError: If PR or task not found.
        """
        # Validate task and PR exist
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        pr = await self.pr_dao.get(pr_id)
        if not pr:
            raise ValueError(f"PR not found: {pr_id}")

        if pr.task_id != task_id:
            raise ValueError(f"PR {pr_id} does not belong to task {task_id}")

        # Get repo info for GitHub API
        repo = await self.repo_dao.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Extract owner/repo from repo_url
        repo_full_name = self._extract_repo_full_name(repo.repo_url)
        if not repo_full_name:
            raise ValueError(f"Cannot parse repo URL: {repo.repo_url}")

        # Get CI status from GitHub
        try:
            status = await self.github.get_pr_check_status(pr.number, repo_full_name)
        except Exception as e:
            logger.error(f"Failed to get CI status: {e}")
            status = "error"

        # Build detailed CI result
        ci_data = await self._build_ci_data(pr.number, repo_full_name, status)

        # Create or update CICheck record
        existing = await self.ci_check_dao.get_latest_by_pr_id(pr_id)
        if existing and existing.status == "pending":
            # Update existing pending check
            ci_check = await self.ci_check_dao.update(
                id=existing.id,
                status=status,
                workflow_run_id=ci_data.get("workflow_run_id"),
                sha=ci_data.get("sha"),
                jobs=ci_data.get("jobs"),
                failed_jobs=ci_data.get("failed_jobs"),
            )
            if not ci_check:
                raise ValueError(f"Failed to update CI check: {existing.id}")
        else:
            # Create new check record
            ci_check = await self.ci_check_dao.create(
                task_id=task_id,
                pr_id=pr_id,
                status=status,
                workflow_run_id=ci_data.get("workflow_run_id"),
                sha=ci_data.get("sha"),
                jobs=ci_data.get("jobs"),
                failed_jobs=ci_data.get("failed_jobs"),
            )

        # Determine if CI is complete
        is_complete = status in ("success", "failure", "error")

        logger.info(f"CI check for PR #{pr.number}: status={status}, complete={is_complete}")

        return CICheckResponse(
            ci_check=ci_check,
            is_complete=is_complete,
        )

    async def get_ci_checks(self, task_id: str) -> list[CICheck]:
        """Get all CI checks for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of CICheck records.
        """
        return await self.ci_check_dao.list_by_task_id(task_id)

    async def _build_ci_data(
        self,
        pr_number: int,
        repo_full_name: str,
        status: str,
    ) -> dict:
        """Build CI data from GitHub API.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.
            status: Combined CI status.

        Returns:
            Dict with CI data (sha, jobs, failed_jobs).
        """
        owner, repo = repo_full_name.split("/", 1)

        result: dict = {
            "workflow_run_id": None,
            "sha": None,
            "jobs": {},
            "failed_jobs": [],
        }

        # Get PR to find head SHA
        try:
            pr_data = await self.github._github_request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}",
            )
            result["sha"] = pr_data.get("head", {}).get("sha", "")
        except Exception as e:
            logger.warning(f"Failed to get PR data: {e}")
            return result

        head_sha = result["sha"]
        if not head_sha:
            return result

        # Get check runs for detailed job info
        try:
            check_runs_data = await self.github._github_request(
                "GET",
                f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
            )

            jobs: dict[str, str] = {}
            failed_jobs: list[CIJobResult] = []

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

            result["jobs"] = jobs
            result["failed_jobs"] = failed_jobs

        except Exception as e:
            logger.warning(f"Failed to get check runs: {e}")

        return result

    def _extract_repo_full_name(self, repo_url: str) -> str | None:
        """Extract owner/repo from repository URL.

        Args:
            repo_url: Git repository URL.

        Returns:
            Full name (owner/repo) or None if cannot parse.
        """
        # Handle various URL formats:
        # https://github.com/owner/repo.git
        # https://github.com/owner/repo
        # git@github.com:owner/repo.git
        # https://x-access-token:...@github.com/owner/repo.git

        import re

        # Try HTTPS format
        match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"

        return None
