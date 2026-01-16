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
        logger.debug(f"Checking CI for task={task_id}, pr={pr_id}")

        # Validate task and PR exist
        task = await self.task_dao.get(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            raise ValueError(f"Task not found: {task_id}")

        pr = await self.pr_dao.get(pr_id)
        if not pr:
            logger.warning(f"PR not found: {pr_id}")
            raise ValueError(f"PR not found: {pr_id}")

        if pr.task_id != task_id:
            logger.warning(f"PR {pr_id} does not belong to task {task_id}")
            raise ValueError(f"PR {pr_id} does not belong to task {task_id}")

        # Get repo info for GitHub API
        repo = await self.repo_dao.get(task.repo_id)
        if not repo:
            logger.warning(f"Repo not found: {task.repo_id}")
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Extract owner/repo from repo_url
        repo_full_name = self._extract_repo_full_name(repo.repo_url)
        if not repo_full_name:
            logger.warning(f"Cannot parse repo URL: {repo.repo_url}")
            raise ValueError(f"Cannot parse repo URL: {repo.repo_url}")

        logger.debug(f"Fetching CI status for {repo_full_name} PR #{pr.number}")

        # Build detailed CI result first (jobs data)
        ci_data = await self._build_ci_data(pr.number, repo_full_name)

        # Derive status from jobs data instead of relying on combined status API
        # This ensures consistency between displayed jobs and overall status
        status = self._derive_status_from_jobs(ci_data.get("jobs", {}))
        sha = ci_data.get("sha")

        # Create or update CICheck record
        # Look for existing check with the same SHA to avoid duplicate records
        existing = await self.ci_check_dao.get_by_pr_and_sha(pr_id, sha) if sha else None
        if existing:
            # Update existing check for this SHA
            ci_check = await self.ci_check_dao.update(
                id=existing.id,
                status=status,
                workflow_run_id=ci_data.get("workflow_run_id"),
                sha=sha,
                jobs=ci_data.get("jobs"),
                failed_jobs=ci_data.get("failed_jobs"),
            )
            if not ci_check:
                raise ValueError(f"Failed to update CI check: {existing.id}")
        else:
            # Create new check record for this SHA
            ci_check = await self.ci_check_dao.create(
                task_id=task_id,
                pr_id=pr_id,
                status=status,
                workflow_run_id=ci_data.get("workflow_run_id"),
                sha=sha,
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

    def _derive_status_from_jobs(self, jobs: dict[str, str]) -> str:
        """Derive overall CI status from individual job results.

        Args:
            jobs: Dict mapping job name to result/status.

        Returns:
            Overall status: "success", "pending", "failure", or "error".
        """
        if not jobs:
            # No jobs found - could be CI hasn't started yet
            return "pending"

        pending_states = {"in_progress", "queued", "pending"}
        failure_states = {"failure", "cancelled", "timed_out"}
        success_states = {"success", "skipped", "neutral"}

        has_pending = False
        has_failure = False
        has_success = False

        for result in jobs.values():
            if result in pending_states:
                has_pending = True
            elif result in failure_states:
                has_failure = True
            elif result in success_states:
                has_success = True
            else:
                # Unknown state, treat as pending
                has_pending = True

        # Priority: failure > pending > success
        if has_failure:
            return "failure"
        if has_pending:
            return "pending"
        if has_success:
            return "success"

        # Fallback
        return "pending"

    async def _build_ci_data(
        self,
        pr_number: int,
        repo_full_name: str,
    ) -> dict:
        """Build CI data from GitHub API.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.

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
        # This requires "checks:read" permission on the GitHub App
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
            # 403 error likely means GitHub App doesn't have "checks:read" permission
            # Fall back to using the combined status API (requires "statuses:read")
            if "403" in str(e):
                logger.warning(f"No 'checks:read' permission, falling back to statuses API: {e}")
                # Try to get statuses as fallback
                try:
                    statuses_data = await self.github._github_request(
                        "GET",
                        f"/repos/{owner}/{repo}/commits/{head_sha}/statuses",
                    )
                    for status_item in statuses_data:
                        context = status_item.get("context", "unknown")
                        state = status_item.get("state", "unknown")
                        result["jobs"][context] = state
                        if state == "failure":
                            result["failed_jobs"].append(
                                CIJobResult(
                                    job_name=context,
                                    result=state,
                                    error_log=status_item.get("description"),
                                )
                            )
                except Exception as status_err:
                    logger.warning(f"Failed to get statuses as fallback: {status_err}")
            else:
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
